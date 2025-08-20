#!/usr/bin/env python3
"""
Run script for SESAME Web API
This script can be used as an alternative to running main.py directly.
"""

import uvicorn
from config import config

if __name__ == "__main__":
    # Validate configuration
    try:
        config.validate()
    except ValueError as e:
        print(f"Configuration Error: {e}")
        print("\nPlease check your environment variables:")
        print("- SESAME_BLE_UUID: Your device's BLE UUID")
        print("- SESAME_SECRET_KEY: Your device's secret key")
        print("- SESAME_PUBLIC_KEY: Your device's public key")
        print("\nYou can get these from the QR code using: https://sesame-qr-reader.vercel.app/")
        exit(1)
    
    print("Starting SESAME Web API server...")
    print(f"Device BLE UUID: {config.BLE_UUID}")
    print(f"Scan Duration: {config.SCAN_DURATION} seconds")
    print(f"Server will be available at: http://{config.HOST}:{config.PORT}")
    print(f"API documentation at: http://{config.HOST}:{config.PORT}/docs")
    
    # Run the server
    uvicorn.run(
        "main:app", 
        host=config.HOST, 
        port=config.PORT,
        reload=config.DEBUG,
        log_level=config.LOG_LEVEL.lower()
    )
