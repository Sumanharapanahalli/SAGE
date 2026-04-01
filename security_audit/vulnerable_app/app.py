"""Intentionally vulnerable Flask web application for OWASP Top 10 audit.
DO NOT deploy this in production — educational/training use only.
"""
import sqlite3
import os
import subprocess
import urllib.request
from functools import wraps
from flask import Flask, request, jsonify, session, render_template_string

app = Flask(__name__)
app.secret_key = "hardcoded_secret_123"  # VULN: hardcoded weak secret
DB_PATH = "/tmp/vulnerable_app.db"


def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT UNIQUE,
            password TEXT,
            role TEXT DEFAULT 'user',
            email TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY,
            owner_id INTEGER,
            title TEXT,
            content TEXT,
            is_private INTEGER DEFAULT 1
        )
    """)
    # Seed data
    try:
        c.execute("INSERT INTO users (username, password, role, email) VALUES (?, ?, ?, ?)",
                  ("admin", "admin123", "admin", "admin@example.com"))
        c.execute("INSERT INTO users (username, password, role, email) VALUES (?, ?, ?, ?)",
                  ("alice", "password1", "user", "alice@example.com"))
        c.execute("INSERT INTO users (username, password, role, email) VALUES (?, ?, ?, ?)",
                  ("bob", "secret99", "user", "bob@example.com"))
        c.execute("INSERT INTO documents (owner_id, title, content, is_private) VALUES (?, ?, ?, ?)",
                  (1, "Admin Secret", "Top secret admin content", 1))
        c.execute("INSERT INTO documents (owner_id, title, content, is_private) VALUES (?, ?, ?, ?)",
                  (2, "Alice's Note", "Alice private note", 1))
    except sqlite3.IntegrityError:
        pass
    conn.commit()
    conn.close()


# --- VULNERABILITY 1: SQL Injection (A03:2021) ---
@app.route("/login", methods=["POST"])
def login():
    """VULN: SQL Injection — username input directly interpolated into query."""
    username = request.form.get("username", "")
    password = request.form.get("password", "")
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # DANGEROUS: string formatting in SQL query
    query = f"SELECT id, username, role FROM users WHERE username = '{username}' AND password = '{password}'"
    try:
        c.execute(query)
        user = c.fetchone()
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    finally:
        conn.close()
    if user:
        session["user_id"] = user[0]
        session["username"] = user[1]
        session["role"] = user[2]
        return jsonify({"status": "ok", "username": user[1], "role": user[2]})
    return jsonify({"status": "fail"}), 401


# --- VULNERABILITY 2: XSS — Reflected (A03:2021) ---
@app.route("/search")
def search():
    """VULN: Reflected XSS — user input rendered directly in HTML without escaping."""
    query = request.args.get("q", "")
    # DANGEROUS: raw user input embedded in HTML
    html = f"""
    <html><body>
      <h1>Search Results for: {query}</h1>
      <p>No results found.</p>
    </body></html>
    """
    return render_template_string(html)


# --- VULNERABILITY 3: Broken Authentication — Weak Session (A07:2021) ---
@app.route("/admin")
def admin_panel():
    """VULN: Broken auth — role check is client-supplied, easily bypassed."""
    # DANGEROUS: trusting user-supplied header for authorization
    role = request.headers.get("X-User-Role", session.get("role", ""))
    if role == "admin":
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT id, username, email, role FROM users")
        users = [{"id": r[0], "username": r[1], "email": r[2], "role": r[3]} for r in c.fetchall()]
        conn.close()
        return jsonify({"users": users})
    return jsonify({"error": "forbidden"}), 403


# --- VULNERABILITY 4: IDOR — Insecure Direct Object Reference (A01:2021) ---
@app.route("/document/<int:doc_id>")
def get_document(doc_id):
    """VULN: IDOR — no ownership check, any authenticated user can read any document."""
    # DANGEROUS: only checks session exists, not ownership
    if "user_id" not in session:
        return jsonify({"error": "login required"}), 401
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, owner_id, title, content FROM documents WHERE id = ?", (doc_id,))
    doc = c.fetchone()
    conn.close()
    if doc:
        return jsonify({"id": doc[0], "owner_id": doc[1], "title": doc[2], "content": doc[3]})
    return jsonify({"error": "not found"}), 404


# --- VULNERABILITY 5: SSRF — Server-Side Request Forgery (A10:2021) ---
@app.route("/fetch")
def fetch_url():
    """VULN: SSRF — fetches arbitrary user-supplied URLs including internal services."""
    url = request.args.get("url", "")
    if not url:
        return jsonify({"error": "url required"}), 400
    try:
        # DANGEROUS: no allowlist, no private IP blocking
        with urllib.request.urlopen(url, timeout=5) as resp:
            content = resp.read(1024).decode("utf-8", errors="replace")
        return jsonify({"content": content})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# --- VULNERABILITY 6: Command Injection (A03:2021) ---
@app.route("/ping")
def ping_host():
    """VULN: Command injection — host parameter passed directly to shell."""
    host = request.args.get("host", "8.8.8.8")
    # DANGEROUS: shell=True with unsanitized input
    result = subprocess.run(
        f"ping -c 1 {host}",
        shell=True, capture_output=True, text=True, timeout=10
    )
    return jsonify({"stdout": result.stdout, "stderr": result.stderr})


if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5001)  # VULN: debug=True in production
