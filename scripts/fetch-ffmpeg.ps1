# Downloads the LGPL-licensed win64 ffmpeg/ffprobe build from BtbN/FFmpeg-Builds
# into assets\ffmpeg, if it isn't already there. Run automatically by build.ps1.
# ffmpeg.exe/ffprobe.exe are ~110MB each, so they aren't committed to git —
# GitHub rejects files over 100MB in a normal push anyway.

$ErrorActionPreference = "Stop"

$ffmpegDir = Join-Path $PSScriptRoot "..\assets\ffmpeg"

if (Test-Path (Join-Path $ffmpegDir "ffmpeg.exe")) {
    Write-Host "ffmpeg already present, skipping download."
    exit 0
}

Write-Host "Fetching bundled ffmpeg (LGPL build from BtbN/FFmpeg-Builds)..."
New-Item -ItemType Directory -Force -Path $ffmpegDir | Out-Null

$release = Invoke-RestMethod -Uri "https://api.github.com/repos/BtbN/FFmpeg-Builds/releases" -Headers @{ "User-Agent" = "yt-dlp-gui-build" } |
    Select-Object -First 1

$asset = $release.assets |
    Where-Object { $_.name -match "^ffmpeg-n\d+(\.\d+)*-.*-win64-lgpl-\d.*\.zip$" } |
    Select-Object -First 1

if (-not $asset) {
    throw "Could not find a matching win64 LGPL ffmpeg build in the latest BtbN/FFmpeg-Builds release."
}

$zipPath = Join-Path $env:TEMP "ffmpeg-lgpl-build.zip"
$extractDir = Join-Path $env:TEMP "ffmpeg-lgpl-extract"

Write-Host "Downloading $($asset.name) ($([math]::Round($asset.size / 1MB))MB)..."
Invoke-WebRequest -Uri $asset.browser_download_url -OutFile $zipPath

if (Test-Path $extractDir) {
    Remove-Item $extractDir -Recurse -Force
}
Expand-Archive -Path $zipPath -DestinationPath $extractDir -Force

$binDir = (Get-ChildItem -Path $extractDir -Recurse -Filter "ffmpeg.exe" | Select-Object -First 1).DirectoryName
$rootDir = Split-Path $binDir -Parent

Copy-Item (Join-Path $binDir "ffmpeg.exe") (Join-Path $ffmpegDir "ffmpeg.exe") -Force
Copy-Item (Join-Path $binDir "ffprobe.exe") (Join-Path $ffmpegDir "ffprobe.exe") -Force
Copy-Item (Join-Path $rootDir "LICENSE.txt") (Join-Path $ffmpegDir "LICENSE.txt") -Force

Remove-Item $zipPath -Force
Remove-Item $extractDir -Recurse -Force

Write-Host "ffmpeg ready in $ffmpegDir"
