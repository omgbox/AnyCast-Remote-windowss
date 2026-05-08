import re
import socket
import time
import xml.etree.ElementTree as ET
from urllib.parse import urljoin
import requests
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0

device_config = {
    "base_url": None,
    "control_url": None,
    "rendering_control_url": None,
    "connection_manager_url": None,
    "friendly_name": None,
    "uuid": None,
}

current_url = ""

SOAP_NS = {
    "s": "http://schemas.xmlsoap.org/soap/envelope/",
    "u": "urn:schemas-upnp-org:service:AVTransport:1",
}

SOAP_HEADERS = {
    "Content-Type": 'text/xml; charset="utf-8"',
}


def _soap(action, body):
    if not device_config["control_url"]:
        return 0, "No device configured"
    h = {**SOAP_HEADERS, "SOAPAction": f'"urn:schemas-upnp-org:service:AVTransport:1#{action}"'}
    try:
        r = requests.post(device_config["control_url"], data=body, headers=h, timeout=5)
        return r.status_code, r.text
    except requests.RequestException as e:
        return 0, str(e)


def _soap_rc(action, body):
    url = device_config.get("rendering_control_url")
    if not url:
        return 0, "No rendering control URL"
    h = {**SOAP_HEADERS, "SOAPAction": f'"urn:schemas-upnp-org:service:RenderingControl:1#{action}"'}
    try:
        r = requests.post(url, data=body, headers=h, timeout=5)
        return r.status_code, r.text
    except requests.RequestException as e:
        return 0, str(e)


def _time_to_sec(t):
    parts = list(map(int, t.split(":")))
    if len(parts) == 3:
        return parts[0] * 3600 + parts[1] * 60 + parts[2]
    if len(parts) == 2:
        return parts[0] * 60 + parts[1]
    return 0


def set_uri(url):
    body = f"""<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
  <s:Body>
    <u:SetAVTransportURI xmlns:u="urn:schemas-upnp-org:service:AVTransport:1">
      <InstanceID>0</InstanceID>
      <CurrentURI>{url}</CurrentURI>
      <CurrentURIMetaData></CurrentURIMetaData>
    </u:SetAVTransportURI>
  </s:Body>
</s:Envelope>"""
    return _soap("SetAVTransportURI", body)


def send_play():
    body = """<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
  <s:Body>
    <u:Play xmlns:u="urn:schemas-upnp-org:service:AVTransport:1">
      <InstanceID>0</InstanceID>
      <Speed>1</Speed>
    </u:Play>
  </s:Body>
</s:Envelope>"""
    return _soap("Play", body)


def send_pause():
    body = """<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
  <s:Body>
    <u:Pause xmlns:u="urn:schemas-upnp-org:service:AVTransport:1">
      <InstanceID>0</InstanceID>
    </u:Pause>
  </s:Body>
</s:Envelope>"""
    return _soap("Pause", body)


def send_stop():
    body = """<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
  <s:Body>
    <u:Stop xmlns:u="urn:schemas-upnp-org:service:AVTransport:1">
      <InstanceID>0</InstanceID>
    </u:Stop>
  </s:Body>
</s:Envelope>"""
    return _soap("Stop", body)


def send_seek(target):
    body = f"""<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
  <s:Body>
    <u:Seek xmlns:u="urn:schemas-upnp-org:service:AVTransport:1">
      <InstanceID>0</InstanceID>
      <Unit>REL_TIME</Unit>
      <Target>{target}</Target>
    </u:Seek>
  </s:Body>
</s:Envelope>"""
    return _soap("Seek", body)


