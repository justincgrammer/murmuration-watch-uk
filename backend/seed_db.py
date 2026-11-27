import json
from pathlib import Path
from init_db import get_connection, init_database

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"

COUNTIES = [
    ("Kent", "kent", "South East", 51.2400, 0.7500, 9),
    ("Sussex", "sussex", "South East", 50.9200, -0.1400, 9),
    ("Cumbria", "cumbria", "North West", 54.4609, -2.8500, 9),
    ("Lancashire", "lancashire", "North West", 53.9500, -2.6500, 9),
]

NORTH_WEST_ROOSTS = [
    {
        "county_slug": "cumbria",
        "name": "North Walney & Jubilee Bridge (Barrow-in-Furness)",
        "latitude": 54.1135,
        "longitude": -3.2412,
        "parking_lat": 54.1128,
        "parking_lng": -3.2395,
        "parking_access": "Jubilee Bridge / North Walney Nature Reserve parking (LA14 3YF).",
        "habitat_type": "Coastal Saltmarsh & Bridge Girders",
        "best_months": "Oct-Feb",
        "reliability": "High",
        "status": "active",
        "notes": "Roughly 45 mins southwest of Kendal; starlings swirl over Walney Channel before dropping under Jubilee Bridge or into North Walney reedbeds.",
    },
    {
        "county_slug": "cumbria",
        "name": "Siddick Ponds Nature Reserve (Workington)",
        "latitude": 54.6618,
        "longitude": -3.5415,
        "parking_lat": 54.6605,
        "parking_lng": -3.5428,
        "parking_access": "Siddick Ponds lay-by / Northside Road (CA14 1LE).",
        "habitat_type": "Coastal Wetland & Reedbed",
        "best_months": "Oct-Feb",
        "reliability": "High",
        "status": "active",
        "notes": "Reliable West Cumbria sunset roost; best viewed from the public footpath overlooking the main reedbed lagoon.",
    },
    {
        "county_slug": "cumbria",
        "name": "Watchtree Nature Reserve (Wigton)",
        "latitude": 54.8532,
        "longitude": -3.1124,
        "parking_lat": 54.8515,
        "parking_lng": -3.1102,
        "parking_access": "Watchtree Reserve visitor car park (CA7 0NL); check reserve winter gate times.",
        "habitat_type": "Solway Plain Wetland & Reedbed",
        "best_months": "Nov-Feb",
        "reliability": "Medium",
        "status": "active",
        "notes": "Community-run reserve on the Solway Plain with wide open horizons for late-afternoon sunset displays.",
    },
    {
        "county_slug": "cumbria",
        "name": "Silloth & Solway Coast",
        "latitude": 54.8631,
        "longitude": -3.3765,
        "parking_lat": 54.8652,
        "parking_lng": -3.3854,
        "parking_access": "Silloth Green / seafront parking (CA7 4AA).",
        "habitat_type": "Coastal Scrub & Estuary Edge",
        "best_months": "Nov-Feb",
        "reliability": "Medium",
        "status": "occasional",
        "notes": "Traditional winter roost site along the Solway Firth coastal strip; dress warmly against estuary winds.",
    },
    {
        "county_slug": "cumbria",
        "name": "Gretna & Metal Bridge (Solway Border Marshes)",
        "latitude": 54.9825,
        "longitude": -3.0582,
        "parking_lat": 54.9794,
        "parking_lng": -3.0561,
        "parking_access": "Metal Bridge / Gretna Green Old Toll Bar lay-by (CA6 5HP).",
        "habitat_type": "Tidal Estuary & Woodland",
        "best_months": "Oct-Mar",
        "reliability": "High",
        "status": "active",
        "notes": "Famous large mobile winter gatherings straddling the Cumbrian/Scottish border along the River Esk and Solway marshes.",
    },
    {
        "county_slug": "lancashire",
        "name": "WWT Martin Mere Wetland Centre (Burscough)",
        "latitude": 53.6214,
        "longitude": -2.8758,
        "parking_lat": 53.6202,
        "parking_lng": -2.8719,
        "parking_access": "WWT Martin Mere main car park (L40 0TA); closes 4:30pm in winter.",
        "habitat_type": "Managed Wetland & Reedbed",
        "best_months": "Oct-Feb",
        "reliability": "Very High",
        "status": "active",
        "notes": "Tens of thousands gather over the reedbeds; arrives before 4:30pm winter closing when flocks drop straight into roost.",
    },
    {
        "county_slug": "lancashire",
        "name": "Blackpool North Pier",
        "latitude": 53.8184,
        "longitude": -3.0588,
        "parking_lat": 53.8176,
        "parking_lng": -3.0542,
        "parking_access": "Talbot Road multi-storey / promenade parking (FY1 1NE).",
        "habitat_type": "Victorian Iron Pier & Seafront",
        "best_months": "Nov-Feb",
        "reliability": "High",
        "status": "active",
        "notes": "Classic urban coastal roost where flocks swirl above the promenade before settling beneath the pier decking.",
    },
    {
        "county_slug": "lancashire",
        "name": "Marton Mere Local Nature Reserve (Blackpool)",
        "latitude": 53.8058,
        "longitude": -3.0052,
        "parking_lat": 53.8041,
        "parking_lng": -3.0079,
        "parking_access": "Marton Mere Reserve car park, Lawson Road (FY3 9UR).",
        "habitat_type": "Freshwater Mere & Reedbed",
        "best_months": "Nov-Feb",
        "reliability": "Medium",
        "status": "occasional",
        "notes": "Inland reedbed roost east of Blackpool that regularly trades winter starling flocks with the seafront piers.",
    },
    {
        "county_slug": "lancashire",
        "name": "Glasson Dock & Lune Estuary (Lancaster)",
        "latitude": 53.9982,
        "longitude": -2.8456,
        "parking_lat": 53.9971,
        "parking_lng": -2.8469,
        "parking_access": "Glasson Dock Canal Basin car park (LA2 0DB).",
        "habitat_type": "Tidal Basin & Saltmarsh",
        "best_months": "Oct-Feb",
        "reliability": "Medium",
        "status": "active",
        "notes": "Only ~30 mins south of Kendal; flocks gather over the River Lune estuary and dock basin around sunset.",
    },
    {
        "county_slug": "lancashire",
        "name": "RSPB Leighton Moss (Silverdale)",
        "latitude": 54.1678,
        "longitude": -2.7965,
        "parking_lat": 54.1665,
        "parking_lng": -2.7989,
        "parking_access": "RSPB main car park off Storrs Lane (LA5 0SW); level paths & Skytower viewing.",
        "habitat_type": "Reedbed",
        "best_months": "Oct-Feb",
        "reliability": "Very High",
        "status": "active",
        "notes": "Largest reedbed in North West England; 10,000–50,000+ starlings regularly gather at dusk, just 20 mins south of Kendal.",
    },
    {
        "county_slug": "lancashire",
        "name": "Brockholes Nature Reserve (Preston)",
        "latitude": 53.7667,
        "longitude": -2.6335,
        "parking_lat": 53.7675,
        "parking_lng": -2.6392,
        "parking_access": "Paid reserve car park off M6 J31 (PR5 0AG); easy walk to floating visitor village.",
        "habitat_type": "Lakeside Reedbed",
        "best_months": "Nov-Feb",
        "reliability": "High",
        "status": "active",
        "notes": "Large flocks swirl over Meadow Lake and the floating visitor village before dropping into the reeds.",
    },
    {
        "county_slug": "lancashire",
        "name": "Blackpool North Pier",
        "latitude": 53.8194,
        "longitude": -3.0585,
        "parking_lat": 53.8188,
        "parking_lng": -3.0550,
        "parking_access": "Promenade & Talbot Road car parks (FY1 1NE); flat seafront viewing.",
        "habitat_type": "Coastal Pier",
        "best_months": "Nov-Feb",
        "reliability": "High",
        "status": "active",
        "notes": "Classic coastal pier roost; best viewed from the promenade with the western sunset behind the flock.",
    },
    {
        "county_slug": "cumbria",
        "name": "Kent Estuary & Foulshaw Moss Edge (Kendal South)",
        "latitude": 54.2365,
        "longitude": -2.8180,
        "parking_lat": 54.2382,
        "parking_lng": -2.8265,
        "parking_access": "Cumbria Wildlife Trust Foulshaw Moss car park off A590 (LA11 6SP) or Arnside Promenade.",
        "habitat_type": "Estuary Reedbed & Moss",
        "best_months": "Oct-Feb",
        "reliability": "Moderate",
        "status": "active",
        "notes": "Closest roost corridor to Kendal; flocks feed across Lyth Valley pastures before heading toward the Kent estuary reeds.",
    },
    {
        "county_slug": "cumbria",
        "name": "Jubilee Bridge & Walney Channel (Barrow)",
        "latitude": 54.1082,
        "longitude": -3.2355,
        "parking_lat": 54.1075,
        "parking_lng": -3.2390,
        "parking_access": "Promenade parking near Jubilee Bridge on Walney Island (LA14 3AA).",
        "habitat_type": "Coastal Bridge & Estuary",
        "best_months": "Nov-Feb",
        "reliability": "High",
        "status": "active",
        "notes": "Thousands of birds gather over Walney Channel before roosting beneath the bridge girders at dusk.",
    },
    {
        "county_slug": "cumbria",
        "name": "Watchtree Nature Reserve (Great Orton, Carlisle)",
        "latitude": 54.8692,
        "longitude": -3.0655,
        "parking_lat": 54.8678,
        "parking_lng": -3.0620,
        "parking_access": "Reserve visitor car park off A596 at Great Orton (CA5 6NL).",
        "habitat_type": "Wetland & Scrub",
        "best_months": "Nov-Feb",
        "reliability": "High",
        "status": "active",
        "notes": "North Cumbria wetland reserve hosting regular winter pre-roost displays over the ponds and reedbeds.",
    },
]


