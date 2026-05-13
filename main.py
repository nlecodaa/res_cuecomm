from __future__ import annotations

import sqlite3
from contextlib import asynccontextmanager, contextmanager
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
import re
from typing import Literal

from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "rescuecomm.db"

VALID_STATUSES = {"Pending", "Dispatched", "Resolved"}
VALID_CATEGORIES = ("Fire", "Medical", "Police", "General")
VALID_SEVERITIES = ("Low", "Medium", "High", "Critical")
DASHBOARD_ROLE = "dashboard"
CITIZEN_ROLE = "citizen"

DEMO_LOCATIONS = (
    {
        "name": "Green Park",
        "keywords": ("green park", "greenpark"),
        "latitude": 28.5585,
        "longitude": 77.2068,
    },
    {
        "name": "Saket",
        "keywords": ("saket", "select citywalk", "select city walk", "malviya nagar"),
        "latitude": 28.5245,
        "longitude": 77.2066,
    },
    {
        "name": "Chanakyapuri",
        "keywords": (
            "chanakyapuri",
            "chanakya puri",
            "chankyapuri",
            "chankaya puri",
            "chanakya",
            "embassy area",
            "ashoka hotel",
        ),
        "latitude": 28.5950,
        "longitude": 77.1873,
    },
    {
        "name": "Connaught Place",
        "keywords": ("connaught place", "cp", "rajiv chowk", "barakhamba"),
        "latitude": 28.6315,
        "longitude": 77.2167,
    },
    {
        "name": "India Gate",
        "keywords": ("india gate", "kartavya path", "war memorial"),
        "latitude": 28.6129,
        "longitude": 77.2295,
    },
    {
        "name": "Chandni Chowk",
        "keywords": ("chandni chowk", "old delhi", "lal qila", "red fort", "jama masjid"),
        "latitude": 28.6506,
        "longitude": 77.2303,
    },
    {
        "name": "Karol Bagh",
        "keywords": ("karol bagh", "karolbagh", "ganga ram", "rajendra place"),
        "latitude": 28.6516,
        "longitude": 77.1907,
    },
    {
        "name": "Lajpat Nagar",
        "keywords": ("lajpat nagar", "lajpat", "amar colony"),
        "latitude": 28.5677,
        "longitude": 77.2433,
    },
    {
        "name": "Hauz Khas",
        "keywords": ("hauz khas", "hauzkhas", "hkv", "deer park"),
        "latitude": 28.5494,
        "longitude": 77.2001,
    },
    {
        "name": "Dwarka",
        "keywords": ("dwarka", "sector 21", "sector 10 dwarka", "dwarka mor"),
        "latitude": 28.5921,
        "longitude": 77.0460,
    },
    {
        "name": "Rohini",
        "keywords": ("rohini", "rohini sector", "rithala"),
        "latitude": 28.7373,
        "longitude": 77.0822,
    },
    {
        "name": "Pitampura",
        "keywords": ("pitampura", "netaji subhash place", "nsp"),
        "latitude": 28.7033,
        "longitude": 77.1324,
    },
    {
        "name": "Rajouri Garden",
        "keywords": ("rajouri garden", "rajouri", "tagore garden"),
        "latitude": 28.6425,
        "longitude": 77.1179,
    },
    {
        "name": "Janakpuri",
        "keywords": ("janakpuri", "janak puri", "district centre janakpuri"),
        "latitude": 28.6219,
        "longitude": 77.0878,
    },
    {
        "name": "Vasant Kunj",
        "keywords": ("vasant kunj", "vasantkunj", "ambience mall vasant"),
        "latitude": 28.5293,
        "longitude": 77.1558,
    },
    {
        "name": "Vasant Vihar",
        "keywords": ("vasant vihar", "vasantvihar"),
        "latitude": 28.5600,
        "longitude": 77.1607,
    },
    {
        "name": "Delhi University North Campus",
        "keywords": ("north campus", "delhi university", "du north", "vishwavidyalaya"),
        "latitude": 28.6877,
        "longitude": 77.2097,
    },
    {
        "name": "Delhi University South Campus",
        "keywords": ("south campus", "du south", "satya niketan", "venkateswara college"),
        "latitude": 28.5843,
        "longitude": 77.1637,
    },
    {
        "name": "ITO",
        "keywords": ("ito", "income tax office", "delhi gate"),
        "latitude": 28.6272,
        "longitude": 77.2409,
    },
    {
        "name": "Pragati Maidan",
        "keywords": ("pragati maidan", "bharat mandapam"),
        "latitude": 28.6169,
        "longitude": 77.2433,
    },
    {
        "name": "Lodhi Garden",
        "keywords": ("lodhi garden", "lodhi road", "lodhi estate"),
        "latitude": 28.5917,
        "longitude": 77.2197,
    },
    {
        "name": "Khan Market",
        "keywords": ("khan market", "khanmarket"),
        "latitude": 28.6006,
        "longitude": 77.2269,
    },
    {
        "name": "Sarojini Nagar",
        "keywords": ("sarojini nagar", "sarojini", "sn market"),
        "latitude": 28.5755,
        "longitude": 77.1963,
    },
    {
        "name": "Nehru Place",
        "keywords": ("nehru place", "nehruplace"),
        "latitude": 28.5494,
        "longitude": 77.2519,
    },
    {
        "name": "Kalkaji",
        "keywords": ("kalkaji", "govindpuri", "lotus temple"),
        "latitude": 28.5415,
        "longitude": 77.2601,
    },
    {
        "name": "Okhla",
        "keywords": ("okhla", "jamia", "jasola"),
        "latitude": 28.5358,
        "longitude": 77.2842,
    },
    {
        "name": "Greater Kailash",
        "keywords": ("greater kailash", "gk", "gk 1", "gk1", "gk 2", "gk2"),
        "latitude": 28.5485,
        "longitude": 77.2422,
    },
    {
        "name": "Mayur Vihar",
        "keywords": ("mayur vihar", "mayurvihar"),
        "latitude": 28.6086,
        "longitude": 77.2956,
    },
    {
        "name": "Laxmi Nagar",
        "keywords": ("laxmi nagar", "laxminagar", "preet vihar"),
        "latitude": 28.6304,
        "longitude": 77.2774,
    },
    {
        "name": "Shahdara",
        "keywords": ("shahdara", "seelampur", "welcome metro"),
        "latitude": 28.6733,
        "longitude": 77.2890,
    },
    {
        "name": "Kashmere Gate",
        "keywords": ("kashmere gate", "isbt", "civil lines"),
        "latitude": 28.6676,
        "longitude": 77.2273,
    },
    {
        "name": "New Delhi Railway Station",
        "keywords": ("new delhi railway", "ndls", "paharganj", "ajmeri gate"),
        "latitude": 28.6425,
        "longitude": 77.2197,
    },
    {
        "name": "IGI Airport",
        "keywords": ("igi airport", "airport", "terminal 3", "t3", "aerocity"),
        "latitude": 28.5562,
        "longitude": 77.1000,
    },
    {
        "name": "Dhaula Kuan",
        "keywords": ("dhaula kuan", "dhaulakuan"),
        "latitude": 28.5918,
        "longitude": 77.1617,
    },
    {
        "name": "Punjabi Bagh",
        "keywords": ("punjabi bagh", "punjabibagh", "moti nagar"),
        "latitude": 28.6689,
        "longitude": 77.1325,
    },
    {
        "name": "Ashram",
        "keywords": ("ashram", "maharani bagh", "new friends colony"),
        "latitude": 28.5711,
        "longitude": 77.2617,
    },
    {
        "name": "Akshardham",
        "keywords": ("akshardham", "yamuna bank"),
        "latitude": 28.6127,
        "longitude": 77.2773,
    },
    {
        "name": "Jor Bagh",
        "keywords": ("jor bagh", "jorbagh"),
        "latitude": 28.5867,
        "longitude": 77.2124,
    },
    {
        "name": "AIIMS Delhi",
        "keywords": ("aiims", "all india institute"),
        "latitude": 28.5672,
        "longitude": 77.2100,
    },
    {
        "name": "Noida",
        "keywords": ("noida", "sector 18 noida", "botanical garden", "greater noida"),
        "latitude": 28.5355,
        "longitude": 77.3910,
    },
    {
        "name": "Gurugram",
        "keywords": ("gurgaon", "gurugram", "cyber city", "huda city centre", "iffco chowk"),
        "latitude": 28.4595,
        "longitude": 77.0266,
    },
    {
        "name": "Faridabad",
        "keywords": ("faridabad", "badarpur", "ballabhgarh"),
        "latitude": 28.4089,
        "longitude": 77.3178,
    },
    {
        "name": "Ghaziabad",
        "keywords": ("ghaziabad", "indirapuram", "vaishali", "kaushambi"),
        "latitude": 28.6692,
        "longitude": 77.4538,
    },
    {
        "name": "Raisina Hill",
        "keywords": ("raisina", "president house", "rashtrapati"),
        "latitude": 28.6143,
        "longitude": 77.1995,
    },
    {
        "name": "Central Vista",
        "keywords": ("central vista", "kartavya path", "india gate"),
        "latitude": 28.6129,
        "longitude": 77.2295,
    },
    {
        "name": "Library",
        "keywords": ("library",),
        "latitude": 28.6133,
        "longitude": 77.2106,
    },
    {
        "name": "Auditorium",
        "keywords": ("auditorium",),
        "latitude": 28.6150,
        "longitude": 77.2077,
    },
    {
        "name": "Laboratory Block",
        "keywords": ("lab", "laboratory", "chemistry"),
        "latitude": 28.6120,
        "longitude": 77.2115,
    },
)


