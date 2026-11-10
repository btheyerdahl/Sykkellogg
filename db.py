import os
import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS components (
  key TEXT PRIMARY KEY,
  label TEXT NOT NULL,
  interval_km INTEGER
);
CREATE TABLE IF NOT EXISTS bikes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  owner TEXT NOT NULL,
  type TEXT NOT NULL,
  km REAL NOT NULL DEFAULT 0 CHECK (km >= 0),
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
  updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);
CREATE TABLE IF NOT EXISTS service_entries (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  bike_id INTEGER NOT NULL REFERENCES bikes(id) ON DELETE CASCADE,
  component TEXT NOT NULL REFERENCES components(key),
  date TEXT NOT NULL,
  km REAL NOT NULL CHECK (km >= 0),
  note TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);
CREATE INDEX IF NOT EXISTS idx_service_bike ON service_entries(bike_id);
CREATE INDEX IF NOT EXISTS idx_service_date ON service_entries(date);
"""

COMPONENTS = [
    ("kjede", "Kjede"),
    ("bremseklosser", "Bremseklosser"),
    ("dekk", "Dekk"),
    ("slanger", "Slanger"),
    ("kassett", "Kassett"),
    ("kabler", "Kabler"),
    ("kranklager", "Kranklager"),
    ("hjullager", "Hjullager"),
    ("gaffelservice", "Gaffelservice"),
    ("skivebremser", "Skivebremser"),
]

DEMO_BIKES = [
    ("Anna", "Terrengsykkel", 1240),
    ("Erik", "El-sykkel", 3150),
    ("Nora", "Barnesykkel", 310),
    ("Ola", "Landeveisssykkel", 4820),
]

DEMO_ENTRIES = [
    (1, "kjede", "2025-09-12", 1150, "Shimano Deore CN-HG601, ca. 250 kr"),
    (2, "dekk", "2025-10-02", 3050, "Schwalbe Marathon E-Plus bak"),
    (2, "bremseklosser", "2025-08-20", 2780, "Organiske bremseklosser"),
    (3, "slanger", "2025-07-15", 290, "Punktert bak, byttet slange"),
]


def connect(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path, seed_demo_data=True):
    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
    conn = connect(db_path)
    try:
        with conn:
            conn.executescript(SCHEMA)
            for key, label in COMPONENTS:
                conn.execute(
                    "INSERT OR IGNORE INTO components(key, label) VALUES (?, ?)",
                    (key, label),
                )
            if seed_demo_data and conn.execute("SELECT COUNT(*) FROM bikes").fetchone()[0] == 0:
                seed_demo(conn)
    finally:
        conn.close()


def seed_demo(conn):
    ids = []
    for owner, type_, km in DEMO_BIKES:
        cur = conn.execute(
            "INSERT INTO bikes(owner, type, km) VALUES (?, ?, ?)",
            (owner, type_, km),
        )
        ids.append(cur.lastrowid)
    for bike_idx, component, date, km, note in DEMO_ENTRIES:
        conn.execute(
            "INSERT INTO service_entries(bike_id, component, date, km, note) VALUES (?, ?, ?, ?, ?)",
            (ids[bike_idx - 1], component, date, km, note),
        )
