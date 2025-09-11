# app.py
import os
import time
from datetime import datetime
from werkzeug.utils import secure_filename
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash, abort
from flask_sqlalchemy import SQLAlchemy
import cloudinary
import cloudinary.uploader

# -------------------- Config --------------------
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change_this_secret_key")

# DATABASE URL handling (local fallback to sqlite for easy local dev)
db_url = os.environ.get("DATABASE_URL")
if db_url:
    # Some providers return "postgres://..." which SQLAlchemy no longer accepts.
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
else:
    # Local dev fallback (file-based SQLite)
    db_url = "sqlite:///lostfound.db"

app.config["SQLALCHEMY_DATABASE_URI"] = db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# Allowed file types
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}

# Admin creds (for demo only — use env vars in production)
ADMIN_USER = os.environ.get("ADMIN_USER", "Diwakar")
ADMIN_PASS = os.environ.get("ADMIN_PASS", "diwa@11")

# -------------------- Cloudinary Config --------------------
cloudinary.config(
    cloud_name=os.environ.get("CLOUDINARY_CLOUD_NAME"),
    api_key=os.environ.get("CLOUDINARY_API_KEY"),
    api_secret=os.environ.get("CLOUDINARY_API_SECRET")
)

# -------------------- Models --------------------
def now_iso():
    return datetime.utcnow().isoformat()

class FoundItem(db.Model):
    __tablename__ = "found_items"
    id = db.Column(db.Integer, primary_key=True)
    image = db.Column(db.String, nullable=False)
    description = db.Column(db.String, nullable=False)
    contact = db.Column(db.String, nullable=False)
    created_at = db.Column(db.String, default=now_iso)

class LostItem(db.Model):
    __tablename__ = "lost_items"
    id = db.Column(db.Integer, primary_key=True)
    image = db.Column(db.String, nullable=True)   # may be optional for lost posts
    description = db.Column(db.String, nullable=False)
    contact = db.Column(db.String, nullable=False)
    created_at = db.Column(db.String, default=now_iso)

class HelpPost(db.Model):
    __tablename__ = "help_posts"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String, nullable=False)
    description = db.Column(db.String, nullable=False)
    contact = db.Column(db.String, nullable=False)
    requester_name = db.Column(db.String, nullable=False, default="Anonymous")
    created_at = db.Column(db.String, default=now_iso)

class Message(db.Model):
    __tablename__ = "messages"
    id = db.Column(db.Integer, primary_key=True)
    help_id = db.Column(db.Integer, db.ForeignKey("help_posts.id", ondelete="CASCADE"))
    sender_name = db.Column(db.String, nullable=False)
    receiver_name = db.Column(db.String, nullable=True)
    content = db.Column(db.String, nullable=False)
    timestamp = db.Column(db.String, default=now_iso)

# -------------------- Helpers --------------------
def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

# Create tables (safe): will create missing tables, no-op if already present
with app.app_context():
    try:
        db.create_all()
        app.logger.info("Database tables ensured.")
    except Exception:
        app.logger.exception("Error creating DB tables.")

# -------------------- Routes --------------------
@app.route("/")
@app.route("/index")
def index():
    return render_template("index.html")


# -------- Lost (list) --------
@app.route("/lost")
def lost():
    try:
        items = LostItem.query.order_by(LostItem.id.desc()).all()
        return render_template("lost.html", items=items)
    except Exception:
        app.logger.exception("Failed loading lost items")
        # avoid leaking stack trace to users — log and show friendly message
        flash("Unable to load lost items right now. Check logs.", "error")
        return render_template("lost.html", items=[]), 500


# -------- Lost (report/upload) --------
@app.route("/lost/report", methods=["GET", "POST"])
def report_lost():
    if request.method == "POST":
        file = request.files.get("image")
        description = request.form.get("description", "").strip()
        contact = request.form.get("contact", "").strip()

        if not description:
            flash("Description is required.", "error")
            return redirect(url_for("report_lost"))

        image_url = None
        if file and file.filename != "":
            if not allowed_file(file.filename):
                flash("Invalid file type for image.", "error")
                return redirect(url_for("report_lost"))
            # upload to Cloudinary (if configured)
            try:
                filename = secure_filename(f"{int(time.time())}_{file.filename}")
                res = cloudinary.uploader.upload(file, public_id=filename)
                image_url = res.get("secure_url")
            except Exception:
                app.logger.exception("Cloudinary upload failed")
                flash("Image upload failed.", "error")
                return redirect(url_for("report_lost"))

        new_item = LostItem(
            image=image_url,
            description=description,
            contact=contact,
            created_at=datetime.utcnow().isoformat()
        )
        db.session.add(new_item)
        db.session.commit()
        flash("Lost item reported!", "success")
        return redirect(url_for("lost"))

    return render_template("report_lost.html")