def get_position():
    req_body = """<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
  <s:Body>
    <u:GetPositionInfo xmlns:u="urn:schemas-upnp-org:service:AVTransport:1">
      <InstanceID>0</InstanceID>
    </u:GetPositionInfo>
  </s:Body>
</s:Envelope>"""
    code, resp_text = _soap("GetPositionInfo", req_body)
    if code != 200:
        return "00:00:00", "00:00:00"
    try:
        root = ET.fromstring(resp_text)
        body_el = root.find(".//s:Body", SOAP_NS)
        if body_el is None:
            return "00:00:00", "00:00:00"
        resp = body_el.find("u:GetPositionInfoResponse", SOAP_NS)
        if resp is None:
            return "00:00:00", "00:00:00"
        dur_el = resp.find("TrackDuration")
        pos_el = resp.find("RelTime")
        dur = dur_el.text if dur_el is not None and dur_el.text else "00:00:00"
        pos = pos_el.text if pos_el is not None and pos_el.text else "00:00:00"
        return dur, pos
    except ET.ParseError:
        return "00:00:00", "00:00:00"


def get_transport_state():
    req_body = """<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
  <s:Body>
    <u:GetTransportInfo xmlns:u="urn:schemas-upnp-org:service:AVTransport:1">
      <InstanceID>0</InstanceID>
    </u:GetTransportInfo>
  </s:Body>
</s:Envelope>"""
    code, resp_text = _soap("GetTransportInfo", req_body)
    if code != 200:
        return "UNKNOWN"
    try:
        root = ET.fromstring(resp_text)
        body_el = root.find(".//s:Body", SOAP_NS)
        if body_el is None:
            return "UNKNOWN"
        resp = body_el.find("u:GetTransportInfoResponse", SOAP_NS)
        if resp is None:
            return "UNKNOWN"
        state_el = resp.find("CurrentTransportState")
        if state_el is not None and state_el.text:
            return state_el.text
    except ET.ParseError:
        pass
    return "UNKNOWN"


# --- RenderingControl (volume) ---

def get_volume():
    body = """<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
  <s:Body>
    <u:GetVolume xmlns:u="urn:schemas-upnp-org:service:RenderingControl:1">
      <InstanceID>0</InstanceID>
      <Channel>Master</Channel>
    </u:GetVolume>
  </s:Body>
</s:Envelope>"""
    code, text = _soap_rc("GetVolume", body)
    if code != 200:
        return None
    try:
        root = ET.fromstring(text)
        ns = {"s": "http://schemas.xmlsoap.org/soap/envelope/",
              "u": "urn:schemas-upnp-org:service:RenderingControl:1"}
        body_el = root.find(".//s:Body", ns)
        if body_el is None:
            return None
        resp = body_el.find("u:GetVolumeResponse", ns)
        if resp is None:
            return None
        vol_el = resp.find("CurrentVolume")
        return int(vol_el.text) if vol_el is not None and vol_el.text else None
    except (ET.ParseError, ValueError):
        return None


def set_volume(level):
    level = max(0, min(100, int(level)))
    body = f"""<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
  <s:Body>
    <u:SetVolume xmlns:u="urn:schemas-upnp-org:service:RenderingControl:1">
      <InstanceID>0</InstanceID>
      <Channel>Master</Channel>
      <DesiredVolume>{level}</DesiredVolume>
    </u:SetVolume>
  </s:Body>
</s:Envelope>"""
    return _soap_rc("SetVolume", body)


def get_mute():
    body = """<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
  <s:Body>
    <u:GetMute xmlns:u="urn:schemas-upnp-org:service:RenderingControl:1">
      <InstanceID>0</InstanceID>
      <Channel>Master</Channel>
    </u:GetMute>
  </s:Body>
</s:Envelope>"""
    code, text = _soap_rc("GetMute", body)
    if code != 200:
        return None
    try:
        root = ET.fromstring(text)
        ns = {"s": "http://schemas.xmlsoap.org/soap/envelope/",
              "u": "urn:schemas-upnp-org:service:RenderingControl:1"}
        body_el = root.find(".//s:Body", ns)
        if body_el is None:
            return None
        resp = body_el.find("u:GetMuteResponse", ns)
        if resp is None:
            return None
        mute_el = resp.find("CurrentMute")
        if mute_el is not None and mute_el.text:
            return mute_el.text == "1"
        return None
    except (ET.ParseError, ValueError):
        return None


