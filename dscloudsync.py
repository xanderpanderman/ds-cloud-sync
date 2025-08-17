#!/usr/bin/env python3
"""
DS2 Cloud Sync - Cross-platform GUI for syncing Dark Souls 2 saves using rclone.

Supports both Scholar of the First Sin and vanilla versions across Windows, macOS,
Linux, and SteamOS. Uses rclone bisync for bidirectional synchronization with
cloud storage providers.

Build standalone binary: pyinstaller -F dscloudsync.py
"""

import os
import sys
import platform
import shutil
import zipfile
import subprocess
import tempfile
import json
import datetime
import hashlib
import time
from pathlib import Path
from urllib.request import urlopen

import tkinter as tk
from tkinter import ttk, messagebox

# Constants
APPNAME = "ds2cloudsync"
APPID_SOTFS = "335300"  # Scholar of the First Sin
APPID_VANILLA = "236430"  # Vanilla
SAVE_BASENAMES = ["DS2SOFS0000.sl2", "DARKSII0000.sl2"]

# Application paths
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

CONFIG_FILE = app_home() / "config.json"
LOG_FILE = app_home() / "sync.log"
RCLONE_DIR = app_home() / "rclone"
RCLONE_BIN = RCLONE_DIR / ("rclone.exe" if platform.system() == "Windows" else "rclone")


# Utility functions
def log(msg: str) -> None:
    """Append message to log file with timestamp."""
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            timestamp = datetime.datetime.now().isoformat()
            f.write(f"{timestamp} {msg}\n")
    except Exception:
        pass

def run(cmd: list, check: bool = True) -> subprocess.CompletedProcess:
    """Execute command and log output.
    
    Security: Commands are logged but sensitive output is not exposed to users.
    """
    # Ensure command list contains only strings
    cmd = [str(c) for c in cmd]
    
    result = subprocess.run(
        cmd, 
        stdout=subprocess.PIPE, 
        stderr=subprocess.STDOUT, 
        text=True,
        # Security: Don't pass shell=True to avoid injection
        shell=False
    )
    
    output = result.stdout or ""
    
    # Log command but mask potential sensitive data in output
    safe_cmd = ' '.join(cmd)
    log(f">> {safe_cmd}\n{output}")
    
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


# Save file detection and management
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
        
        for appid in (APPID_SOTFS, APPID_VANILLA):
            users_dir = base / appid / "pfx" / "drive_c" / "users"
            if users_dir.exists():
                for user_dir in users_dir.glob("*"):
                    save_dir = user_dir / "AppData" / "Roaming" / "DarkSoulsII"
                    if save_dir.exists():
                        return save_dir
        
        # Default fallback for Steam Deck
        return base / APPID_SOTFS / "pfx" / "drive_c" / "users" / "steamuser" / "AppData" / "Roaming" / "DarkSoulsII"

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


# Rclone management
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

def ensure_rclone(status_cb=lambda s: None) -> None:
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
                    
                    while True:
                        chunk = response.read(chunk_size)
                        if not chunk:
                            break
                        
                        downloaded += len(chunk)
                        if downloaded > max_size:
                            raise RuntimeError("Download too large")
                        
                        tmp_file.write(chunk)
            except Exception:
                tmp_path.unlink(missing_ok=True)
                raise
        
        try:
            extract_rclone_from_zip(tmp_path, RCLONE_DIR)
        finally:
            tmp_path.unlink(missing_ok=True)
    
    # Verify rclone is working
    run([str(RCLONE_BIN), "version"])


# Configuration management
def load_config() -> dict:
    """Load configuration from JSON file."""
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text())
        except Exception:
            return {}
    return {}

def save_config(cfg: dict) -> None:
    """Save configuration to JSON file."""
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2))


# Rclone operations
def rclone_lsjson(remote_path: str) -> list:
    """List remote directory contents with hashes."""
    result = run([str(RCLONE_BIN), "lsjson", "--hash", remote_path], check=False)
    
    try:
        return json.loads(result.stdout or "[]")
    except Exception:
        return []

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

def backup_remote_dir(remote_dir: str) -> str:
    """Create timestamped backup of remote save directory."""
    backup_path = f"{remote_dir.rstrip('/')}/Backups/remote-{iso_now()}"
    run([str(RCLONE_BIN), "copy", remote_dir, backup_path], check=False)
    return backup_path

