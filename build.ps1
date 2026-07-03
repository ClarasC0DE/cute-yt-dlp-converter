# Builds a single-file Windows .exe with PyInstaller.
# Run from the project root: .\build.ps1

$ErrorActionPreference = "Stop"

if (-not (Test-Path ".\.venv")) {
    py -m venv .venv
}

.\.venv\Scripts\pip install --upgrade pip
.\.venv\Scripts\pip install -r requirements.txt

.\scripts\fetch-ffmpeg.ps1

.\.venv\Scripts\pyinstaller `
    --noconfirm `
    --onefile `
    --windowed `
    --name "yt-dlp-gui" `
    --icon "assets\icon.ico" `
    --add-data "assets;assets" `
    main.py

Write-Host "`nDone! The exe is at dist\yt-dlp-gui.exe"