class ReportIn(BaseModel):
    raw_text: str = Field(..., min_length=3, max_length=1000)
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)


class StatusIn(BaseModel):
    status: Literal["Pending", "Dispatched", "Resolved"]


NEGATION_TERMS = {
    "no",
    "not",
    "none",
    "false",
    "fake",
    "mock",
    "practice",
    "drill",
    "safe",
    "resolved",
}

SOFTENING_TERMS = {
    "minor",
    "small",
    "slight",
    "possible",
    "maybe",
    "smell",
    "controlled",
}

CATEGORY_SIGNALS = {
    "Fire": {
        "fire": 5,
        "fier": 5,
        "flame": 5,
        "flames": 5,
        "smoke": 3,
        "smok": 3,
        "explosion": 6,
        "blast": 6,
        "burn": 4,
        "burning": 5,
        "gas leak": 5,
        "cylinder leak": 5,
        "cylinder blast": 7,
        "electric fire": 5,
        "electrical fire": 5,
        "short circuit": 5,
        "sparking": 4,
        "arson": 6,
        "sparks": 3,
        "aag": 5,
        "dhua": 3,
        "jal": 3,
    },
    "Medical": {
        "medical": 3,
        "medicl": 3,
        "ambulance": 4,
        "accident": 4,
        "accidnt": 4,
        "crash": 4,
        "collision": 4,
        "injured": 5,
        "injurd": 5,
        "hurt": 3,
        "injury": 4,
        "unconscious": 6,
        "fainted": 5,
        "heart attack": 7,
        "seizure": 6,
        "stroke": 6,
        "bleeding": 6,
        "bleedng": 6,
        "blood": 4,
        "not breathing": 7,
        "breathing problem": 6,
        "suffocating": 6,
        "electric shock": 6,
        "shock": 4,
        "fracture": 4,
        "snake bite": 6,
        "poison": 5,
        "food poisoning": 5,
        "fever": 2,
        "vomiting": 3,
        "fell": 3,
        "fall": 3,
        "behosh": 6,
        "khoon": 5,
        "chot": 4,
    },
    "Police": {
        "police": 4,
        "polce": 4,
        "fight": 4,
        "violence": 5,
        "assault": 5,
        "weapon": 6,
        "gun": 6,
        "knife": 6,
        "riot": 6,
        "theft": 4,
        "robbery": 5,
        "chain snatching": 5,
        "snatching": 4,
        "stolen": 4,
        "suspicious": 3,
        "security": 3,
        "threat": 5,
        "kidnap": 7,
        "hostage": 7,
        "molestation": 5,
        "harassment": 4,
        "stalking": 4,
        "crowd violence": 5,
        "harassment": 4,
        "ladai": 4,
        "chor": 4,
        "hathiyar": 6,
    },
}