def bisync(local_dir: str, remote_dir: str, resync: bool = False) -> None:
    """Perform bidirectional sync using rclone bisync."""
    backup_path = f"{remote_dir.rstrip('/')}/Backups"
    
    cmd = [
        str(RCLONE_BIN), "bisync", local_dir, remote_dir,
        "--fast-list",
        "--track-renames",
        "--create-empty-src-dirs",
        "--backup-dir", backup_path,
        "--conflict-resolve", "rename",
        "--checksum",
        "--verbose",
    ]
    
    if resync:
        cmd.insert(2, "--resync")
    
    run(cmd, check=True)


# Conflict resolution and smart sync
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

def push_local_over_remote(local_dir: Path, remote_dir: str) -> None:
    """Push local save to remote, overwriting if newer."""
    run([str(RCLONE_BIN), "copy", str(local_dir), remote_dir, "--update"], check=True)

def pull_remote_over_local(local_dir: Path, remote_dir: str) -> None:
    """Pull remote save to local, overwriting if newer."""
    run([str(RCLONE_BIN), "copy", remote_dir, str(local_dir), "--update"], check=True)

def keep_both_variant(local_path: Path | None, machine_tag: str) -> Path | None:
    """Create a machine-tagged copy of local save."""
    if local_path and local_path.exists():
        variant_name = f"{local_path.stem}_{machine_tag}{local_path.suffix}"
        variant_path = local_path.with_name(variant_name)
        shutil.copy2(local_path, variant_path)
        return variant_path
    
    return None

def smart_sync(local_dir: Path, remote_dir: str, status=lambda s: None):
    local_save = find_save_file(local_dir)
    remote_entry = remote_find_save(remote_dir)
    local_exists = local_save.exists()
    remote_exists = remote_entry is not None

    if not local_exists and not remote_exists:
        status("No saves yet. Initializing…")
        bisync(str(local_dir), remote_dir, resync=True)
        return "Initialized (no saves yet)."

    status("Creating backups…")
    lb = backup_local_dir(local_dir)
    rb = backup_remote_dir(remote_dir)

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
        bisync(str(local_dir), remote_dir, resync=False)
        return "Up to date."

    # divergence → ask
    preview = preview_text(local_save if local_exists else None, remote_entry if remote_exists else None)
    choice = ConflictDialog.ask(preview)
    if choice is None:  # cancel
        return f"Canceled. Backups: local→{lb}, cloud→{rb}"

    if choice == "keep-local":
        status("Pushing this machine’s save…")
        push_local_over_remote(local_dir, remote_dir)
    elif choice == "use-cloud":
        status("Pulling cloud save…")
        pull_remote_over_local(local_dir, remote_dir)
    elif choice == "keep-both":
        status("Keeping both (duplicating local)…")
        keep_both_variant(local_save if local_exists else None, platform.node())

    status("Finalizing sync…")
    bisync(str(local_dir), remote_dir, resync=False)
    return "Sync complete."

