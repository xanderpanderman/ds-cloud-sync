"""Save file detection and management across platforms."""

import os
import platform
from pathlib import Path

from . import APPID_SOTFS, APPID_VANILLA, APPID_SOTFS_ALT, SAVE_BASENAMES


def detect_save_root() -> Path:
    """Detect DS2 save folder across platforms."""
    system = platform.system()
    
    if system == "Windows":
        appdata = os.environ.get("APPDATA")
        if not appdata:
            raise RuntimeError("APPDATA environment variable not set")
        return Path(appdata) / "DarkSoulsII"
    
    elif system == "Darwin":
        # Check native macOS location first
        native = Path.home() / "Library" / "Application Support" / "DarkSoulsII"
        if native.exists():
            return native
        
        # Check Steam/CrossOver compatibility paths
        prefixes = [
            Path.home() / ".steam" / "steam" / "steamapps" / "compatdata" / APPID_SOTFS / "pfx",
            Path.home() / ".steam" / "steam" / "steamapps" / "compatdata" / APPID_VANILLA / "pfx",
            Path.home() / "Library" / "Application Support" / "CrossOver" / "Bottles",
        ]
        
        for prefix in prefixes:
            users_dir = prefix / "drive_c" / "users"
            if users_dir.exists():
                for user_dir in users_dir.glob("*"):
                    save_dir = user_dir / "AppData" / "Roaming" / "DarkSoulsII"
                    if save_dir.exists():
                        return save_dir
        
        return native
    
    else:  # Linux/SteamOS
        base = Path.home() / ".local/share/Steam/steamapps/compatdata"
        
        for appid in (APPID_SOTFS, APPID_SOTFS_ALT, APPID_VANILLA):
            users_dir = base / appid / "pfx" / "drive_c" / "users"
            if users_dir.exists():
                for user_dir in users_dir.glob("*"):
                    save_dir = user_dir / "AppData" / "Roaming" / "DarkSoulsII"
                    if save_dir.exists():
                        return save_dir
        
        # Default fallback for Steam Deck - try multiple app IDs
        for appid in (APPID_SOTFS, APPID_SOTFS_ALT, APPID_VANILLA):
            fallback = base / appid / "pfx" / "drive_c" / "users" / "steamuser" / "AppData" / "Roaming" / "DarkSoulsII"
            if fallback.exists():
                return fallback
        
        # Final fallback to most common
        return base / APPID_SOTFS / "pfx" / "drive_c" / "users" / "steamuser" / "AppData" / "Roaming" / "DarkSoulsII"


def check_ds2_installation() -> dict:
    """Check Dark Souls 2 installation and save status.
    
    Returns:
        dict with keys: 'installed', 'has_saves', 'save_root', 'message'
    """
    try:
        save_root = detect_save_root()
        
        # Check if the save directory actually exists
        if not save_root.exists():
            return {
                'installed': False,
                'has_saves': False,
                'save_root': save_root,
                'message': 'Dark Souls 2 not detected on this system'
            }
        
        # Check for any profile directories (DS2 saves)
        profile_dirs = [p for p in save_root.glob("*") if p.is_dir() and p.name.isdigit()]
        
        if not profile_dirs:
            return {
                'installed': True,
                'has_saves': False,
                'save_root': save_root,
                'message': 'Dark Souls 2 detected but no saves found yet'
            }
        
        # Check if any profile has actual save files
        has_saves = False
        for profile_dir in profile_dirs:
            for save_name in SAVE_BASENAMES:
                if (profile_dir / save_name).exists():
                    has_saves = True
                    break
            if has_saves:
                break
        
        if has_saves:
            return {
                'installed': True,
                'has_saves': True,
                'save_root': save_root,
                'message': f'Dark Souls 2 saves found ({len(profile_dirs)} profile{"s" if len(profile_dirs) != 1 else ""})'
            }
        else:
            return {
                'installed': True,
                'has_saves': False,
                'save_root': save_root,
                'message': 'Dark Souls 2 detected but no save files found yet'
            }
            
    except Exception as e:
        return {
            'installed': False,
            'has_saves': False,
            'save_root': None,
            'message': f'Error detecting Dark Souls 2: {str(e)}'
        }


def pick_profile_dir(root: Path) -> Path:
    """Select most recently used profile directory."""
    root.mkdir(parents=True, exist_ok=True)
    
    # Find all numeric profile directories
    profile_dirs = [p for p in root.glob("*") if p.is_dir() and p.name.isdigit()]
    
    if not profile_dirs:
        # Create default profile if none exist
        default_profile = root / "00000000000000000"
        default_profile.mkdir(parents=True, exist_ok=True)
        return default_profile
    
    # Return most recently modified profile
    profile_dirs.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return profile_dirs[0]


def find_save_file(dir_path: Path) -> Path:
    """Locate .sl2 save file in directory."""
    for save_name in SAVE_BASENAMES:
        save_path = dir_path / save_name
        if save_path.exists():
            return save_path
    
    # Return default path if no save exists yet
    return dir_path / SAVE_BASENAMES[0]