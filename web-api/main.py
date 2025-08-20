"""
SESAME Web API Server
A FastAPI web server that provides REST endpoints to control SESAME smart locks.
"""

import asyncio
import logging
import os
from typing import Dict, Any
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


async def get_device_instance():
    """
    Scan for and create a device instance.
    Returns the configured SESAME device ready for connection.
    """
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


async def perform_device_operation(operation: str, history_tag: str = "Web API"):
    """
    Perform an operation on the SESAME device.
    
    Args:
        operation: The operation to perform ('toggle', 'lock', 'unlock', 'click')
        history_tag: Tag to include in device history
        
    Returns:
        Dict containing operation result
    """
    try:
        # Get device instance
        device = await get_device_instance()
        
        # Connect to device
        logger.info("Connecting to device...")
        await device.connect()
        
        # Wait for login to complete
        await device.wait_for_login()
        logger.info("Device login completed")
        
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
        
        # Disconnect from device
        await device.disconnect()
        logger.info("Device disconnected")
        
        return result
        
    except Exception as e:
        logger.error(f"Error performing operation '{operation}': {str(e)}")
        return {
            "success": False,
            "message": f"Error: {str(e)}"
        }


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "message": "SESAME Web API",
        "version": "1.0.0",
        "endpoints": {
            "/toggle": "Toggle the SESAME lock",
            "/lock": "Lock the SESAME device",
            "/unlock": "Unlock the SESAME device", 
            "/click": "Click the SESAME Bot",
            "/status": "Get device status",
            "/health": "Health check"
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
    Get the current status of the SESAME device without performing any operations.
    """
    logger.info("Status endpoint called")
    
    try:
        # Get device instance (but don't perform operations)
        device = await get_device_instance()
        
        # Connect briefly to get status
        await device.connect()
        await device.wait_for_login()
        
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
        
        await device.disconnect()
        
        return StatusResponse(**result)
        
    except Exception as e:
        logger.error(f"Error getting device status: {str(e)}")
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
    
    print("Starting SESAME Web API server...")
    print(f"Device BLE UUID: {BLE_UUID}")
    print(f"Scan Duration: {SCAN_DURATION} seconds")
    print("Server will be available at: http://localhost:8000")
    print("API documentation at: http://localhost:8000/docs")
    
    uvicorn.run(app, host="0.0.0.0", port=8000)