SEVERITY_SIGNALS = {
    "Critical": {
        "people trapped": 9,
        "child trapped": 9,
        "children trapped": 9,
        "trapped": 8,
        "not breathing": 9,
        "cannot breathe": 9,
        "unable to breathe": 9,
        "suffocating": 8,
        "unconscious": 8,
        "heart attack": 9,
        "stroke": 8,
        "severe bleeding": 9,
        "heavy bleeding": 8,
        "explosion": 8,
        "blast": 8,
        "cylinder blast": 9,
        "building collapse": 9,
        "collapse": 8,
        "stampede": 9,
        "crowd crush": 9,
        "weapon": 8,
        "gun": 8,
        "knife": 8,
        "critical": 8,
        "severe": 7,
        "serious": 6,
        "very serious": 7,
        "life danger": 8,
        "life threatening": 9,
        "multiple casualties": 9,
        "many injured": 8,
        "many people injured": 9,
        "dying": 9,
        "dead": 9,
        "behosh": 8,
        "kidnap": 8,
        "hostage": 9,
    },
    "High": {
        "massive": 4,
        "major": 4,
        "large": 3,
        "huge": 4,
        "urgent": 5,
        "emergency": 5,
        "sos": 5,
        "please help": 4,
        "plz help": 4,
        "fire spreading": 7,
        "spreading fast": 7,
        "spreading": 5,
        "fire": 5,
        "flames": 5,
        "burning": 5,
        "arson": 5,
        "gas leak": 6,
        "cylinder leak": 6,
        "electric shock": 6,
        "smoke": 4,
        "injured": 5,
        "accident": 4,
        "collision": 4,
        "crash": 4,
        "bleeding": 6,
        "burn": 5,
        "fight": 4,
        "assault": 5,
        "robbery": 5,
        "snatching": 4,
        "riot": 6,
        "threat": 5,
        "multiple": 4,
        "crowd": 3,
        "panic": 4,
        "missing child": 5,
        "evacuation": 5,
        "earthquake": 6,
        "flood": 5,
        "water logging": 3,
        "tree fallen": 4,
        "aag": 5,
        "madad": 3,
    },
    "Medium": {
        "smell": 2,
        "smoke smell": 3,
        "sparks": 3,
        "small fire": 3,
        "minor fire": 3,
        "pain": 3,
        "minor injury": 3,
        "vomiting": 3,
        "fever": 2,
        "theft": 3,
        "stolen": 3,
        "suspicious": 3,
        "security": 2,
        "power cut": 2,
        "electric fault": 3,
        "water leakage": 2,
        "road blocked": 3,
        "traffic blocked": 3,
        "help": 2,
        "small": 2,
        "possible": 2,
    },
}


