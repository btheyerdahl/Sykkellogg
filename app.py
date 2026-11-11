#!/usr/bin/env python3
import argparse
import json
import os
import re
import sqlite3
import traceback
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

import db

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
DEFAULT_DB = os.path.join(BASE_DIR, "data", "app.db")

CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".webmanifest": "application/manifest+json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".ico": "image/x-icon",
}

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
MAX_BODY = 1024 * 1024


class ApiError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status
        self.message = message


def clean_str(value, field, required=True, max_len=200):
    if value is None or (isinstance(value, str) and not value.strip()):
        if required:
            raise ApiError(400, f"{field} er påkrevd")
        return ""
    if not isinstance(value, str):
        raise ApiError(400, f"{field} må være tekst")
    v = value.strip()
    if len(v) > max_len:
        raise ApiError(400, f"{field} er for lang (maks {max_len} tegn)")
    return v


def clean_km(value, field="km"):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ApiError(400, f"{field} må være et tall")
    if value < 0:
        raise ApiError(400, f"{field} kan ikke være negativ")
    return float(value)


def clean_date(value):
    if not isinstance(value, str) or not DATE_RE.match(value):
        raise ApiError(400, "dato må være på formatet ÅÅÅÅ-MM-DD")
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        raise ApiError(400, "dato er ikke en gyldig kalenderdato")
    return value


def clean_bike_id(value):
    if isinstance(value, bool) or not isinstance(value, int):
        raise ApiError(400, "bike_id må være et heltall")
    return value


