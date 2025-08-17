"""GUI dialogs for DS2 Cloud Sync."""

import tkinter as tk
from tkinter import ttk, scrolledtext


class ConflictDialog(tk.Toplevel):
    """Dialog for resolving save conflicts."""
    
    result = None
    
    def __init__(self, master, preview_text: str):
        super().__init__(master)
        self.title("Resolve Saves")
        self.resizable(False, False)
        self.grab_set()
        
        frm = ttk.Frame(self, padding=12)
        frm.grid(row=0, column=0)
        
        ttk.Label(
            frm, 
            text="We found different saves. Choose what to keep:", 
            font=("Segoe UI", 10, "bold")
        ).grid(sticky="w")
        
        txt = tk.Text(frm, width=80, height=8, wrap="word")
        txt.insert("1.0", preview_text)
        txt.configure(state="disabled")
        txt.grid(pady=(8,8))
        
        btns = ttk.Frame(frm)
        btns.grid(sticky="ew")
        
        ttk.Button(
            btns, 
            text="Use this machine's save (recommended)", 
            command=lambda: self.done("keep-local")
        ).grid(row=0, column=0, padx=4, pady=4)
        
        ttk.Button(
            btns, 
            text="Use cloud save", 
            command=lambda: self.done("use-cloud")
        ).grid(row=0, column=1, padx=4, pady=4)
        
        ttk.Button(
            btns, 
            text="Keep both (safe copy)", 
            command=lambda: self.done("keep-both")
        ).grid(row=0, column=2, padx=4, pady=4)
        
        ttk.Button(
            btns, 
            text="Cancel", 
            command=lambda: self.done(None)
        ).grid(row=0, column=3, padx=4, pady=4)
        
        self.bind("<Escape>", lambda e: self.done(None))
        self.update_idletasks()
        self.geometry(f"+{master.winfo_rootx()+40}+{master.winfo_rooty()+40}")

    def done(self, val):
        """Close dialog with result."""
        ConflictDialog.result = val
        self.destroy()

    @staticmethod
    def ask(preview_text: str):
        """Show conflict dialog and return choice."""
        # Called from non-GUI code too; create a hidden root if needed
        root = tk._get_default_root()
        if root is None:
            root = tk.Tk()
            root.withdraw()
        
        dlg = ConflictDialog(root, preview_text)
        root.wait_window(dlg)
        return ConflictDialog.result


