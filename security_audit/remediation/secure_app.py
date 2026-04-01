"""Hardened Flask application — remediates all 6 OWASP findings.
Production-ready patterns for each vulnerability class.
"""
import hashlib
import hmac
import ipaddress
import os
import re
import secrets
import socket
import sqlite3
import subprocess
from functools import wraps
from typing import Optional

from flask import Flask, jsonify, request, session
from markupsafe import escape

app = Flask(__name__)
# FIX AUTH-02: Secret from environment, never hardcoded
app.secret_key = os.environ.get("FLASK_SECRET_KEY") or secrets.token_hex(32)
DB_PATH = "/tmp/secure_app.db"

# ---------------------------------------------------------------------------
# PRIVATE-IP BLOCKLIST for SSRF fix
# ---------------------------------------------------------------------------
_PRIVATE_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),   # AWS/GCP IMDS
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
]

_VALID_HOST_RE = re.compile(
    r'^([a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$'
    r'|^(\d{1,3}\.){3}\d{1,3}$'
)


def _hash_password(password: str, salt: Optional[str] = None) -> str:
    """PBKDF2-HMAC-SHA256 password hashing."""
    if salt is None:
        salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 260_000)
    return f"{salt}${dk.hex()}"


def _check_password(password: str, stored_hash: str) -> bool:
    salt, _ = stored_hash.split("$", 1)
    return hmac.compare_digest(_hash_password(password, salt), stored_hash)


