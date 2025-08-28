# College Lost & Found

Flask + SQLite mini-project for college lost/found/help with 1:1 chat.

## Features
- Home with three cards (Lost, Found, Help) + tiny Admin link on bottom-left.
- Lost page: list-only (no upload).
- Found page: upload image + description + contact.
- Help page: create help posts and chat 1:1 per post.
- Admin login (Diwakar / diwa@11) to delete posts/items.
- TailwindCSS for a clean, modern UI.

## Run
```bash
pip install -r requirements.txt
python app.py
```
Open http://127.0.0.1:5000

## Notes
- Uploaded images saved to `static/uploads`.
- Database file `lostfound.db` auto-created.
- Messaging uses simple polling every 2 seconds.
