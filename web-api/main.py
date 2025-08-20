"""
SESAME Web API Server with Connection Pooling
A FastAPI web server that provides REST endpoints to control SESAME smart locks with persistent connections.
"""

import asyncio
import logging
import os
import time
from typing import Dict, Any, Optional, Union
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# Import SESAME library modules
import sys
sys.path.append('..')  # Add parent directory to path to import pysesameos2

from pysesameos2.ble import CHBleManager
from pysesameos2.device import CHDeviceKey
from pysesameos2.helper import CHProductModel
from pysesameos2.chsesame2 import CHSesame2
from pysesameos2.chsesamebot import CHSesameBot


# Configure logging
logging.basicConfig(level=logging.INFO)
logging.getLogger("bleak").setLevel(level=logging.WARNING)
logger = logging.getLogger(__name__)

# Configuration from environment variables
BLE_UUID = os.getenv("SESAME_BLE_UUID", "")
SECRET_KEY = os.getenv("SESAME_SECRET_KEY", "")
PUBLIC_KEY = os.getenv("SESAME_PUBLIC_KEY", "")
SCAN_DURATION = int(os.getenv("SESAME_SCAN_DURATION", "15"))
CONNECTION_TIMEOUT = int(os.getenv("SESAME_CONNECTION_TIMEOUT", "1800"))  # 30 minutes in seconds
MAX_RECONNECT_ATTEMPTS = int(os.getenv("SESAME_MAX_RECONNECT_ATTEMPTS", "5"))

# FastAPI app
app = FastAPI(
    title="SESAME Web API",
    description="REST API for controlling SESAME smart locks",
    version="1.0.0"
)

# Response models
class ToggleResponse(BaseModel):
    success: bool
    message: str
    device_id: str = None
    product_model: str = None
    device_status: str = None
    connection_reused: bool = False
    reconnect_attempts: int = 0

class StatusResponse(BaseModel):
    success: bool
    message: str
    device_id: str = None
    product_model: str = None
    device_status: str = None
    battery_percentage: int = None
    battery_voltage: float = None
    is_in_lock_range: bool = None
    is_in_unlock_range: bool = None
    position: int = None

class ConnectionResponse(BaseModel):
    success: bool
    message: str
    device_id: str = None
    product_model: str = None
    connection_established: bool = False
    connection_time: str = None


# Global connection manager
class SesameConnectionManager:
    def __init__(self):
        self.device: Optional[Union[CHSesame2, CHSesameBot]] = None
        self.connection_time: Optional[float] = None
        self.is_connected: bool = False
        self.connection_lock = asyncio.Lock()
    
    def is_connection_valid(self) -> bool:
        """Check if the current connection is still valid and within timeout."""
        if not self.is_connected or not self.connection_time:
            return False
        
        # Check if connection has expired
        if time.time() - self.connection_time > CONNECTION_TIMEOUT:
            logger.info("Connection has expired, will reconnect")
            return False
        
        return True
    
    async def get_or_create_device(self) -> Union[CHSesame2, CHSesameBot]:
        """Get existing device instance or create a new one."""
        if not self.device:
            self.device = await self._create_device_instance()
        return self.device
    
    async def _create_device_instance(self) -> Union[CHSesame2, CHSesameBot]:
        """Create a new device instance."""
        if not BLE_UUID:
            raise ValueError("SESAME_BLE_UUID environment variable not set")
        
        if not SECRET_KEY or not PUBLIC_KEY:
            raise ValueError("SESAME_SECRET_KEY and SESAME_PUBLIC_KEY environment variables must be set")
        
        logger.info(f"Scanning for device: {BLE_UUID}")
        
        # Scan for the specific device
        device = await CHBleManager().scan_by_address(
            ble_device_identifier=BLE_UUID, 
            scan_duration=SCAN_DURATION
        )
        
        if not device:
            raise RuntimeError(f"Device {BLE_UUID} not found during scan")
        
        # Set up device keys
        device_key = CHDeviceKey()
        device_key.setSecretKey(SECRET_KEY)
        device_key.setSesame2PublicKey(PUBLIC_KEY)
        device.setKey(device_key)
        
        logger.info(f"Device found: {device.getDeviceUUID()}, Model: {device.productModel}")
        return device
    
    async def ensure_connection(self, max_attempts: int = MAX_RECONNECT_ATTEMPTS) -> bool:
        """Ensure device is connected, reconnect if necessary."""
        async with self.connection_lock:
            attempts = 0
            
            while attempts < max_attempts:
                try:
                    # Check if we have a valid connection
                    if self.is_connection_valid():
                        logger.info("Using existing connection")
                        return True
                    
                    # Get or create device
                    device = await self.get_or_create_device()
                    
                    # Connect to device
                    logger.info(f"Connecting to device (attempt {attempts + 1}/{max_attempts})...")
                    await device.connect()
                    
                    # Wait for login to complete
                    await device.wait_for_login()
                    
                    # Update connection state
                    self.is_connected = True
                    self.connection_time = time.time()
                    
                    logger.info("Device connected and authenticated successfully")
                    return True
                    
                except Exception as e:
                    attempts += 1
                    logger.error(f"Connection attempt {attempts} failed: {str(e)}")
                    
                    # Reset connection state
                    self.is_connected = False
                    self.connection_time = None
                    
                    if attempts < max_attempts:
                        logger.info(f"Retrying in 2 seconds...")
                        await asyncio.sleep(2)
                    else:
                        logger.error(f"Failed to connect after {max_attempts} attempts")
                        return False
            
            return False
    
    async def disconnect(self):
        """Disconnect the current device."""
        async with self.connection_lock:
            if self.device and self.is_connected:
                try:
                    await self.device.disconnect()
                    logger.info("Device disconnected")
                except Exception as e:
                    logger.error(f"Error disconnecting device: {str(e)}")
                finally:
                    self.is_connected = False
                    self.connection_time = None
    
    def get_device_info(self) -> Dict[str, Any]:
        """Get current device information."""
        if not self.device:
            return {}
        
        return {
            "device_id": self.device.getDeviceUUID(),
            "product_model": str(self.device.productModel),
            "is_connected": self.is_connected,
            "connection_time": self.connection_time,
            "connection_age": time.time() - self.connection_time if self.connection_time else None
        }