# -------- Found (upload/list) --------
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

        # Upload to Cloudinary
        try:
            filename = secure_filename(f"{int(time.time())}_{file.filename}")
            upload_result = cloudinary.uploader.upload(file, public_id=filename)
            image_url = upload_result.get("secure_url")
        except Exception:
            app.logger.exception("Cloudinary upload failed")
            flash("Image upload failed.", "error")
            return redirect(url_for("found"))

        # Save in DB
        new_item = FoundItem(
            image=image_url,
            description=description,
            contact=contact,
            created_at=datetime.utcnow().isoformat()
        )
        db.session.add(new_item)
        db.session.commit()

        flash("Item uploaded successfully!", "success")
        return redirect(url_for("found"))

    # GET: list found items
    found_items = FoundItem.query.order_by(FoundItem.id.desc()).all()
    return render_template("found.html", items=found_items)


# -------- Help board + chat (unchanged) --------
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

        new_post = HelpPost(
            title=title,
            description=description,
            contact=contact,
            requester_name=requester_name,
            created_at=datetime.utcnow().isoformat()
        )
        db.session.add(new_post)
        db.session.commit()

        flash("Help request posted!", "success")
        return redirect(url_for("help_page"))

    posts = HelpPost.query.order_by(HelpPost.id.desc()).all()
    return render_template("help.html", posts=posts)


@app.route("/help/<int:help_id>/chat", methods=["GET", "POST"])
def help_chat(help_id):
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if name:
            session["chat_name"] = name
        return redirect(url_for("help_chat", help_id=help_id))

    post = HelpPost.query.get(help_id)
    if not post:
        return "Help post not found.", 404
    chat_name = session.get("chat_name")
    return render_template("chat.html", post=post, chat_name=chat_name)


@app.route("/help/<int:help_id>/messages")
def get_messages(help_id):
    rows = Message.query.filter_by(help_id=help_id).order_by(Message.id.asc()).all()
    return jsonify([{
        "id": r.id,
        "help_id": r.help_id,
        "sender_name": r.sender_name,
        "receiver_name": r.receiver_name,
        "content": r.content,
        "timestamp": r.timestamp
    } for r in rows])


@app.route("/help/<int:help_id>/send", methods=["POST"])
def send_message(help_id):
    sender = session.get("chat_name") or request.form.get("sender_name", "").strip() or "Anonymous"
    receiver = request.form.get("receiver_name", "").strip()
    content = request.form.get("content", "").strip()
    if not content:
        return jsonify({"ok": False, "error": "Empty message."}), 400

    if not HelpPost.query.get(help_id):
        return jsonify({"ok": False, "error": "Help post not found."}), 404

    msg = Message(
        help_id=help_id,
        sender_name=sender,
        receiver_name=receiver,
        content=content,
        timestamp=datetime.utcnow().isoformat()
    )
    db.session.add(msg)
    db.session.commit()
    return jsonify({"ok": True})


# -------- Admin (shows both found & lost) --------
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
        found_items = FoundItem.query.order_by(FoundItem.id.desc()).all()
        lost_items = LostItem.query.order_by(LostItem.id.desc()).all()
        posts = HelpPost.query.order_by(HelpPost.id.desc()).all()
        counts = {post.id: Message.query.filter_by(help_id=post.id).count() for post in posts}

        return render_template("admin.html", found_items=found_items, lost_items=lost_items, posts=posts, counts=counts)
    return render_template("admin.html")


@app.route("/admin/delete/found/<int:item_id>")
def admin_delete_found(item_id):
    if not session.get("admin"):
        return redirect(url_for("admin"))
    item = FoundItem.query.get(item_id)
    if item:
        db.session.delete(item)
        db.session.commit()
    return redirect(url_for("admin"))


@app.route("/admin/delete/lost/<int:item_id>")
def admin_delete_lost(item_id):
    if not session.get("admin"):
        return redirect(url_for("admin"))
    item = LostItem.query.get(item_id)
    if item:
        db.session.delete(item)
        db.session.commit()
    return redirect(url_for("admin"))


@app.route("/admin/delete/help/<int:help_id>")
def admin_delete_help(help_id):
    if not session.get("admin"):
        return redirect(url_for("admin"))
    post = HelpPost.query.get(help_id)
    if post:
        Message.query.filter_by(help_id=help_id).delete()
        db.session.delete(post)
        db.session.commit()
    return redirect(url_for("admin"))


@app.route("/logout")
def logout():
    session.pop("admin", None)
    return redirect(url_for("index"))


# -------------------- Run --------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    # For production on Render use gunicorn; this block helps local dev.
    app.run(host="0.0.0.0", port=port)
