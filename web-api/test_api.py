#!/usr/bin/env python3
"""
Test script for SESAME Web API
This script tests the API endpoints without requiring an actual SESAME device.
"""

import asyncio
import json
import sys
from unittest.mock import patch, MagicMock
import pytest
from fastapi.testclient import TestClient

# Mock the SESAME modules before importing main
sys.modules['pysesameos2.ble'] = MagicMock()
sys.modules['pysesameos2.device'] = MagicMock()
sys.modules['pysesameos2.helper'] = MagicMock()
sys.modules['pysesameos2.chsesame2'] = MagicMock()
sys.modules['pysesameos2.chsesamebot'] = MagicMock()

# Set test environment variables
import os
os.environ['SESAME_BLE_UUID'] = 'test-uuid'
os.environ['SESAME_SECRET_KEY'] = 'test-secret-key'
os.environ['SESAME_PUBLIC_KEY'] = 'test-public-key'

from main import app

client = TestClient(app)


def test_root_endpoint():
    """Test the root endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "version" in data
    assert "endpoints" in data


def test_health_endpoint():
    """Test the health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


def test_toggle_endpoint_structure():
    """Test that the toggle endpoint exists and has proper structure."""
    # This will fail with our mock, but we can test the endpoint structure
    response = client.post("/toggle")
    # Should return an error due to mocked dependencies, but endpoint should exist
    assert response.status_code in [500, 422]  # Either server error or validation error


def test_lock_endpoint_structure():
    """Test that the lock endpoint exists."""
    response = client.post("/lock")
    assert response.status_code in [500, 422]


def test_unlock_endpoint_structure():
    """Test that the unlock endpoint exists."""
    response = client.post("/unlock")
    assert response.status_code in [500, 422]


def test_click_endpoint_structure():
    """Test that the click endpoint exists."""
    response = client.post("/click")
    assert response.status_code in [500, 422]


def test_status_endpoint_structure():
    """Test that the status endpoint exists."""
    response = client.get("/status")
    assert response.status_code in [500, 422]


if __name__ == "__main__":
    print("Running SESAME Web API tests...")
    
    print("✓ Testing root endpoint...")
    test_root_endpoint()
    
    print("✓ Testing health endpoint...")
    test_health_endpoint()
    
    print("✓ Testing toggle endpoint structure...")
    test_toggle_endpoint_structure()
    
    print("✓ Testing lock endpoint structure...")
    test_lock_endpoint_structure()
    
    print("✓ Testing unlock endpoint structure...")
    test_unlock_endpoint_structure()
    
    print("✓ Testing click endpoint structure...")
    test_click_endpoint_structure()
    
    print("✓ Testing status endpoint structure...")
    test_status_endpoint_structure()
    
    print("\nAll tests passed! ✅")
    print("Note: These are structure tests with mocked dependencies.")
    print("To test with a real device, set up proper environment variables and run the server.")
