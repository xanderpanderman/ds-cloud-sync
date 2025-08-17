"""
DS2 Cloud Sync - Cross-platform GUI for syncing Dark Souls 2 saves using rclone.

Supports both Scholar of the First Sin and vanilla versions across Windows, macOS,
Linux, and SteamOS. Uses rclone bisync for bidirectional synchronization with
cloud storage providers.
"""

__version__ = "1.0.0"
__author__ = "DS2 Cloud Sync"

APPNAME = "ds2cloudsync"
APPID_SOTFS = "335300"  # Scholar of the First Sin
APPID_VANILLA = "236430"  # Vanilla
SAVE_BASENAMES = ["DS2SOFS0000.sl2", "DARKSII0000.sl2"]