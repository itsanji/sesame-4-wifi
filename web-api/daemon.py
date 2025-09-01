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
import platform
from pathlib import Path
from typing import Optional

# Import fcntl only on Unix systems
try:
    import fcntl
    HAS_FCNTL = True
except ImportError:
    HAS_FCNTL = False

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

# Setup logging with local time
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
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
            # Use file locking to prevent race conditions
            with open(self.pid_file, 'r') as f:
                if HAS_FCNTL and platform.system() != 'Windows':
                    fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                pid = int(f.read().strip())
                
            # Check if process exists
            os.kill(pid, 0)
            return True
        except (ValueError, OSError, ProcessLookupError, BlockingIOError):
            # Process doesn't exist or file is locked, clean up PID file
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
            # Open log file for appending (preserve historical logs)
            with open(self.log_file, 'a') as log_handle:
                # Add startup separator to logs
                log_handle.write(f"\n{'='*50}\n")
                log_handle.write(f"SESAME Web API Daemon Starting - {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                log_handle.write(f"{'='*50}\n")
                log_handle.flush()
                
                # Prepare subprocess arguments (cross-platform)
                subprocess_kwargs = {
                    'args': [sys.executable, str(main_script)],
                    'cwd': self.app_dir,
                    'stdout': log_handle,
                    'stderr': subprocess.STDOUT,
                }
                
                # Add process group creation for Unix systems only
                if platform.system() != 'Windows':
                    subprocess_kwargs['preexec_fn'] = os.setsid
                
                # Start the Python process
                self.process = subprocess.Popen(**subprocess_kwargs)
                
                # Save PID to file with locking
                with open(self.pid_file, 'w') as pid_handle:
                    if HAS_FCNTL and platform.system() != 'Windows':
                        fcntl.flock(pid_handle.fileno(), fcntl.LOCK_EX)
                    pid_handle.write(str(self.process.pid))
                    pid_handle.flush()
                
                logger.info(f"Daemon started with PID: {self.process.pid}")
                
                # Wait longer and check periodically for startup
                startup_timeout = 10
                for i in range(startup_timeout):
                    time.sleep(1)
                    if self.process.poll() is not None:
                        # Process has terminated
                        logger.error(f"Process terminated early with code: {self.process.returncode}")
                        break
                    if i >= 3 and self.is_running():  # Check after 3 seconds minimum
                        break
                
                if self.is_running():
                    logger.info("Daemon started successfully!")
                    # Wait a bit more for the web server to fully start
                    time.sleep(2)
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
            
            # Cross-platform process termination
            if platform.system() == 'Windows':
                # On Windows, use taskkill for graceful shutdown
                try:
                    subprocess.run(['taskkill', '/pid', str(pid), '/t'], 
                                 check=True, capture_output=True)
                except subprocess.CalledProcessError:
                    # Force kill on Windows
                    subprocess.run(['taskkill', '/pid', str(pid), '/f', '/t'], 
                                 capture_output=True)
            else:
                # Unix-like systems
                try:
                    # Try graceful shutdown (SIGTERM)
                    os.kill(pid, signal.SIGTERM)
                    
                    # Wait for graceful shutdown
                    for i in range(15):  # Increased timeout
                        if not self.is_running():
                            break
                        time.sleep(1)
                    
                    # Force kill if still running (SIGKILL)
                    if self.is_running():
                        logger.warning("Graceful shutdown timeout, force killing daemon...")
                        os.kill(pid, signal.SIGKILL)
                        time.sleep(2)
                        
                except ProcessLookupError:
                    # Process already dead
                    pass
            
            # Clean up PID file
            self.pid_file.unlink(missing_ok=True)
            
            # Final check
            if not self.is_running():
                logger.info("Daemon stopped successfully!")
                # Add shutdown log entry
                if self.log_file.exists():
                    with open(self.log_file, 'a') as log_handle:
                        log_handle.write(f"\n{'='*50}\n")
                        log_handle.write(f"SESAME Web API Daemon Stopped - {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                        log_handle.write(f"{'='*50}\n\n")
            else:
                logger.error("Failed to stop daemon!")
                
        except Exception as e:
            logger.error(f"Error stopping daemon: {e}")
            # Force cleanup PID file on error
            self.pid_file.unlink(missing_ok=True)
    
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
                response = requests.get("http://localhost:8000/health", timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    logger.info("  API: ✓ Responding")
                    logger.info(f"    Status: {data.get('status', 'unknown')}")
                else:
                    logger.warning(f"  API: ⚠ Not responding properly (status: {response.status_code})")
            except ImportError:
                logger.warning("  API: ⚠ Cannot check (requests library not installed)")
            except requests.exceptions.ConnectConnectionError:
                logger.warning("  API: ⚠ Connection refused (service may be starting)")
            except requests.exceptions.Timeout:
                logger.warning("  API: ⚠ Request timeout (service may be busy)")
            except Exception as e:
                logger.warning(f"  API: ⚠ Error checking ({type(e).__name__})")
        else:
            logger.info("✗ Daemon is STOPPED")
    
    def logs(self, follow: bool = False, lines: int = 50):
        """Show daemon logs."""
        if not self.log_file.exists():
            logger.warning(f"No log file found: {self.log_file}")
            return
            
        if follow:
            logger.info("Showing logs (Ctrl+C to exit):")
            try:
                # Show recent logs first
                with open(self.log_file, 'r') as f:
                    recent_lines = f.readlines()
                    for line in recent_lines[-lines:]:
                        print(line.rstrip())
                
                # Then follow new logs
                last_position = self.log_file.stat().st_size
                
                while True:
                    current_size = self.log_file.stat().st_size
                    if current_size > last_position:
                        with open(self.log_file, 'r') as f:
                            f.seek(last_position)
                            new_lines = f.readlines()
                            for line in new_lines:
                                print(line.rstrip())
                        last_position = current_size
                    time.sleep(0.5)
                    
            except KeyboardInterrupt:
                logger.info("\nLog viewing stopped")
            except Exception as e:
                logger.error(f"Error following logs: {e}")
        else:
            logger.info(f"Recent logs (last {lines} lines):")
            try:
                with open(self.log_file, 'r') as f:
                    all_lines = f.readlines()
                    recent_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines
                    
                    if not recent_lines:
                        logger.info("No logs found")
                        return
                        
                    for line in recent_lines:
                        print(line.rstrip())
                        
                    logger.info(f"\n--- End of logs (showing {len(recent_lines)} lines) ---")
                    
            except Exception as e:
                logger.error(f"Error reading logs: {e}")

def main():
    parser = argparse.ArgumentParser(
        description="SESAME Web API Daemon",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python daemon.py start          # Start the daemon
  python daemon.py stop           # Stop the daemon
  python daemon.py restart        # Restart the daemon  
  python daemon.py status         # Show daemon status
  python daemon.py logs           # Show recent logs
  python daemon.py follow         # Follow logs in real-time
        """)
    
    parser.add_argument("command", choices=["start", "stop", "restart", "status", "logs", "follow"],
                       help="Command to execute")
    parser.add_argument("--app-dir", default=".",
                       help="Application directory (default: current directory)")
    parser.add_argument("--pid-file", default="sesame_webapi.pid",
                       help="PID file path (default: sesame_webapi.pid)")
    parser.add_argument("--log-file", default="sesame_webapi.log",
                       help="Log file path (default: sesame_webapi.log)")
    parser.add_argument("--lines", type=int, default=50,
                       help="Number of log lines to show (default: 50)")
    
    args = parser.parse_args()
    
    # Validate arguments
    if args.lines < 1:
        parser.error("--lines must be a positive integer")
    
    # Create daemon instance
    daemon = SesameDaemon(args.app_dir, args.pid_file, args.log_file)
    
    # Execute command
    try:
        if args.command == "start":
            daemon.start()
        elif args.command == "stop":
            daemon.stop()
        elif args.command == "restart":
            daemon.restart()
        elif args.command == "status":
            daemon.status()
        elif args.command == "logs":
            daemon.logs(follow=False, lines=args.lines)
        elif args.command == "follow":
            daemon.logs(follow=True, lines=args.lines)
    except KeyboardInterrupt:
        logger.info("\nOperation cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
