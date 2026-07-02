# yt-dlp GUI Downloader

Eine kleine, moderne Desktop-GUI (CustomTkinter) rund um [yt-dlp](https://github.com/yt-dlp/yt-dlp),
um Videos und Playlists bequem herunterzuladen — als eigenständige Windows-`.exe`.

## Features

- Modernes Dark-Theme UI (CustomTkinter)
- Qualitätsauswahl (Beste Qualität, 1080p, 720p, 480p, Nur Audio als MP3)
- Playlist-Unterstützung
- Live-Fortschrittsanzeige + Log-Ausgabe
- Läuft als portable Einzeldatei-`.exe`

## Voraussetzungen

- [ffmpeg](https://ffmpeg.org/download.html) muss installiert und im `PATH` verfügbar sein
  (wird für Zusammenführen von Video/Audio sowie für die MP3-Konvertierung benötigt).

## Entwicklung / Start ohne exe

```powershell
py -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python main.py
```

## Windows-exe bauen

```powershell
.\build.ps1
```

Die fertige `.exe` liegt danach unter `dist\yt-dlp-gui.exe`.

## Bekannte Einschränkung

YouTube ändert regelmäßig seine Anti-Bot-Maßnahmen, wodurch Downloads zeitweise mit
Fehlern wie `HTTP Error 403` fehlschlagen können. In diesem Fall hilft meist ein
Update von yt-dlp auf die neueste Version (`pip install -U yt-dlp`), da das Projekt
sehr aktiv gegen solche Änderungen patcht.

## Hinweis zur Nutzung

Dieses Tool lädt lediglich Inhalte über die offene [yt-dlp](https://github.com/yt-dlp/yt-dlp)-Bibliothek
herunter (Unlicense). Bitte nur Inhalte herunterladen, für die du die entsprechenden Rechte
hast bzw. die Nutzungsbedingungen der jeweiligen Plattform es erlauben.

## Lizenz

MIT — siehe [LICENSE](LICENSE).
