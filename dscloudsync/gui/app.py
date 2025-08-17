"""Main application GUI for DS2 Cloud Sync."""

import os
import platform
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path

from ..config import load_config, save_config
from ..save_detection import detect_save_root, pick_profile_dir, find_save_file, check_ds2_installation
from ..rclone_manager import ensure_rclone, RCLONE_BIN, bisync, list_existing_remotes, test_remote_connection
from ..sync_engine import smart_sync, preview_text, remote_find_save
from ..autostart import install_autostart, uninstall_autostart
from ..utils import LOG_FILE
from .dialogs import ConflictDialog, ProcessOutputDialog, CloudSetupDialog


class App(tk.Tk):
    """Main application window."""
    
    def __init__(self):
        super().__init__()
        self.title("DS2 Cloud Sync")
        self.minsize(520, 300)
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        
        # Load configuration and check DS2 installation
        self.cfg = load_config()
        self.ds2_status = check_ds2_installation()
        
        # Set up save locations (create directories as needed for sync)
        if self.ds2_status['save_root']:
            self.local_root = self.ds2_status['save_root']
            self.profile = pick_profile_dir(self.local_root)
            self.local_dir = self.profile.resolve()
        else:
            # Fallback if detection failed
            self.local_root = detect_save_root()
            self.profile = pick_profile_dir(self.local_root)
            self.local_dir = self.profile.resolve()
        
        # Initialize UI variables
        self.status_var = tk.StringVar(value=self.ds2_status['message'])
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
        
        # DS2 Status indicator
        ds2_status_frame = ttk.Frame(main)
        ds2_status_frame.grid(row=0, column=0, columnspan=4, sticky="we", pady=(0, 10))
        
        status_icon = "🎮" if self.ds2_status['installed'] else "❓"
        self._ds2_status_label = ttk.Label(ds2_status_frame, text=f"{status_icon} {self.ds2_status['message']}")
        self._ds2_status_label.pack(side="left")
        
        # Save folder display
        ttk.Label(main, text="Save folder:").grid(row=1, column=0, sticky="w")
        ttk.Entry(
            main, textvariable=self.path_var, state="readonly", width=70
        ).grid(row=1, column=1, columnspan=3, sticky="we", pady=2)
        
        # Cloud remote configuration
        ttk.Label(main, text="Cloud remote:").grid(row=2, column=0, sticky="w")
        ttk.Entry(
            main, textvariable=self.remote_var, state="readonly", width=50
        ).grid(row=2, column=1, sticky="we", pady=2)
        ttk.Button(
            main, text="Connect...", command=self.on_connect
        ).grid(row=2, column=2, sticky="w", padx=6)
        
        ttk.Separator(main).grid(row=3, column=0, columnspan=4, sticky="we", pady=8)
        
        # Action buttons
        ttk.Button(
            main, text="Sync now", command=self.on_sync, width=20
        ).grid(row=4, column=0, pady=4, sticky="w")
        ttk.Button(
            main, text="Preview", command=self.on_preview
        ).grid(row=4, column=1, pady=4, sticky="w")
        ttk.Button(
            main, text="Open log", command=self.on_open_log
        ).grid(row=4, column=2, pady=4, sticky="w")
        
        # Auto-start checkbox
        ttk.Checkbutton(
            main, text="Sync automatically at login",
            variable=self.auto_var,
            command=self.on_toggle_autostart
        ).grid(row=5, column=0, columnspan=2, sticky="w", pady=(8, 4))
        
        ttk.Separator(main).grid(row=6, column=0, columnspan=4, sticky="we", pady=8)
        
        # Status label
        ttk.Label(
            main, textvariable=self.status_var
        ).grid(row=7, column=0, columnspan=4, sticky="w")
        
        # Configure column weights
        for i in range(4):
            main.columnconfigure(i, weight=1)
    
    def refresh_ds2_status(self):
        """Refresh DS2 installation status display."""
        self.ds2_status = check_ds2_installation()
        
        # Update the status in the UI if it's been created
        if hasattr(self, '_ds2_status_label'):
            status_icon = "🎮" if self.ds2_status['installed'] else "❓"
            self._ds2_status_label.config(text=f"{status_icon} {self.ds2_status['message']}")
        
        # Update status bar if DS2 status changed
        if not self.ds2_status['installed']:
            self.set_status(f"{self.ds2_status['message']} - Cloud sync ready when you install DS2")
        elif not self.ds2_status['has_saves']:
            self.set_status(f"{self.ds2_status['message']} - Cloud sync ready when you start playing")
        else:
            self.set_status("Ready to sync Dark Souls 2 saves")

    def set_status(self, msg: str) -> None:
        """Update status message in UI."""
        self.status_var.set(msg)
        self.update_idletasks()

    def startup(self) -> None:
        """Perform startup tasks: ensure rclone, configure remote, initial sync."""
        
        def run_startup():
            """Run startup tasks in background thread."""
            try:
                # Show process dialog for startup
                if not RCLONE_BIN.exists():
                    startup_dialog = ProcessOutputDialog(self, "Setting up DS2 Cloud Sync")
                    
                    def status_update(msg):
                        self.after(0, lambda: startup_dialog.set_status(msg))
                    
                    def output_callback(text):
                        self.after(0, lambda: startup_dialog.append_output(text))
                    
                    self.after(0, lambda: self.set_status("Downloading rclone..."))
                    ensure_rclone(status_update, output_callback)
                    self.after(0, lambda: startup_dialog.operation_complete(True))
                else:
                    self.after(0, lambda: self.set_status("Checking rclone..."))
                    ensure_rclone(self.set_status)
                
                # Check for existing rclone remotes before showing first-run wizard
                if "remote" not in self.cfg:
                    existing_remotes = list_existing_remotes()
                    if existing_remotes:
                        # Test and configure first available remote
                        remote_name = existing_remotes[0]
                        self.after(0, lambda: self.set_status(f"Testing {remote_name} connection..."))
                        
                        # Test the connection and refresh token if needed
                        if test_remote_connection(remote_name, lambda msg: self.after(0, lambda: self.set_status(msg.strip()))):
                            remote_config = f"{remote_name}:ds2cloudsync"
                            self.cfg["remote"] = remote_config
                            self.after(0, lambda: self.remote_var.set(remote_config))
                            save_config(self.cfg)
                            self.after(0, lambda: self.set_status(f"Connected to {remote_name}"))
                        else:
                            self.after(0, lambda: self.set_status(f"Failed to connect to {remote_name}"))
                            self.after(0, self._show_first_run_wizard)
                            return
                    else:
                        self.after(0, self._show_first_run_wizard)
                        return
                
                # Perform one-time resync for this host
                host = platform.node()
                resynced = self.cfg.get("resynced_hosts", {}).get(host, False)
                
                if not resynced and "remote" in self.cfg:
                    # Show process dialog for initial sync
                    init_dialog = ProcessOutputDialog(self, "Initializing Device")
                    
                    def status_update(msg):
                        self.after(0, lambda: init_dialog.set_status(msg))
                    
                    def output_callback(text):
                        self.after(0, lambda: init_dialog.append_output(text))
                    
                    try:
                        self.after(0, lambda: self.set_status("Initializing this device (one-time)..."))
                        bisync(str(self.local_dir), self.cfg["remote"], resync=True, output_cb=output_callback)
                        
                        # Mark host as resynced
                        self.cfg.setdefault("resynced_hosts", {})[host] = True
                        save_config(self.cfg)
                        
                        self.after(0, lambda: init_dialog.operation_complete(True))
                    except Exception as e:
                        error_msg = str(e)
                        self.after(0, lambda: init_dialog.operation_failed(error_msg))
                        self.after(0, lambda: messagebox.showwarning("Initial sync", f"Initial sync failed:\n{error_msg}"))
                
                self.after(0, lambda: self.set_status("Ready."))
                
            except Exception as e:
                error_msg = str(e)
                self.after(0, lambda: messagebox.showerror("Startup error", error_msg))
        
        # Run startup in background thread
        startup_thread = threading.Thread(target=run_startup, daemon=True)
        startup_thread.start()
    
    def _show_first_run_wizard(self):
        """Show first-run wizard on main thread."""
        # Automatically start the connection wizard for first-time users
        if messagebox.askyesno(
            "Welcome to DS2 Cloud Sync",
            "Welcome! Let's set up cloud sync for your Dark Souls 2 saves.\n\n"
            "This will:\n"
            "• Connect to your preferred cloud storage\n"
            "• Automatically sync your saves across devices\n"
            "• Keep backups of your progress\n\n"
            "Would you like to set up cloud sync now?"
        ):
            # Automatically launch the connect wizard
            self.after(100, self.connect_wizard)
        else:
            self.set_status("Ready. Click 'Connect...' when you want to set up cloud storage.")

    def on_connect(self) -> None:
        """Handle Connect button click."""
        self.connect_wizard()

    def connect_wizard(self) -> bool:
        """Show simplified cloud connection wizard."""
        # Show the user-friendly cloud setup dialog
        result, provider, folder_path = CloudSetupDialog.show(self)
        
        if result != "connect" or not provider:
            return False
        
        # Show setup progress in main window
        self.set_status(f"Connecting to {provider.title()}...")
        
        def run_setup():
            """Run cloud setup in background thread."""
            try:
                def status_update(msg):
                    self.after(0, lambda m=msg: self.set_status(m))
                
                def output_callback(text):
                    # Just update status with key messages, not all output
                    if "Starting authentication" in text or "Successfully set up" in text or "Setup failed" in text:
                        self.after(0, lambda m=text.strip(): self.set_status(m))
                
                # Import the setup function
                from ..rclone_manager import setup_cloud_provider_simple
                
                # Use provider name as remote name for simplicity
                remote_name = provider
                
                success = setup_cloud_provider_simple(
                    provider, remote_name, output_callback
                )
                
                if success:
                    # Save remote configuration
                    remote_config = f"{remote_name}:{folder_path}"
                    self.cfg["remote"] = remote_config
                    self.remote_var.set(remote_config)
                    save_config(self.cfg)
                    
                    self.after(0, lambda: self._setup_complete_simple(True))
                else:
                    self.after(0, lambda: self._setup_complete_simple(False))
                    
            except Exception as e:
                from ..utils import log
                error_msg = str(e)
                log(f"Setup error: {error_msg}")
                self.after(0, lambda: self._setup_complete_simple(False, error_msg))
        
        # Start setup in background thread
        setup_thread = threading.Thread(target=run_setup, daemon=True)
        setup_thread.start()
        
        return True  # Don't wait, let it complete in background
    
    def _setup_complete_simple(self, success: bool, error_msg: str = ""):
        """Handle setup completion in main window."""
        if success:
            # Update DS2 status and main window
            self.ds2_status = check_ds2_installation()
            
            # Show success message
            messagebox.showinfo(
                "Setup Complete", 
                f"✅ Cloud storage connected successfully!\n\n"
                f"📁 {self.ds2_status['message']}\n\n"
                f"Your saves will sync automatically when you play Dark Souls 2."
            )
            self.set_status("Ready. Cloud storage connected.")
        else:
            # Show error message
            error_text = f"❌ Could not connect to cloud storage."
            if error_msg:
                error_text += f"\n\nError: {error_msg}"
            messagebox.showerror("Setup Failed", error_text)
            self.set_status("Setup failed. Click Connect to retry.")
    
    def _setup_complete(self, dialog: ProcessOutputDialog, success: bool):
        """Handle setup completion."""
        dialog._success = success
        dialog.operation_complete(success)
        
        if success:
            # Auto-close dialog after 2 seconds and show success message
            self.after(2000, dialog.destroy)
            
            # Update DS2 status and main window
            self.ds2_status = check_ds2_installation()
            
            # Show success message
            messagebox.showinfo(
                "Setup Complete", 
                f"✅ Cloud storage connected successfully!\n\n"
                f"📁 {self.ds2_status['message']}\n\n"
                f"Your saves will sync automatically when you play Dark Souls 2."
            )
            self.set_status("Ready. Cloud storage connected.")
        else:
            # Keep dialog open on failure so user can see error details
            messagebox.showerror(
                "Setup Failed",
                "❌ Could not connect to cloud storage.\n\n"
                "Check the process output above for details.\n"
                "You can close this window and try again."
            )
            self.set_status("Setup failed. Click Connect to retry.")
    
    def _setup_failed(self, dialog: ProcessOutputDialog, error_msg: str):
        """Handle setup failure."""
        dialog.operation_failed(error_msg)
        dialog._success = False

    def on_sync(self) -> None:
        """Handle Sync button click."""
        if "remote" not in self.cfg:
            messagebox.showwarning(
                "Not connected",
                "Click Connect to set up your cloud first."
            )
            return
        
        # Show sync progress in main window
        self.set_status("Syncing...")
        
        def run_sync():
            """Run sync in background thread."""
            try:
                def status_update(msg):
                    self.after(0, lambda m=msg: self.set_status(m))
                
                def output_callback(text):
                    # Update status with key sync messages
                    if any(keyword in text for keyword in ["Syncing", "Creating backups", "Complete", "Error"]):
                        self.after(0, lambda m=text.strip(): self.set_status(m))
                
                msg = smart_sync(
                    self.local_dir,
                    self.cfg["remote"],
                    status=status_update,
                    conflict_resolver=ConflictDialog.ask,
                    output_cb=output_callback
                )
                
                # Update UI on main thread
                self.after(0, lambda m=msg: self._sync_complete_simple(m, True))
                
            except Exception as e:
                from ..utils import log
                error_msg = str(e)
                log(f"Sync error: {error_msg}")
                self.after(0, lambda m=error_msg: self._sync_complete_simple(m, False))
        
        # Start sync in background thread
        sync_thread = threading.Thread(target=run_sync, daemon=True)
        sync_thread.start()
    
    def _sync_complete_simple(self, message: str, success: bool):
        """Handle sync completion in main window."""
        self.set_status(message if success else "Error.")
        
        if success:
            messagebox.showinfo("Sync Complete", message)
        else:
            messagebox.showerror("Sync Error", message)
    
    def _sync_complete(self, dialog: ProcessOutputDialog, message: str, success: bool):
        """Handle sync completion on main thread."""
        dialog.operation_complete(success)
        self.set_status(message if success else "Error.")
        
        if success:
            messagebox.showinfo("Sync", message)
        else:
            messagebox.showerror("Sync error", message)

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