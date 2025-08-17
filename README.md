# DS2 Cloud Sync

A cross-platform GUI application for syncing Dark Souls 2 saves (both Scholar of the First Sin and vanilla) between Windows, macOS, Linux, and SteamOS devices using cloud storage providers.

![Platform Support](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux%20%7C%20Steam%20Deck-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Python](https://img.shields.io/badge/python-3.8%2B-blue)

## Features

- **Universal Save Sync**: Works with both Scholar of the First Sin and vanilla Dark Souls 2
- **Multiple Cloud Providers**: Google Drive, OneDrive, Dropbox, Box
- **Cross-Platform**: Windows (native), Steam Deck/Linux (Proton), macOS (via compatibility layers)
- **Automatic Sync**: Set up once, syncs automatically when you play
- **Conflict Resolution**: Smart handling of save conflicts with user choice
- **Portable**: Single executable files, no installation required
- **Steam Deck Ready**: Native support for Proton save locations

### Platform Notes
- **Windows**: Full native Dark Souls 2 support
- **Steam Deck/Linux**: Sync saves for Dark Souls 2 running via Proton/Wine
- **macOS**: Transfer saves for Dark Souls 2 running via CrossOver, Wine, or other compatibility layers

*This app doesn't make Dark Souls 2 run on non-Windows platforms - it syncs your saves between platforms where you can run the game.*

## Quick Start

### Download & Run

1. **Download** the appropriate binary for your platform from [Releases](https://github.com/xanderpanderman/ds-cloud-sync/releases):
   - Windows: `ds2cloudsync-windows-x64.exe`
   - Steam Deck/Linux: `ds2cloudsync-linux-x64`
   - macOS: `ds2cloudsync-macos-x64`

2. **Run** the executable:
   - Windows: Double-click the `.exe` file
   - Linux/Steam Deck: `chmod +x ds2cloudsync-linux-x64 && ./ds2cloudsync-linux-x64`
   - macOS: `chmod +x ds2cloudsync-macos-x64 && ./ds2cloudsync-macos-x64`

3. **Follow the setup wizard** to connect your cloud storage
4. **Start playing** - your saves sync automatically!

### Steam Deck Installation

**Quick install** (Desktop Mode terminal):
```bash
wget https://github.com/xanderpanderman/ds-cloud-sync/releases/download/v1.0.7/ds2cloudsync-linux-x64 -O ds2cloudsync && chmod +x ds2cloudsync && ./ds2cloudsync
```

**Install to Applications folder**:
```bash
mkdir -p ~/Applications && cd ~/Applications && wget https://github.com/xanderpanderman/ds-cloud-sync/releases/download/v1.0.7/ds2cloudsync-linux-x64 -O ds2cloudsync && chmod +x ds2cloudsync && ./ds2cloudsync
```

*Note: Using `wget` instead of `curl` for better Steam Deck compatibility*

To add to Gaming Mode: Right-click Steam → Add a Non-Steam Game → Browse to the binary

## Supported Games

### Currently Supported
- **Dark Souls 2: Scholar of the First Sin**
- **Dark Souls 2 (Original)**

### Future Plans
- **Dark Souls 3** (coming as I play through it!)
- **Bloodborne** (planned for future development)
- **Elden Ring** (considering based on community interest)

*Want to see a specific game supported? Open an issue or submit a PR!*

## Development

### Prerequisites
- Python 3.8+
- tkinter (included with Python)

### Running from Source
```bash
git clone https://github.com/xanderpanderman/ds-cloud-sync.git
cd ds-cloud-sync
python3 main.py
```

### Building Distributables
```bash
pip install pyinstaller
pyinstaller -F main.py
```

## Contributing

**Pull requests are welcome!** This project is developed by a father of two young children, so:

- **Response times may vary** - patience appreciated!
- **Clear descriptions help** - explain your changes well
- **Test your changes** - especially across different platforms
- **Feature requests welcome** - open an issue to discuss

### Ways to Contribute
- **Bug reports** and fixes
- **New game support** (DS3, Bloodborne, etc.)
- **Platform improvements** (better Steam Deck integration, etc.)
- **Documentation** improvements
- **Translations** (future feature)

## Support & Maintenance

This project is maintained by a busy parent, so please understand:

- **Limited availability** - responses may take time
- **Family first** - development happens around family time
- **Community-driven** - PRs and community help are especially appreciated
- **Well-documented issues** help me help you faster

For urgent issues, consider submitting a PR with a fix if possible!

## Privacy & Security

- **No data collection** - your saves stay between you and your cloud
- **Secure authentication** - uses official cloud provider APIs
- **Local credentials** - authentication tokens stored locally via rclone
- **No telemetry** - completely private operation

## Requirements

### Dark Souls 2 Save Locations
The app automatically detects saves in these locations:

**Windows:**
- `%APPDATA%\DarkSoulsII\`

**macOS:**
- Native: `~/Library/Application Support/DarkSoulsII/`
- Steam/CrossOver: Various compatibility paths

**Linux/Steam Deck:**
- `~/.local/share/Steam/steamapps/compatdata/335300/pfx/drive_c/users/steamuser/AppData/Roaming/DarkSoulsII/` (Scholar of the First Sin)
- `~/.local/share/Steam/steamapps/compatdata/236430/pfx/drive_c/users/steamuser/AppData/Roaming/DarkSoulsII/` (Original DS2)

## Troubleshooting

### Common Issues

#### No saves detected
Make sure Dark Souls 2 is installed and you've started the game at least once

#### Sync conflicts
The app will show you both saves and let you choose which to keep

#### Cloud connection issues
Check your internet connection and re-authenticate if needed

#### Steam Deck: "address already in use" during cloud setup
If you get port conflicts during rclone setup:

1. **Kill stuck processes**:
```bash
sudo fuser -k 53682/tcp
sudo pkill -f rclone
```

2. **If that doesn't work, restart Steam Deck** (unfortunately this is the most reliable fix)

3. **Alternative - use external keyboard**: Connect USB keyboard temporarily for easier rclone config

4. **Manual rclone setup**:
```bash
cd ~/.local/share/ds2cloudsync/rclone
./rclone config delete gdrive
./rclone config
```
- Choose "n" for new remote
- Name: gdrive  
- Type: drive
- When prompted about browser auth, choose "N" (no)
- Copy the URL to Firefox and complete authentication
- Paste the code back

#### "empty token" or OAuth errors
The app should automatically refresh tokens, but if it fails:
```bash
cd ~/.local/share/ds2cloudsync/rclone
./rclone config
```
Edit the existing remote and re-authenticate following the prompts.

### Getting Help
1. Check [existing issues](https://github.com/xanderpanderman/ds-cloud-sync/issues)
2. Create a new issue with:
   - Your operating system
   - Error messages (if any)
   - Steps to reproduce

## License

MIT License - see [LICENSE](LICENSE) for details.

## Acknowledgments

- Built with [rclone](https://rclone.org/) for cloud storage operations
- Inspired by the Dark Souls community's need for save portability
- Thanks to all contributors and the patient Dark Souls community!

---

*May the flames guide thee... across all your devices*