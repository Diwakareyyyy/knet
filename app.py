from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from datetime import datetime
import os, time, cloudinary, cloudinary.uploader

# -------------------- Config --------------------
app = Flask(__name__)
app.secret_key = "change_this_secret_key"

# Use Render PostgreSQL database (set in env variable for security)
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
    "DATABASE_URL",
    "postgresql://diwa_2203_k_net_user:8HHxgtbZ4Ap1pNFt8tIjEAFWzqmuRlpZ@dpg-d302if0gjchc73clqol0-a.oregon-postgres.render.com/diwa_2203_k_net"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# Allowed file types
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}

# Admin creds
ADMIN_USER = "Diwakar"
ADMIN_PASS = "diwa@11"

# -------------------- Cloudinary Config --------------------
cloudinary.config(
    cloud_name=os.environ.get("CLOUDINARY_CLOUD_NAME", "dtotaxzqn"),
    api_key=os.environ.get("CLOUDINARY_API_KEY", "552353135944524"),
    api_secret=os.environ.get("CLOUDINARY_API_SECRET", "KXzryxR9P8n_vwZtg415HcX_c9c")
)

# -------------------- Models --------------------
class FoundItem(db.Model):
    __tablename__ = "found_items"
    id = db.Column(db.Integer, primary_key=True)
    image = db.Column(db.String, nullable=False)   # URL from Cloudinary
    description = db.Column(db.String, nullable=False)
    contact = db.Column(db.String, nullable=False)
    created_at = db.Column(db.String, default=datetime.utcnow().isoformat)

class HelpPost(db.Model):
    __tablename__ = "help_posts"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String, nullable=False)
    description = db.Column(db.String, nullable=False)
    contact = db.Column(db.String, nullable=False)
    requester_name = db.Column(db.String, nullable=False, default="Anonymous")
    created_at = db.Column(db.String, default=datetime.utcnow().isoformat)

class Message(db.Model):
    __tablename__ = "messages"
    id = db.Column(db.Integer, primary_key=True)
    help_id = db.Column(db.Integer, db.ForeignKey("help_posts.id", ondelete="CASCADE"))
    sender_name = db.Column(db.String, nullable=False)
    receiver_name = db.Column(db.String, nullable=True)
    content = db.Column(db.String, nullable=False)
    timestamp = db.Column(db.String, default=datetime.utcnow().isoformat)

# -------------------- Helpers --------------------
def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

with app.app_context():
    db.create_all()

# -------------------- Routes --------------------
@app.route("/index")
def index():
    return render_template("index.html")

# -------- Lost (List only) --------
@app.route("/lost")
def lost():
    items = FoundItem.query.order_by(FoundItem.id.desc()).all()
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

        # Upload to Cloudinary
        filename = secure_filename(f"{int(time.time())}_{file.filename}")
        upload_result = cloudinary.uploader.upload(file, public_id=filename)
        image_url = upload_result["secure_url"]

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

# -------- Help Chat --------
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

# -------- Admin --------
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
        posts = HelpPost.query.order_by(HelpPost.id.desc()).all()
        counts = {msg.help_id: db.session.query(Message).filter_by(help_id=msg.help_id).count() for msg in posts}
        return render_template("admin.html", found_items=found_items, posts=posts, counts=counts)
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
    app.run(host="0.0.0.0", port=port)
