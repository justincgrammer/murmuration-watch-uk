import hashlib
import json
import math
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path
import requests
from bs4 import BeautifulSoup

# Paths aligned with SSADM Workspace Structure
BASE_DIR = Path(__file__).resolve().parent.parent
ROOST_FILE = BASE_DIR / "data" / "roost_sites.json"
OUTPUT_FILE = BASE_DIR / "data" / "sightings.json"

HEADERS = {
    "User-Agent": "MurmurationWatchUK/1.0 (Kent & Sussex Regional Pipeline)"
}

# Bounding Box for Kent & Sussex (including Romney Marsh / Dungeness & West Sussex)
LAT_MIN, LAT_MAX = 50.70, 51.55
LON_MIN, LON_MAX = -0.95, 1.50
RETENTION_DAYS = 30


def load_roost_sites():
    with open(ROOST_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def load_existing_sightings():
    if not OUTPUT_FILE.exists():
        return []
    try:
        with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("sightings", [])
    except Exception:
        return []


def match_roost_site(text, roost_sites):
    """Match sighting location text against canonical Master Roosts or aliases."""
    haystack = text.lower()
    for site in roost_sites:
        candidates = [site["canonical_name"].lower()] + [a.lower() for a in site.get("aliases", [])]
        for name in candidates:
            if name and name in haystack:
                return site
    return None


def is_in_kent_or_sussex(lat, lon):
    if lat is None or lon is None:
        return False
    return (LAT_MIN <= lat <= LAT_MAX) and (LON_MIN <= lon <= LON_MAX)


def infer_county(text, lat, lon, matched_roost):
    if matched_roost:
        return matched_roost["county"]
    lower = text.lower()
    if any(k in lower for k in ["kent", "dungeness", "sandwich", "thanet", "cliffe", "swale", "sheppey", "foreland", "stodmarsh", "folkestone", "ashford", "maidstone", "canterbury"]):
        return "Kent"
    if "west sussex" in lower or any(k in lower for k in ["worthing", "pulborough", "chichester", "arundel", "bognor", "shoreham", "lancing"]):
        return "West Sussex"
    if "east sussex" in lower or any(k in lower for k in ["hastings", "rye", "brighton", "eastbourne", "newhaven", "pevensey", "seaford", "cuckmere"]):
        return "East Sussex"
    if lon is not None and lon >= 0.80:
        return "Kent"
    return None


def classify_activity(notes):
    lower = notes.lower()
    roost_keywords = ["murmuration", "roost", "pre-roost", "coming in to roost", "into roost", "dusk", "wheel", "swirl", "gathering", "sunset"]
    if any(kw in lower for kw in roost_keywords):
        return "Murmuration / Roost"
    return "Daytime Passage"


def extract_bird_count(notes):
    """Extract numerical flock estimate (e.g. 'c. 5,000', '2k-3k', '1000 Common Starling') as int."""
    # Handle shorthand ranges like '2k-3k' or '2k'
    k_range = re.search(r"\b(\d+(?:\.\d+)?)\s*k\s*[-–to]+\s*(\d+(?:\.\d+)?)\s*k\b", notes, re.IGNORECASE)
    if k_range:
        low, high = float(k_range.group(1)) * 1000, float(k_range.group(2)) * 1000
        return int((low + high) / 2)

    k_single = re.search(r"\b(\d+(?:\.\d+)?)\s*k\b", notes, re.IGNORECASE)
    if k_single:
        return int(float(k_single.group(1)) * 1000)

    # Prefer direct count immediately before 'Starling' if present
    starling_match = re.search(
        r"(?:c\.?|ca\.?|approx\.?|around|about|over|at least)?\s*(\d{1,3}(?:,\d{3})+|\d{1,6})\+?\s*(?:common\s+)?starlings?\b",
        notes,
        re.IGNORECASE
    )
    if starling_match:
        return int(starling_match.group(1).replace(",", ""))

    # Fallback: general flock estimate in Starling-specific notes
    general_match = re.search(
        r"(?:c\.?|ca\.?|approx\.?|around|about|over|at least)\s*(\d{1,3}(?:,\d{3})+|\d{2,6})\+?\s*(?:birds?|roosting|flying|at|dusk)?",
        notes,
        re.IGNORECASE
    )
    if general_match:
        return int(general_match.group(1).replace(",", ""))
    return None


def os_gridref_to_wgs84(gridref):
    """Convert UK OS National Grid reference (e.g. 'TR401697') to WGS84 (lat, lon)."""
    if not gridref:
        return None, None
    clean = re.sub(r"\s+", "", gridref.upper())
    match = re.match(r"^([A-Z]{2})(\d+)$", clean)
    if not match or len(match.group(2)) % 2 != 0:
        return None, None

    letters, digits = match.group(1), match.group(2)
    l1 = ord(letters[0]) - ord("A")
    l2 = ord(letters[1]) - ord("A")
    if l1 > 7:
        l1 -= 1
    if l2 > 7:
        l2 -= 1

    e100km = ((l1 - 2) % 5) * 5 + (l2 % 5)
    n100km = (19 - (l1 // 5) * 5) - (l2 // 5)
    if not (0 <= e100km <= 6 and 0 <= n100km <= 12):
        return None, None

    half = len(digits) // 2
    scale = 10 ** (5 - half)
    E = e100km * 100000 + int(digits[:half]) * scale + (scale / 2.0)
    N = n100km * 100000 + int(digits[half:]) * scale + (scale / 2.0)

    a, b = 6377563.396, 6356256.909
    F0 = 0.9996012717
    lat0, lon0 = math.radians(49.0), math.radians(-2.0)
    N0, E0 = -100000.0, 400000.0
    e2 = 1.0 - (b * b) / (a * a)
    n = (a - b) / (a + b)
    n2, n3 = n * n, n * n * n

    lat = lat0
    M = 0.0
    while True:
        lat = (N - N0 - M) / (a * F0) + lat
        Ma = (1 + n + (5 / 4) * (n2 + n3)) * (lat - lat0)
        Mb = (3 * n + 3 * n2 + (21 / 8) * n3) * math.sin(lat - lat0) * math.cos(lat + lat0)
        Mc = ((15 / 8) * (n2 + n3)) * math.sin(2 * (lat - lat0)) * math.cos(2 * (lat + lat0))
        Md = (35 / 24) * n3 * math.sin(3 * (lat - lat0)) * math.cos(3 * (lat + lat0))
        M = b * F0 * (Ma - Mb + Mc - Md)
        if abs(N - N0 - M) < 1e-5:
            break

    cos_lat, sin_lat = math.cos(lat), math.sin(lat)
    nu = a * F0 / math.sqrt(1 - e2 * sin_lat * sin_lat)
    rho = a * F0 * (1 - e2) / ((1 - e2 * sin_lat * sin_lat) ** 1.5)
    eta2 = nu / rho - 1.0
    tan_lat = math.tan(lat)
    tan2, tan4, tan6 = tan_lat ** 2, tan_lat ** 4, tan_lat ** 6
    sec_lat = 1.0 / cos_lat
    nu3, nu5, nu7 = nu ** 3, nu ** 5, nu ** 7

    VII = tan_lat / (2 * rho * nu)
    VIII = (tan_lat / (24 * rho * nu3)) * (5 + 3 * tan2 + eta2 - 9 * tan2 * eta2)
    IX = (tan_lat / (720 * rho * nu5)) * (61 + 90 * tan2 + 45 * tan4)
    X = sec_lat / nu
    XI = (sec_lat / (6 * nu3)) * (nu / rho + 2 * tan2)
    XII = (sec_lat / (120 * nu5)) * (5 + 28 * tan2 + 24 * tan4)
    XIIA = (sec_lat / (5040 * nu7)) * (61 + 662 * tan2 + 1320 * tan4 + 720 * tan6)

    dE = E - E0
    lat_osgb = lat - VII * (dE ** 2) + VIII * (dE ** 4) - IX * (dE ** 6)
    lon_osgb = lon0 + X * dE - XI * (dE ** 3) + XII * (dE ** 5) - XIIA * (dE ** 7)

    sin_la, cos_la = math.sin(lat_osgb), math.cos(lat_osgb)
    sin_lo, cos_lo = math.sin(lon_osgb), math.cos(lon_osgb)
    nu_h = a / math.sqrt(1 - e2 * sin_la * sin_la)
    x1 = nu_h * cos_la * cos_lo
    y1 = nu_h * cos_la * sin_lo
    z1 = (1 - e2) * nu_h * sin_la

    tx, ty, tz = 446.448, -125.157, 542.060
    s = -20.4894e-6
    rx = math.radians(0.1502 / 3600.0)
    ry = math.radians(0.2470 / 3600.0)
    rz = math.radians(0.8421 / 3600.0)

    x2 = tx + (1 + s) * x1 - rz * y1 + ry * z1
    y2 = ty + rz * x1 + (1 + s) * y1 - rx * z1
    z2 = tz - ry * x1 + rx * y1 + (1 + s) * z1

    a2, b2 = 6378137.0, 6356752.3142
    e2_wgs = 1.0 - (b2 * b2) / (a2 * a2)
    p = math.hypot(x2, y2)
    lat_wgs = math.atan2(z2, p * (1 - e2_wgs))
    for _ in range(5):
        nu_w = a2 / math.sqrt(1 - e2_wgs * (math.sin(lat_wgs) ** 2))
        lat_wgs = math.atan2(z2 + e2_wgs * nu_w * math.sin(lat_wgs), p)
    lon_wgs = math.atan2(y2, x2)

    return round(math.degrees(lat_wgs), 4), round(math.degrees(lon_wgs), 4)


def make_id(prefix, seed):
    digest = hashlib.sha1(seed.encode("utf-8")).hexdigest()[:12]
    return f"{prefix}-{digest}"


def parse_uk_date(date_str):
    clean = re.sub(r"(\d+)(st|nd|rd|th)", r"\1", date_str.strip())
    for fmt in ("%d/%m/%Y", "%d/%m/%y", "%A %d %B %Y", "%d %B %Y", "%d %b %Y", "%d %b %y"):
        try:
            return datetime.strptime(clean, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def fetch_src_001_sos(roost_sites):
    index_url = "https://sos.org.uk/weekly-sightings-report/"
    records = []
    try:
        res = requests.get(index_url, headers=HEADERS, timeout=15)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, "html.parser")

        report_links = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "sos.org.uk/weekly-sightings-report/" in href and href.rstrip("/") != index_url.rstrip("/"):
                if href not in report_links:
                    report_links.append(href)

        for post_url in report_links[:3]:
            p_res = requests.get(post_url, headers=HEADERS, timeout=15)
            if p_res.status_code != 200:
                continue
            p_soup = BeautifulSoup(p_res.text, "html.parser")
            full_text = " ".join(p_soup.get_text(" ").split())

            date_match = re.search(r"(\d{1,2}\s+[A-Za-z]+\s+20\d{2})", full_text)
            obs_date = parse_uk_date(date_match.group(1)) if date_match else datetime.now(timezone.utc).strftime("%Y-%m-%d")

            for sentence in re.split(r"(?<=[.!?])\s+", full_text):
                if "starling" not in sentence.lower():
                    continue
                matched_roost = match_roost_site(sentence, roost_sites)
                if not matched_roost:
                    continue
                county = matched_roost.get("county", "East Sussex")
                site_name = matched_roost["canonical_name"]
                records.append({
                    "sighting_id": make_id("sos", f"{obs_date}-{site_name}-{sentence[:40]}"),
                    "source_id": "SRC-001",
                    "site_id": matched_roost["site_id"],
                    "site_name": site_name,
                    "county": county,
                    "observation_date": obs_date,
                    "latitude": matched_roost["latitude"],
                    "longitude": matched_roost["longitude"],
                    "coord_source": "roost_lookup",
                    "bird_count": extract_bird_count(sentence),
                    "activity_type": classify_activity(sentence),
                    "raw_notes": sentence[:240],
                    "source_url": post_url
                })
    except Exception as exc:
        print(f"[WARN] SRC-001 fetch issue: {exc}")
    return records


def fetch_src_002_dungeness(roost_sites):
    url = "http://www.dungenessbirdobs.org.uk/"
    records = []
    try:
        res = requests.get(url, headers=HEADERS, timeout=15)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, "html.parser")
        dung_roost = match_roost_site("Dungeness", roost_sites)

        for block in soup.find_all(["p", "div", "article"]):
            text = " ".join(block.get_text(" ").split())
            if len(text) < 40 or len(text) > 1500:
                continue
            if "starling" not in text.lower():
                continue

            sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if "starling" in s.lower()]
            if not sentences:
                continue
            notes = " ".join(sentences)
            obs_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

            records.append({
                "sighting_id": make_id("dbo", f"{obs_date}-{notes[:50]}"),
                "source_id": "SRC-002",
                "site_id": dung_roost["site_id"] if dung_roost else "ROOST-002",
                "site_name": "Dungeness RSPB & Peninsula",
                "county": "Kent",
                "observation_date": obs_date,
                "latitude": dung_roost["latitude"] if dung_roost else 50.9165,
                "longitude": dung_roost["longitude"] if dung_roost else 0.9635,
                "coord_source": "roost_lookup",
                "bird_count": extract_bird_count(notes),
                "activity_type": classify_activity(notes),
                "raw_notes": notes,
                "source_url": url
            })
            break
    except Exception as exc:
        print(f"[WARN] SRC-002 fetch issue: {exc}")
    return records


def fetch_src_003_kos(roost_sites):
    url = "https://www.kentos.org.uk/index.php/sightings/bird-news?view=news"
    records = []
    try:
        res = requests.get(url, headers=HEADERS, timeout=15)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, "html.parser")

        for visit in soup.find_all("div", class_="gc-birdsightings-list-visit"):
            p_tag = visit.find("p")
            if not p_tag:
                continue
            p_text = " ".join(p_tag.get_text(" ").split())
            if "starling" not in p_text.lower():
                continue

            starling_parts = [
                seg.strip() for seg in p_text.split(",")
                if "starling" in seg.lower()
            ]
            notes = "; ".join(starling_parts) if starling_parts else p_text

            prev_h3 = visit.find_previous_sibling("h3")
            obs_date = parse_uk_date(prev_h3.get_text(" ", strip=True)) if prev_h3 else datetime.now(timezone.utc).strftime("%Y-%m-%d")

            h4 = visit.find("h4")
            site_name = "Kent Site"
            gridref = None
            if h4:
                grid_span = h4.find("span", class_="gc-birdsightings-gridrefs")
                if grid_span:
                    gridref = grid_span.get("data-gridref")
                first_text = next((t.strip() for t in h4.strings if t.strip()), "")
                if first_text:
                    site_name = first_text

            matched_roost = match_roost_site(f"{site_name} {notes}", roost_sites)
            lat, lon = os_gridref_to_wgs84(gridref)
            coord_source = "source_gridref"

            if (lat is None or lon is None) and matched_roost:
                lat, lon = matched_roost["latitude"], matched_roost["longitude"]
                coord_source = "roost_lookup"

            if not is_in_kent_or_sussex(lat, lon):
                continue

            records.append({
                "sighting_id": make_id("kos", f"{obs_date}-{site_name}-{notes[:40]}"),
                "source_id": "SRC-003",
                "site_id": matched_roost["site_id"] if matched_roost else None,
                "site_name": site_name,
                "county": "Kent",
                "observation_date": obs_date,
                "latitude": lat,
                "longitude": lon,
                "coord_source": coord_source,
                "bird_count": extract_bird_count(notes),
                "activity_type": classify_activity(notes),
                "raw_notes": notes,
                "source_url": url
            })
    except Exception as exc:
        print(f"[WARN] SRC-003 fetch issue: {exc}")
    return records


