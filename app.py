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
