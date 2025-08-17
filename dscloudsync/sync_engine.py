"""Sync engine and conflict resolution logic."""

import datetime
import platform
import shutil
from pathlib import Path

from . import SAVE_BASENAMES
from .utils import run, iso_now, file_sha1
from .save_detection import find_save_file
from .rclone_manager import RCLONE_BIN, rclone_lsjson, bisync


def remote_find_save(remote_dir: str) -> dict | None:
    """Find save file in remote directory."""
    entries = rclone_lsjson(remote_dir)
    
    # Create name->entry mapping for files only
    files_by_name = {
        entry.get("Name"): entry 
        for entry in entries 
        if not entry.get("IsDir", False)
    }
    
    # Look for known save file names
    for save_name in SAVE_BASENAMES:
        if save_name in files_by_name:
            return files_by_name[save_name]
    
    return None


def backup_local_dir(local_dir: Path) -> Path:
    """Create timestamped backup of local save directory."""
    backup_dir = local_dir.parent / "Backups" / f"local-{iso_now()}"
    shutil.copytree(local_dir, backup_dir, dirs_exist_ok=True)
    return backup_dir


def backup_remote_dir(remote_dir: str, output_cb=None) -> str:
    """Create timestamped backup of remote save directory."""
    backup_path = f"{remote_dir.rstrip('/')}/Backups/remote-{iso_now()}"
    run([str(RCLONE_BIN), "copy", remote_dir, backup_path], check=False, output_callback=output_cb)
    return backup_path


def preview_text(local_path: Path | None, remote_entry: dict | None) -> str:
    """Generate preview text comparing local and remote saves."""
    lines = ["Save preview:"]
    
    # Local save info
    if local_path and local_path.exists():
        stat = local_path.stat()
        size_kb = stat.st_size / 1024
        mtime = datetime.datetime.fromtimestamp(stat.st_mtime)
        sha1 = file_sha1(local_path)
        
        lines.append(
            f"Local : {local_path.name} | {size_kb:.1f} KiB | "
            f"mtime {mtime} | sha1 {sha1}"
        )
    else:
        lines.append("Local : (none)")
    
    # Remote save info
    if remote_entry:
        name = remote_entry.get("Name")
        size = int(remote_entry.get("Size", 0))
        size_kb = size / 1024
        
        hashes = remote_entry.get("Hashes") or {}
        hash_value = hashes.get("SHA-1") or hashes.get("MD5") or "(no-hash)"
        mod_time = remote_entry.get("ModTime") or "(unknown)"
        
        lines.append(
            f"Cloud : {name} | {size_kb:.1f} KiB | "
            f"mtime {mod_time} | hash {hash_value}"
        )
    else:
        lines.append("Cloud : (none)")
    
    return "\n".join(lines)


def push_local_over_remote(local_dir: Path, remote_dir: str, output_cb=None) -> None:
    """Push local save to remote, overwriting if newer."""
    run([str(RCLONE_BIN), "copy", str(local_dir), remote_dir, "--update"], check=True, output_callback=output_cb)


def pull_remote_over_local(local_dir: Path, remote_dir: str, output_cb=None) -> None:
    """Pull remote save to local, overwriting if newer."""
    run([str(RCLONE_BIN), "copy", remote_dir, str(local_dir), "--update"], check=True, output_callback=output_cb)


def keep_both_variant(local_path: Path | None, machine_tag: str) -> Path | None:
    """Create a machine-tagged copy of local save."""
    if local_path and local_path.exists():
        variant_name = f"{local_path.stem}_{machine_tag}{local_path.suffix}"
        variant_path = local_path.with_name(variant_name)
        shutil.copy2(local_path, variant_path)
        return variant_path
    
    return None


def smart_sync(local_dir: Path, remote_dir: str, status=lambda s: None, conflict_resolver=None, output_cb=None):
    """Perform intelligent sync with conflict resolution.
    
    Args:
        local_dir: Local save directory
        remote_dir: Remote save directory path
        status: Status callback function
        conflict_resolver: Function to resolve conflicts, should return choice string
    """
    local_save = find_save_file(local_dir)
    remote_entry = remote_find_save(remote_dir)
    local_exists = local_save.exists()
    remote_exists = remote_entry is not None

    if not local_exists and not remote_exists:
        status("No saves yet. Initializing…")
        bisync(str(local_dir), remote_dir, resync=True, output_cb=output_cb)
        return "Initialized (no saves yet)."

    status("Creating backups…")
    lb = backup_local_dir(local_dir)
    rb = backup_remote_dir(remote_dir, output_cb=output_cb)

    equal = False
    if local_exists and remote_exists:
        try:
            r_hash = (remote_entry.get("Hashes") or {}).get("SHA-1")
            if r_hash:
                equal = (file_sha1(local_save) == r_hash)
            else:
                equal = (local_save.stat().st_size == int(remote_entry.get("Size", -1)))
        except Exception:
            equal = False

    if equal:
        status("Matching saves. Syncing…")
        bisync(str(local_dir), remote_dir, resync=False, output_cb=output_cb)
        return "Up to date."

    # Divergence detected - need to resolve conflict
    if conflict_resolver is None:
        # If no resolver provided, default to keeping local
        choice = "keep-local"
    else:
        preview = preview_text(local_save if local_exists else None, remote_entry if remote_exists else None)
        choice = conflict_resolver(preview)
        if choice is None:  # cancel
            return f"Canceled. Backups: local→{lb}, cloud→{rb}"

    if choice == "keep-local":
        status("Pushing this machine's save…")
        push_local_over_remote(local_dir, remote_dir, output_cb=output_cb)
    elif choice == "use-cloud":
        status("Pulling cloud save…")
        pull_remote_over_local(local_dir, remote_dir, output_cb=output_cb)
    elif choice == "keep-both":
        status("Keeping both (duplicating local)…")
        keep_both_variant(local_save if local_exists else None, platform.node())

    status("Finalizing sync…")
    bisync(str(local_dir), remote_dir, resync=False, output_cb=output_cb)
    return "Sync complete."