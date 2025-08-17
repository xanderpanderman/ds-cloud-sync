#!/bin/bash
# DS2 Cloud Sync Steam Deck Installation Script

set -e

echo "🎮 Installing DS2 Cloud Sync for Steam Deck..."

# Download directory
INSTALL_DIR="$HOME/Applications"
BINARY_NAME="ds2cloudsync"
DESKTOP_FILE="$HOME/.local/share/applications/ds2cloudsync.desktop"

# Create install directory
mkdir -p "$INSTALL_DIR"

# Download the latest release
echo "📥 Downloading latest release..."
LATEST_URL=$(curl -s https://api.github.com/repos/xanderpanderman/ds-cloud-sync/releases/latest | grep "browser_download_url.*linux-x64" | cut -d '"' -f 4)

if [ -z "$LATEST_URL" ]; then
    echo "❌ Could not find latest release. Please download manually from:"
    echo "   https://github.com/xanderpanderman/ds-cloud-sync/releases"
    exit 1
fi

# Download binary
curl -L "$LATEST_URL" -o "$INSTALL_DIR/$BINARY_NAME"
chmod +x "$INSTALL_DIR/$BINARY_NAME"

echo "✅ Binary installed to $INSTALL_DIR/$BINARY_NAME"

# Create desktop entry for Steam Deck
echo "🖥️ Creating desktop entry..."
cat > "$DESKTOP_FILE" << EOF
[Desktop Entry]
Name=DS2 Cloud Sync
Comment=Sync Dark Souls 2 saves to cloud storage
Exec=$INSTALL_DIR/$BINARY_NAME
Icon=applications-games
Terminal=false
Type=Application
Categories=Game;Utility;
EOF

echo "✅ Desktop entry created"

# Add to Steam (if steam is available)
if command -v steam >/dev/null 2>&1; then
    echo "🚂 Adding to Steam library..."
    echo "Note: You may need to restart Steam and look for 'DS2 Cloud Sync' in your library"
fi

echo ""
echo "🎉 Installation complete!"
echo ""
echo "To use DS2 Cloud Sync:"
echo "1. Open 'DS2 Cloud Sync' from your applications menu"
echo "2. Or run directly: $INSTALL_DIR/$BINARY_NAME"
echo ""
echo "For Steam Deck Gaming Mode:"
echo "1. Restart Steam"
echo "2. Look for 'DS2 Cloud Sync' in your library"
echo "3. Add it to your favorites for easy access"
EOF