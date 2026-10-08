import os, json, hmac, hashlib, time
from flask import Flask, request, jsonify, send_from_directory

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.environ.get("DATA_DIR", "/data")          # the persistent volume
FILE = os.path.join(DATA, "scripts.json")
USER = os.environ.get("ADMIN_USER", "StudShin")
PASS = os.environ.get("ADMIN_PASS", "")             # set in Wasmer dashboard, NOT in code
SECRET = os.environ.get("SECRET") or PASS

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024

def token():
    return hmac.new(SECRET.encode(), b"admin-v1", hashlib.sha256).hexdigest()

def authed():
    got = request.headers.get("Authorization", "").replace("Bearer ", "", 1)
    return bool(SECRET) and hmac.compare_digest(got, token())

@app.after_request
def no_cache(resp):
    # always serve fresh data/pages (avoids stale 304 / cached old index.html)
    resp.headers["Cache-Control"] = "no-store"
    return resp

@app.get("/")
def index():
    return send_from_directory(HERE, "index.html")

@app.get("/api/scripts")
def get_scripts():
    try:
        with open(FILE, encoding="utf-8") as f:
            return jsonify(json.load(f))
    except Exception:
        return jsonify(None), 404

@app.post("/api/login")
def login():
    d = request.get_json(silent=True) or {}
    ok = (PASS and hmac.compare_digest(str(d.get("user", "")), USER)
          and hmac.compare_digest(str(d.get("pass", "")), PASS))
    if not ok:
        time.sleep(1.5)  # slow down guessing
        return jsonify(error="bad"), 401
    return jsonify(token=token())

@app.post("/api/scripts")
def save_scripts():
    if not authed():
        return jsonify(error="auth"), 401
    d = request.get_json(silent=True)
    if not isinstance(d, list) or not 0 < len(d) <= 100:
        return jsonify(error="invalid"), 400
    clean = []
    for s in d:
        if not isinstance(s, dict) or not all(isinstance(s.get(k), str) for k in ("name", "zh", "en", "code")):
            return jsonify(error="invalid"), 400
        if len(s["name"]) > 80 or len(s["code"]) > 400_000:
            return jsonify(error="too big"), 400
        clean.append({k: s[k] for k in ("name", "zh", "en", "code")})
    try:
        os.makedirs(DATA, exist_ok=True)
        tmp = FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(clean, f, ensure_ascii=False)
        os.replace(tmp, FILE)
    except OSError as e:
        return jsonify(error="storage: " + (e.strerror or "cannot write")), 500
    return jsonify(ok=True)

@app.get("/api/health")
def health():
    """Open /api/health in the browser to check the setup (shows no secrets)."""
    writable = False
    try:
        os.makedirs(DATA, exist_ok=True)
        t = os.path.join(DATA, ".w")
        open(t, "w").close(); os.remove(t); writable = True
    except OSError:
        pass
    return jsonify(data_dir=DATA, writable=writable,
                   scripts_file_exists=os.path.exists(FILE),
                   admin_pass_set=bool(PASS), admin_user=USER)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
