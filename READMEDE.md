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

Ohne Optionen startet ein interaktiver Assistent. Er fragt nach Video-Input,
Audio-Modus, Audio-Input-Ordner, Output-Ordner, In-place-Modus und
Ueberschreiben vorhandener Dateien. Danach zeigt er eine Preflight-Uebersicht
mit Video- und MP3-Gesamtlaengen und fragt vor dem Start nach Bestaetigung.

Hauefige Optionen:

- `--list-audio-lengths` Laengen der MP3-Dateien in `audio/` ausgeben
- `--list-audio-input-lengths` Laengen der MP3-Dateien in `audio-input/` ausgeben
- `--list-audio-sort name|date` Sortierung fuer `--list-audio-lengths`
- `--combine-only` MP3s aus `audio-input/` zu einer MP3 in `audio/` kombinieren und beenden
- `--shuffle-audio-input` zufaellige Reihenfolge der MP3s aus `audio-input/`
- `--force-shuffle-audio-input` immer eine neue zufaellig gemischte MP3 aus `audio-input/` erzeugen, auch wenn in `audio/` schon eine vorhanden ist
- `--audio-file /pfad/zur/datei.mp3` eine konkrete MP3 verwenden
- `--audio-pick latest|oldest|name` waehlt die MP3, wenn mehrere vorhanden sind
- `--audio-name datei.mp3` zusammen mit `--audio-pick name` (Endung optional)
- `--video-input /pfad/zum/video.mp4` Videodatei(en), einen Ordner oder ein Glob wie `"/pfad/zu/*.mp4"` statt `video/` nutzen
- `--output-dir /pfad/zum/output` bearbeitete Videos mit Originaldateinamen in diesen Ordner schreiben
- `--in-place` Video nach erfolgreichem Export ersetzen

Verhalten:

- Wenn `audio/` mehrere MP3s hat, wird die neueste genutzt.
- Wenn `audio/` keine MP3s hat, werden MP3s aus `audio-input/` kombiniert und unter `audio/JJJJ.MM.TT-SS.MM.SS.mp3` gespeichert.
- Mit `--force-shuffle-audio-input` werden MP3s aus `audio-input/` immer zu einer neuen zufaellig gemischten Datei in `audio/` kombiniert, auch wenn schon eine kombinierte MP3 vorhanden ist.
- Wenn `--force-shuffle-audio-input` mit einem oder mehreren Videos genutzt wird, wird pro Video eine eigene zufaellig gemischte Audiodatei erzeugt. Die Eingabe-MP3s werden nach Moeglichkeit so lange ausgewaehlt, bis ihre Gesamtlaenge die Videolaenge erreicht oder ueberschreitet.
- Wenn die ausgewaehlten MP3s aus `audio-input/` kuerzer als das Zielvideo sind, wird eine Warnung ausgegeben und das Audio bei der Videoverarbeitung geloopt.
- Tracklists fuer Force-Shuffle pro Video werden neben dem Video-Output mit gleichem Basisnamen geschrieben, zum Beispiel erzeugt `output/Mein Clip.mp4` die Datei `output/Mein Clip.txt`.
- Tracklists enthalten Kopfzeilen mit Videonamen, Videolaenge und Audiolaenge, sofern ein Video-Kontext vorhanden ist.
- Beim Kombinieren wird eine Tracklist-Textdatei neben der MP3 erzeugt mit Startzeiten pro Song (Dateiendungen werden weggelassen; zweistellige Praefixe wie `01 ` werden entfernt).
- Mit `--shuffle-audio-input` bleiben MP3s mit zweistelligen Praefixen zuerst in numerischer Reihenfolge, die restlichen Dateien werden zufaellig gemischt.
  Beispiel fuer feste Reihenfolge: `00 Intro.mp3`, `01 Theme.mp3`, `02 Outro.mp3` (zwei Ziffern + Leerzeichen/Unterstrich/Bindestrich).
  Beispiel fuer Shuffle-Teil: `Song A.mp3`, `Mein Track.mp3` (kein zweistelliges Praefix).
- Wenn Audio laenger als das Video ist, wird es am Ende abgeschnitten.
- Wenn Audio kuerzer als das Video ist, wird es ab Anfang geloopt, bis das Video zu Ende ist.
- Mit `--output-dir` werden bearbeitete Videos mit ihren Originaldateinamen in diesen Ordner geschrieben. Ohne `--output-dir` wird das konfigurierte Suffix neben dem Quellvideo angehaengt.
- Der Audio-Codec wird automatisch nach Container gewaehlt, ausser `--audio-codec` ist gesetzt (`.webm` -> `opus`, `.mp4/.mov/.m4v/.mkv` -> `aac`, `.avi` -> `mp3`).
- Bei mehreren Videos werden Fehler ausgegeben und die Verarbeitung wird mit den restlichen Videos fortgesetzt.

## Beispiele

```bash
# Kombiniert automatisch (wenn audio/ leer ist) und ersetzt Audio
./switch_audio.py

# MP3-Laengen in audio/ anzeigen
./switch_audio.py --list-audio-lengths

# Nur MP3s in audio-input/ kombinieren
./switch_audio.py --combine-only

# Kombinieren mit Shuffle, aber zweistellige Praefixe zuerst (00, 01, ...)
./switch_audio.py --combine --shuffle-audio-input

# Neue zufaellig gemischte kombinierte Audiodatei erzwingen, auch wenn audio/ schon eine hat
./switch_audio.py --force-shuffle-audio-input

# Alle passenden Videos bearbeiten und pro Video frische Audio-/Tracklist-Dateien erzeugen
./switch_audio.py --video-input "/pfad/zu/*.mp4" --force-shuffle-audio-input

# Bearbeitete Videos in separaten Output-Ordner schreiben
./switch_audio.py --video-input "/pfad/zu/*.mp4" --output-dir "/pfad/zum/output"
```
