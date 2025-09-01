if text.startswith("/start"):
    parts = text.split(" ", 1)
    if len(parts) == 2 and parts[1].strip():
        from storage.db import set_user_source
        set_user_source(chat_id, parts[1].strip())
import os, time, logging, json
from collections import defaultdict, deque
import requests
from flask import Flask, request, jsonify

# --- DB imports (حتماً بالای فایل) ---
from storage.db import init_db, upsert_user, get_user_lang, set_user_lang, log_message, get_stats, list_user_ids
init_db()  # دیتابیس همان لحظه ایجاد می‌شود

app = Flask(__name__)

# ----- ENV -----
# هر دو نام را پشتیبانی می‌کنیم: TELEGRAM_BOT_TOKEN یا TG_BOT_TOKEN
BOT_TOKEN = (os.environ.get("TG_BOT_TOKEN") or os.environ.get("TELEGRAM_BOT_TOKEN") or "").strip()
if not BOT_TOKEN:
    raise RuntimeError("ENV TG_BOT_TOKEN (or TELEGRAM_BOT_TOKEN) is missing.")
TG_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

ADMINS_ENV = os.environ.get("ADMINS", "").strip()
ADMINS = {int(x) for x in ADMINS_ENV.split(",") if x.strip().isdigit()}

# ----- Logging -----
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("jawab")

# ----- Rate limit -----
rate_bucket = defaultdict(lambda: deque(maxlen=10))  # chat_id -> last timestamps

# ----- Text packs -----
TEXT = {
    "FA": {
        "welcome": "سلام! من Jawab هستم 👋\nگزینه‌ها: 1) منو 🗂  2) پشتیبانی 🛟  3) زبان 🌐",
        "menu": "منو 🗂\n- قیمت‌ها\n- دربارهٔ ما\n- پشتیبانی 🛟",
        "support": "پشتیبانی 🛟\nبرای گفتگو پیام بده: @welluroo_support (نمونه)\nیا ایمیل: support@welluroo.com",
        "about": "ما Jawab هستیم؛ دستیار پیام‌رسان برای کسب‌وکار شما.",
        "lang_choose": "زبان را انتخاب کنید:",
        "lang_set": "زبان شما روی فارسی تنظیم شد.",
        "default": "سوال شما را متوجه نشدم؛ از «منو 🗂» کمک بگیرید یا «پشتیبانی 🛟».",
        "rate_limit": "لطفاً کمی صبر کنید و آهسته‌تر پیام بدهید 🙏",
        "stats_title": "آمار ربات 📊",
        "broadcast_ok": "پیام برای {n} کاربر ارسال شد.",
        "broadcast_usage": "روش استفاده: /broadcast متن_پیام"
    },
    "EN": {
        "welcome": "Hello! I’m Jawab 👋\nOptions: 1) Menu 🗂  2) Support 🛟  3) Language 🌐",
        "menu": "Menu 🗂\n- Pricing\n- About us\n- Support 🛟",
        "support": "Support 🛟\nDM: @welluroo_support (sample)\nEmail: support@welluroo.com",
        "about": "We are Jawab—your messaging assistant for business.",
        "lang_choose": "Choose your language:",
        "lang_set": "Language set to English.",
        "default": "I didn’t get that. Use “Menu 🗂” or “Support 🛟”.",
        "rate_limit": "Please slow down a bit 🙏",
        "stats_title": "Bot stats 📊",
        "broadcast_ok": "Broadcast sent to {n} users.",
        "broadcast_usage": "Usage: /broadcast your_message"
    },
    "AR": {
        "welcome": "مرحباً! أنا جواب 👋\nالخيارات: 1) القائمة 🗂  2) الدعم 🛟  3) اللغة 🌐",
        "menu": "القائمة 🗂\n- الأسعار\n- من نحن\n- الدعم 🛟",
        "support": "الدعم 🛟\nراسلنا: @welluroo_support (مثال)\nEmail: support@welluroo.com",
        "about": "نحن جواب—مساعد الرسائل لعملك.",
        "lang_choose": "اختر اللغة:",
        "lang_set": "تم ضبط اللغة على العربية.",
        "default": "لم أفهم. استخدم «القائمة 🗂» أو «الدعم 🛟».",
        "rate_limit": "الرجاء الإبطاء قليلاً 🙏",
        "stats_title": "إحصاءات البوت 📊",
        "broadcast_ok": "تم الإرسال إلى {n} مستخدمين.",
        "broadcast_usage": "الاستخدام: /broadcast رسالتك"
    }
}

def reply_keyboard_main(lang):
    labels = {
        "FA": [["منو 🗂", "پشتیبانی 🛟", "زبان 🌐"]],
        "EN": [["Menu 🗂", "Support 🛟", "Language 🌐"]],
        "AR": [["القائمة 🗂", "الدعم 🛟", "اللغة 🌐"]],
    }
    return {"keyboard": labels.get(lang, labels["FA"]), "resize_keyboard": True}

def reply_keyboard_lang():
    return {"keyboard": [["FA 🇮🇷", "EN 🇬🇧", "AR 🇸🇦"]], "resize_keyboard": True, "one_time_keyboard": True}

def rate_limited(chat_id):
    now = time.time()
    q = rate_bucket[chat_id]
    while q and now - q[0] > 5:
        q.popleft()
    q.append(now)
    return len(q) > 5