def fetch_src_004_starlings_uk(roost_sites):
    """Extract dated 2026 field updates for Kent & Sussex from Starlings in the UK KML."""
    kml_url = "https://www.google.com/maps/d/kml?mid=1Sx30KAMlL9y4y6DXlzjqv4D_Qx8&forcekml=1"
    page_url = "https://www.starlingsintheuk.co.uk/roost-map.html"
    records = []
    try:
        res = requests.get(kml_url, headers=HEADERS, timeout=20)
        res.raise_for_status()
        root = ET.fromstring(res.text)
        ns = {"kml": "http://www.opengis.net/kml/2.2"}

        for pm in root.findall(".//kml:Placemark", ns):
            name_el = pm.find("kml:name", ns)
            desc_el = pm.find("kml:description", ns)
            coord_el = pm.find(".//kml:Point/kml:coordinates", ns)
            if coord_el is None or not coord_el.text:
                continue

            parts = coord_el.text.strip().split(",")
            if len(parts) < 2:
                continue
            lon, lat = round(float(parts[0]), 4), round(float(parts[1]), 4)
            if not is_in_kent_or_sussex(lat, lon):
                continue

            raw_name = name_el.text.strip() if (name_el is not None and name_el.text) else "Roost Site"
            # Strictly keep Kent, East Sussex, and West Sussex placemarks
            if not re.match(r"^(Kent|East Sussex|West Sussex)\b", raw_name, re.IGNORECASE):
                continue

            raw_desc = desc_el.text if (desc_el is not None and desc_el.text) else ""
            clean_desc = " ".join(BeautifulSoup(raw_desc, "html.parser").get_text(" ").split())
            if "deactivated" in clean_desc[:40].lower():
                continue

            # Look for a 2026 field report date (e.g. 4/11/26, 01/11/26, 18/10/26)
            date_match = re.search(r"\b(\d{1,2}/\d{1,2}/26)\b", clean_desc)
            if not date_match:
                continue

            obs_date = parse_uk_date(date_match.group(1))
            matched_roost = match_roost_site(raw_name, roost_sites)
            if not matched_roost:
                matched_roost = match_roost_site(clean_desc, roost_sites)
            county = infer_county(raw_name, lat, lon, matched_roost)
            if not county:
                continue

            site_name = matched_roost["canonical_name"] if matched_roost else raw_name
            # Isolate only the latest top report (before any older Update/Reactivated/New block)
            latest_report = re.split(
                r"\s+(?:Update|REACTIVATED|Reactivated|NEW|New|DEACTIVATED|Deactivated)[,:\s]+\d{1,2}",
                clean_desc,
                maxsplit=1
            )[0].strip()
            snippet = latest_report

            records.append({
                "sighting_id": make_id("suk", f"{obs_date}-{site_name}"),
                "source_id": "SRC-004",
                "site_id": matched_roost["site_id"] if matched_roost else None,
                "site_name": site_name,
                "county": county,
                "observation_date": obs_date,
                "latitude": lat,
                "longitude": lon,
                "coord_source": "source_kml",
                "bird_count": extract_bird_count(clean_desc),
                "activity_type": "Murmuration / Roost",
                "raw_notes": snippet,
                "source_url": page_url
            })
    except Exception as exc:
        print(f"[WARN] SRC-004 fetch issue: {exc}")
    return records