def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            email TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY,
            owner_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            content TEXT,
            is_private INTEGER DEFAULT 1
        )
    """)
    try:
        admin_hash = _hash_password("admin-strong-passphrase-2024!")
        alice_hash = _hash_password("alice-passphrase-2024!")
        c.execute("INSERT INTO users (username, password_hash, role, email) VALUES (?, ?, ?, ?)",
                  ("admin", admin_hash, "admin", "admin@example.com"))
        c.execute("INSERT INTO users (username, password_hash, role, email) VALUES (?, ?, ?, ?)",
                  ("alice", alice_hash, "user", "alice@example.com"))
        c.execute("INSERT INTO documents (owner_id, title, content, is_private) VALUES (?, ?, ?, ?)",
                  (1, "Admin Secret", "Top secret admin content", 1))
        c.execute("INSERT INTO documents (owner_id, title, content, is_private) VALUES (?, ?, ?, ?)",
                  (2, "Alice's Note", "Alice private note", 1))
    except sqlite3.IntegrityError:
        pass
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return jsonify({"error": "login required"}), 401
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        # FIX AUTH-01: role read from server-side session ONLY
        if session.get("role") != "admin":
            return jsonify({"error": "forbidden"}), 403
        return f(*args, **kwargs)
    return decorated


# ---------------------------------------------------------------------------
# FIX 1: SQL Injection — parameterized queries
# ---------------------------------------------------------------------------
@app.route("/login", methods=["POST"])
def login():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    if not username or not password:
        return jsonify({"error": "username and password required"}), 400

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # SECURE: parameterized query — no string interpolation
    c.execute(
        "SELECT id, username, role, password_hash FROM users WHERE username = ?",
        (username,),
    )
    row = c.fetchone()
    conn.close()

    if row and _check_password(password, row[3]):
        session.clear()
        session["user_id"]  = row[0]
        session["username"] = row[1]
        session["role"]     = row[2]
        return jsonify({"status": "ok", "username": row[1]})
    return jsonify({"status": "fail"}), 401


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"status": "ok"})


# ---------------------------------------------------------------------------
# FIX 2: XSS — HTML-escape user input via markupsafe
# ---------------------------------------------------------------------------
@app.route("/search")
def search():
    raw_query = request.args.get("q", "")
    # SECURE: escape() neutralizes all HTML special characters
    safe_query = escape(raw_query)
    # Return JSON (no HTML rendering of user input at all)
    return jsonify({"query": str(safe_query), "results": []})


# ---------------------------------------------------------------------------
# FIX 3: Broken Auth — server-side session role check only
# ---------------------------------------------------------------------------
@app.route("/admin")
@admin_required
def admin_panel():
    # SECURE: role is from session (signed, server-side), never from header
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, username, email, role FROM users")
    users = [{"id": r[0], "username": r[1], "email": r[2], "role": r[3]} for r in c.fetchall()]
    conn.close()
    return jsonify({"users": users})


# ---------------------------------------------------------------------------
# FIX 4: IDOR — ownership enforcement
# ---------------------------------------------------------------------------
@app.route("/document/<int:doc_id>")
@login_required
def get_document(doc_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # SECURE: WHERE clause enforces ownership — admin may read all
    if session.get("role") == "admin":
        c.execute("SELECT id, owner_id, title, content FROM documents WHERE id = ?", (doc_id,))
    else:
        # Regular users only see their own documents
        c.execute(
            "SELECT id, owner_id, title, content FROM documents WHERE id = ? AND owner_id = ?",
            (doc_id, session["user_id"]),
        )
    doc = c.fetchone()
    conn.close()
    if doc:
        return jsonify({"id": doc[0], "title": doc[2], "content": doc[3]})
    # SECURE: 404 not 403 to avoid confirming object existence
    return jsonify({"error": "not found"}), 404


# ---------------------------------------------------------------------------
# FIX 5: SSRF — allowlist + private IP blocking
# ---------------------------------------------------------------------------
ALLOWED_FETCH_HOSTS = os.environ.get("ALLOWED_FETCH_HOSTS", "").split(",")


def _is_private_ip(hostname: str) -> bool:
    """Returns True if hostname resolves to a private/loopback address."""
    try:
        addrs = socket.getaddrinfo(hostname, None)
        for addr in addrs:
            ip = ipaddress.ip_address(addr[4][0])
            for net in _PRIVATE_NETWORKS:
                if ip in net:
                    return True
    except Exception:
        return True  # fail-closed on resolution errors
    return False


@app.route("/fetch")
@login_required
def fetch_url():
    import urllib.parse
    import urllib.request

    url = request.args.get("url", "")
    if not url:
        return jsonify({"error": "url required"}), 400

    parsed = urllib.parse.urlparse(url)
    # SECURE: only https allowed
    if parsed.scheme != "https":
        return jsonify({"error": "only https URLs permitted"}), 400

    hostname = parsed.hostname or ""
    # SECURE: allowlist enforcement (when configured)
    if ALLOWED_FETCH_HOSTS and ALLOWED_FETCH_HOSTS[0]:
        if hostname not in ALLOWED_FETCH_HOSTS:
            return jsonify({"error": "host not in allowlist"}), 400

    # SECURE: block private/internal IP ranges
    if _is_private_ip(hostname):
        return jsonify({"error": "access to internal hosts denied"}), 400

    try:
        with urllib.request.urlopen(url, timeout=5) as resp:  # noqa: S310
            content = resp.read(4096).decode("utf-8", errors="replace")
        return jsonify({"content": content})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


# ---------------------------------------------------------------------------
# FIX 6: Command Injection — shell=False + strict input validation
# ---------------------------------------------------------------------------
@app.route("/ping")
def ping_host():
    host = request.args.get("host", "").strip()
    # SECURE: strict allowlist regex — reject anything with special chars
    if not _VALID_HOST_RE.match(host):
        return jsonify({"error": "invalid host — only hostnames and IPv4 addresses accepted"}), 400

    # SECURE: shell=False, args as a list — no shell expansion possible
    result = subprocess.run(
        ["ping", "-c", "1", host],
        shell=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    return jsonify({"stdout": result.stdout, "returncode": result.returncode})


if __name__ == "__main__":
    init_db()
    # SECURE: debug=False, no debug output in production
    app.run(debug=False, port=5002)
