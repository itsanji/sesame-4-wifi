#!/usr/bin/env python3
"""
SESAME Web API Daemon
A Python daemon script to run the SESAME web app in the background.
"""

import os
import sys
import time
import signal
import logging
import argparse
import subprocess
from pathlib import Path
from typing import Optional

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class SesameDaemon:
    def __init__(self, app_dir: str, pid_file: str, log_file: str):
        self.app_dir = Path(app_dir).resolve()
        self.pid_file = Path(pid_file)
        self.log_file = Path(log_file)
        self.process: Optional[subprocess.Popen] = None
        
    def is_running(self) -> bool:
        """Check if the daemon is running."""
        if not self.pid_file.exists():
            return False
            
        try:
            pid = int(self.pid_file.read_text().strip())
            # Check if process exists
            os.kill(pid, 0)
            return True
        except (ValueError, OSError, ProcessLookupError):
            # Process doesn't exist, clean up PID file
            self.pid_file.unlink(missing_ok=True)
            return False
    
    def start(self):
        """Start the SESAME web app daemon."""
        if self.is_running():
            logger.warning("Daemon is already running!")
            self.status()
            return
            
        # Check if main.py exists
        main_script = self.app_dir / "main.py"
        if not main_script.exists():
            logger.error(f"Main script not found: {main_script}")
            return
            
        # Check if .env exists
        env_file = self.app_dir / ".env"
        if not env_file.exists():
            logger.warning(".env file not found. Creating from env.example...")
            env_example = self.app_dir / "env.example"
            if env_example.exists():
                env_example.copy(env_file)
                logger.warning(f"Please edit {env_file} with your device credentials")
            else:
                logger.error("env.example not found!")
                return
        
        # Create log directory if it doesn't exist
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Start the process
        logger.info(f"Starting SESAME Web API daemon...")
        logger.info(f"App directory: {self.app_dir}")
        logger.info(f"Log file: {self.log_file}")
        
        try:
            # Open log file for writing
            with open(self.log_file, 'w') as log_handle:
                # Start the Python process
                self.process = subprocess.Popen(
                    [sys.executable, str(main_script)],
                    cwd=self.app_dir,
                    stdout=log_handle,
                    stderr=subprocess.STDOUT,
                    preexec_fn=os.setsid  # Create new process group
                )
                
                # Save PID to file
                self.pid_file.write_text(str(self.process.pid))
                logger.info(f"Daemon started with PID: {self.process.pid}")
                
                # Wait a moment to check if it started successfully
                time.sleep(2)
                
                if self.is_running():
                    logger.info("Daemon started successfully!")
                    self.status()
                else:
                    logger.error("Failed to start daemon!")
                    self.stop()
                    
        except Exception as e:
            logger.error(f"Error starting daemon: {e}")
            self.stop()
    
    def stop(self):
        """Stop the SESAME web app daemon."""
        if not self.is_running():
            logger.warning("Daemon is not running!")
            return
            
        try:
            pid = int(self.pid_file.read_text().strip())
            logger.info(f"Stopping daemon (PID: {pid})...")
            
            # Try graceful shutdown
            os.kill(pid, signal.SIGTERM)
            
            # Wait for graceful shutdown
            for i in range(10):
                if not self.is_running():
                    break
                time.sleep(1)
            
            # Force kill if still running
            if self.is_running():
                logger.warning("Force killing daemon...")
                os.kill(pid, signal.SIGKILL)
                time.sleep(1)
            
            # Clean up PID file
            self.pid_file.unlink(missing_ok=True)
            
            if not self.is_running():
                logger.info("Daemon stopped successfully!")
            else:
                logger.error("Failed to stop daemon!")
                
        except Exception as e:
            logger.error(f"Error stopping daemon: {e}")
    
    def restart(self):
        """Restart the SESAME web app daemon."""
        logger.info("Restarting daemon...")
        self.stop()
        time.sleep(2)
        self.start()
    
    def status(self):
        """Show daemon status."""
        if self.is_running():
            pid = int(self.pid_file.read_text().strip())
            logger.info(f"✓ Daemon is RUNNING (PID: {pid})")
            logger.info(f"  PID file: {self.pid_file}")
            logger.info(f"  Log file: {self.log_file}")
            logger.info(f"  App dir: {self.app_dir}")
            
            # Check if API is responding
            try:
                import requests
                response = requests.get("http://localhost:8000/health", timeout=5)
                if response.status_code == 200:
                    logger.info("  API: ✓ Responding")
                else:
                    logger.warning("  API: ⚠ Not responding properly")
            except:
                logger.warning("  API: ⚠ Not responding")
        else:
            logger.info("✗ Daemon is STOPPED")
    
    def logs(self, follow: bool = False):
        """Show daemon logs."""
        if not self.log_file.exists():
            logger.warning(f"No log file found: {self.log_file}")
            return
            
        if follow:
            logger.info("Showing logs (Ctrl+C to exit):")
            try:
                # Use tail -f equivalent
                with open(self.log_file, 'r') as f:
                    # Go to end of file
                    f.seek(0, 2)
                    while True:
                        line = f.readline()
                        if line:
                            print(line.rstrip())
                        else:
                            time.sleep(0.1)
            except KeyboardInterrupt:
                logger.info("Log viewing stopped")
        else:
            logger.info("Recent logs:")
            try:
                with open(self.log_file, 'r') as f:
                    lines = f.readlines()
                    for line in lines[-50:]:  # Last 50 lines
                        print(line.rstrip())
            except Exception as e:
                logger.error(f"Error reading logs: {e}")

def main():
    parser = argparse.ArgumentParser(description="SESAME Web API Daemon")
    parser.add_argument("command", choices=["start", "stop", "restart", "status", "logs", "follow"],
                       help="Command to execute")
    parser.add_argument("--app-dir", default=".",
                       help="Application directory (default: current directory)")
    parser.add_argument("--pid-file", default="sesame_webapi.pid",
                       help="PID file path (default: sesame_webapi.pid)")
    parser.add_argument("--log-file", default="sesame_webapi.log",
                       help="Log file path (default: sesame_webapi.log)")
    
    args = parser.parse_args()
    
    # Create daemon instance
    daemon = SesameDaemon(args.app_dir, args.pid_file, args.log_file)
    
    # Execute command
    if args.command == "start":
        daemon.start()
    elif args.command == "stop":
        daemon.stop()
    elif args.command == "restart":
        daemon.restart()
    elif args.command == "status":
        daemon.status()
    elif args.command == "logs":
        daemon.logs(follow=False)
    elif args.command == "follow":
        daemon.logs(follow=True)

if __name__ == "__main__":
    main()
