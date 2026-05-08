# AnyCast DLNA Remote Control

Python scripts to stream audio/video to an Anycast DLNA dongle, plus a **Flask web UI** for full remote control.

## Scripts

| Script | Purpose |
|---|---|
| `dlna_send_audio.py` | Plays an audio stream via ffmpeg |
| `dlna_send_video.py` | Plays a screen+audio stream via ffmpeg |
| `dlna_send_webvideo.py` | Sends any media URL directly to the dongle |
| `dlna_web_interface.py` | **Web UI** — control everything from a browser |

## Web Interface (recommended)

```
python dlna_web_interface.py
```

Open `http://127.0.0.1:5500` in a browser. Features:

- **Scan** — discovers Anycast dongles on your LAN via SSDP
- **Play/Pause/Stop/Resume** — full playback control
- **Seek** — drag bar or +/-10s buttons
- **Volume** — slider (0–100) + mute toggle
- **Codecs** — view all formats the dongle supports
- **Device info** — shows active dongle details

All device config happens at runtime — no hardcoded IPs.

## Quick Start (CLI)

Install ffmpeg, then:

1. **Start a stream** (choose one):

   ```bash
   # Stream a URL directly (no ffmpeg needed)
   python dlna_send_webvideo.py

   # Or stream your screen + audio via ffmpeg
   ffmpeg -f x11grab -video_size 1280x720 -framerate 30 -i :0.0 \
          -f pulse -i default \
          -c:v libx264 -preset ultrafast -tune zerolatency -pix_fmt yuv420p -b:v 800k \
          -c:a aac -b:a 128k \
          -f mpegts -listen 1 http://0.0.0.0:8090/streamvideo
   ```

2. **Run the matching Python script** in another terminal.

### Windows

Use `gdigrab` instead of `x11grab` and `dshow` instead of `pulse`:

```bash
ffmpeg -f gdigrab -video_size 1280x720 -framerate 30 -i desktop ^
       -f dshow -i audio="Microphone (Realtek Audio)" ^
       -c:v libx264 -preset ultrafast -tune zerolatency -pix_fmt yuv420p -b:v 800k ^
       -c:a aac -b:a 128k ^
       -f mpegts -listen 1 http://0.0.0.0:8090/streamvideo
```

## Install Dependencies

```bash
pip install requests flask
```

## Requirements

- Python 3.6+
- ffmpeg (for streaming scripts)
- Network access to an Anycast DLNA dongle (MediaRenderer:1, Intel MicroStack)

## How It Works

1. ffmpeg generates an MPEG-TS stream and serves it over HTTP
2. Python/Flask sends SOAP/UPnP commands to the dongle's `AVTransport`, `RenderingControl`, and `ConnectionManager` services
3. The web UI polls `/api/status` every 2 seconds to stay in sync