class CloudSetupDialog(tk.Toplevel):
    """User-friendly cloud provider setup dialog."""
    
    def __init__(self, master):
        super().__init__(master)
        self.title("Connect to Cloud Storage")
        self.geometry("600x600")
        self.resizable(True, True)
        
        self.result = None
        self.selected_provider = None
        
        # Make dialog modal
        self.transient(master)
        self.grab_set()
        
        # Center on parent
        self.update_idletasks()
        x = master.winfo_rootx() + (master.winfo_width() // 2) - (600 // 2)
        y = master.winfo_rooty() + (master.winfo_height() // 2) - (600 // 2)
        self.geometry(f"+{x}+{y}")
        
        self._create_ui()
    
    def _create_ui(self):
        """Create the setup wizard UI."""
        # Create main container with scrollable area if needed
        main_frame = ttk.Frame(self, padding=20)
        main_frame.pack(fill="both", expand=True)
        
        # Content frame for all widgets
        content_frame = ttk.Frame(main_frame)
        content_frame.pack(fill="both", expand=True)
        
        # Title
        title_label = ttk.Label(
            content_frame, 
            text="Choose Your Cloud Storage Provider"
        )
        # Configure title font
        try:
            title_label.configure(font=("", 14, "bold"))
        except:
            pass  # Fallback to default font if styling fails
        title_label.pack(pady=(0, 20))
        
        # Instructions
        instructions = ttk.Label(
            content_frame,
            text="DS2 Cloud Sync will automatically set up your chosen provider.\n"
                 "Your saves will be stored securely in your personal cloud storage.",
            justify="center"
        )
        instructions.pack(pady=(0, 20))
        
        # Provider selection frame
        provider_frame = ttk.LabelFrame(content_frame, text="Select Provider", padding=15)
        provider_frame.pack(fill="x", pady=(0, 20))
        
        self.provider_var = tk.StringVar(value="gdrive")
        
        # Popular cloud providers
        providers = [
            ("gdrive", "Google Drive", "Free 15GB, works great with DS2 saves"),
            ("onedrive", "Microsoft OneDrive", "Free 5GB, integrated with Windows"),
            ("dropbox", "Dropbox", "Free 2GB, reliable sync"),
            ("box", "Box", "Free 10GB, enterprise-grade security"),
        ]
        
        for value, name, description in providers:
            provider_frame_item = ttk.Frame(provider_frame)
            provider_frame_item.pack(fill="x", pady=5)
            
            # Simple radio button with text
            radio = ttk.Radiobutton(
                provider_frame_item,
                text=f"{name} - {description}",
                variable=self.provider_var,
                value=value
            )
            radio.pack(anchor="w")
        
        # Folder name setting
        folder_frame = ttk.LabelFrame(content_frame, text="Storage Location", padding=15)
        folder_frame.pack(fill="x", pady=(0, 20))
        
        ttk.Label(folder_frame, text="Folder name in your cloud storage:").pack(anchor="w")
        self.folder_var = tk.StringVar(value="GameSaves/DarkSouls2")
        folder_entry = ttk.Entry(folder_frame, textvariable=self.folder_var, width=40)
        folder_entry.pack(anchor="w", pady=(5, 0))
        
        # Privacy note - place before buttons
        privacy_label = ttk.Label(
            content_frame,
            text="🔒 Your login credentials are handled securely by rclone and never stored by this app.",
            font=("", 9),
            foreground="gray",
            justify="center"
        )
        privacy_label.pack(pady=(10, 20))
        
        # Button frame - always at bottom of main frame (not content frame)
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(side="bottom", fill="x", pady=(10, 0))
        
        ttk.Button(
            button_frame,
            text="Cancel",
            command=self._cancel
        ).pack(side="right", padx=(10, 0))
        
        ttk.Button(
            button_frame,
            text="Connect & Authenticate",
            command=self._connect
        ).pack(side="right")
    
    def _connect(self):
        """Handle connect button click."""
        self.selected_provider = self.provider_var.get()
        self.folder_path = self.folder_var.get().strip() or "GameSaves/DarkSouls2"
        self.result = "connect"
        self.destroy()
    
    def _cancel(self):
        """Handle cancel button click."""
        self.result = "cancel"
        self.destroy()
    
    @staticmethod
    def show(master):
        """Show the cloud setup dialog and return result."""
        dialog = CloudSetupDialog(master)
        master.wait_window(dialog)
        return dialog.result, getattr(dialog, 'selected_provider', None), getattr(dialog, 'folder_path', None)


class ProcessOutputDialog(tk.Toplevel):
    """Dialog showing real-time process output."""
    
    def __init__(self, master, title="Process Output"):
        super().__init__(master)
        self.title(title)
        self.geometry("800x600")
        self.resizable(True, True)
        
        # Create UI
        self._create_ui()
        
        # Make dialog modal but allow interaction
        self.transient(master)
        self.grab_set()
        
        # Center on parent
        self.update_idletasks()
        x = master.winfo_rootx() + (master.winfo_width() // 2) - (800 // 2)
        y = master.winfo_rooty() + (master.winfo_height() // 2) - (600 // 2)
        self.geometry(f"+{x}+{y}")
    
    def _create_ui(self):
        """Create the dialog UI."""
        main_frame = ttk.Frame(self, padding=10)
        main_frame.pack(fill="both", expand=True)
        
        # Status label
        self.status_label = ttk.Label(main_frame, text="Initializing...")
        self.status_label.pack(anchor="w", pady=(0, 5))
        
        # Output text area with scrollbar
        self.output_text = scrolledtext.ScrolledText(
            main_frame,
            wrap=tk.WORD,
            width=100,
            height=30,
            font=("Consolas", 10)
        )
        self.output_text.pack(fill="both", expand=True, pady=(0, 10))
        
        # Button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill="x")
        
        # Close button (initially disabled)
        self.close_btn = ttk.Button(
            button_frame, 
            text="Close", 
            command=self.destroy,
            state="disabled"
        )
        self.close_btn.pack(side="right")
        
        # Clear button
        self.clear_btn = ttk.Button(
            button_frame,
            text="Clear Output",
            command=self.clear_output
        )
        self.clear_btn.pack(side="right", padx=(0, 10))
        
        # Progress bar
        self.progress = ttk.Progressbar(
            button_frame,
            mode="indeterminate"
        )
        self.progress.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.progress.start()
    
    def set_status(self, status: str):
        """Update the status label."""
        self.status_label.config(text=status)
        self.update_idletasks()
    
    def append_output(self, text: str):
        """Append text to the output area."""
        self.output_text.insert(tk.END, text)
        self.output_text.see(tk.END)
        self.update_idletasks()
    
    def clear_output(self):
        """Clear the output text area."""
        self.output_text.delete(1.0, tk.END)
    
    def operation_complete(self, success: bool = True):
        """Called when the operation is complete."""
        self.progress.stop()
        self.progress.pack_forget()
        self.close_btn.config(state="normal")
        
        if success:
            self.set_status("Operation completed successfully!")
        else:
            self.set_status("Operation failed - check output above")
    
    def operation_failed(self, error_msg: str):
        """Called when the operation fails."""
        self.append_output(f"\n[ERROR] {error_msg}\n")
        self.operation_complete(success=False)