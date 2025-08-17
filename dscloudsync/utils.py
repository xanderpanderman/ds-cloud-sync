"""Utility functions for DS2 Cloud Sync."""

import os
import platform
import subprocess
import datetime
import hashlib
from pathlib import Path

from . import APPNAME


def app_home() -> Path:
    """Get platform-specific application data directory."""
    system = platform.system()
    
    if system == "Windows":
        base = Path(os.environ.get("APPDATA", Path.home()))
    elif system == "Darwin":
        base = Path.home() / "Library" / "Application Support"
    else:  # Linux/SteamOS
        base = Path.home() / ".local" / "share"
    
    app_dir = base / APPNAME
    app_dir.mkdir(parents=True, exist_ok=True)
    return app_dir


LOG_FILE = app_home() / "sync.log"


def log(msg: str) -> None:
    """Append message to log file with timestamp."""
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            timestamp = datetime.datetime.now().isoformat()
            f.write(f"{timestamp} {msg}\n")
    except Exception:
        pass


def run(cmd: list, check: bool = True, output_callback=None, env=None) -> subprocess.CompletedProcess:
    """Execute command and log output.
    
    Security: Commands are logged but sensitive output is not exposed to users.
    
    Args:
        cmd: Command list to execute
        check: Whether to raise exception on non-zero exit
        output_callback: Optional callback function for real-time output streaming
    """
    # Ensure command list contains only strings
    cmd = [str(c) for c in cmd]
    safe_cmd = ' '.join(cmd)
    
    # Log command start
    log(f">> {safe_cmd}")
    if output_callback:
        output_callback(f"Running: {safe_cmd}\n")
    
    if output_callback:
        # Stream output in real-time
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True,
            shell=False,
            env=env
        )
        
        output_lines = []
        while True:
            line = process.stdout.readline()
            if line:
                output_lines.append(line)
                output_callback(line)
            elif process.poll() is not None:
                break
        
        # Get any remaining output
        remaining = process.stdout.read()
        if remaining:
            output_lines.append(remaining)
            output_callback(remaining)
        
        output = ''.join(output_lines)
        returncode = process.returncode
        
        # Create result object to match subprocess.run interface
        result = subprocess.CompletedProcess(cmd, returncode, output, None)
    else:
        # Use original synchronous approach
        result = subprocess.run(
            cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.STDOUT, 
            text=True,
            shell=False,
            env=env
        )
        output = result.stdout or ""
    
    # Log output
    log(output)
    
    if check and result.returncode != 0:
        error_msg = output.strip() or f"Command failed: {safe_cmd}"
        raise RuntimeError(error_msg)
    
    return result


def iso_now() -> str:
    """Get current timestamp in ISO format for filenames."""
    return datetime.datetime.now().strftime("%Y%m%d-%H%M%S")


def file_sha1(path: Path) -> str:
    """Calculate SHA-1 hash of file."""
    hash_obj = hashlib.sha1()
    
    with open(path, "rb") as f:
        # Read in 64KB chunks
        for chunk in iter(lambda: f.read(65536), b""):
            hash_obj.update(chunk)
    
    return hash_obj.hexdigest()