def normalize_for_nlp(text: str) -> str:
    replacements = {
        "can't": "cannot",
        "cant": "cannot",
        "won't": "will not",
        "wont": "will not",
        "doesn't": "does not",
        "dont": "do not",
        "don't": "do not",
    }
    normalized = text.lower()
    for source, replacement in replacements.items():
        normalized = normalized.replace(source, replacement)
    normalized = re.sub(r"(.)\1{2,}", r"\1\1", normalized)
    normalized = re.sub(r"[^a-z0-9\s]", " ", normalized)
    return " ".join(normalized.split())


def fuzzy_ratio(left: str, right: str) -> float:
    return SequenceMatcher(None, left, right).ratio()


def token_threshold(keyword: str) -> float:
    if len(keyword) <= 3:
        return 0.95
    if len(keyword) <= 5:
        return 0.78
    return 0.80


def best_signal_match(normalized: str, keyword: str) -> tuple[float, int] | None:
    tokens = normalized.split()
    keyword = normalize_for_nlp(keyword)
    keyword_tokens = keyword.split()
    if not tokens or not keyword_tokens:
        return None

    if len(keyword_tokens) == 1:
        best: tuple[float, int] | None = None
        threshold = token_threshold(keyword)
        for index, token in enumerate(tokens):
            ratio = 1.0 if token == keyword else fuzzy_ratio(token, keyword)
            if ratio >= threshold and (best is None or ratio > best[0]):
                best = (ratio, index)
        return best

    best = None
    phrase_length = len(keyword_tokens)
    threshold = 0.82
    for index in range(0, max(len(tokens) - phrase_length + 1, 0)):
        candidate = " ".join(tokens[index : index + phrase_length])
        ratio = max(
            fuzzy_ratio(candidate, keyword),
            fuzzy_ratio(candidate.replace(" ", ""), keyword.replace(" ", "")),
        )
        if ratio >= threshold and (best is None or ratio > best[0]):
            best = (ratio, index)
    return best


