import requests

# Target device and control URL
device_base_url = "http://192.168.1.112:62343"
control_url = f"{device_base_url}/AVTransport/control"

# Media URI — change this to your own image if desired
image_url = "http://192.168.1.108:8090/streamvideo"

# SOAP headers
headers = {
    "Content-Type": "text/xml; charset=\"utf-8\"",
    "SOAPAction": "\"urn:schemas-upnp-org:service:AVTransport:1#SetAVTransportURI\""
}

# SOAP body
soap_body = f"""<?xml version="1.0" encoding="utf-8"?>
<s:Envelope 
    xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" 
    s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
  <s:Body>
    <u:SetAVTransportURI 
        xmlns:u="urn:schemas-upnp-org:service:AVTransport:1">
      <InstanceID>0</InstanceID>
      <CurrentURI>{image_url}</CurrentURI>
      <CurrentURIMetaData></CurrentURIMetaData>
    </u:SetAVTransportURI>
  </s:Body>
</s:Envelope>"""

# Send the SetAVTransportURI command
response = requests.post(control_url, data=soap_body, headers=headers)
print("SetAVTransportURI response:", response.status_code, response.text)

# Now send the Play command
headers["SOAPAction"] = "\"urn:schemas-upnp-org:service:AVTransport:1#Play\""
soap_body_play = """<?xml version="1.0" encoding="utf-8"?>
<s:Envelope 
    xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" 
    s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
  <s:Body>
    <u:Play xmlns:u="urn:schemas-upnp-org:service:AVTransport:1">
      <InstanceID>0</InstanceID>
      <Speed>1</Speed>
    </u:Play>
  </s:Body>
</s:Envelope>"""

response_play = requests.post(control_url, data=soap_body_play, headers=headers)
print("Play response:", response_play.status_code, response_play.text)
