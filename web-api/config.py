"""
Configuration module for SESAME Web API
"""

import os
from typing import Optional


class Config:
    """Configuration class for SESAME Web API."""
    
    # SESAME Device Configuration
    BLE_UUID: str = os.getenv("SESAME_BLE_UUID", "")
    SECRET_KEY: str = os.getenv("SESAME_SECRET_KEY", "")
    PUBLIC_KEY: str = os.getenv("SESAME_PUBLIC_KEY", "")
    SCAN_DURATION: int = int(os.getenv("SESAME_SCAN_DURATION", "15"))
    
    # Server Configuration
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    
    # Logging Configuration
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    @classmethod
    def validate(cls) -> bool:
        """Validate that required configuration is present."""
        if not cls.BLE_UUID:
            raise ValueError("SESAME_BLE_UUID environment variable is required")
        
        if not cls.SECRET_KEY:
            raise ValueError("SESAME_SECRET_KEY environment variable is required")
        
        if not cls.PUBLIC_KEY:
            raise ValueError("SESAME_PUBLIC_KEY environment variable is required")
        
        return True


# Global config instance
config = Config()
