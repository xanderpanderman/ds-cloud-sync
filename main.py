#!/usr/bin/env python3
"""
DS2 Cloud Sync - Cross-platform GUI for syncing Dark Souls 2 saves using rclone.

Supports both Scholar of the First Sin and vanilla versions across Windows, macOS,
Linux, and SteamOS. Uses rclone bisync for bidirectional synchronization with
cloud storage providers.

Build standalone binary: pyinstaller -F main.py
"""

import sys
from tkinter import messagebox

from dscloudsync.config import load_config
from dscloudsync.save_detection import detect_save_root, pick_profile_dir
from dscloudsync.rclone_manager import ensure_rclone
from dscloudsync.sync_engine import smart_sync
from dscloudsync.utils import log


def cli_sync_mode() -> None:
    """Run sync in CLI mode for scheduled tasks."""
    cfg = load_config()
    
    if "remote" not in cfg:
        print("Cloud not configured. Run without --sync first.")
        sys.exit(1)
    
    ensure_rclone()
    
    local_root = detect_save_root()
    profile = pick_profile_dir(local_root)
    
    # Perform sync with status output to console
    msg = smart_sync(
        profile.resolve(),
        cfg["remote"],
        status=lambda s: print(s)
    )
    
    print(msg)


def main() -> None:
    """Main entry point."""
    if "--sync" in sys.argv:
        # CLI sync mode for scheduled runs
        try:
            cli_sync_mode()
        except Exception as e:
            log(f"CLI sync error: {e}")
            print(f"[error] {e}")
            sys.exit(1)
    else:
        # GUI mode
        try:
            from dscloudsync.gui.app import App
            app = App()
            app.mainloop()
        except KeyboardInterrupt:
            pass
        except Exception as e:
            log(f"Fatal error: {e}")
            print(f"Fatal Error: {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()