def set_mute(muted):
    val = "1" if muted else "0"
    body = f"""<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
  <s:Body>
    <u:SetMute xmlns:u="urn:schemas-upnp-org:service:RenderingControl:1">
      <InstanceID>0</InstanceID>
      <Channel>Master</Channel>
      <DesiredMute>{val}</DesiredMute>
    </u:SetMute>
  </s:Body>
</s:Envelope>"""
    return _soap_rc("SetMute", body)


# --- ConnectionManager (codec info) ---

CM_NS = {
    "s": "http://schemas.xmlsoap.org/soap/envelope/",
    "u": "urn:schemas-upnp-org:service:ConnectionManager:1",
}


def _soap_cm(action, body):
    url = device_config.get("connection_manager_url")
    if not url:
        return 0, "No connection manager URL"
    h = {**SOAP_HEADERS, "SOAPAction": f'"urn:schemas-upnp-org:service:ConnectionManager:1#{action}"'}
    try:
        r = requests.post(url, data=body, headers=h, timeout=5)
        return r.status_code, r.text
    except requests.RequestException as e:
        return 0, str(e)


def get_protocol_info():
    body = """<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
  <s:Body>
    <u:GetProtocolInfo xmlns:u="urn:schemas-upnp-org:service:ConnectionManager:1" />
  </s:Body>
</s:Envelope>"""
    code, text = _soap_cm("GetProtocolInfo", body)
    if code != 200:
        return None
    try:
        root = ET.fromstring(text)
        body_el = root.find(".//s:Body", CM_NS)
        if body_el is None:
            return None
        resp = body_el.find("u:GetProtocolInfoResponse", CM_NS)
        if resp is None:
            return None
        src = resp.find("Source")
        sink = resp.find("Sink")
        return {
            "source": src.text if src is not None and src.text else "",
            "sink": sink.text if sink is not None and sink.text else "",
        }
    except ET.ParseError:
        return None


def _parse_protocol_string(raw):
    entries = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        segments = part.split(":")
        entry = {
            "protocol": segments[0] if len(segments) > 0 else "",
            "network": segments[1] if len(segments) > 1 else "",
            "content_type": segments[2] if len(segments) > 2 and segments[2] else "*",
            "details": ":".join(segments[3:]) if len(segments) > 3 else "",
        }
        entries.append(entry)
    return entries


# --- Device discovery ---

def _parse_ssdp_headers(text):
    headers = {}
    for line in text.split("\r\n")[1:]:
        if ":" in line:
            key, _, val = line.partition(":")
            headers[key.strip().upper()] = val.strip()
    return headers


def _fetch_device_desc(base_url):
    try:
        r = requests.get(base_url, timeout=3)
        if r.status_code != 200:
            return None
        root = ET.fromstring(r.text)
        ns = {"d": "urn:schemas-upnp-org:device-1-0"}
        dev = root.find(".//d:device", ns)
        if dev is None:
            return None
        fn = dev.find("d:friendlyName", ns)
        udn = dev.find("d:UDN", ns)
        friendly_name = fn.text if fn is not None and fn.text else "Unknown"
        uuid = ""
        if udn is not None and udn.text:
            m = re.search(r"uuid:(.+)", udn.text)
            if m:
                uuid = m.group(1)
        control_url = None
        svcs = dev.find("d:serviceList", ns)
        if svcs is not None:
            for svc in svcs.findall("d:service", ns):
                st = svc.find("d:serviceType", ns)
                if st is not None and st.text and "AVTransport" in st.text:
                    cu = svc.find("d:controlURL", ns)
                    if cu is not None and cu.text:
                        control_url = urljoin(base_url, cu.text)
        return {
            "friendly_name": friendly_name,
            "uuid": uuid,
            "control_url": control_url,
        }
    except Exception:
        return None