def fetch_src_005_swt_rye(roost_sites):
    news_url = "https://sussexwildlifetrust.org.uk/news/"
    records = []
    try:
        res = requests.get(news_url, headers=HEADERS, timeout=15)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, "html.parser")

        sightings_links = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "rye-harbour-nature-reserve-sightings" in href and href not in sightings_links:
                sightings_links.append(href)

        rye_roost = next((r for r in roost_sites if r["site_id"] == "ROOST-004"), None)
        for post_url in sightings_links[:2]:
            p_res = requests.get(post_url, headers=HEADERS, timeout=15)
            if p_res.status_code != 200:
                continue
            p_soup = BeautifulSoup(p_res.text, "html.parser")
            full_text = " ".join(p_soup.get_text(" ").split())

            date_match = re.search(r"(\d{1,2}\s+[A-Za-z]+\s+20\d{2})", full_text)
            obs_date = parse_uk_date(date_match.group(1)) if date_match else datetime.now(timezone.utc).strftime("%Y-%m-%d")

            for sentence in re.split(r"(?<=[.!?])\s+", full_text):
                if "starling" not in sentence.lower():
                    continue
                site_name = rye_roost["canonical_name"] if rye_roost else "Rye Harbour Nature Reserve"
                lat = rye_roost["latitude"] if rye_roost else 50.9355
                lon = rye_roost["longitude"] if rye_roost else 0.7645
                records.append({
                    "sighting_id": make_id("swt", f"{obs_date}-{site_name}-{sentence[:40]}"),
                    "source_id": "SRC-005",
                    "site_id": "ROOST-004",
                    "site_name": site_name,
                    "county": "East Sussex",
                    "observation_date": obs_date,
                    "latitude": lat,
                    "longitude": lon,
                    "coord_source": "roost_lookup",
                    "bird_count": extract_bird_count(sentence),
                    "activity_type": classify_activity(sentence),
                    "raw_notes": sentence[:240],
                    "source_url": post_url
                })
    except Exception as exc:
        print(f"[WARN] SRC-005 fetch issue: {exc}")
    return records