def is_negated(tokens: list[str], start_index: int) -> bool:
    window_start = max(start_index - 3, 0)
    window_end = min(start_index + 3, len(tokens))
    context = set(tokens[window_start:window_end])
    return bool(context & NEGATION_TERMS)


def score_signals(
    normalized: str,
    signals: dict[str, int],
) -> tuple[int, list[str]]:
    tokens = normalized.split()
    score = 0
    evidence: list[str] = []

    for keyword, weight in signals.items():
        match = best_signal_match(normalized, keyword)
        if match is None:
            continue

        ratio, start_index = match
        if is_negated(tokens, start_index):
            continue

        score += max(1, round(weight * ratio))
        evidence.append(keyword)

    return score, evidence


def process_emergency_text(text: str) -> dict[str, str]:
    """
    Constrained local emergency classifier.

    It behaves like an AI extraction layer, but stays deterministic and local:
    normalize text, tolerate common misspellings, score domain signals, and
    return only approved labels. A hosted LLM can later replace this function
    without changing the REST/WebSocket/database flow.
    """
    normalized = normalize_for_nlp(text)
    if not normalized:
        return {"category": "General", "severity": "Low"}

    category_scores: dict[str, int] = {}
    for candidate, signals in CATEGORY_SIGNALS.items():
        category_scores[candidate], _ = score_signals(normalized, signals)

    best_category = max(category_scores, key=category_scores.get)
    category = "General"
    if category_scores[best_category] >= 3:
        category = best_category

    severity_scores: dict[str, int] = {}
    for candidate, signals in SEVERITY_SIGNALS.items():
        severity_scores[candidate], _ = score_signals(normalized, signals)

    if severity_scores["Critical"] >= 6 or (
        severity_scores["Critical"] >= 4 and severity_scores["High"] >= 4
    ):
        severity = "Critical"
    elif severity_scores["High"] >= 4:
        severity = "High"
    elif severity_scores["Medium"] >= 2 or category != "General":
        severity = "Medium"
    else:
        severity = "Low"

    tokens = set(normalized.split())
    if tokens & SOFTENING_TERMS and severity == "High":
        severity = "Medium"
    elif tokens & SOFTENING_TERMS and severity == "Medium" and category == "General":
        severity = "Low"

    if category not in VALID_CATEGORIES:
        category = "General"
    if severity not in VALID_SEVERITIES:
        severity = "Low"

    return {"category": category, "severity": severity}


def normalize_place_text(text: str) -> str:
    return " ".join(text.lower().replace("-", " ").replace("_", " ").split())


def text_mentions_place(text: str, keyword: str) -> bool:
    normalized = normalize_place_text(text)
    compact = normalized.replace(" ", "")
    normalized_keyword = normalize_place_text(keyword)
    compact_keyword = normalized_keyword.replace(" ", "")
    if normalized_keyword in normalized or compact_keyword in compact:
        return True

    tokens = normalized.split()
    keyword_tokens = normalized_keyword.split()
    if not tokens or not keyword_tokens:
        return False

    if len(keyword_tokens) == 1:
        threshold = 0.88 if len(normalized_keyword) <= 4 else 0.78
        return any(
            SequenceMatcher(None, token, normalized_keyword).ratio() >= threshold
            for token in tokens
        )

    phrase_length = len(keyword_tokens)
    threshold = 0.78
    for index in range(0, max(len(tokens) - phrase_length + 1, 0)):
        candidate = " ".join(tokens[index : index + phrase_length])
        ratio = max(
            SequenceMatcher(None, candidate, normalized_keyword).ratio(),
            SequenceMatcher(
                None,
                candidate.replace(" ", ""),
                normalized_keyword.replace(" ", ""),
            ).ratio(),
        )
        if ratio >= threshold:
            return True

    return False


def resolve_demo_location(
    text: str,
    fallback_latitude: float,
    fallback_longitude: float,
) -> tuple[float, float]:
    """
    Offline demo geocoder.

    The browser still supplies the fallback GPS coordinate. For college demos,
    this resolver lets typed places such as "near Saket" or "fire in Noida"
    appear at different map points without depending on a paid/cloud geocoder.
    """
    for location in DEMO_LOCATIONS:
        if any(text_mentions_place(text, keyword) for keyword in location["keywords"]):
            return float(location["latitude"]), float(location["longitude"])

    return fallback_latitude, fallback_longitude


