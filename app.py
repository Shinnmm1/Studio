"""Studio Shin - script library backend.

Storage (automatic):
  * Upstash Redis  -> if UPSTASH_REDIS_REST_URL/TOKEN (or Vercel's KV_REST_API_URL/TOKEN) are set
  * a JSON file    -> otherwise (needs a persistent volume, e.g. on Wasmer)
Works on Vercel, Wasmer, Render, Koyeb... any host that runs Flask.
"""
import os, json, hmac, hashlib, time, urllib.request
from flask import Flask, request, jsonify, send_from_directory

HERE = os.path.dirname(os.path.abspath(__file__))
USER = os.environ.get("ADMIN_USER", "StudShin")
PASS = os.environ.get("ADMIN_PASS", "")             # set in the host's dashboard, NOT in code
SECRET = os.environ.get("SECRET") or PASS

# --- storage config ---
RURL = (os.environ.get("UPSTASH_REDIS_REST_URL") or os.environ.get("KV_REST_API_URL") or "").rstrip("/")
RTOK = os.environ.get("UPSTASH_REDIS_REST_TOKEN") or os.environ.get("KV_REST_API_TOKEN") or ""
USE_REDIS = bool(RURL and RTOK)
KEY = "studio-shin:scripts"
DATA = os.environ.get("DATA_DIR", "/data")
FILE = os.path.join(DATA, "scripts.json")
MAX_REDIS_BYTES = 900_000                           # stay under Upstash's request size limit

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024


def rcmd(*cmd):
    """Run one Redis command through Upstash's REST API (no extra packages needed)."""
    req = urllib.request.Request(
        RURL, data=json.dumps(list(cmd)).encode("utf-8"), method="POST",
        headers={"Authorization": "Bearer " + RTOK, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=8) as r:
        out = json.loads(r.read().decode("utf-8"))
    if isinstance(out, dict) and out.get("error"):
        raise OSError(out["error"])
    return out.get("result") if isinstance(out, dict) else None


def load_scripts():
    if USE_REDIS:
        raw = rcmd("GET", KEY)
        return json.loads(raw) if raw else None
    try:
        with open(FILE, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return None


def store_scripts(items):
    text = json.dumps(items, ensure_ascii=False)
    if USE_REDIS:
        if len(text.encode("utf-8")) > MAX_REDIS_BYTES:
            raise ValueError("too big (max about 900KB in total)")
        rcmd("SET", KEY, text)
        return
    os.makedirs(DATA, exist_ok=True)
    tmp = FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, FILE)


def token():
    return hmac.new(SECRET.encode(), b"admin-v1", hashlib.sha256).hexdigest()


def authed():
    got = request.headers.get("Authorization", "").replace("Bearer ", "", 1)
    return bool(SECRET) and hmac.compare_digest(got, token())


@app.after_request
def no_cache(resp):
    resp.headers["Cache-Control"] = "no-store"   # always fresh pages/data
    return resp


@app.get("/")
def index():
    return send_from_directory(HERE, "index.html")


@app.get("/api/scripts")
def get_scripts():
    try:
        data = load_scripts()
    except Exception as e:
        return jsonify(error="storage: %s" % e), 502
    if data is None:
        return jsonify(None), 404
    return jsonify(data)


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
        store_scripts(clean)
    except ValueError as e:
        return jsonify(error=str(e)), 400
    except Exception as e:
        return jsonify(error="storage: %s" % (getattr(e, "strerror", None) or e)), 500
    return jsonify(ok=True)


@app.get("/api/health")
def health():
    """Open /api/health in the browser to check the setup (shows no secrets)."""
    info = dict(storage="redis" if USE_REDIS else "file", admin_pass_set=bool(PASS), admin_user=USER)
    try:
        if USE_REDIS:
            info["storage_ok"] = rcmd("PING") == "PONG"
        else:
            os.makedirs(DATA, exist_ok=True)
            t = os.path.join(DATA, ".w")
            open(t, "w").close(); os.remove(t)
            info["storage_ok"] = True
            info["data_dir"] = DATA
        info["has_saved_scripts"] = load_scripts() is not None
    except Exception as e:
        info["storage_ok"] = False
        info["storage_error"] = str(e)[:200]
    return jsonify(info)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
