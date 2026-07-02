# Builds a single-file Windows .exe with PyInstaller.
# Run from the project root: .\build.ps1

$ErrorActionPreference = "Stop"

if (-not (Test-Path ".\.venv")) {
    py -m venv .venv
}

.\.venv\Scripts\pip install --upgrade pip
.\.venv\Scripts\pip install -r requirements.txt

.\.venv\Scripts\pyinstaller `
    --noconfirm `
    --onefile `
    --windowed `
    --name "yt-dlp-gui" `
    main.py

Write-Host "`nFertig! Die exe liegt in dist\yt-dlp-gui.exe"
