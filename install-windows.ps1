# DS2 Cloud Sync Windows Installation Script
param(
    [switch]$AddToStartMenu,
    [switch]$AddToDesktop,
    [string]$InstallPath = "$env:LOCALAPPDATA\DS2CloudSync"
)

Write-Host "🎮 Installing DS2 Cloud Sync for Windows..." -ForegroundColor Green

# Create install directory
if (!(Test-Path $InstallPath)) {
    New-Item -ItemType Directory -Path $InstallPath -Force | Out-Null
}

$BinaryPath = "$InstallPath\ds2cloudsync.exe"

# Download the latest release
Write-Host "📥 Downloading latest release..." -ForegroundColor Yellow

try {
    $LatestRelease = Invoke-RestMethod -Uri "https://api.github.com/repos/xanderpanderman/ds-cloud-sync/releases/latest"
    $WindowsAsset = $LatestRelease.assets | Where-Object { $_.name -like "*windows-x64.exe" }
    
    if (!$WindowsAsset) {
        throw "Windows binary not found in latest release"
    }
    
    $DownloadUrl = $WindowsAsset.browser_download_url
    Write-Host "Downloading from: $DownloadUrl" -ForegroundColor Gray
    
    Invoke-WebRequest -Uri $DownloadUrl -OutFile $BinaryPath
    Write-Host "✅ Binary installed to $BinaryPath" -ForegroundColor Green
}
catch {
    Write-Host "❌ Could not download latest release: $_" -ForegroundColor Red
    Write-Host "Please download manually from: https://github.com/xanderpanderman/ds-cloud-sync/releases" -ForegroundColor Yellow
    exit 1
}

# Create Start Menu shortcut
if ($AddToStartMenu -or $PSCmdlet.ShouldContinue("Create Start Menu shortcut?", "Shortcut Creation")) {
    $StartMenuPath = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs"
    $ShortcutPath = "$StartMenuPath\DS2 Cloud Sync.lnk"
    
    $WshShell = New-Object -comObject WScript.Shell
    $Shortcut = $WshShell.CreateShortcut($ShortcutPath)
    $Shortcut.TargetPath = $BinaryPath
    $Shortcut.WorkingDirectory = $InstallPath
    $Shortcut.Description = "Sync Dark Souls 2 saves to cloud storage"
    $Shortcut.Save()
    
    Write-Host "✅ Start Menu shortcut created" -ForegroundColor Green
}

# Create Desktop shortcut
if ($AddToDesktop -or $PSCmdlet.ShouldContinue("Create Desktop shortcut?", "Shortcut Creation")) {
    $DesktopPath = [Environment]::GetFolderPath("Desktop")
    $ShortcutPath = "$DesktopPath\DS2 Cloud Sync.lnk"
    
    $WshShell = New-Object -comObject WScript.Shell
    $Shortcut = $WshShell.CreateShortcut($ShortcutPath)
    $Shortcut.TargetPath = $BinaryPath
    $Shortcut.WorkingDirectory = $InstallPath
    $Shortcut.Description = "Sync Dark Souls 2 saves to cloud storage"
    $Shortcut.Save()
    
    Write-Host "✅ Desktop shortcut created" -ForegroundColor Green
}

# Add to PATH (optional)
if ($PSCmdlet.ShouldContinue("Add to system PATH for command-line access?", "PATH Addition")) {
    $CurrentPath = [Environment]::GetEnvironmentVariable("PATH", "User")
    if ($CurrentPath -notlike "*$InstallPath*") {
        $NewPath = "$CurrentPath;$InstallPath"
        [Environment]::SetEnvironmentVariable("PATH", $NewPath, "User")
        Write-Host "✅ Added to PATH (restart terminal to use 'ds2cloudsync' command)" -ForegroundColor Green
    } else {
        Write-Host "ℹ️ Already in PATH" -ForegroundColor Blue
    }
}

Write-Host ""
Write-Host "🎉 Installation complete!" -ForegroundColor Green
Write-Host ""
Write-Host "To use DS2 Cloud Sync:" -ForegroundColor White
Write-Host "• Run from Start Menu: 'DS2 Cloud Sync'" -ForegroundColor Gray
Write-Host "• Run from Desktop shortcut (if created)" -ForegroundColor Gray
Write-Host "• Run directly: $BinaryPath" -ForegroundColor Gray
Write-Host ""
Write-Host "The app will help you:" -ForegroundColor White
Write-Host "• Connect to Google Drive, OneDrive, Dropbox, or Box" -ForegroundColor Gray
Write-Host "• Automatically sync your Dark Souls 2 saves" -ForegroundColor Gray
Write-Host "• Keep backups and resolve conflicts" -ForegroundColor Gray