def infer_county_id(lat: float, lng: float, county_map: dict[str, int]) -> int:
    if lat > 54.20:
        return county_map["cumbria"]
    if lat > 53.50:
        return county_map["lancashire"]
    if lng >= 0.25 or lat >= 51.12:
        return county_map["kent"]
    return county_map["sussex"]


def seed_all() -> None:
    init_database()

    with get_connection() as conn:
        for name, slug, region, lat, lng, zoom in COUNTIES:
            conn.execute(
                """
                INSERT INTO counties (name, slug, region, center_lat, center_lng, default_zoom)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(slug) DO UPDATE SET
                    name = excluded.name,
                    region = excluded.region,
                    center_lat = excluded.center_lat,
                    center_lng = excluded.center_lng,
                    default_zoom = excluded.default_zoom
                """,
                (name, slug, region, lat, lng, zoom),
            )

        county_rows = conn.execute("SELECT id, slug FROM counties").fetchall()
        county_map = {row["slug"]: row["id"] for row in county_rows}

        roost_json_path = DATA_DIR / "roost_sites.json"
        imported_roosts = 0
        if roost_json_path.exists():
            raw_roosts = json.loads(roost_json_path.read_text(encoding="utf-8"))
            if isinstance(raw_roosts, dict):
                raw_roosts = raw_roosts.get("roosts", raw_roosts.get("sites", []))

            for r in raw_roosts:
                name = r.get("canonical_name") or r.get("name") or r.get("title")
                lat = r.get("lat") if r.get("lat") is not None else r.get("latitude")
                lng = r.get("lng") if r.get("lng") is not None else r.get("longitude")
                if not name or lat is None or lng is None:
                    continue

                raw_county = str(r.get("county", "")).strip().lower()
                if "sussex" in raw_county:
                    cid = county_map["sussex"]
                elif "kent" in raw_county:
                    cid = county_map["kent"]
                elif "cumbria" in raw_county:
                    cid = county_map["cumbria"]
                elif "lancashire" in raw_county:
                    cid = county_map["lancashire"]
                else:
                    cid = infer_county_id(float(lat), float(lng), county_map)

                notes = (r.get("notes") or r.get("description") or "").strip()
                aliases = r.get("aliases") or []
                if aliases:
                    alias_text = f"Also known as: {', '.join(aliases)}."
                    notes = f"{notes} {alias_text}".strip()

                conn.execute(
                    """
                    INSERT OR IGNORE INTO roost_sites
                    (county_id, name, latitude, longitude, habitat_type, reliability, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        cid,
                        name.strip(),
                        float(lat),
                        float(lng),
                        r.get("habitat_type") or r.get("habitat") or "Reedbed / Coastal",
                        r.get("reliability") or "High",
                        notes,
                    ),
                )
                imported_roosts += 1

        for nr in NORTH_WEST_ROOSTS:
            conn.execute(
                """
                INSERT INTO roost_sites (
                    county_id, name, latitude, longitude, parking_lat, parking_lng,
                    parking_access, habitat_type, best_months, reliability, status, notes
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(county_id, name) DO UPDATE SET
                    latitude = excluded.latitude,
                    longitude = excluded.longitude,
                    parking_lat = excluded.parking_lat,
                    parking_lng = excluded.parking_lng,
                    parking_access = excluded.parking_access,
                    habitat_type = excluded.habitat_type,
                    best_months = excluded.best_months,
                    reliability = excluded.reliability,
                    status = excluded.status,
                    notes = excluded.notes
                """,
                (
                    county_map[nr["county_slug"]],
                    nr["name"],
                    nr["latitude"],
                    nr["longitude"],
                    nr["parking_lat"],
                    nr["parking_lng"],
                    nr["parking_access"],
                    nr["habitat_type"],
                    nr["best_months"],
                    nr["reliability"],
                    nr["status"],
                    nr["notes"],
                ),
            )

        sightings_json_path = DATA_DIR / "sightings.json"
        imported_sightings = 0
        if sightings_json_path.exists():
            raw_sightings = json.loads(sightings_json_path.read_text(encoding="utf-8"))
            if isinstance(raw_sightings, dict):
                raw_sightings = raw_sightings.get("sightings", [])

            existing_count = conn.execute("SELECT COUNT(*) FROM sightings").fetchone()[0]
            if existing_count == 0:
                for s in raw_sightings:
                    lat = s.get("lat") if s.get("lat") is not None else s.get("latitude")
                    lng = s.get("lng") if s.get("lng") is not None else s.get("longitude")
                    if lat is None or lng is None:
                        continue
                    cid = infer_county_id(float(lat), float(lng), county_map)
                    conn.execute(
                        """
                        INSERT INTO sightings (
                            county_id, custom_location_name, latitude, longitude,
                            observed_date, observed_time, flock_size, behaviour_notes, source
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            cid,
                            s.get("location") or s.get("site_name") or "Imported Sighting",
                            float(lat),
                            float(lng),
                            s.get("date") or s.get("observed_date") or "2026-11-01",
                            s.get("time") or s.get("observed_time"),
                            str(s.get("flock_size") or s.get("count") or ""),
                            s.get("notes") or s.get("behaviour_notes") or "",
                            s.get("source") or "scraper",
                        ),
                    )
                    imported_sightings += 1

        summary = conn.execute(
            """
            SELECT c.region, c.name, COUNT(r.id) AS roost_count
            FROM counties c
            LEFT JOIN roost_sites r ON r.county_id = c.id
            GROUP BY c.id
            ORDER BY c.region, c.name
            """
        ).fetchall()

    print(f"JSON roosts checked: {imported_roosts} | JSON sightings imported: {imported_sightings}")
    print("\n--- Current SQLite Roost Summary ---")
    for row in summary:
        print(f"  [{row['region']}] {row['name']}: {row['roost_count']} roost sites")


if __name__ == "__main__":
    seed_all()