def main():
    roost_sites = load_roost_sites()
    existing = load_existing_sightings()

    fresh = []
    fresh.extend(fetch_src_001_sos(roost_sites))
    fresh.extend(fetch_src_002_dungeness(roost_sites))
    fresh.extend(fetch_src_003_kos(roost_sites))
    fresh.extend(fetch_src_004_starlings_uk(roost_sites))
    fresh.extend(fetch_src_005_swt_rye(roost_sites))

    # Non-destructive merge: retain records within RETENTION_DAYS and overwrite with fresher updates
    cutoff = (datetime.now(timezone.utc) - timedelta(days=RETENTION_DAYS)).strftime("%Y-%m-%d")
    merged = {}
    for item in existing + fresh:
        if item.get("observation_date", "9999-99-99") >= cutoff:
            merged[item["sighting_id"]] = item

    deduped = sorted(
        merged.values(),
        key=lambda r: (r.get("observation_date", ""), r.get("site_name", "")),
        reverse=True
    )

    payload = {
        "metadata": {
            "schema_version": "1.0",
            "region": "Kent & Sussex",
            "last_updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "total_sightings": len(deduped),
            "sources_checked": ["SRC-001", "SRC-002", "SRC-003", "SRC-004", "SRC-005"]
        },
        "sightings": deduped
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    print(f"Saved {len(deduped)} v1.0 sighting(s) across Kent & Sussex to {OUTPUT_FILE}")
    for item in deduped:
        cnt = item["bird_count"] if item["bird_count"] is not None else "n/a"
        print(
            f" - [{item['sighting_id']}] ({item['county']}) {item['site_name']} | "
            f"Date: {item['observation_date']} | Count: {cnt} | {item['activity_type']}"
        )


if __name__ == "__main__":
    main()