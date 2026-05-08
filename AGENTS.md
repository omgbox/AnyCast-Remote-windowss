# AGENTS.md — AnyCast-Ubuntu - Vibe Coded with Opencode Big Pickle

## What this is

Three Python scripts that send SOAP/UPnP commands to an Anycast DLNA dongle to start playback of an ffmpeg-generated stream.

## How it works

1. **ffmpeg** generates an MPEG-TS stream and serves it over HTTP (see `README.md` for exact commands).
2. **Python scripts** talk to the dongle's UPnP AVTransport service via HTTP POST with SOAP XML:
   - `SetAVTransportURI` — tells the dongle where the stream lives
   - `Play` — starts playback

## Scripts

| Script | Stream type | Media URL |
|---|---|---|
| `dlna_send_audio.py` | Audio | `http://192.168.1.108:8088/streamaudio` |
| `dlna_send_video.py` | Screen + audio | `http://192.168.1.108:8090/streamvideo` |
| `dlna_send_webvideo.py` | Web video | Any URL (currently `https://www.papytane.com/mp4/accrobra.mp4`) |

## Key facts

- **IP addresses are hardcoded** — edit before use: `device_base_url` (the dongle) and `image_url` (the stream source).
- **Run ffmpeg first**, then the Python script in another terminal. For `dlna_send_webvideo.py` no ffmpeg needed (sends a URL directly).
- **Prerequisites**: X11 (not Wayland), `ffmpeg`, `python3-requests` (`pip install requests`), `xhost` permission, firewall may need port opened.
- **Order of operations in scripts**: `SetAVTransportURI` → `Play` (two separate SOAP calls).
- **Device discovery**: Use UPnP SSDP (`M-SEARCH *`, ST: `ssdp:all`) to find the Anycast dongle. Look for `MediaRenderer:1` with server `Intel MicroStack/1.0.2777`. The control URL is `http://<ip>:<port>/AVTransport/control` (no UUID in path).

## Web interface

`dlna_web_interface.py` is a Flask app with a dark-theme UI (port 5500) for controlling the dongle from a browser:

| Endpoint | Method | Purpose |
|---|---|---|
| `/` | GET | Web UI (HTML + CSS + vanilla JS) |
| `/api/play` | POST | Set URL + play (`{"url": "..."}`) |
| `/api/pause` | POST | Pause playback |
| `/api/resume` | POST | Resume paused playback (no URL needed) |
| `/api/stop` | POST | Stop playback |
| `/api/seek` | POST | Seek to position (`{"position": "hh:mm:ss"}`) |
| `/api/status` | GET | Returns state, position, duration, progress % |
| `/api/volume` | GET/POST | Get volume+mute or set (`{"level": 0-100}`, `{"muted": true/false}`) |
| `/api/codecs` | GET | Lists all supported video/audio codecs from device |
| `/api/device` | GET | Current configured device info |
| `/api/discover` | GET | SSDP scan for Anycast dongles on LAN |
| `/api/configure` | POST | Set active device (`{"base_url", "control_url", "friendly_name", "uuid"}`) |

Run with: `python dlna_web_interface.py` then open `http://127.0.0.1:5500`. Requires `flask` (`pip install flask`).

The web UI has a built-in **device scanner** using SSDP multicast. Click **Scan** to discover Anycast MediaRenderer dongles on the local network. Found devices display their friendly name and IP, and you can click **Use** to select one. The backend dynamically reconfigures itself — no need to hardcode IPs.
