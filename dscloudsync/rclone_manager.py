"""Rclone management and operations."""

import os
import platform
import tempfile
import zipfile
import json
from pathlib import Path
from urllib.request import urlopen

from .utils import app_home, run


RCLONE_DIR = app_home() / "rclone"
RCLONE_BIN = RCLONE_DIR / ("rclone.exe" if platform.system() == "Windows" else "rclone")


def rclone_asset() -> str:
    """Get platform-specific rclone download filename."""
    arch = platform.machine().lower()
    
    # Normalize architecture names
    if arch in ("x86_64", "amd64"):
        arch = "amd64"
    elif arch in ("aarch64", "arm64"):
        arch = "arm64"
    else:
        arch = "amd64"  # Default fallback
    
    system = platform.system()
    
    if system == "Windows":
        return f"rclone-current-windows-{arch}.zip"
    elif system == "Darwin":
        return f"rclone-current-osx-{arch}.zip"
    else:
        return f"rclone-current-linux-{arch}.zip"


def extract_rclone_from_zip(zip_path: Path, dest_dir: Path) -> Path:
    """Extract rclone binary from downloaded zip."""
    with zipfile.ZipFile(zip_path, 'r') as zip_file:
        names = zip_file.namelist()
        
        # Find rclone binary in archive
        rclone_files = [n for n in names if n.endswith("rclone") or n.endswith("rclone.exe")]
        if not rclone_files:
            raise RuntimeError("rclone binary not found in archive")
        
        # Select appropriate binary for platform
        if platform.system() == "Windows":
            exe_files = [n for n in rclone_files if n.endswith(".exe")]
            binary_name = exe_files[0] if exe_files else rclone_files[0]
        else:
            binary_name = rclone_files[0]
        
        # Extract and move to final location
        zip_file.extract(binary_name, dest_dir)
        src_path = dest_dir / binary_name
        
        RCLONE_BIN.parent.mkdir(parents=True, exist_ok=True)
        if RCLONE_BIN.exists():
            RCLONE_BIN.unlink()
        
        src_path.rename(RCLONE_BIN)
        
        # Make executable on Unix-like systems
        if platform.system() != "Windows":
            os.chmod(RCLONE_BIN, 0o755)
        
        return RCLONE_BIN


def ensure_rclone(status_cb=lambda s: None, output_cb=None) -> None:
    """Auto-download rclone binary if not present.
    
    Security: Downloads from official rclone.org only.
    """
    if not RCLONE_BIN.exists():
        status_cb("Downloading rclone...")
        
        filename = rclone_asset()
        # Security: Only download from official rclone.org
        url = f"https://downloads.rclone.org/{filename}"
        
        # Download to temp file with secure permissions
        with tempfile.NamedTemporaryFile(delete=False, mode='wb') as tmp_file:
            tmp_path = Path(tmp_file.name)
            
            try:
                with urlopen(url) as response:
                    # Limit download size to prevent DoS
                    max_size = 100 * 1024 * 1024  # 100MB max
                    downloaded = 0
                    chunk_size = 8192
                    last_progress = 0
                    
                    while True:
                        chunk = response.read(chunk_size)
                        if not chunk:
                            break
                        
                        downloaded += len(chunk)
                        if downloaded > max_size:
                            raise RuntimeError("Download too large")
                        
                        # Show progress for downloads
                        if output_cb:
                            progress_mb = downloaded / (1024 * 1024)
                            if progress_mb - last_progress >= 1:  # Update every MB
                                output_cb(f"Downloaded {progress_mb:.1f} MB...\n")
                                last_progress = progress_mb
                        
                        tmp_file.write(chunk)
            except Exception:
                tmp_path.unlink(missing_ok=True)
                raise
        
        try:
            if output_cb:
                output_cb("Extracting rclone binary...\n")
            extract_rclone_from_zip(tmp_path, RCLONE_DIR)
        finally:
            tmp_path.unlink(missing_ok=True)
    
    # Verify rclone is working
    run([str(RCLONE_BIN), "version"], output_callback=output_cb)


def rclone_lsjson(remote_path: str) -> list:
    """List remote directory contents with hashes."""
    result = run([str(RCLONE_BIN), "lsjson", "--hash", remote_path], check=False)
    
    try:
        return json.loads(result.stdout or "[]")
    except Exception:
        return []


def ensure_remote_dir(remote_dir: str, output_cb=None) -> None:
    """Ensure remote directory exists before sync operations."""
    if output_cb:
        output_cb(f"Ensuring remote directory exists: {remote_dir}\n")
    
    # Use mkdir to create the directory if it doesn't exist
    cmd = [str(RCLONE_BIN), "mkdir", remote_dir]
    
    # Don't check=True because mkdir fails if directory already exists
    result = run(cmd, check=False, output_callback=output_cb)
    
    if result.returncode == 0:
        if output_cb:
            output_cb(f"Created remote directory: {remote_dir}\n")
    else:
        # Directory might already exist, which is fine
        if output_cb:
            output_cb(f"Remote directory check complete (may already exist)\n")


def bisync(local_dir: str, remote_dir: str, resync: bool = False, output_cb=None) -> None:
    """Perform bidirectional sync using rclone bisync."""
    
    # Ensure remote directory exists before syncing
    ensure_remote_dir(remote_dir, output_cb)
    
    if resync:
        # Simple resync command for initial setup
        cmd = [
            str(RCLONE_BIN), "bisync", local_dir, remote_dir,
            "--resync",
            "--create-empty-src-dirs",
            "--verbose",
        ]
    else:
        # Regular sync with conflict resolution
        cmd = [
            str(RCLONE_BIN), "bisync", local_dir, remote_dir,
            "--create-empty-src-dirs",
            "--compare", "size,checksum,modtime",
            "--conflict-resolve", "newer",
            "--verbose",
        ]
    
    run(cmd, check=True, output_callback=output_cb)




def setup_cloud_provider_simple(provider: str, remote_name: str, output_cb=None) -> bool:
    """Simplified cloud provider setup using rclone's built-in web auth."""
    
    # Map provider names to rclone backend types
    backend_map = {
        "gdrive": "drive",
        "onedrive": "onedrive", 
        "dropbox": "dropbox",
        "box": "box"
    }
    
    if provider not in backend_map:
        if output_cb:
            output_cb(f"❌ Unsupported provider: {provider}\n")
        return False
    
    backend_type = backend_map[provider]
    
    try:
        if output_cb:
            output_cb(f"Setting up {provider} cloud storage...\n")
            output_cb("This will open your web browser for authentication.\n")
        
        # Use simple rclone config create with minimal options
        cmd = [str(RCLONE_BIN), "config", "create", remote_name, backend_type]
        
        # Add provider-specific minimal settings
        if provider == "gdrive":
            cmd.extend(["scope", "drive"])
        
        if output_cb:
            output_cb("Starting authentication process...\n")
        
        result = run(cmd, check=False, output_callback=output_cb)
        
        if result.returncode == 0:
            if output_cb:
                output_cb(f"✅ Successfully set up {provider}!\n")
            return True
        else:
            if output_cb:
                output_cb(f"❌ Setup failed with exit code {result.returncode}\n")
                output_cb("This usually means authentication was cancelled or failed.\n")
            return False
            
    except Exception as e:
        if output_cb:
            output_cb(f"❌ Setup failed: {str(e)}\n")
        return False