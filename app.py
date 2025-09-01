import os
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# هر دو اسم را پشتیبانی کن
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN") or os.environ.get("TG_BOT_TOKEN")
API = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage" if BOT_TOKEN else None

WELCOME = (
    "سلام! من Jawab هستم 👋 | Hello! I’m Jawab.\n"
    "گزینه‌ها: 1) منو  2) پشتیبانی  3) دربارهٔ ما"
)
KEYBOARD = {
    "keyboard": [
        [{"text": "منو 🗂"}, {"text": "پشتیبانی 🆘"}],
        [{"text": "دربارهٔ ما ℹ️"}],
    ],
    "resize_keyboard": True,
}

@app.route("/health", methods=["GET", "HEAD"])
def health():
    return jsonify(status="ok")

@app.route("/telegram", methods=["GET", "POST"])
def telegram():
    # اجازه بده GET برگرده 200 تا پروب‌ها 404 نگیرن
    if request.method == "GET":
        return "OK", 200

    if not BOT_TOKEN:
        return jsonify({"error": "TELEGRAM_BOT_TOKEN missing"}), 500

    update = request.get_json(silent=True) or {}
    message = update.get("message") or update.get("edited_message") or {}
    chat_id = (message.get("chat") or {}).get("id")
    text = (message.get("text") or "").strip()

    if not chat_id:
        return jsonify({"ok": True})

    if text == "/start":
        payload = {"chat_id": chat_id, "text": WELCOME, "reply_markup": KEYBOARD}
    else:
        payload = {"chat_id": chat_id, "text": f"گفتی: {text}"}

    r = requests.post(API, json=payload, timeout=10)
    return jsonify({"ok": True, "telegram_status": r.status_code})

@app.route("/", methods=["GET"])
def root():
    return "Jawab bot is running."

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
