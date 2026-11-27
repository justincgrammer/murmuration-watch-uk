import hashlib
import json
import os
import re
import sqlite3
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

ROOT_DIR = Path(__file__).resolve().parent.parent
# On Fly.io persistent volume, DB_PATH can be overridden via environment variable
DB_PATH = Path(os.getenv("DB_PATH", str(Path(__file__).parent / "murmurations.db")))

app = FastAPI(title="Murmuration Watch UK API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


class SightingCreate(BaseModel):
    county_slug: str = Field(..., min_length=2, max_length=50)
    roost_id: Optional[int] = None
    custom_location_name: Optional[str] = Field(default=None, max_length=120)
    latitude: float = Field(..., ge=49.0, le=61.5)
    longitude: float = Field(..., ge=-9.0, le=2.5)
    observed_date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    observed_time: Optional[str] = Field(default=None, max_length=10)
    flock_size: Optional[str] = Field(default="Medium (1,000–5,000)", max_length=60)
    display_quality: Optional[int] = Field(default=3, ge=1, le=5)
    weather_summary: Optional[str] = Field(default=None, max_length=100)
    behaviour_notes: Optional[str] = Field(default="", max_length=600)


@app.get("/api/health")
def health_check():
    with get_db() as conn:
        counties = conn.execute("SELECT COUNT(*) FROM counties WHERE is_active = 1").fetchone()[0]
        roosts = conn.execute("SELECT COUNT(*) FROM roost_sites WHERE status = 'active'").fetchone()[0]
        sightings = conn.execute("SELECT COUNT(*) FROM sightings WHERE status = 'published'").fetchone()[0]
    return {
        "status": "ok",
        "db_path": str(DB_PATH),
        "counties": counties,
        "roosts": roosts,
        "sightings": sightings,
    }


@app.get("/api/bootstrap")
def get_bootstrap():
    with get_db() as conn:
        counties = [
            dict(row)
            for row in conn.execute(
                """
                SELECT id, name, slug, region, center_lat, center_lng, default_zoom
                FROM counties
                WHERE is_active = 1
                ORDER BY region, name
                """
            ).fetchall()
        ]

        roosts = [
            dict(row)
            for row in conn.execute(
                """
                SELECT
                    r.id, r.county_id, c.slug AS county_slug, c.name AS county_name,
                    c.region, r.name, r.latitude, r.longitude,
                    COALESCE(r.parking_lat, r.latitude) AS nav_lat,
                    COALESCE(r.parking_lng, r.longitude) AS nav_lng,
                    r.parking_access, r.habitat_type, r.best_months,
                    r.reliability, r.status, r.notes
                FROM roost_sites r
                JOIN counties c ON c.id = r.county_id
                WHERE c.is_active = 1 AND r.status = 'active'
                ORDER BY c.name, r.name
                """
            ).fetchall()
        ]

        sightings = [
            dict(row)
            for row in conn.execute(
                """
                SELECT
                    s.id, s.roost_id, r.name AS roost_name,
                    s.county_id, c.slug AS county_slug, c.name AS county_name,
                    COALESCE(r.name, s.custom_location_name, 'Field Observation') AS display_location,
                    s.latitude, s.longitude, s.observed_date, s.observed_time,
                    s.flock_size, s.display_quality, s.weather_summary,
                    s.wind_speed_mph, s.behaviour_notes, s.photo_url,
                    s.source, s.created_at
                FROM sightings s
                JOIN counties c ON c.id = s.county_id
                LEFT JOIN roost_sites r ON r.id = s.roost_id
                WHERE s.status = 'published' AND c.is_active = 1
                ORDER BY s.observed_date DESC, s.id DESC
                LIMIT 250
                """
            ).fetchall()
        ]

    return {
        "counties": counties,
        "roosts": roosts,
        "sightings": sightings,
    }


@app.post("/api/sightings", status_code=201)
def create_sighting(payload: SightingCreate, request: Request):
    client_ip = request.client.host if request.client else "unknown"
    raw_fp = f"{client_ip}:{payload.observed_date}:{round(payload.latitude, 2)}:{round(payload.longitude, 2)}"
    client_hash = hashlib.sha256(raw_fp.encode("utf-8")).hexdigest()[:16]

    with get_db() as conn:
        county = conn.execute(
            "SELECT id, name FROM counties WHERE slug = ? AND is_active = 1",
            (payload.county_slug.strip().lower(),),
        ).fetchone()
        if not county:
            raise HTTPException(status_code=400, detail="Invalid or inactive county selected.")

        # Duplicate / spam guard: prevent identical location+date submission from same client
        duplicate = conn.execute(
            """
            SELECT id FROM sightings
            WHERE client_hash = ? AND observed_date = ? AND source = 'user'
            """,
            (client_hash, payload.observed_date),
        ).fetchone()
        if duplicate:
            raise HTTPException(
                status_code=429,
                detail="A sighting for this area and date was already logged from your connection.",
            )

        cursor = conn.execute(
            """
            INSERT INTO sightings (
                roost_id, county_id, custom_location_name, latitude, longitude,
                observed_date, observed_time, flock_size, display_quality,
                weather_summary, behaviour_notes, source, status, client_hash
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'user', 'published', ?)
            """,
            (
                payload.roost_id,
                county["id"],
                (payload.custom_location_name or "").strip() or None,
                payload.latitude,
                payload.longitude,
                payload.observed_date,
                payload.observed_time,
                payload.flock_size,
                payload.display_quality,
                payload.weather_summary,
                (payload.behaviour_notes or "").strip(),
                client_hash,
            ),
        )
        new_id = cursor.lastrowid

    return {"id": new_id, "status": "published", "message": "Sighting saved to database."}


@app.get("/api/forecast")
def get_dusk_forecast(
    lat: float = Query(..., ge=49.0, le=61.5),
    lng: float = Query(..., ge=-9.0, le=2.5),
    target_date: str = Query(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
):
    chosen_date = target_date or date.today().isoformat()
    url = (
        f"https://api.open-meteo.com/v1/forecast?"
        f"latitude={lat}&longitude={lng}"
        f"&daily=sunset,temperature_2m_max,precipitation_probability_max,wind_speed_10m_max"
        f"&wind_speed_unit=mph&timezone=Europe%2FLondon"
        f"&start_date={chosen_date}&end_date={chosen_date}"
    )
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "MurmurationWatchUK/2.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Weather service unavailable: {exc}")

    daily = data.get("daily", {})
    if not daily.get("time"):
        raise HTTPException(status_code=400, detail="Forecast only available up to 16 days ahead.")

    wind_mph = daily["wind_speed_10m_max"][0] or 0
    rain_prob = daily["precipitation_probability_max"][0] or 0
    temp_c = daily["temperature_2m_max"][0]
    sunset_iso = daily["sunset"][0]

    if rain_prob >= 65 or wind_mph >= 25:
        outlook = "Poor — High wind/rain; birds likely to drop straight to roost early."
        rating = "low"
    elif rain_prob >= 35 or wind_mph >= 16:
        outlook = "Fair — Breezy or patchy showers; shorter pre-roost flight expected."
        rating = "moderate"
    else:
        outlook = "Prime — Calm, dry dusk conditions ideal for tight aerial shapes."
        rating = "high"

    return {
        "date": chosen_date,
        "sunset": sunset_iso.split("T")[-1] if "T" in sunset_iso else sunset_iso,
        "temp_c": temp_c,
        "wind_mph": wind_mph,
        "rain_probability": rain_prob,
        "rating": rating,
        "outlook": outlook,
    }


@app.get("/api/geocode")
def geocode_location(
    q: str = Query(..., min_length=2, max_length=120),
    county_slug: Optional[str] = Query(default=None),
):
    cleaned = q.strip()
    w3w_clean = cleaned.lstrip("/").strip().lower()

    # 1. Detect what3words format (e.g. ///word.word.word or word.word.word)
    if re.fullmatch(r"[a-z]+\.[a-z]+\.[a-z]+", w3w_clean):
        w3w_key = os.getenv("W3W_API_KEY", "").strip()
        if not w3w_key:
            raise HTTPException(
                status_code=400,
                detail="what3words detected (///" + w3w_clean + "), but W3W_API_KEY is not configured on the server yet. Use a place name, postcode, GPS, or map tap for now.",
            )
        w3w_url = (
            f"https://api.what3words.com/v3/convert-to-coordinates?"
            f"words={urllib.parse.quote(w3w_clean)}&key={urllib.parse.quote(w3w_key)}"
        )
        try:
            req = urllib.request.Request(w3w_url, headers={"User-Agent": "MurmurationWatchUK/2.0"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"what3words lookup failed: {exc}")

        if "coordinates" not in data:
            raise HTTPException(status_code=404, detail="Could not find that what3words address.")

        return {
            "label": f"///{data.get('words', w3w_clean)} ({data.get('nearestPlace', 'UK')})",
            "latitude": data["coordinates"]["lat"],
            "longitude": data["coordinates"]["lng"],
            "method": "what3words",
        }

    # 2. Free UK Place / Postcode lookup via OpenStreetMap Nominatim
    search_query = cleaned
    if county_slug:
        search_query = f"{cleaned}, {county_slug.replace('-', ' ').title()}, UK"
    else:
        search_query = f"{cleaned}, UK"

    nom_url = (
        f"https://nominatim.openstreetmap.org/search?"
        f"q={urllib.parse.quote(search_query)}&countrycodes=gb&format=json&limit=1"
    )
    try:
        req = urllib.request.Request(
            nom_url,
            headers={"User-Agent": "MurmurationWatchUK/2.0 (murmurations.gunlo.co.uk)"},
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            results = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Place lookup failed: {exc}")

    if not results:
        raise HTTPException(status_code=404, detail=f"Could not locate '{cleaned}' in the UK.")

    top = results[0]
    short_label = ", ".join(top.get("display_name", cleaned).split(",")[:2]).strip()
    return {
        "label": short_label,
        "latitude": float(top["lat"]),
        "longitude": float(top["lon"]),
        "method": "nominatim",
    }


# Serve existing frontend assets cleanly
if (ROOT_DIR / "icons").exists():
    app.mount("/icons", StaticFiles(directory=ROOT_DIR / "icons"), name="icons")
if (ROOT_DIR / "data").exists():
    app.mount("/data", StaticFiles(directory=ROOT_DIR / "data"), name="data")
if (ROOT_DIR / ".well-known").exists():
    app.mount("/.well-known", StaticFiles(directory=ROOT_DIR / ".well-known"), name="well-known")


@app.get("/")
def serve_index():
    return FileResponse(ROOT_DIR / "index.html")


@app.get("/{file_name}")
def serve_root_files(file_name: str):
    allowed = {"manifest.json", "sw.js", "index.html"}
    if file_name in allowed and (ROOT_DIR / file_name).exists():
        return FileResponse(ROOT_DIR / file_name)
    raise HTTPException(status_code=404, detail="Not found")