def discover_devices():
    msg = (
        "M-SEARCH * HTTP/1.1\r\n"
        "HOST: 239.255.255.250:1900\r\n"
        "MAN: \"ssdp:discover\"\r\n"
        "MX: 3\r\n"
        "ST: ssdp:all\r\n"
        "\r\n"
    ).encode()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.settimeout(4)
    try:
        sock.sendto(msg, ("239.255.255.250", 1900))
    except OSError:
        sock.close()
        return []
    raw = []
    try:
        while True:
            data, addr = sock.recvfrom(2048)
            raw.append((data, addr))
    except socket.timeout:
        pass
    finally:
        sock.close()

    candidates = {}
    for data, addr in raw:
        text = data.decode(errors="replace")
        hdrs = _parse_ssdp_headers(text)
        st = hdrs.get("ST", "")
        server = hdrs.get("SERVER", "")
        location = hdrs.get("LOCATION", "")
        usn = hdrs.get("USN", "")

        uuid_match = re.search(r"uuid:([a-f0-9\-]+)", usn, re.I)
        if not uuid_match:
            continue
        uuid = uuid_match.group(1)

        if uuid not in candidates:
            candidates[uuid] = {}

        if location and not candidates[uuid].get("location"):
            candidates[uuid]["location"] = location.rstrip("/")
            m = re.match(r"https?://([^:/]+)(?::(\d+))?", location)
            if m:
                candidates[uuid]["ip"] = m.group(1)
                candidates[uuid]["port"] = int(m.group(2)) if m.group(2) else 80

        if "MediaRenderer" in st:
            candidates[uuid]["is_media_renderer"] = True
        if "Intel MicroStack" in server:
            candidates[uuid]["is_anycast"] = True

    results = []
    for uuid, info in candidates.items():
        if not info.get("is_media_renderer") or not info.get("is_anycast"):
            continue
        location = info.get("location")
        if not location:
            continue
        desc = _fetch_device_desc(location)
        if desc is None:
            continue
        results.append({
            "uuid": uuid,
            "ip": info.get("ip", ""),
            "port": info.get("port", ""),
            "friendly_name": desc["friendly_name"],
            "base_url": location,
            "control_url": desc["control_url"],
        })
    return results


# --- Flask routes ---

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/device")
def api_device():
    return jsonify({
        "configured": device_config["base_url"] is not None,
        "base_url": device_config["base_url"],
        "friendly_name": device_config["friendly_name"],
        "uuid": device_config["uuid"],
    })


@app.route("/api/codecs")
def api_codecs():
    if not device_config.get("connection_manager_url"):
        return jsonify({"sink": [], "source": "", "raw": ""})
    info = get_protocol_info()
    if info is None:
        return jsonify({"sink": [], "source": "", "raw": ""})
    parsed = _parse_protocol_string(info["sink"])
    return jsonify({
        "sink": parsed,
        "source": info["source"],
        "raw": info["sink"],
    })


@app.route("/api/discover")
def api_discover():
    devices = discover_devices()
    return jsonify({"devices": devices})


@app.route("/api/configure", methods=["POST"])
def api_configure():
    global current_url
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"success": False, "error": "No data"}), 400
    base_url = data.get("base_url", "").rstrip("/")
    control_url = data.get("control_url", "")
    friendly_name = data.get("friendly_name", "Unknown")
    uuid = data.get("uuid", "")
    if not base_url or not control_url:
        return jsonify({"success": False, "error": "Missing base_url or control_url"}), 400
    device_config["base_url"] = base_url
    device_config["control_url"] = control_url
    device_config["rendering_control_url"] = f"{base_url}/RenderingControl/control"
    device_config["connection_manager_url"] = f"{base_url}/ConnectionManager/control"
    device_config["friendly_name"] = friendly_name
    device_config["uuid"] = uuid
    current_url = ""
    return jsonify({"success": True, "device": {
        "configured": True,
        "base_url": base_url,
        "friendly_name": friendly_name,
        "uuid": uuid,
    }})