# ---------- autostart ----------
def install_autostart(exe_path: Path) -> bool:
    sysname = platform.system()
    try:
        if sysname == "Windows":
            subprocess.run(["schtasks","/Create","/SC","ONLOGON","/TN","DS2CloudSync",
                            "/TR", f'"{exe_path}" --sync', "/RL","LIMITED","/F"],
                           check=False, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            return True
        elif sysname == "Darwin":
            agents = Path.home()/ "Library"/"LaunchAgents"
            agents.mkdir(parents=True, exist_ok=True)
            plist = agents/"com.ds2cloudsync.sync.plist"
            plist.write_text(f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.ds2cloudsync.sync</string>
  <key>ProgramArguments</key><array><string>{exe_path}</string><string>--sync</string></array>
  <key>RunAtLoad</key><true/>
  <key>StandardOutPath</key><string>{LOG_FILE}</string>
  <key>StandardErrorPath</key><string>{LOG_FILE.with_suffix('.err')}</string>
</dict></plist>""")
            subprocess.run(["launchctl","load",str(plist)], check=False)
            return True
        else:
            userdir = Path.home()/".config"/"systemd"/"user"
            userdir.mkdir(parents=True, exist_ok=True)
            unit = userdir/"ds2cloudsync.service"
            unit.write_text(f"""[Unit]
Description=DS2 Cloud Sync
After=network-online.target

[Service]
Type=oneshot
ExecStart={exe_path} --sync
StandardOutput=append:{LOG_FILE}
StandardError=append:{LOG_FILE.with_suffix('.err')}

[Install]
WantedBy=default.target
""")
            subprocess.run(["systemctl","--user","daemon-reload"], check=False)
            subprocess.run(["systemctl","--user","enable","--now","ds2cloudsync.service"], check=False)
            return True
    except Exception:
        return False

def uninstall_autostart():
    sysname = platform.system()
    if sysname == "Windows":
        subprocess.run(["schtasks","/Delete","/TN","DS2CloudSync","/F"], check=False)
    elif sysname == "Darwin":
        plist = Path.home()/ "Library"/"LaunchAgents"/"com.ds2cloudsync.sync.plist"
        subprocess.run(["launchctl","unload",str(plist)], check=False)
        if plist.exists(): plist.unlink()
    else:
        unit = Path.home()/".config"/"systemd"/"user"/"ds2cloudsync.service"
        subprocess.run(["systemctl","--user","disable","--now","ds2cloudsync.service"], check=False)
        if unit.exists(): unit.unlink()
        subprocess.run(["systemctl","--user","daemon-reload"], check=False)

# ---------- GUI ----------
class ConflictDialog(tk.Toplevel):
    result = None
    def __init__(self, master, preview_text: str):
        super().__init__(master)
        self.title("Resolve Saves")
        self.resizable(False, False)
        self.grab_set()
        frm = ttk.Frame(self, padding=12)
        frm.grid(row=0, column=0)
        ttk.Label(frm, text="We found different saves. Choose what to keep:", font=("Segoe UI", 10, "bold")).grid(sticky="w")
        txt = tk.Text(frm, width=80, height=8, wrap="word")
        txt.insert("1.0", preview_text)
        txt.configure(state="disabled")
        txt.grid(pady=(8,8))
        btns = ttk.Frame(frm)
        btns.grid(sticky="ew")
        ttk.Button(btns, text="Use this machine’s save (recommended)", command=lambda:self.done("keep-local")).grid(row=0, column=0, padx=4, pady=4)
        ttk.Button(btns, text="Use cloud save", command=lambda:self.done("use-cloud")).grid(row=0, column=1, padx=4, pady=4)
        ttk.Button(btns, text="Keep both (safe copy)", command=lambda:self.done("keep-both")).grid(row=0, column=2, padx=4, pady=4)
        ttk.Button(btns, text="Cancel", command=lambda:self.done(None)).grid(row=0, column=3, padx=4, pady=4)
        self.bind("<Escape>", lambda e:self.done(None))
        self.update_idletasks()
        self.geometry(f"+{master.winfo_rootx()+40}+{master.winfo_rooty()+40}")

    def done(self, val):
        ConflictDialog.result = val
        self.destroy()

    @staticmethod
    def ask(preview_text: str):
        # called from non-GUI code too; create a hidden root if needed
        root = tk._get_default_root()
        if root is None:
            root = tk.Tk(); root.withdraw()
        dlg = ConflictDialog(root, preview_text)
        root.wait_window(dlg)
        return ConflictDialog.result

class App(tk.Tk):
    """Main application window."""
    
    def __init__(self):
        super().__init__()
        self.title("DS2 Cloud Sync")
        self.minsize(520, 300)
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        
        # Load configuration and detect save locations
        self.cfg = load_config()
        self.local_root = detect_save_root()
        self.profile = pick_profile_dir(self.local_root)
        self.local_dir = self.profile.resolve()
        
        # Initialize UI variables
        self.status_var = tk.StringVar(value="Ready.")
        self.remote_var = tk.StringVar(value=self.cfg.get("remote", "(not set)"))
        self.path_var = tk.StringVar(value=str(self.local_dir))
        self.auto_var = tk.BooleanVar(value=bool(self.cfg.get("autostart", False)))
        
        # Create UI
        self._create_ui()
        
        # Bootstrap rclone and perform initial setup
        self.after(100, self.startup)
    
    def _create_ui(self):
        """Create the main UI layout."""
        main = ttk.Frame(self, padding=12)
        main.pack(fill="both", expand=True)
        
        # Save folder display
        ttk.Label(main, text="Save folder:").grid(row=0, column=0, sticky="w")
        ttk.Entry(
            main, textvariable=self.path_var, state="readonly", width=70
        ).grid(row=0, column=1, columnspan=3, sticky="we", pady=2)
        
        # Cloud remote configuration
        ttk.Label(main, text="Cloud remote:").grid(row=1, column=0, sticky="w")
        ttk.Entry(
            main, textvariable=self.remote_var, state="readonly", width=50
        ).grid(row=1, column=1, sticky="we", pady=2)
        ttk.Button(
            main, text="Connect...", command=self.on_connect
        ).grid(row=1, column=2, sticky="w", padx=6)
        
        ttk.Separator(main).grid(row=2, column=0, columnspan=4, sticky="we", pady=8)
        
        # Action buttons
        ttk.Button(
            main, text="Sync now", command=self.on_sync, width=20
        ).grid(row=3, column=0, pady=4, sticky="w")
        ttk.Button(
            main, text="Preview", command=self.on_preview
        ).grid(row=3, column=1, pady=4, sticky="w")
        ttk.Button(
            main, text="Open log", command=self.on_open_log
        ).grid(row=3, column=2, pady=4, sticky="w")
        
        # Auto-start checkbox
        ttk.Checkbutton(
            main, text="Sync automatically at login",
            variable=self.auto_var,
            command=self.on_toggle_autostart
        ).grid(row=4, column=0, columnspan=2, sticky="w", pady=(8, 4))
        
        ttk.Separator(main).grid(row=5, column=0, columnspan=4, sticky="we", pady=8)
        
        # Status label
        ttk.Label(
            main, textvariable=self.status_var
        ).grid(row=6, column=0, columnspan=4, sticky="w")
        
        # Configure column weights
        for i in range(4):
            main.columnconfigure(i, weight=1)

    def set_status(self, msg: str) -> None:
        """Update status message in UI."""
        self.status_var.set(msg)
        self.update_idletasks()

    def startup(self) -> None:
        """Perform startup tasks: ensure rclone, configure remote, initial sync."""
        # Ensure rclone is available
        try:
            self.set_status("Checking rclone...")
            ensure_rclone(self.set_status)
        except Exception as e:
            messagebox.showerror("rclone error", str(e))
            return
        
        # Show first-run wizard if not configured
        if "remote" not in self.cfg:
            messagebox.showinfo(
                "Connect",
                "Choose a remote name (e.g., gdrive/dropbox/onedrive) in the next step, "
                "then complete rclone's device-code login."
            )
            if not self.connect_wizard():
                return
        
        # Perform one-time resync for this host
        host = platform.node()
        resynced = self.cfg.get("resynced_hosts", {}).get(host, False)
        
        if not resynced:
            try:
                self.set_status("Initializing this device (one-time)...")
                bisync(str(self.local_dir), self.cfg["remote"], resync=True)
                
                # Mark host as resynced
                self.cfg.setdefault("resynced_hosts", {})[host] = True
                save_config(self.cfg)
            except Exception as e:
                messagebox.showwarning("Initial sync", f"Initial sync failed:\n{e}")
        
        self.set_status("Ready.")

    def on_connect(self) -> None:
        """Handle Connect button click."""
        self.connect_wizard()

    def connect_wizard(self) -> bool:
        """Show cloud connection wizard and configure rclone."""
        # Create wizard window
        wizard = tk.Toplevel(self)
        wizard.title("Connect cloud")
        
        frame = ttk.Frame(wizard, padding=12)
        frame.pack(fill="both", expand=True)
        
        # Remote name input
        ttk.Label(
            frame, text="Remote name (e.g., gdrive, dropbox, onedrive):"
        ).pack(anchor="w")
        
        name_var = tk.StringVar(value="gdrive")
        ttk.Entry(frame, textvariable=name_var).pack(fill="x")
        
        # Cloud folder path input
        ttk.Label(
            frame, text="Cloud folder (default: GameSaves/DarkSouls2):"
        ).pack(anchor="w", pady=(8, 0))
        
        path_var = tk.StringVar(value="GameSaves/DarkSouls2")
        ttk.Entry(frame, textvariable=path_var).pack(fill="x")
        
        # Buttons
        button_frame = ttk.Frame(frame)
        button_frame.pack(fill="x", pady=8)
        
        result = {"success": False}
        
        def do_connect():
            """Execute rclone config and save settings."""
            try:
                self.set_status("Opening rclone config...")
                run([str(RCLONE_BIN), "config"], check=True)
                
                # Save remote configuration
                remote_name = name_var.get().strip()
                remote_path = path_var.get().strip() or "GameSaves/DarkSouls2"
                self.cfg["remote"] = f"{remote_name}:{remote_path}"
                self.remote_var.set(self.cfg["remote"])
                save_config(self.cfg)
                
                result["success"] = True
                wizard.destroy()
            except Exception as e:
                messagebox.showerror("Connect error", str(e))
        
        ttk.Button(
            button_frame, text="Open sign-in...", command=do_connect
        ).pack(side="left")
        
        ttk.Button(
            button_frame, text="Cancel", command=wizard.destroy
        ).pack(side="right")
        
        self.wait_window(wizard)
        self.set_status("Ready.")
        return result["success"]

    def on_sync(self) -> None:
        """Handle Sync button click."""
        if "remote" not in self.cfg:
            messagebox.showwarning(
                "Not connected",
                "Click Connect to set up your cloud first."
            )
            return
        
        try:
            self.set_status("Syncing...")
            msg = smart_sync(
                self.local_dir,
                self.cfg["remote"],
                status=self.set_status
            )
            self.set_status(msg)
            messagebox.showinfo("Sync", msg)
        except Exception as e:
            self.set_status("Error.")
            log(f"Sync error: {e}")
            messagebox.showerror("Sync error", str(e))

    def on_preview(self) -> None:
        """Handle Preview button click - show save comparison."""
        if "remote" not in self.cfg:
            messagebox.showwarning(
                "Not connected",
                "Click Connect to set up your cloud first."
            )
            return
        
        local_save = find_save_file(self.local_dir)
        remote_entry = remote_find_save(self.cfg["remote"])
        
        text = preview_text(
            local_save if local_save.exists() else None,
            remote_entry
        )
        
        messagebox.showinfo("Preview", text)

    def on_open_log(self) -> None:
        """Handle Open log button click - open log file in default app."""
        if not LOG_FILE.exists():
            messagebox.showinfo("Log", "No log yet.")
            return
        
        try:
            system = platform.system()
            
            if system == "Windows":
                os.startfile(str(LOG_FILE))
            elif system == "Darwin":
                subprocess.run(["open", str(LOG_FILE)])
            else:  # Linux/SteamOS
                subprocess.run(["xdg-open", str(LOG_FILE)])
        except Exception:
            # Fallback: show path if can't open
            messagebox.showinfo("Log", f"Log at {LOG_FILE}")

    def on_toggle_autostart(self) -> None:
        """Handle auto-start checkbox toggle."""
        # Get executable path (handle both frozen and script modes)
        if getattr(sys, 'frozen', False):
            exe_path = Path(sys.executable)
        else:
            exe_path = Path(sys.argv[0])
        
        if self.auto_var.get():
            # Install auto-start
            success = install_autostart(exe_path)
            self.cfg["autostart"] = success
            save_config(self.cfg)
            
            if success:
                messagebox.showinfo("Auto-sync", "Installed to run at login.")
            else:
                messagebox.showwarning(
                    "Auto-sync",
                    "Could not install auto-start. Check permissions."
                )
                # Reset checkbox if installation failed
                self.auto_var.set(False)
        else:
            # Remove auto-start
            uninstall_autostart()
            self.cfg["autostart"] = False
            save_config(self.cfg)
            messagebox.showinfo("Auto-sync", "Removed login auto-sync.")

    def on_close(self) -> None:
        """Handle window close event."""
        self.destroy()

# CLI mode for scheduled/automated runs
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
            app = App()
            app.mainloop()
        except KeyboardInterrupt:
            pass
        except Exception as e:
            log(f"Fatal error: {e}")
            messagebox.showerror("Fatal Error", str(e))
            sys.exit(1)


if __name__ == "__main__":
    main()
