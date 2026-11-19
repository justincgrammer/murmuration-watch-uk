import json
import re
from collections import Counter
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
ROOSTS_FILE = BASE_DIR / "data" / "roost_sites.json"
SIGHTINGS_FILE = BASE_DIR / "data" / "sightings.json"

REQUIRED_FIELDS = [
    "sighting_id", "source_id", "site_id", "site_name", "county",
    "observation_date", "latitude", "longitude", "coord_source",
    "bird_count", "activity_type", "raw_notes", "source_url"
]
VALID_COUNTIES = {"Kent", "East Sussex", "West Sussex"}


def run_audit():
    print("=== MURMURATION WATCH UK: DATA PIPELINE AUDIT ===\n")

    roosts_data = json.loads(ROOSTS_FILE.read_text(encoding="utf-8"))
    roosts = roosts_data.get("roost_sites", roosts_data) if isinstance(roosts_data, dict) else roosts_data
    roost_ids = {r["site_id"] for r in roosts}
    print(f"[1] Master Roosts Loaded: {len(roosts)} canonical sites")

    # Check duplicate roost coordinates or IDs
    if len(roost_ids) != len(roosts):
        print("    [FAIL] Duplicate site_id found in roost_sites.json!")
    else:
        print("    [PASS] All site_id primary keys are unique.")

    payload = json.loads(SIGHTINGS_FILE.read_text(encoding="utf-8"))
    meta = payload.get("metadata", {})
    sightings = payload.get("sightings", [])
    print(f"\n[2] Sightings Feed Loaded: {len(sightings)} records (Schema v{meta.get('schema_version')})")
    print(f"    Last Updated: {meta.get('last_updated')} | Sources Checked: {meta.get('sources_checked')}")

    errors = []
    warnings = []
    seen_ids = set()
    site_date_pairs = Counter()

    for idx, s in enumerate(sightings, start=1):
        sid = s.get("sighting_id", f"ROW-{idx}")

        # Schema completeness
        missing = [f for f in REQUIRED_FIELDS if f not in s]
        if missing:
            errors.append(f"{sid}: Missing fields {missing}")

        # Primary key uniqueness
        if sid in seen_ids:
            errors.append(f"{sid}: Duplicate sighting_id")
        seen_ids.add(sid)

        # Foreign key integrity
        if s.get("site_id") and s["site_id"] not in roost_ids:
            errors.append(f"{sid}: Orphan foreign key site_id={s['site_id']}")

        # Date format check
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", str(s.get("observation_date", ""))):
            errors.append(f"{sid}: Invalid date format '{s.get('observation_date')}'")

        # County & bounding box check (Kent & Sussex: lat 50.7..51.55, lon -0.95..1.50)
        county = s.get("county")
        lat, lon = s.get("latitude"), s.get("longitude")
        if county not in VALID_COUNTIES:
            errors.append(f"{sid}: Invalid county '{county}'")
        if not (isinstance(lat, (int, float)) and isinstance(lon, (int, float))):
            errors.append(f"{sid}: Non-numeric coordinates ({lat}, {lon})")
        elif not (50.70 <= lat <= 51.55 and -0.95 <= lon <= 1.50):
            errors.append(f"{sid}: Coordinates out of Kent/Sussex bounds ({lat}, {lon})")

        # Bird count sanity
        cnt = s.get("bird_count")
        if cnt is not None and (not isinstance(cnt, int) or cnt <= 0):
            warnings.append(f"{sid}: Unusual bird_count={cnt}")

        # Cross-source same-site/same-date collision check
        key = (s.get("site_id") or s.get("site_name"), s.get("observation_date"))
        site_date_pairs[key] += 1

    collisions = {k: v for k, v in site_date_pairs.items() if v > 1}
    if collisions:
        for (site, dt), count in collisions.items():
            warnings.append(f"Multiple reports ({count}) for '{site}' on {dt}")

    print("\n[3] Breakdown by Source & County:")
    print("    Sources :", dict(Counter(s.get("source_id") for s in sightings)))
    print("    Counties:", dict(Counter(s.get("county") for s in sightings)))
    print("    Activity:", dict(Counter(s.get("activity_type") for s in sightings)))

    print("\n[4] Audit Verdict:")
    if errors:
        print(f"    [FAIL] {len(errors)} error(s) found:")
        for e in errors:
            print("      -", e)
    else:
        print("    [PASS] Zero schema, key, date, or geographic boundary errors.")

    if warnings:
        print(f"    [WARN] {len(warnings)} warning(s):")
        for w in warnings:
            print("      -", w)
    else:
        print("    [PASS] Zero cross-source collisions or count anomalies.")


if __name__ == "__main__":
    run_audit()