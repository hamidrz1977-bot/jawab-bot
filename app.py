import os
from flask import Flask, request

app = Flask(__name__)

@app.route("/")
def home():
    return "Hello from Jawab! ✅"

@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    if request.method == "GET":
        mode = request.args.get("hub.mode")
        challenge = request.args.get("hub.challenge")
        token = request.args.get("hub.verify_token")
        verify_token = os.getenv("VERIFY_TOKEN", "CHANGE_ME")
        if mode == "subscribe" and token == verify_token:
            return challenge, 200
        return "Verification failed", 403

    # POST: فعلاً فقط تأیید دریافت
    return "EVENT_RECEIVED", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
# --- Telegram webhook (Jawab) ---
import os, requests
from flask import request, jsonify

TG_TOKEN = os.getenv("TG_BOT_TOKEN")

@app.route("/telegram", methods=["POST"])
def telegram_webhook():
    data = request.get_json(silent=True) or {}
    try:
        if "message" in data:
            chat_id = data["message"]["chat"]["id"]
            text = data["message"].get("text", "")
            send_telegram_text(chat_id, f"سلام از Jawab 👋\nپیام شما رسید: {text}")
    except Exception as e:
        app.logger.exception(e)
    return jsonify(ok=True)

def send_telegram_text(chat_id, text):
    if not TG_TOKEN:
        app.logger.warning("TG_BOT_TOKEN not set; skipping Telegram send.")
        return
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    r = requests.post(url, json=payload, timeout=15)
    app.logger.info(f"TG SEND RESP: {r.status_code} {r.text}")
