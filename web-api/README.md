# SESAME Web API with Connection Pooling

A FastAPI-based web server that provides REST endpoints to control SESAME smart locks via Bluetooth Low Energy (BLE) with persistent connections for improved performance.

**Note**: This web API is part of the larger `sesame-4-wifi` project. The web API source code is located in the `web-api/` folder.

## Table of Contents

-   [Project Structure](#project-structure)
-   [Features](#features)
-   [Pre-install (Get Credentials)](#pre-install-get-credentials)
-   [Install and Setup](#install-and-setup)
-   [Usage](#usage)
-   [Development](#development)
-   [Troubleshooting](#troubleshooting)

## Project Structure

```
sesame-4-wifi/
├── discover.py                 # Scan and discover SESAME devices
├── connect.py                  # Direct connection and control script
└── web-api/                   # Web API source code
    ├── main.py                # Main FastAPI application
    ├── config.py              # Configuration management
    ├── daemon.py              # Python daemon script
    ├── requirements.txt       # Python dependencies
    ├── env.example           # Environment variables template
    └── README.md             # This file
```

## Features

-   **Connection Pooling**: Persistent connections for faster operations
-   **Auto Reconnection**: Automatic reconnection with configurable retry attempts
-   **Toggle Endpoint**: `/toggle` - Toggle the lock state (lock/unlock) with connection reuse
-   **Lock Control**: `/lock` - Lock the device
-   **Unlock Control**: `/unlock` - Unlock the device
-   **Status Check**: `/status` - Get device status and battery info
-   **Connection Management**: `/connect`, `/disconnect`, `/connection`,`/test-connection` - Manage persistent connections
-   **Health Check**: `/health` - API health check

## Pre-install (Get Credentials)

Before setting up the web API, you need to obtain your SESAME device credentials:

### Step 1: Get BLE UUID using discover.py

```bash
# From the project root directory
python discover.py
```

This will scan for nearby SESAME devices and display their BLE UUIDs. Note down the UUID for your device.

### Step 2: Get Secret Key and Public Key using QR Reader

-   Scan your SESAME device QR code using: [SESAME QR Reader](https://sesame-qr-reader.vercel.app/)
-   Extract the **Secret Key** and **Public Key** from the QR code
-   **Note**: The QR reader will also show the BLE UUID, but using `discover.py` is more reliable for getting the correct UUID

### Required Credentials Summary:

-   **BLE UUID**: Obtained from `discover.py`
-   **Secret Key**: Obtained from QR code scanner
-   **Public Key**: Obtained from QR code scanner

## Install and Setup

1. **Install Dependencies**:

    ```bash
    pip install -r requirements.txt
    ```

2. **Set up Environment Variables**:

    ```bash
    cp env.example .env
    # Edit .env with your device credentials
    ```

3. **Configure Environment Variables**:
    - The application automatically loads variables from `.env` file
    - No need to manually source or export environment variables
    - Variables are loaded when the application starts

### Configuration

Set the following environment variables in your `.env` file:

| Variable                        | Description                   | Required              |
| ------------------------------- | ----------------------------- | --------------------- |
| `SESAME_BLE_UUID`               | Your device's BLE UUID        | Yes                   |
| `SESAME_SECRET_KEY`             | 16-byte secret key (hex)      | Yes                   |
| `SESAME_PUBLIC_KEY`             | 64-byte public key (hex)      | Yes                   |
| `SESAME_SCAN_DURATION`          | BLE scan duration in seconds  | No (default: 15)      |
| `SESAME_CONNECTION_TIMEOUT`     | Connection timeout in seconds | No (default: 1800)    |
| `SESAME_MAX_RECONNECT_ATTEMPTS` | Maximum reconnection attempts | No (default: 5)       |
| `HOST`                          | Server host                   | No (default: 0.0.0.0) |
| `PORT`                          | Server port                   | No (default: 8000)    |
| `DEBUG`                         | Enable debug mode             | No (default: false)   |
| `LOG_LEVEL`                     | Logging level                 | No (default: INFO)    |

## Usage

### Start the Server

#### Method 1: Direct execution

```bash
python main.py
```

#### Method 2: Using Python daemon (Recommended)

```bash
# Start the service in background
python daemon.py start

# Check status
python daemon.py status

# View recent logs
python daemon.py logs

# Follow logs (live)
python daemon.py follow

# Stop the service
python daemon.py stop

# Restart the service
python daemon.py restart
```

The server will start on `http://localhost:8000`

**Note**: Environment variables are automatically loaded from the `.env` file - no manual sourcing required!

### API Documentation

Visit `http://localhost:8000/docs` for interactive API documentation (Swagger UI).

### Example Requests

#### Toggle the Lock

```bash
curl -X GET http://localhost:8000/toggle
```

#### Lock the Device

```bash
curl -X GET http://localhost:8000/lock
```

#### Unlock the Device

```bash
curl -X GET http://localhost:8000/unlock
```

#### Get Device Status

```bash
curl http://localhost:8000/status
```

#### Establish Connection (Pre-connect)

```bash
curl -X GET http://localhost:8000/connect
```

#### Get Connection Status

```bash
curl http://localhost:8000/connection
```

#### Disconnect

```bash
curl -X GET http://localhost:8000/disconnect
```

#### Health Check

```bash
curl http://localhost:8000/health
```

### Response Format

#### Success Response

```json
{
    "success": true,
    "message": "Operation 'toggle' completed successfully",
    "device_id": "your-device-uuid",
    "product_model": "CHProductModel.SS2",
    "device_status": "CHSesame2Status.Unlocked",
    "battery_percentage": 85,
    "battery_voltage": 3.2,
    "is_in_lock_range": true,
    "is_in_unlock_range": true,
    "position": 50,
    "connection_reused": true,
    "reconnect_attempts": 0
}
```

#### Error Response

```json
{
    "detail": "Error: Device not found during scan"
}
```

### Connection Pooling

The API uses connection pooling to maintain persistent connections to your SESAME device:

-   **Persistent Connections**: Once connected, the connection is maintained for up to 30 minutes (configurable)
-   **Fast Operations**: Subsequent operations reuse the existing connection, eliminating connection overhead
-   **Auto Reconnection**: If the connection fails, the API automatically reconnects with up to 5 retry attempts
-   **Connection Management**: Manual connection control via `/connect`, `/disconnect`, and `/connection` endpoints

### Performance Benefits

-   **First Request**: ~15-20 seconds (scan + connect + authenticate + operation)
-   **Subsequent Requests**: ~1-3 seconds (operation only, connection reused)

### Supported Devices

-   **SESAME 2 (SS2)**: lock, unlock, toggle operations
-   **SESAME 4 (SS4)**: lock, unlock, toggle operations
-   **SESAME Bot**: click operation

## Development

### Project Structure

```
web-api/
├── main.py                    # Main FastAPI application
├── config.py                  # Configuration management
├── daemon.py                  # Python daemon script (recommended)
├── requirements.txt           # Python dependencies
├── env.example               # Environment variables template
└── README.md                 # This file
```

### Running in Development Mode

```bash
# Enable debug logging
export DEBUG=true
export LOG_LEVEL=DEBUG

# Start the server
python main.py
```

### Using with Docker

```dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 8000
CMD ["python", "main.py"]
```

## Troubleshooting

### Common Issues

1. **"Device not found during scan"**

    - Ensure your device is nearby and powered on
    - Check that the BLE UUID is correct (use `discover.py` to verify)
    - Increase `SESAME_SCAN_DURATION` if needed

2. **"Device keys not set"**

    - Verify `SESAME_SECRET_KEY` and `SESAME_PUBLIC_KEY` are set correctly
    - Keys should be hex strings without spaces or prefixes

3. **"Permission denied" on Linux**

    - Run with `sudo` or set up proper udev rules for BLE access
    - Ensure your user is in the `bluetooth` group

4. **Connection timeouts**
    - Move closer to the device
    - Ensure no other apps are connected to the device
    - Try increasing the scan duration

### Logging

Set `LOG_LEVEL=DEBUG` for detailed logs including BLE communication details.

### Security Considerations

-   **Environment Variables**: Never commit your actual device keys to version control
-   **Network Access**: Consider using HTTPS in production
-   **Authentication**: Add authentication for production deployments
-   **Rate Limiting**: Consider adding rate limiting to prevent abuse

## License

This project uses the same license as the underlying pysesameos2 library.