def get_connection() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    return connection


@contextmanager
def db_connection():
    connection = get_connection()
    try:
        yield connection
    finally:
        connection.close()


def init_db() -> None:
    with db_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS incidents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                raw_text TEXT NOT NULL,
                category TEXT NOT NULL,
                severity TEXT NOT NULL,
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                status TEXT NOT NULL DEFAULT 'Pending',
                timestamp DATETIME NOT NULL
            )
            """
        )
        connection.commit()


def row_to_incident(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "raw_text": row["raw_text"],
        "category": row["category"],
        "severity": row["severity"],
        "latitude": row["latitude"],
        "longitude": row["longitude"],
        "status": row["status"],
        "timestamp": row["timestamp"],
    }


def to_public_incident(incident: dict) -> dict:
    return {
        "id": incident["id"],
        "category": incident["category"],
        "severity": incident["severity"],
        "latitude": incident["latitude"],
        "longitude": incident["longitude"],
        "status": incident["status"],
        "timestamp": incident["timestamp"],
    }


def list_incidents(include_resolved: bool = False) -> list[dict]:
    query = "SELECT * FROM incidents"
    params: tuple = ()
    if not include_resolved:
        query += " WHERE status != ?"
        params = ("Resolved",)
    query += """
        ORDER BY
            CASE severity
                WHEN 'Critical' THEN 0
                WHEN 'Medium' THEN 1
                ELSE 2
            END,
            datetime(timestamp) DESC
    """

    with db_connection() as connection:
        rows = connection.execute(query, params).fetchall()
        return [row_to_incident(row) for row in rows]


def get_incident(ticket_id: int) -> dict | None:
    with db_connection() as connection:
        row = connection.execute(
            "SELECT * FROM incidents WHERE id = ?",
            (ticket_id,),
        ).fetchone()
        return row_to_incident(row) if row else None


def create_incident(report: ReportIn) -> dict:
    analysis = process_emergency_text(report.raw_text)
    latitude, longitude = resolve_demo_location(
        report.raw_text,
        report.latitude,
        report.longitude,
    )
    timestamp = datetime.now(timezone.utc).isoformat()

    with db_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO incidents (
                raw_text, category, severity, latitude, longitude, status, timestamp
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                report.raw_text.strip(),
                analysis["category"],
                analysis["severity"],
                latitude,
                longitude,
                "Pending",
                timestamp,
            ),
        )
        connection.commit()
        ticket_id = cursor.lastrowid

    incident = get_incident(ticket_id)
    if incident is None:
        raise RuntimeError("Incident insert succeeded but could not be reloaded.")
    return incident


def regeocode_active_incidents() -> list[dict]:
    updated_ids: list[int] = []

    with db_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, raw_text, latitude, longitude
            FROM incidents
            WHERE status != 'Resolved'
            """
        ).fetchall()

        for row in rows:
            latitude, longitude = resolve_demo_location(
                row["raw_text"],
                row["latitude"],
                row["longitude"],
            )
            if latitude == row["latitude"] and longitude == row["longitude"]:
                continue

            connection.execute(
                "UPDATE incidents SET latitude = ?, longitude = ? WHERE id = ?",
                (latitude, longitude, row["id"]),
            )
            updated_ids.append(row["id"])

        connection.commit()

    return [
        incident
        for incident in list_incidents(include_resolved=False)
        if incident["id"] in updated_ids
    ]