# Global connection manager instance
connection_manager = SesameConnectionManager()

async def get_device_instance():
    """
    Scan for and create a device instance.
    Returns the configured SESAME device ready for connection.
    """
    return await connection_manager.get_or_create_device()


async def perform_device_operation(operation: str, history_tag: str = "Web API"):
    """
    Perform an operation on the SESAME device using connection pooling.
    
    Args:
        operation: The operation to perform ('toggle', 'lock', 'unlock', 'click')
        history_tag: Tag to include in device history
        
    Returns:
        Dict containing operation result
    """
    connection_reused = False
    reconnect_attempts = 0
    
    try:
        # Ensure we have a valid connection
        if connection_manager.is_connection_valid():
            connection_reused = True
            logger.info("Using existing connection for operation")
        else:
            logger.info("No valid connection, establishing new connection")
            reconnect_attempts = 1
            if not await connection_manager.ensure_connection():
                raise RuntimeError("Failed to establish connection to device")
        
        # Get the connected device
        device = connection_manager.device
        
        # Perform the requested operation
        if device.productModel in [CHProductModel.SS2, CHProductModel.SS4]:
            if operation == "toggle":
                await device.toggle(history_tag=history_tag)
            elif operation == "lock":
                await device.lock(history_tag=history_tag)
            elif operation == "unlock":
                await device.unlock(history_tag=history_tag)
            else:
                raise ValueError(f"Operation '{operation}' not supported for SESAME 2/4")
                
        elif device.productModel == CHProductModel.SesameBot1:
            if operation == "click":
                await device.click(history_tag=history_tag)
            else:
                raise ValueError(f"Operation '{operation}' not supported for SESAME Bot")
        
        # Get device status
        mech_status = device.getMechStatus()
        device_status = device.getDeviceStatus()
        
        result = {
            "success": True,
            "message": f"Operation '{operation}' completed successfully",
            "device_id": device.getDeviceUUID(),
            "product_model": str(device.productModel),
            "device_status": str(device_status),
            "connection_reused": connection_reused,
            "reconnect_attempts": reconnect_attempts
        }
        
        # Add mechanical status if available
        if mech_status:
            result.update({
                "battery_percentage": mech_status.getBatteryPrecentage(),
                "battery_voltage": mech_status.getBatteryVoltage(),
                "is_in_lock_range": mech_status.isInLockRange(),
                "is_in_unlock_range": mech_status.isInUnlockRange()
            })
            
            # Add position for SESAME 2/4
            if hasattr(mech_status, 'getPosition'):
                result["position"] = mech_status.getPosition()
        
        return result
        
    except Exception as e:
        logger.error(f"Error performing operation '{operation}': {str(e)}")
        
        # If operation failed, try to reconnect and retry once
        if not connection_reused and reconnect_attempts < MAX_RECONNECT_ATTEMPTS:
            logger.info("Operation failed, attempting to reconnect and retry...")
            try:
                # Reset connection and try again
                connection_manager.is_connected = False
                connection_manager.connection_time = None
                
                if await connection_manager.ensure_connection():
                    # Retry the operation
                    device = connection_manager.device
                    
                    if device.productModel in [CHProductModel.SS2, CHProductModel.SS4]:
                        if operation == "toggle":
                            await device.toggle(history_tag=history_tag)
                        elif operation == "lock":
                            await device.lock(history_tag=history_tag)
                        elif operation == "unlock":
                            await device.unlock(history_tag=history_tag)
                    elif device.productModel == CHProductModel.SesameBot1:
                        if operation == "click":
                            await device.click(history_tag=history_tag)
                    
                    # Get updated status
                    mech_status = device.getMechStatus()
                    device_status = device.getDeviceStatus()
                    
                    result = {
                        "success": True,
                        "message": f"Operation '{operation}' completed successfully after reconnection",
                        "device_id": device.getDeviceUUID(),
                        "product_model": str(device.productModel),
                        "device_status": str(device_status),
                        "connection_reused": False,
                        "reconnect_attempts": reconnect_attempts + 1
                    }
                    
                    if mech_status:
                        result.update({
                            "battery_percentage": mech_status.getBatteryPrecentage(),
                            "battery_voltage": mech_status.getBatteryVoltage(),
                            "is_in_lock_range": mech_status.isInLockRange(),
                            "is_in_unlock_range": mech_status.isInUnlockRange()
                        })
                        
                        if hasattr(mech_status, 'getPosition'):
                            result["position"] = mech_status.getPosition()
                    
                    return result
                    
            except Exception as retry_error:
                logger.error(f"Retry attempt also failed: {str(retry_error)}")
        
        return {
            "success": False,
            "message": f"Error: {str(e)}",
            "connection_reused": connection_reused,
            "reconnect_attempts": reconnect_attempts
        }


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "message": "SESAME Web API with Connection Pooling",
        "version": "2.0.0",
        "features": {
            "connection_pooling": True,
            "auto_reconnection": True,
            "persistent_connections": True
        },
        "endpoints": {
            "/toggle": "Toggle the SESAME lock (with connection pooling)",
            "/lock": "Lock the SESAME device",
            "/unlock": "Unlock the SESAME device", 
            "/click": "Click the SESAME Bot",
            "/status": "Get device status",
            "/connect": "Manually establish connection",
            "/disconnect": "Manually disconnect",
            "/connection": "Get connection status",
            "/health": "Health check"
        },
        "configuration": {
            "connection_timeout": f"{CONNECTION_TIMEOUT} seconds ({CONNECTION_TIMEOUT/60:.1f} minutes)",
            "max_reconnect_attempts": MAX_RECONNECT_ATTEMPTS,
            "scan_duration": f"{SCAN_DURATION} seconds"
        }
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "message": "SESAME Web API is running"}


