#!/usr/bin/env python3
"""Check a newly started, empty runtime over HTTP; no account or secrets needed."""
import json
import sys
import time
from urllib.error import URLError
from urllib.request import urlopen

base = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000").rstrip("/")
for attempt in range(90):
    try:
        with urlopen(base + "/api/v1/quest/bootstrap", timeout=3) as response:
            bootstrap = json.load(response)
        break
    except (URLError, TimeoutError):
        time.sleep(1)
else:
    raise SystemExit("Quest did not become ready within 90 attempts")

assert bootstrap["success"] is True, bootstrap
data = bootstrap["data"]
assert data["event"]["status"] == "draft", data["event"]
assert len(data["rooms"]) == 5, data["rooms"]
assert all(not room["steps"] for room in data["rooms"]), "Unexpected seeded challenges"
for route in ("/", "/quest", "/quest/standings", "/quest/stage", "/login"):
    with urlopen(base + route, timeout=5) as response:
        assert response.status == 200, route
        assert b"<html" in response.read().lower(), route
for asset in ("quest.js", "quest.css"):
    with urlopen(base + "/plugins/open_tech_quest/assets/app/" + asset, timeout=5) as response:
        assert response.status == 200 and response.read(1), asset
print("Runtime smoke passed: shell, assets, draft event, five empty rooms")
