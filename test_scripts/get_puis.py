import xml.etree.ElementTree as ET
import requests

# Fetch the XML from the URL
url = "https://demos.lightstreamer.com/ISSLive/assets/PUIList.xml"
response = requests.get(url)
response.raise_for_status()  # Ensure we notice bad responses

# Parse the XML content
tree = ET.ElementTree(ET.fromstring(response.content))
root = tree.getroot()

# Extract all Public_PUI values from the XML
public_puis = [elem.text for elem in root.findall(".//Public_PUI") if elem.text]

# Sort the list alphabetically
public_puis.sort()

# Join the sorted list into a comma-delimited string with each value in quotes
result = ",".join(f'"{pui}"' for pui in public_puis)

print(result)