@app.route("/api/play", methods=["POST"])
def api_play():
    global current_url
    data = request.get_json(silent=True)
    url = (data or {}).get("url", "").strip()
    if not url:
        return jsonify({"success": False, "error": "No URL provided"}), 400
    if not device_config["control_url"]:
        return jsonify({"success": False, "error": "No device configured. Scan and select a device first."}), 400
    current_url = url
    code, msg = set_uri(url)
    if code != 200:
        return jsonify({"success": False, "error": f"SetAVTransportURI failed ({code}): {msg[:200]}"}), 502
    time.sleep(0.3)
    code2, msg2 = send_play()
    if code2 != 200:
        return jsonify({"success": False, "error": f"Play failed ({code2}): {msg2[:200]}"}), 502
    return jsonify({"success": True, "status": "playing"})


@app.route("/api/resume", methods=["POST"])
def api_resume():
    if not device_config["control_url"]:
        return jsonify({"success": False, "error": "No device configured"}), 400
    code, msg = send_play()
    if code != 200:
        return jsonify({"success": False, "error": f"Resume failed ({code}): {msg[:200]}"}), 502
    return jsonify({"success": True, "status": "playing"})


@app.route("/api/pause", methods=["POST"])
def api_pause():
    code, msg = send_pause()
    if code != 200:
        return jsonify({"success": False, "error": f"Pause failed ({code}): {msg[:200]}"}), 502
    return jsonify({"success": True, "status": "paused"})


@app.route("/api/stop", methods=["POST"])
def api_stop():
    code, msg = send_stop()
    if code != 200:
        return jsonify({"success": False, "error": f"Stop failed ({code}): {msg[:200]}"}), 502
    return jsonify({"success": True, "status": "stopped"})


@app.route("/api/seek", methods=["POST"])
def api_seek():
    data = request.get_json(silent=True)
    target = (data or {}).get("position", "00:00:00")
    if not re.match(r"^\d{2}:\d{2}:\d{2}$", target):
        return jsonify({"success": False, "error": "Invalid time format"}), 400
    parts = target.split(":")
    h, m, s = int(parts[0]), int(parts[1]), int(parts[2])
    if m > 59 or s > 59:
        return jsonify({"success": False, "error": "Minutes and seconds must be 0-59"}), 400
    code, msg = send_seek(target)
    if code != 200:
        return jsonify({"success": False, "error": f"Seek failed ({code}): {msg[:200]}"}), 502
    return jsonify({"success": True})


@app.route("/api/volume", methods=["GET", "POST"])
def api_volume():
    if request.method == "GET":
        vol = get_volume()
        mute = get_mute()
        return jsonify({"volume": vol, "muted": mute})
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"success": False, "error": "No data"}), 400
    if "level" in data:
        level = data["level"]
        if not isinstance(level, int) or level < 0 or level > 100:
            return jsonify({"success": False, "error": "Volume must be 0-100"}), 400
        code, msg = set_volume(level)
        if code != 200:
            return jsonify({"success": False, "error": f"SetVolume failed ({code}): {msg[:200]}"}), 502
    if "muted" in data:
        code, msg = set_mute(bool(data["muted"]))
        if code != 200:
            return jsonify({"success": False, "error": f"SetMute failed ({code}): {msg[:200]}"}), 502
    return jsonify({"success": True})


@app.route("/api/status")
def api_status():
    if not device_config["control_url"]:
        return jsonify({"state": "NO_DEVICE", "duration": "00:00:00", "position": "00:00:00", "duration_sec": 0, "position_sec": 0, "progress": 0, "url": ""})
    dur, pos = get_position()
    state = get_transport_state()
    dur_sec = _time_to_sec(dur)
    pos_sec = _time_to_sec(pos)
    pct = (pos_sec / dur_sec * 100) if dur_sec > 0 else 0
    vol, mute = None, None
    if device_config.get("rendering_control_url"):
        vol = get_volume()
        mute = get_mute()
    return jsonify({
        "state": state,
        "duration": dur,
        "position": pos,
        "duration_sec": dur_sec,
        "position_sec": pos_sec,
        "progress": round(pct, 1),
        "url": current_url,
        "volume": vol,
        "muted": mute,
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5500, debug=False)