def reclassify_active_incidents() -> list[dict]:
    updated_ids: list[int] = []

    with db_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, raw_text, category, severity, latitude, longitude
            FROM incidents
            WHERE status != 'Resolved'
            """
        ).fetchall()

        for row in rows:
            analysis = process_emergency_text(row["raw_text"])
            latitude, longitude = resolve_demo_location(
                row["raw_text"],
                row["latitude"],
                row["longitude"],
            )
            changed = (
                analysis["category"] != row["category"]
                or analysis["severity"] != row["severity"]
                or latitude != row["latitude"]
                or longitude != row["longitude"]
            )
            if not changed:
                continue

            connection.execute(
                """
                UPDATE incidents
                SET category = ?, severity = ?, latitude = ?, longitude = ?
                WHERE id = ?
                """,
                (
                    analysis["category"],
                    analysis["severity"],
                    latitude,
                    longitude,
                    row["id"],
                ),
            )
            updated_ids.append(row["id"])

        connection.commit()

    return [
        incident
        for incident in list_incidents(include_resolved=False)
        if incident["id"] in updated_ids
    ]


def update_incident_status(ticket_id: int, status: str) -> dict:
    if status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail="Invalid status.")

    with db_connection() as connection:
        cursor = connection.execute(
            "UPDATE incidents SET status = ? WHERE id = ?",
            (status, ticket_id),
        )
        connection.commit()

    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="Ticket not found.")

    incident = get_incident(ticket_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="Ticket not found.")
    return incident


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: dict[WebSocket, str] = {}

    async def connect(self, websocket: WebSocket, role: str) -> str:
        await websocket.accept()
        normalized_role = DASHBOARD_ROLE if role == DASHBOARD_ROLE else CITIZEN_ROLE
        self._connections[websocket] = normalized_role
        return normalized_role

    def disconnect(self, websocket: WebSocket) -> None:
        self._connections.pop(websocket, None)

    async def send_snapshot(self, websocket: WebSocket, role: str) -> None:
        incidents = list_incidents(include_resolved=False)
        if role != DASHBOARD_ROLE:
            incidents = [to_public_incident(incident) for incident in incidents]
        await websocket.send_json({"type": "snapshot", "incidents": incidents})

    async def broadcast_incident(self, event_type: str, incident: dict) -> None:
        stale_connections: list[WebSocket] = []
        for websocket, role in list(self._connections.items()):
            payload_incident = (
                incident if role == DASHBOARD_ROLE else to_public_incident(incident)
            )
            try:
                await websocket.send_json(
                    {"type": event_type, "incident": payload_incident}
                )
            except RuntimeError:
                stale_connections.append(websocket)

        for websocket in stale_connections:
            self.disconnect(websocket)


manager = ConnectionManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="RescueComm",
    description="Local real-time emergency communication demo.",
    version="1.0.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse(url="/citizen")


@app.get("/citizen", include_in_schema=False)
async def citizen_portal():
    return FileResponse(STATIC_DIR / "citizen.html")


@app.get("/dashboard", include_in_schema=False)
async def dashboard():
    return FileResponse(STATIC_DIR / "dashboard.html")


@app.get("/health")
async def health_check():
    return {"status": "ok", "database": str(DB_PATH)}


@app.get("/incidents")
async def active_incidents(include_resolved: bool = Query(default=False)):
    return list_incidents(include_resolved=include_resolved)


@app.get("/incidents/public")
async def public_active_incidents():
    return [to_public_incident(incident) for incident in list_incidents()]


@app.get("/classify")
async def classify_preview(text: str = Query(..., min_length=1, max_length=1000)):
    return process_emergency_text(text)


@app.post("/report", status_code=201)
async def report_incident(report: ReportIn):
    incident = create_incident(report)
    await manager.broadcast_incident("incident_created", incident)
    return incident


@app.patch("/ticket/{ticket_id}/status")
async def patch_ticket_status(ticket_id: int, status_update: StatusIn):
    incident = update_incident_status(ticket_id, status_update.status)
    await manager.broadcast_incident("incident_updated", incident)
    return incident


@app.post("/admin/regeocode")
async def admin_regeocode():
    incidents = regeocode_active_incidents()
    for incident in incidents:
        await manager.broadcast_incident("incident_updated", incident)
    return {"updated": len(incidents), "incidents": incidents}


@app.post("/admin/reclassify")
async def admin_reclassify():
    incidents = reclassify_active_incidents()
    for incident in incidents:
        await manager.broadcast_incident("incident_updated", incident)
    return {"updated": len(incidents), "incidents": incidents}


@app.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    role: str = Query(default=CITIZEN_ROLE),
):
    normalized_role = await manager.connect(websocket, role)
    await manager.send_snapshot(websocket, normalized_role)

    try:
        while True:
            message = await websocket.receive_text()
            if message == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        manager.disconnect(websocket)