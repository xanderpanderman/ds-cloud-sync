"""Platform-specific autostart functionality."""

import platform
import subprocess
from pathlib import Path

from .utils import LOG_FILE


def install_autostart(exe_path: Path) -> bool:
    """Install platform-specific autostart configuration."""
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
    """Remove platform-specific autostart configuration."""
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