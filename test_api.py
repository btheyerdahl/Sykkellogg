#!/usr/bin/env python3
import json
import os
import sys
import tempfile
import threading
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import app

PASS = 0
FAIL = 0


def check(name, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"PASS  {name}")
    else:
        FAIL += 1
        print(f"FAIL  {name}  {extra}")


def req(method, base, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(base + path, data=data, method=method,
                               headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(r, timeout=10) as resp:
            raw = resp.read()
            try:
                parsed = json.loads(raw) if raw else None
            except json.JSONDecodeError:
                parsed = None
            return resp.status, parsed, raw
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return e.code, json.loads(raw), raw
        except Exception:
            return e.code, None, raw


def main():
    with tempfile.TemporaryDirectory() as td:
        db_path = os.path.join(td, "test.db")
        server = app.create_server("127.0.0.1", 0, db_path, seed=False)
        port = server.server_address[1]
        base = f"http://127.0.0.1:{port}"
        t = threading.Thread(target=server.serve_forever, daemon=True)
        t.start()

        s, bikes, _ = req("GET", base, "/api/bikes")
        check("GET /api/bikes tom ved start", s == 200 and bikes == [], f"status={s} body={bikes}")

        s, b, _ = req("POST", base, "/api/bikes", {"owner": "Anna", "type": "Terrengsykkel", "km": 1240})
        check("POST /api/bikes gyldig", s == 201 and b["owner"] == "Anna" and b["km"] == 1240, f"status={s} body={b}")
        bike_id = b["id"]

        s, b2, _ = req("POST", base, "/api/bikes", {"owner": "Erik", "type": "El-sykkel", "km": 3150})
        bike2_id = b2["id"]

        s, err, _ = req("POST", base, "/api/bikes", {"type": "Hybrid", "km": 10})
        check("POST /api/bikes mangler eier -> 400", s == 400 and "error" in err, f"status={s} body={err}")

        s, err, _ = req("POST", base, "/api/bikes", {"owner": "X", "type": "Y", "km": -5})
        check("POST /api/bikes negativ km -> 400", s == 400, f"status={s}")

        s, err, _ = req("POST", base, "/api/bikes", {"owner": "X", "type": "Y", "km": "mye"})
        check("POST /api/bikes km ikke tall -> 400", s == 400, f"status={s}")

        s, bikes, _ = req("GET", base, "/api/bikes")
        check("GET /api/bikes returnerer 2 sykler", s == 200 and len(bikes) == 2, f"n={len(bikes) if bikes else 0}")

        s, b, _ = req("PUT", base, f"/api/bikes/{bike_id}", {"owner": "Anna", "type": "Terrengsykkel", "km": 1300})
        check("PUT /api/bikes/:id oppdaterer", s == 200 and b["km"] == 1300, f"status={s} body={b}")

        s, err, _ = req("PUT", base, "/api/bikes/999", {"owner": "A", "type": "B", "km": 1})
        check("PUT /api/bikes/999 -> 404", s == 404, f"status={s}")

        s, e, _ = req("POST", base, "/api/service",
                      {"bike_id": bike_id, "component": "kjede", "date": "2025-11-01", "km": 1280, "note": "Shimano Deore"})
        check("POST /api/service gyldig", s == 201 and e["component_label"] == "Kjede" and e["bike_owner"] == "Anna",
              f"status={s} body={e}")
        entry_id = e["id"]

        s, e2, _ = req("POST", base, "/api/service",
                       {"bike_id": bike2_id, "component": "skivebremser", "date": "2025-11-05", "km": 3100, "note": ""})
        entry2_id = e2["id"]

        s, err, _ = req("POST", base, "/api/service",
                        {"bike_id": bike_id, "component": "motor", "date": "2025-11-01", "km": 1, "note": ""})
        check("POST /api/service ukjent komponent -> 400", s == 400, f"status={s} body={err}")

        s, err, _ = req("POST", base, "/api/service",
                        {"bike_id": bike_id, "component": "kjede", "date": "01.11.2025", "km": 1, "note": ""})
        check("POST /api/service ugyldig datoformat -> 400", s == 400, f"status={s}")

        s, err, _ = req("POST", base, "/api/service",
                        {"bike_id": bike_id, "component": "kjede", "date": "2025-02-30", "km": 1, "note": ""})
        check("POST /api/service ugyldig kalenderdato -> 400", s == 400, f"status={s}")

        s, err, _ = req("POST", base, "/api/service",
                        {"bike_id": 999, "component": "kjede", "date": "2025-11-01", "km": 1, "note": ""})
        check("POST /api/service ukjent sykkel -> 400", s == 400, f"status={s}")

        s, entries, _ = req("GET", base, "/api/service")
        check("GET /api/service returnerer 2, nyeste først",
              s == 200 and len(entries) == 2 and entries[0]["id"] == entry2_id, f"body={entries}")

        s, entries, _ = req("GET", base, f"/api/service?bike_id={bike_id}")
        check("GET /api/service?bike_id= filtrerer",
              s == 200 and len(entries) == 1 and entries[0]["component"] == "kjede", f"body={entries}")

        s, comps, _ = req("GET", base, "/api/components")
        keys = sorted(c["key"] for c in comps) if comps else []
        expected = sorted(["kjede", "bremseklosser", "dekk", "slanger", "kassett", "kabler",
                           "kranklager", "hjullager", "gaffelservice", "skivebremser"])
        check("GET /api/components returnerer alle 10 komponenter", s == 200 and keys == expected,
              f"status={s} keys={keys} expected={expected}")

        s, e, _ = req("PUT", base, f"/api/service/{entry_id}",
                      {"bike_id": bike_id, "component": "kassett", "date": "2025-11-02", "km": 1290, "note": "11-42"})
        check("PUT /api/service/:id oppdaterer", s == 200 and e["component"] == "kassett" and e["note"] == "11-42",
              f"status={s} body={e}")

        s, _, _ = req("DELETE", base, f"/api/service/{entry_id}")
        check("DELETE /api/service/:id -> 204", s == 204, f"status={s}")

        s, err, _ = req("DELETE", base, "/api/service/999")
        check("DELETE /api/service/999 -> 404", s == 404, f"status={s}")

        s, bikes, _ = req("GET", base, "/api/bikes")
        b1 = next(b for b in bikes if b["id"] == bike_id)
        check("sykkel uten oppføringer har entry_count=0 og ingen last_component",
              b1["entry_count"] == 0 and b1["last_component"] is None and b1["last_date"] is None, f"bike={b1}")

        s, _, _ = req("DELETE", base, f"/api/bikes/{bike2_id}")
        s2, entries, _ = req("GET", base, "/api/service")
        check("slette sykkel kaskaderer serviceoppføringer",
              s == 204 and all(e["bike_id"] != bike2_id for e in entries), f"entries={entries}")

        s, _, raw = req("GET", base, "/")
        check("GET / serverer index.html", s == 200 and b"Sykkellogg" in raw, f"status={s}")

        s, _, raw = req("GET", base, "/app.js")
        check("GET /app.js -> 200", s == 200 and len(raw) > 1000, f"status={s}")

        s, _, raw = req("GET", base, "/styles.css")
        check("GET /styles.css -> 200", s == 200, f"status={s}")

        s, _, _ = req("GET", base, "/api/nope")
        check("GET /api/nope -> 404", s == 404, f"status={s}")

        s, _, _ = req("GET", base, "/app.py")
        check("GET /app.py blokkert -> 404", s == 404, f"status={s}")

        server.shutdown()
        server.server_close()

        server2 = app.create_server("127.0.0.1", 0, db_path, seed=False)
        port2 = server2.server_address[1]
        base2 = f"http://127.0.0.1:{port2}"
        t2 = threading.Thread(target=server2.serve_forever, daemon=True)
        t2.start()
        s, bikes, _ = req("GET", base2, "/api/bikes")
        check("persistens: sykkel overlever restart",
              s == 200 and len(bikes) == 1 and bikes[0]["owner"] == "Anna" and bikes[0]["km"] == 1300,
              f"body={bikes}")
        server2.shutdown()
        server2.server_close()

    print(f"\nResultat: {PASS} bestått, {FAIL} feilet")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