def send_message(chat_id, text, keyboard=None):
    payload = {"chat_id": chat_id, "text": text}
    if keyboard:
        payload["reply_markup"] = json.dumps(keyboard, ensure_ascii=False)
    try:
        r = requests.post(f"{TG_API}/sendMessage", data=payload, timeout=5)
        logging.info("TG SEND RESP: %s - %s", r.status_code, r.text[:200])
        log_message(chat_id, text, "out")
    except Exception as e:
        logging.exception("sendMessage failed: %s", e)

def handle_text(chat_id, name, text):
    upsert_user(chat_id, name)
    log_message(chat_id, text or "", "in")

    lang = get_user_lang(chat_id)
    t = (text or "").strip()
    lower = t.lower()

    # انتخاب زبان
    if t in ("FA 🇮🇷", "EN 🇬🇧", "AR 🇸🇦"):
        new_lang = "FA" if "FA" in t else ("EN" if "EN" in t else "AR")
        set_user_lang(chat_id, new_lang)
        send_message(chat_id, TEXT[new_lang]["lang_set"], keyboard=reply_keyboard_main(new_lang))
        return

    # Admin: /stats
    if lower.startswith("/stats"):
        if chat_id in ADMINS:
            s = get_stats()
            msg = (f"{TEXT[lang]['stats_title']}\n"
                   f"- Users: {s['users_total']}\n"
                   f"- Messages: {s['messages_total']} (24h: {s['messages_24h']})\n"
                   f"- Langs: {', '.join([f'{k}:{v}' for k,v in s['langs'].items()])}")
            send_message(chat_id, msg)
        return

    # Admin: /broadcast <msg>
    if lower.startswith("/broadcast"):
        if chat_id in ADMINS:
            parts = t.split(" ", 1)
            if len(parts) == 1 or not parts[1].strip():
                send_message(chat_id, TEXT[lang]["broadcast_usage"])
                return
            body = parts[1].strip()
            ids = list_user_ids(limit=200)
            sent = 0
            for uid in ids:
                try:
                    send_message(uid, body); sent += 1
                    time.sleep(0.05)
                except Exception:
                    pass
            send_message(chat_id, TEXT[lang]["broadcast_ok"].format(n=sent))
        return

    # /start
    if lower.startswith("/start"):
        send_message(chat_id, TEXT[lang]["welcome"], keyboard=reply_keyboard_main(lang))
        return

    # Language
    if t in ("زبان 🌐", "Language 🌐", "اللغة 🌐"):
        send_message(chat_id, TEXT[lang]["lang_choose"], keyboard=reply_keyboard_lang())
        return

    # Greetings
    if t in {"سلام","درود","سلام!"} or lower in {"hi","hello","hey"} or t in {"مرحبا","السلام عليكم"}:
        send_message(chat_id, TEXT[lang]["welcome"], keyboard=reply_keyboard_main(lang))
        return

    # Menu/Support/About
    if t in ("منو 🗂","منو","Menu 🗂","Menu","القائمة 🗂","القائمة"):
        send_message(chat_id, TEXT[lang]["menu"], keyboard=reply_keyboard_main(lang)); return
    if t in ("پشتیبانی 🛟","پشتیبانی","Support 🛟","Support","الدعم 🛟","الدعم"):
        send_message(chat_id, TEXT[lang]["support"], keyboard=reply_keyboard_main(lang)); return
    if t in ("درباره ما","About us","من نحن"):
        send_message(chat_id, TEXT[lang]["about"], keyboard=reply_keyboard_main(lang)); return

    # Pricing/Hours
    if "قیمت" in t or "pricing" in lower or "ساعت کاری" in t or "hours" in lower:
        msg = "برای دریافت قیمت و ساعات کاری با «پشتیبانی 🛟» در تماس باشید."
        if lang == "EN": msg = "For pricing and business hours, contact “Support 🛟”."
        if lang == "AR": msg = "للاسعار وساعات العمل تواصل مع «الدعم 🛟»."
        send_message(chat_id, msg, keyboard=reply_keyboard_main(lang)); return

    # Default
    send_message(chat_id, TEXT[lang]["default"], keyboard=reply_keyboard_main(lang))

@app.route("/health", methods=["GET","HEAD"])
def health():
    return jsonify(status="ok")

@app.route("/telegram", methods=["POST","GET"])
def telegram():
    if request.method == "GET":
        return "OK", 200
    try:
        update = request.get_json(silent=True) or {}
        logging.info("INCOMING: %s", str(update)[:500])
        message = update.get("message") or update.get("edited_message") or {}
        chat = message.get("chat") or {}
        chat_id = chat.get("id")
        name = ((chat.get("first_name") or "") + " " + (chat.get("last_name") or "")).strip()
        text = message.get("text") or ""

        if not chat_id:
            return jsonify(ok=True)

        if rate_limited(chat_id):
            lang = get_user_lang(chat_id)
            send_message(chat_id, TEXT[lang]["rate_limit"])
            return jsonify(ok=True)

        handle_text(chat_id, name, text)
    except Exception as e:
        logging.exception("Webhook error: %s", e)
    return jsonify(ok=True)

@app.get("/")
def root():
    return "Jawab bot is running."

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port)