@app.post("/toggle")
async def toggle_lock() -> ToggleResponse:
    """
    Toggle the SESAME lock state.
    If locked, it will unlock. If unlocked, it will lock.
    """
    logger.info("Toggle endpoint called")
    
    result = await perform_device_operation("toggle", "Web API Toggle")
    
    if result["success"]:
        return ToggleResponse(**result)
    else:
        raise HTTPException(status_code=500, detail=result["message"])


@app.post("/lock")
async def lock_device() -> ToggleResponse:
    """Lock the SESAME device."""
    logger.info("Lock endpoint called")
    
    result = await perform_device_operation("lock", "Web API Lock")
    
    if result["success"]:
        return ToggleResponse(**result)
    else:
        raise HTTPException(status_code=500, detail=result["message"])


@app.post("/unlock")
async def unlock_device() -> ToggleResponse:
    """Unlock the SESAME device."""
    logger.info("Unlock endpoint called")
    
    result = await perform_device_operation("unlock", "Web API Unlock")
    
    if result["success"]:
        return ToggleResponse(**result)
    else:
        raise HTTPException(status_code=500, detail=result["message"])


@app.post("/click")
async def click_bot() -> ToggleResponse:
    """Click the SESAME Bot."""
    logger.info("Click endpoint called")
    
    result = await perform_device_operation("click", "Web API Click")
    
    if result["success"]:
        return ToggleResponse(**result)
    else:
        raise HTTPException(status_code=500, detail=result["message"])


