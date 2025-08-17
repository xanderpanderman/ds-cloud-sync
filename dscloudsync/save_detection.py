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
        # Profile dirs can be numeric or hex (e.g., "0110000107afa7e2")
        profile_dirs = [p for p in save_root.glob("*") if p.is_dir() and len(p.name) > 5]
        
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
            # Check for any .sl2 files, not just specific names
            sl2_files = list(profile_dir.glob("*.sl2"))
            if sl2_files:
                has_saves = True
                break
            # Also check the specific names as backup
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
    """Select profile directory, prioritizing ones with actual saves for cross-platform compatibility."""
    root.mkdir(parents=True, exist_ok=True)
    
    # Find all profile directories (numeric or hex)
    profile_dirs = [p for p in root.glob("*") if p.is_dir() and len(p.name) > 5]
    
    if not profile_dirs:
        # Create default profile if none exist - use generic Steam ID format
        default_profile = root / "0000000000000000"  # Generic default profile
        default_profile.mkdir(parents=True, exist_ok=True)
        return default_profile
    
    # Prioritize directories that actually contain save files
    profiles_with_saves = []
    profiles_without_saves = []
    
    for profile_dir in profile_dirs:
        sl2_files = list(profile_dir.glob("*.sl2"))
        if sl2_files:
            # Check modification time of most recent save file
            most_recent_save = max(sl2_files, key=lambda f: f.stat().st_mtime)
            profiles_with_saves.append((profile_dir, most_recent_save.stat().st_mtime))
        else:
            profiles_without_saves.append((profile_dir, profile_dir.stat().st_mtime))
    
    # If we have profiles with saves, return the one with most recent save activity
    if profiles_with_saves:
        profiles_with_saves.sort(key=lambda x: x[1], reverse=True)
        return profiles_with_saves[0][0]
    
    # If no profiles have saves, return most recently modified directory
    if profiles_without_saves:
        profiles_without_saves.sort(key=lambda x: x[1], reverse=True)
        return profiles_without_saves[0][0]
    
    # This shouldn't happen, but fallback to first profile
    return profile_dirs[0]


def find_save_file(dir_path: Path) -> Path:
    """Locate .sl2 save file in directory."""
    # First check for DS2-specific save names
    for save_name in SAVE_BASENAMES:
        save_path = dir_path / save_name
        if save_path.exists():
            return save_path
    
    # Fallback: check for any .sl2 files
    sl2_files = list(dir_path.glob("*.sl2"))
    if sl2_files:
        # Return the most recently modified .sl2 file
        return max(sl2_files, key=lambda f: f.stat().st_mtime)
    
    # Return default path if no save exists yet
    return dir_path / SAVE_BASENAMES[0]


def consolidate_cross_platform_saves(root: Path) -> None:
    """Consolidate saves from different profile directories for cross-platform compatibility.
    
    This helps when saves are synced from a different platform with a different Steam ID.
    Moves saves from other profile directories to the currently active one.
    """
    try:
        # Find all profile directories
        profile_dirs = [p for p in root.glob("*") if p.is_dir() and len(p.name) > 5]
        
        if len(profile_dirs) <= 1:
            return  # Nothing to consolidate
        
        # Find the active profile (the one we would use)
        active_profile = pick_profile_dir(root)
        
        # Look for saves in other profile directories
        for profile_dir in profile_dirs:
            if profile_dir == active_profile:
                continue
                
            # Check if this directory has saves
            sl2_files = list(profile_dir.glob("*.sl2"))
            if not sl2_files:
                continue
                
            # Move saves to active profile if they're newer or if active profile is empty
            active_saves = list(active_profile.glob("*.sl2"))
            
            for save_file in sl2_files:
                dest_path = active_profile / save_file.name
                
                # Move if destination doesn't exist or source is newer
                if not dest_path.exists() or save_file.stat().st_mtime > dest_path.stat().st_mtime:
                    save_file.rename(dest_path)
                    
    except Exception:
        # Don't let consolidation errors break the main flow
        pass