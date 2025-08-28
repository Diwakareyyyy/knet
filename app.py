from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_from_directory, flash
import sqlite3, os, time
from werkzeug.utils import secure_filename
from datetime import datetime

# -------------------- Config --------------------
app = Flask(__name__)
app.secret_key = "change_this_secret_key"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "lostfound.db")
UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}
ADMIN_USER = "Diwakar"
ADMIN_PASS = "diwa@11"

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# -------------------- Helpers --------------------
def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    # Items found by students that might match someone's lost belongings
    c.execute("""
        CREATE TABLE IF NOT EXISTS found_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            image TEXT,
            description TEXT,
            contact TEXT,
            created_at TEXT
        )
    """)
    # Public help requests (e.g., "Need printout of syllabus")
    c.execute("""
        CREATE TABLE IF NOT EXISTS help_posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            description TEXT,
            contact TEXT,
            requester_name TEXT,
            created_at TEXT
        )
    """)
    # Messages under a given help request (basic 1-on-1 style chat)
    c.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            help_id INTEGER,
            sender_name TEXT,
            receiver_name TEXT,
            content TEXT,
            timestamp TEXT,
            FOREIGN KEY(help_id) REFERENCES help_posts(id) ON DELETE CASCADE
        )
    """)
    conn.commit()
    conn.close()

init_db()

# -------------------- Routes --------------------
@app.route("/")
def index():
    return render_template("index.html")

# -------- Lost (List only) --------
@app.route("/lost")
def lost():
    conn = get_db()
    items = conn.execute("SELECT * FROM found_items ORDER BY id DESC").fetchall()
    conn.close()
    return render_template("lost.html", items=items)

# -------- Found (Upload) --------
@app.route("/found", methods=["GET", "POST"])
def found():
    if request.method == "POST":
        file = request.files.get("image")
        description = request.form.get("description", "").strip()
        contact = request.form.get("contact", "").strip()

        if not file or file.filename == "":
            flash("Please select an image to upload.", "error")
            return redirect(url_for("found"))
        if not allowed_file(file.filename):
            flash("Invalid file type. Allowed: png, jpg, jpeg, gif.", "error")
            return redirect(url_for("found"))

        filename = secure_filename(f"{int(time.time())}_{file.filename}")
        file.save(os.path.join(UPLOAD_FOLDER, filename))

        conn = get_db()
        conn.execute(
            "INSERT INTO found_items (image, description, contact, created_at) VALUES (?, ?, ?, ?)",
            (filename, description, contact, datetime.utcnow().isoformat())
        )
        conn.commit()
        conn.close()
        flash("Item uploaded successfully!", "success")
        return redirect(url_for("found"))
    return render_template("found.html")

# -------- Help (Board + Create posts) --------
@app.route("/help", methods=["GET", "POST"])
def help_page():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        contact = request.form.get("contact", "").strip()
        requester_name = request.form.get("requester_name", "").strip() or "Anonymous"

        if not title:
            flash("Title is required.", "error")
            return redirect(url_for("help_page"))

        conn = get_db()
        conn.execute(
            "INSERT INTO help_posts (title, description, contact, requester_name, created_at) VALUES (?, ?, ?, ?, ?)",
            (title, description, contact, requester_name, datetime.utcnow().isoformat())
        )
        conn.commit()
        conn.close()
        flash("Help request posted!", "success")
        return redirect(url_for("help_page"))

    conn = get_db()
    posts = conn.execute("SELECT * FROM help_posts ORDER BY id DESC").fetchall()
    conn.close()
    return render_template("help.html", posts=posts)

# -------- Help Chat (1-on-1 style per post) --------
@app.route("/help/<int:help_id>/chat", methods=["GET", "POST"])
def help_chat(help_id):
    # Ensure chat name in session
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if name:
            session["chat_name"] = name
        return redirect(url_for("help_chat", help_id=help_id))

    conn = get_db()
    post = conn.execute("SELECT * FROM help_posts WHERE id = ?", (help_id,)).fetchone()
    conn.close()
    if not post:
        return "Help post not found.", 404

    chat_name = session.get("chat_name")
    return render_template("chat.html", post=post, chat_name=chat_name)

@app.route("/help/<int:help_id>/messages")
def get_messages(help_id):
    conn = get_db()
    rows = conn.execute(
        "SELECT id, help_id, sender_name, receiver_name, content, timestamp FROM messages WHERE help_id = ? ORDER BY id ASC",
        (help_id,)
    ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route("/help/<int:help_id>/send", methods=["POST"])
def send_message(help_id):
    sender = session.get("chat_name") or request.form.get("sender_name", "").strip() or "Anonymous"
    receiver = request.form.get("receiver_name", "").strip()  # optional
    content = request.form.get("content", "").strip()
    if not content:
        return jsonify({"ok": False, "error": "Empty message."}), 400

    # Ensure post exists
    conn = get_db()
    post = conn.execute("SELECT id FROM help_posts WHERE id = ?", (help_id,)).fetchone()
    if not post:
        conn.close()
        return jsonify({"ok": False, "error": "Help post not found."}), 404

    conn.execute(
        "INSERT INTO messages (help_id, sender_name, receiver_name, content, timestamp) VALUES (?, ?, ?, ?, ?)",
        (help_id, sender, receiver, content, datetime.utcnow().isoformat())
    )
    conn.commit()
    conn.close()
    return jsonify({"ok": True})
#--------------------index--------------------
@app.route("/index")
def home():
    return render_template("index.html")   # or whatever your homepage template is
# -------------------- Admin --------------------
@app.route("/admin", methods=["GET", "POST"])
def admin():
    if request.method == "POST":
        user = request.form.get("username", "")
        pw = request.form.get("password", "")
        if user == ADMIN_USER and pw == ADMIN_PASS:
            session["admin"] = True
            return redirect(url_for("admin"))
        else:
            return render_template("admin.html", error="Invalid credentials")
    if session.get("admin"):
        conn = get_db()
        found_items = conn.execute("SELECT * FROM found_items ORDER BY id DESC").fetchall()
        posts = conn.execute("SELECT * FROM help_posts ORDER BY id DESC").fetchall()
        msg_count = conn.execute("SELECT help_id, COUNT(*) as c FROM messages GROUP BY help_id").fetchall()
        conn.close()
        counts = {row["help_id"]: row["c"] for row in msg_count}
        return render_template("admin.html", found_items=found_items, posts=posts, counts=counts)
    return render_template("admin.html")

@app.route("/admin/delete/found/<int:item_id>")
def admin_delete_found(item_id):
    if not session.get("admin"):
        return redirect(url_for("admin"))
    conn = get_db()
    row = conn.execute("SELECT image FROM found_items WHERE id = ?", (item_id,)).fetchone()
    if row and row["image"]:
        try:
            os.remove(os.path.join(UPLOAD_FOLDER, row["image"]))
        except Exception:
            pass
    conn.execute("DELETE FROM found_items WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("admin"))

@app.route("/admin/delete/help/<int:help_id>")
def admin_delete_help(help_id):
    if not session.get("admin"):
        return redirect(url_for("admin"))
    conn = get_db()
    conn.execute("DELETE FROM messages WHERE help_id = ?", (help_id,))
    conn.execute("DELETE FROM help_posts WHERE id = ?", (help_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("admin"))

@app.route("/logout")
def logout():
    session.pop("admin", None)
    return redirect(url_for("index"))

# --------------- Static helper ---------------
@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

# -------------------- Run --------------------
if __name__ == "__main__":
    app.run(debug=True)
