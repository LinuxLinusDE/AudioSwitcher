# AudioSwitcher

Ersetzt die Audiospur eines langen Videos mit MP3-Audio mittels ffmpeg. Das Video wird ohne Neukodierung kopiert.

## Voraussetzungen

- Python 3
- ffmpeg (inkl. ffprobe)

## Ordner

- `video/` enthaelt die zu bearbeitenden Videos
- `audio/` enthaelt die MP3, die verwendet wird
- `audio-input/` enthaelt MP3s zum Kombinieren, falls `audio/` leer ist

## Nutzung

```bash
./switch_audio.py
```

Hauefige Optionen:

- `--list-audio-lengths` Laengen der MP3-Dateien in `audio/` ausgeben
- `--audio-file /pfad/zur/datei.mp3` eine konkrete MP3 verwenden
- `--audio-pick latest|oldest|name` waehlt die MP3, wenn mehrere vorhanden sind
- `--audio-name datei.mp3` zusammen mit `--audio-pick name` (Endung optional)
- `--in-place` Video nach erfolgreichem Export ersetzen

Verhalten:

- Wenn `audio/` mehrere MP3s hat, wird die neueste genutzt.
- Wenn `audio/` keine MP3s hat, werden MP3s aus `audio-input/` kombiniert und unter `audio/JJJJ.MM.TT-SS.MM.SS.mp3` gespeichert.
- Wenn Audio laenger als das Video ist, wird es am Ende abgeschnitten.
- Der Audio-Codec wird automatisch nach Container gewaehlt, ausser `--audio-codec` ist gesetzt (`.webm` -> `opus`, `.mp4/.mov/.m4v/.mkv` -> `aac`, `.avi` -> `mp3`).
- Bei mehreren Videos werden Fehler ausgegeben und die Verarbeitung wird mit den restlichen Videos fortgesetzt.

## Beispiele

```bash
# Kombiniert automatisch (wenn audio/ leer ist) und ersetzt Audio
./switch_audio.py

# MP3-Laengen in audio/ anzeigen
./switch_audio.py --list-audio-lengths
```
