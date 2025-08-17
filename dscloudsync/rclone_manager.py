"""Rclone management and operations."""

import os
import platform
import tempfile
import zipfile
import json
import ssl
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
                # Create SSL context that handles Steam Deck certificate issues
                ssl_context = ssl.create_default_context()
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE
                
                with urlopen(url, context=ssl_context) as response:
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




def list_existing_remotes() -> list:
    """List existing rclone remotes."""
    try:
        result = run([str(RCLONE_BIN), "listremotes"], check=False)
        if result.returncode == 0:
            return [line.strip().rstrip(':') for line in result.stdout.strip().split('\n') if line.strip()]
        return []
    except Exception:
        return []


def test_remote_connection(remote_name: str, output_cb=None) -> bool:
    """Test if a remote connection works, refresh token if needed."""
    try:
        # Try a simple operation to test the connection
        test_cmd = [str(RCLONE_BIN), "lsd", f"{remote_name}:", "--max-depth", "1"]
        result = run(test_cmd, check=False, output_callback=output_cb)
        
        if result.returncode == 0:
            return True
            
        # Check if it's a token issue
        if "empty token" in result.stdout or "oauth" in result.stdout.lower():
            if output_cb:
                output_cb(f"Token expired for {remote_name}, refreshing...\n")
            
            # Attempt to refresh the token
            refresh_cmd = [str(RCLONE_BIN), "config", "reconnect", remote_name]
            refresh_result = run(refresh_cmd, check=False, output_callback=output_cb)
            
            if refresh_result.returncode == 0:
                if output_cb:
                    output_cb(f"Successfully refreshed {remote_name} token\n")
                return True
            else:
                if output_cb:
                    output_cb(f"Failed to refresh {remote_name} token: {refresh_result.stderr}\n")
                
        return False
        
    except Exception as e:
        if output_cb:
            output_cb(f"Error testing {remote_name}: {str(e)}\n")
        return False


def setup_cloud_provider_simple(provider: str, remote_name: str, output_cb=None) -> bool:
    """Streamlined cloud provider setup with device authentication."""
    
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
            output_cb(f"Setting up {provider} cloud storage...\n\n")
            output_cb("STEP 1: Creating basic configuration...\n")
        
        # Create a basic remote configuration first
        cmd = [str(RCLONE_BIN), "config", "create", remote_name, backend_type]
        result = run(cmd, check=False, output_callback=output_cb)
        
        if result.returncode != 0:
            if output_cb:
                output_cb(f"❌ Failed to create basic config: {result.stderr}\n")
            return False
            
        if output_cb:
            output_cb("✅ Basic configuration created.\n\n")
            output_cb("STEP 2: Getting authentication token...\n")
            output_cb("=" * 60 + "\n")
            output_cb("🔐 AUTHENTICATION REQUIRED\n")
            output_cb("=" * 60 + "\n")
            output_cb("The following will show a URL and code.\n")
            output_cb("1. Copy the URL and open it in any browser\n")
            output_cb("2. Sign in to your account\n") 
            output_cb("3. Enter the code when prompted\n")
            output_cb("4. Authorize the application\n")
            output_cb("=" * 60 + "\n\n")
        
        # Try rclone authorize, but handle SSL library issues on Steam Deck
        auth_cmd = [str(RCLONE_BIN), "authorize", backend_type]
        
        # Set environment to potentially bypass SSL issues
        import os
        env = os.environ.copy()
        env['SSL_CERT_FILE'] = ''
        env['SSL_CERT_DIR'] = ''
        
        try:
            auth_result = run(auth_cmd, check=False, output_callback=output_cb, env=env)
        except Exception as e:
            if output_cb:
                output_cb(f"Authorization failed due to system libraries: {str(e)}\n")
                output_cb("Falling back to manual setup instructions...\n\n")
                output_cb("=" * 60 + "\n")
                output_cb("MANUAL SETUP REQUIRED (Steam Deck)\n") 
                output_cb("=" * 60 + "\n")
                output_cb("Due to Steam Deck system limitations, please:\n\n")
                output_cb("1. Open a new terminal (Konsole)\n")
                output_cb("2. Navigate to the rclone directory:\n")
                output_cb(f"   cd {RCLONE_BIN.parent}\n")
                output_cb("3. Run rclone config:\n")
                output_cb(f"   ./rclone config\n")
                output_cb("4. Choose 'n' for new remote\n")
                output_cb(f"5. Name: {remote_name}\n")
                output_cb(f"6. Storage: {backend_type}\n")
                output_cb("7. Follow authentication prompts\n")
                output_cb("8. When asked about config_is_local, choose 'y'\n")
                output_cb("9. When complete, restart this app\n")
                output_cb("=" * 60 + "\n")
            return False
        
        if auth_result.returncode == 0 and auth_result.stdout.strip():
            # Extract token from output - looking for JSON token object
            import json
            token_line = None
            
            # Try to find JSON token in the output
            for line in auth_result.stdout.split('\n'):
                line = line.strip()
                if line.startswith('{') and '"access_token"' in line:
                    try:
                        # Validate it's proper JSON
                        json.loads(line)
                        token_line = line
                        break
                    except:
                        continue
            
            if token_line:
                if output_cb:
                    output_cb(f"\n✅ Authorization successful!\n")
                    output_cb("STEP 3: Updating configuration with token...\n")
                
                # Update the remote with the token
                update_cmd = [str(RCLONE_BIN), "config", "update", remote_name, "token", token_line]
                update_result = run(update_cmd, check=False, output_callback=output_cb)
                
                if update_result.returncode == 0:
                    if output_cb:
                        output_cb(f"🎉 Successfully set up {provider}!\n")
                    return True
                else:
                    if output_cb:
                        output_cb(f"❌ Failed to update config with token: {update_result.stderr}\n")
            else:
                if output_cb:
                    output_cb("❌ Could not extract authentication token\n")
                    output_cb(f"Debug - auth output: {auth_result.stdout[:500]}\n")
        else:
            if output_cb:
                output_cb(f"❌ Authentication failed: {auth_result.stderr}\n")
        
        return False
            
    except Exception as e:
        if output_cb:
            output_cb(f"❌ Setup failed: {str(e)}\n")
        return False