@app.get("/status")
async def get_device_status() -> StatusResponse:
    """
    Get the current status of the SESAME device using connection pooling.
    """
    logger.info("Status endpoint called")
    
    try:
        # Ensure we have a valid connection
        if not connection_manager.is_connection_valid():
            logger.info("No valid connection, establishing new connection for status check")
            if not await connection_manager.ensure_connection():
                raise RuntimeError("Failed to establish connection to device")
        
        # Get the connected device
        device = connection_manager.device
        
        # Get current status
        mech_status = device.getMechStatus()
        device_status = device.getDeviceStatus()
        
        result = {
            "success": True,
            "message": "Device status retrieved successfully",
            "device_id": device.getDeviceUUID(),
            "product_model": str(device.productModel),
            "device_status": str(device_status)
        }
        
        # Add mechanical status if available
        if mech_status:
            result.update({
                "battery_percentage": mech_status.getBatteryPrecentage(),
                "battery_voltage": mech_status.getBatteryVoltage(),
                "is_in_lock_range": mech_status.isInLockRange(),
                "is_in_unlock_range": mech_status.isInUnlockRange()
            })
            
            # Add position for SESAME 2/4
            if hasattr(mech_status, 'getPosition'):
                result["position"] = mech_status.getPosition()
        
        return StatusResponse(**result)
        
    except Exception as e:
        logger.error(f"Error getting device status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@app.post("/connect")
async def establish_connection() -> ConnectionResponse:
    """
    Manually establish a connection to the SESAME device.
    This can be used to pre-establish a connection for faster subsequent operations.
    """
    logger.info("Connect endpoint called")
    
    try:
        if await connection_manager.ensure_connection():
            device_info = connection_manager.get_device_info()
            
            result = {
                "success": True,
                "message": "Connection established successfully",
                "device_id": device_info.get("device_id"),
                "product_model": device_info.get("product_model"),
                "connection_established": True,
                "connection_time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(device_info.get("connection_time")))
            }
            
            return ConnectionResponse(**result)
        else:
            raise RuntimeError("Failed to establish connection")
            
    except Exception as e:
        logger.error(f"Error establishing connection: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@app.post("/disconnect")
async def disconnect_device() -> ConnectionResponse:
    """
    Manually disconnect from the SESAME device.
    """
    logger.info("Disconnect endpoint called")
    
    try:
        await connection_manager.disconnect()
        
        result = {
            "success": True,
            "message": "Device disconnected successfully",
            "device_id": None,
            "product_model": None,
            "connection_established": False,
            "connection_time": None
        }
        
        return ConnectionResponse(**result)
        
    except Exception as e:
        logger.error(f"Error disconnecting device: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@app.get("/connection")
async def get_connection_status() -> ConnectionResponse:
    """
    Get the current connection status and information.
    """
    logger.info("Connection status endpoint called")
    
    try:
        device_info = connection_manager.get_device_info()
        
        result = {
            "success": True,
            "message": "Connection status retrieved successfully",
            "device_id": device_info.get("device_id"),
            "product_model": device_info.get("product_model"),
            "connection_established": device_info.get("is_connected", False),
            "connection_time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(device_info.get("connection_time"))) if device_info.get("connection_time") else None
        }
        
        return ConnectionResponse(**result)
        
    except Exception as e:
        logger.error(f"Error getting connection status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    
    # Check if required environment variables are set
    if not BLE_UUID:
        print("ERROR: SESAME_BLE_UUID environment variable not set")
        print("Please set the BLE UUID of your SESAME device")
        exit(1)
    
    if not SECRET_KEY or not PUBLIC_KEY:
        print("ERROR: SESAME_SECRET_KEY and SESAME_PUBLIC_KEY environment variables not set")
        print("Please set your device's secret key and public key")
        print("You can get these from the QR code using: https://sesame-qr-reader.vercel.app/")
        exit(1)
    
    print("Starting SESAME Web API server with Connection Pooling...")
    print(f"Device BLE UUID: {BLE_UUID}")
    print(f"Scan Duration: {SCAN_DURATION} seconds")
    print(f"Connection Timeout: {CONNECTION_TIMEOUT} seconds ({CONNECTION_TIMEOUT/60:.1f} minutes)")
    print(f"Max Reconnect Attempts: {MAX_RECONNECT_ATTEMPTS}")
    print("Server will be available at: http://localhost:8000")
    print("API documentation at: http://localhost:8000/docs")
    
    uvicorn.run(app, host="0.0.0.0", port=8000)
