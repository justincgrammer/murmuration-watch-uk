import xml.etree.ElementTree as ET
import requests

KML_URL = "https://www.google.com/maps/d/kml?mid=1Sx30KAMlL9y4y6DXlzjqv4D_Qx8&forcekml=1"
HEADERS = {
    "User-Agent": "MurmurationWatchUK/1.0 (Kent & Sussex Regional Pipeline)"
}

# Kent & Sussex bounding box
LAT_MIN, LAT_MAX = 50.70, 51.55
LON_MIN, LON_MAX = -0.95, 1.50


def probe_mymaps_kml():
    print(f"Fetching KML from {KML_URL} ...")
    res = requests.get(KML_URL, headers=HEADERS, timeout=20)
    print(f"HTTP Status: {res.status_code} | Payload size: {len(res.text)} chars")
    res.raise_for_status()

    root = ET.fromstring(res.text)
    ns = {"kml": "http://www.opengis.net/kml/2.2"}

    total_placemarks = 0
    regional_hits = []

    for pm in root.findall(".//kml:Placemark", ns):
        total_placemarks += 1
        name_el = pm.find("kml:name", ns)
        desc_el = pm.find("kml:description", ns)
        coord_el = pm.find(".//kml:Point/kml:coordinates", ns)

        if coord_el is None or not coord_el.text:
            continue

        parts = coord_el.text.strip().split(",")
        if len(parts) < 2:
            continue

        lon, lat = float(parts[0]), float(parts[1])
        if (LAT_MIN <= lat <= LAT_MAX) and (LON_MIN <= lon <= LON_MAX):
            name = name_el.text.strip() if (name_el is not None and name_el.text) else "Unnamed Site"
            desc = desc_el.text.strip() if (desc_el is not None and desc_el.text) else ""
            regional_hits.append((name, round(lat, 4), round(lon, 4), desc))

    print(f"Total UK placemarks scanned: {total_placemarks}")
    print(f"Kent & Sussex regional placemarks found: {len(regional_hits)}\n")

    for name, lat, lon, desc in regional_hits:
        clean_desc = " ".join(desc.split())[:180]
        print(f" - {name} | Lat: {lat}, Lon: {lon}")
        if clean_desc:
            print(f"   Notes: {clean_desc}")


if __name__ == "__main__":
    probe_mymaps_kml()