class Handler(BaseHTTPRequestHandler):
    server_version = "Sykkellogg/1.0"

    def do_GET(self):
        self.route("GET")

    def do_POST(self):
        self.route("POST")

    def do_PUT(self):
        self.route("PUT")

    def do_DELETE(self):
        self.route("DELETE")

    def route(self, method):
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/"):
            try:
                status, payload = self.handle_api(method, parsed.path, parse_qs(parsed.query))
            except ApiError as e:
                status, payload = e.status, {"error": e.message}
            except Exception:
                traceback.print_exc()
                status, payload = 500, {"error": "Intern serverfeil"}
            self.send_json(status, payload, no_store=True)
        else:
            self.serve_static(parsed.path)

    def read_body(self):
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            raise ApiError(400, "Ugyldig Content-Length")
        if length > MAX_BODY:
            raise ApiError(413, "For stor forespørsel")
        raw = self.rfile.read(length) if length else b""
        if not raw:
            return {}
        try:
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise ApiError(400, "Ugyldig JSON")
        if not isinstance(data, dict):
            raise ApiError(400, "Kroppen må være et JSON-objekt")
        return data

    def handle_api(self, method, path, query):
        m = re.match(r"^/api/bikes(?:/(\d+))?$", path)
        if m:
            return self.bikes_api(method, int(m.group(1)) if m.group(1) else None)
        m = re.match(r"^/api/service(?:/(\d+))?$", path)
        if m:
            return self.service_api(method, int(m.group(1)) if m.group(1) else None, query)
        if path == "/api/components" and method == "GET":
            return 200, self.list_components()
        raise ApiError(404, "Ukjent endepunkt")

    def bikes_api(self, method, bike_id):
        conn = db.connect(self.server.db_path)
        try:
            if method == "GET" and bike_id is None:
                rows = conn.execute(
                    """
                    SELECT b.id, b.owner, b.type, b.km, b.created_at, b.updated_at,
                           (SELECT COUNT(*) FROM service_entries s WHERE s.bike_id = b.id) AS entry_count,
                           (SELECT c.label FROM service_entries s JOIN components c ON c.key = s.component
                             WHERE s.bike_id = b.id ORDER BY s.date DESC, s.id DESC LIMIT 1) AS last_component,
                           (SELECT s.date FROM service_entries s WHERE s.bike_id = b.id
                             ORDER BY s.date DESC, s.id DESC LIMIT 1) AS last_date,
                           (SELECT s.km FROM service_entries s WHERE s.bike_id = b.id
                             ORDER BY s.date DESC, s.id DESC LIMIT 1) AS last_km
                    FROM bikes b ORDER BY b.owner COLLATE NOCASE, b.id
                    """
                ).fetchall()
                return 200, [dict(r) for r in rows]
            if method == "POST" and bike_id is None:
                body = self.read_body()
                owner = clean_str(body.get("owner"), "eier")
                type_ = clean_str(body.get("type"), "type")
                km = clean_km(body.get("km"), "km")
                cur = conn.execute(
                    "INSERT INTO bikes(owner, type, km) VALUES (?, ?, ?)",
                    (owner, type_, km),
                )
                conn.commit()
                row = conn.execute("SELECT * FROM bikes WHERE id = ?", (cur.lastrowid,)).fetchone()
                return 201, dict(row)
            if bike_id is None:
                raise ApiError(405, "Metode ikke tillatt")
            row = conn.execute("SELECT * FROM bikes WHERE id = ?", (bike_id,)).fetchone()
            if row is None:
                raise ApiError(404, "Sykkel ikke funnet")
            if method == "PUT":
                body = self.read_body()
                owner = clean_str(body.get("owner"), "eier")
                type_ = clean_str(body.get("type"), "type")
                km = clean_km(body.get("km"), "km")
                conn.execute(
                    "UPDATE bikes SET owner = ?, type = ?, km = ?, updated_at = strftime('%Y-%m-%dT%H:%M:%SZ','now') WHERE id = ?",
                    (owner, type_, km, bike_id),
                )
                conn.commit()
                row = conn.execute("SELECT * FROM bikes WHERE id = ?", (bike_id,)).fetchone()
                return 200, dict(row)
            if method == "DELETE":
                conn.execute("DELETE FROM bikes WHERE id = ?", (bike_id,))
                conn.commit()
                return 204, None
            raise ApiError(405, "Metode ikke tillatt")
        finally:
            conn.close()

    def service_api(self, method, entry_id, query):
        conn = db.connect(self.server.db_path)
        try:
            if method == "GET" and entry_id is None:
                bike_id = None
                if "bike_id" in query:
                    try:
                        bike_id = int(query["bike_id"][0])
                    except ValueError:
                        raise ApiError(400, "bike_id må være et heltall")
                sql = """
                    SELECT s.id, s.bike_id, s.component, c.label AS component_label,
                           s.date, s.km, s.note, s.created_at,
                           b.owner AS bike_owner, b.type AS bike_type
                    FROM service_entries s
                    JOIN components c ON c.key = s.component
                    JOIN bikes b ON b.id = s.bike_id
                """
                params = []
                if bike_id is not None:
                    sql += " WHERE s.bike_id = ?"
                    params.append(bike_id)
                sql += " ORDER BY s.date DESC, s.id DESC"
                rows = conn.execute(sql, params).fetchall()
                return 200, [dict(r) for r in rows]
            if method == "POST" and entry_id is None:
                body = self.read_body()
                payload = self.validate_entry(body, conn)
                cur = conn.execute(
                    "INSERT INTO service_entries(bike_id, component, date, km, note) VALUES (?, ?, ?, ?, ?)",
                    (payload["bike_id"], payload["component"], payload["date"], payload["km"], payload["note"]),
                )
                conn.commit()
                row = conn.execute(
                    """
                    SELECT s.*, c.label AS component_label, b.owner AS bike_owner, b.type AS bike_type
                    FROM service_entries s
                    JOIN components c ON c.key = s.component
                    JOIN bikes b ON b.id = s.bike_id
                    WHERE s.id = ?
                    """,
                    (cur.lastrowid,),
                ).fetchone()
                return 201, dict(row)
            if entry_id is None:
                raise ApiError(405, "Metode ikke tillatt")
            row = conn.execute("SELECT * FROM service_entries WHERE id = ?", (entry_id,)).fetchone()
            if row is None:
                raise ApiError(404, "Serviceoppføring ikke funnet")
            if method == "PUT":
                body = self.read_body()
                payload = self.validate_entry(body, conn)
                conn.execute(
                    "UPDATE service_entries SET bike_id = ?, component = ?, date = ?, km = ?, note = ? WHERE id = ?",
                    (payload["bike_id"], payload["component"], payload["date"], payload["km"], payload["note"], entry_id),
                )
                conn.commit()
                row = conn.execute(
                    """
                    SELECT s.*, c.label AS component_label, b.owner AS bike_owner, b.type AS bike_type
                    FROM service_entries s
                    JOIN components c ON c.key = s.component
                    JOIN bikes b ON b.id = s.bike_id
                    WHERE s.id = ?
                    """,
                    (entry_id,),
                ).fetchone()
                return 200, dict(row)
            if method == "DELETE":
                conn.execute("DELETE FROM service_entries WHERE id = ?", (entry_id,))
                conn.commit()
                return 204, None
            raise ApiError(405, "Metode ikke tillatt")
        finally:
            conn.close()

    def validate_entry(self, body, conn):
        bike_id = clean_bike_id(body.get("bike_id"))
        if conn.execute("SELECT 1 FROM bikes WHERE id = ?", (bike_id,)).fetchone() is None:
            raise ApiError(400, "sykkelen finnes ikke")
        component = clean_str(body.get("component"), "komponent")
        if conn.execute("SELECT 1 FROM components WHERE key = ?", (component,)).fetchone() is None:
            raise ApiError(400, f"ukjent komponent: {component}")
        date = clean_date(body.get("date"))
        km = clean_km(body.get("km"), "km")
        note = clean_str(body.get("note"), "merknad", required=False, max_len=1000)
        return {"bike_id": bike_id, "component": component, "date": date, "km": km, "note": note}

    def list_components(self):
        conn = db.connect(self.server.db_path)
        try:
            rows = conn.execute("SELECT key, label, interval_km FROM components ORDER BY label COLLATE NOCASE").fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def send_json(self, status, payload, no_store=False):
        body = b"" if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        if no_store:
            self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if body:
            self.wfile.write(body)

    def serve_static(self, path):
        if path == "/":
            path = "/index.html"
        static_root = os.path.realpath(STATIC_DIR)
        full = os.path.realpath(os.path.join(static_root, path.lstrip("/")))
        if not (full == static_root or full.startswith(static_root + os.sep)) or not os.path.isfile(full):
            self.send_response(404)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            msg = b"404 - fant ikke"
            self.send_header("Content-Length", str(len(msg)))
            self.end_headers()
            self.wfile.write(msg)
            return
        ext = os.path.splitext(full)[1].lower()
        ctype = CONTENT_TYPES.get(ext, "application/octet-stream")
        with open(full, "rb") as f:
            data = f.read()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def create_server(host="127.0.0.1", port=8000, db_path=DEFAULT_DB, seed=True):
    db.init_db(db_path, seed_demo_data=seed)
    server = ThreadingHTTPServer((host, port), Handler)
    server.db_path = db_path
    return server


def main():
    parser = argparse.ArgumentParser(description="Sykkellogg - vedlikeholdslogg for familiens sykler")
    parser.add_argument("--host", default="127.0.0.1", help="adresse å lytte på (standard: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="port (standard: 8000)")
    parser.add_argument("--db", default=DEFAULT_DB, help="sti til SQLite-fil (standard: data/app.db)")
    parser.add_argument("--no-seed", action="store_true", help="ikke fyll inn eksempeldata ved første kjøring")
    args = parser.parse_args()
    server = create_server(args.host, args.port, args.db, seed=not args.no_seed)
    print(f"Sykkellogg kjører på http://{args.host}:{args.port}  (database: {args.db})")
    print("Trykk Ctrl+C for å stoppe.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
