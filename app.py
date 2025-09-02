import os, requests, time, csv, io
from flask import Flask, request, jsonify

# ---------- ENV ----------
BOT_TOKEN = os.environ.get("TG_BOT_TOKEN") or os.environ.get("TELEGRAM_BOT_TOKEN")
API = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage" if BOT_TOKEN else None

BRAND_NAME = os.environ.get("BRAND_NAME", "Jawab")
DEFAULT_LANG = (os.environ.get("DEFAULT_LANG") or "FA").upper()
SUPPORT_WHATSAPP = os.environ.get("SUPPORT_WHATSAPP", "")
ADMINS = [x.strip() for x in (os.environ.get("ADMINS") or "").split(",") if x.strip()]
PLAN = (os.environ.get("PLAN") or "bronze").lower()
SHEET_URL = os.environ.get("SHEET_URL", "").strip()   # برای Silver

# ---------- DB ----------
from storage.db import (
    init_db, upsert_user, get_user_lang, set_user_lang,
    log_message, get_stats, list_user_ids, set_user_source, set_user_phone
)
init_db()

app = Flask(__name__)

# ---------- متن‌ها ----------
TEXT = {
    "FA": {
        "welcome": f"سلام! من {BRAND_NAME} هستم 👋\nگزینه‌ها: 1) منو 🗂  2) پشتیبانی 🛟  3) زبان 🌐",
        "menu": "یکی از گزینه‌های زیر را انتخاب کن:",
        "support": "پشتیبانی 🛟\nبرای گفتگو پیام بده: @welluroo_support" + (f"\nواتساپ: {SUPPORT_WHATSAPP}" if SUPPORT_WHATSAPP else ""),
        "language": "لطفاً زبان را انتخاب کنید: FA / EN / AR",
        "set_ok": "زبان تنظیم شد.",
        "unknown": "متوجه نشدم. از دکمه‌ها استفاده کن یا بنویس: /help",
        "catalog_empty": "کاتالوگ خالی است. اگر مدیر هستی، /sync را بزن.",
        "sync_ok": "کاتالوگ به‌روزرسانی شد: {n} قلم.",
        "sync_fail": "نشد! آدرس Sheet یا فرمت CSV را چک کن.",
        "no_perm": "دسترسی نداری.",
        "broadcast_ok": "ارسال شد به {n} کاربر.",
        "not_config": "هنوز تنظیم نشده.",
        "phone_ok": "شماره‌ات ثبت شد. همکاران ما با شما تماس می‌گیرند.",
        "choose": "یک گزینه را انتخاب کن:",
        "back": "بازگشت ↩️",
        "btn_prices": "قیمت‌ها 💵",
        "btn_about": "دربارهٔ ما ℹ️",
        "btn_send_phone": "ارسال شماره 📞",
    },
    "EN": {
        "welcome": f"Hello! I’m {BRAND_NAME} 👋\nOptions: 1) Menu 🗂  2) Support 🛟  3) Language 🌐",
        "menu": "Please choose:",
        "support": "Support 🛟\nDM: @welluroo_support" + (f"\nWhatsApp: {SUPPORT_WHATSAPP}" if SUPPORT_WHATSAPP else ""),
        "language": "Choose a language: FA / EN / AR",
        "set_ok": "Language set.",
        "unknown": "Sorry, I didn’t get that. Use the buttons or type /help",
        "catalog_empty": "Catalog is empty. If you are admin, run /sync.",
        "sync_ok": "Catalog updated: {n} items.",
        "sync_fail": "Failed! Check Sheet URL or CSV format.",
        "no_perm": "No permission.",
        "broadcast_ok": "Sent to {n} users.",
        "not_config": "Not configured yet.",
        "phone_ok": "Your phone number is saved. We will contact you shortly.",
        "choose": "Choose an option:",
        "back": "Back ↩️",
        "btn_prices": "Prices 💵",
        "btn_about": "About us ℹ️",
        "btn_send_phone": "Share phone 📞",
    },
    "AR": {
        "welcome": f"مرحباً! أنا {BRAND_NAME} 👋\nالخيارات: 1) القائمة 🗂  2) الدعم 🛟  3) اللغة 🌐",
        "menu": "اختر خياراً:",
        "support": "الدعم 🛟\nراسلنا: @welluroo_support" + (f"\nواتساب: {SUPPORT_WHATSAPP}" if SUPPORT_WHATSAPP else ""),
        "language": "اختر اللغة: FA / EN / AR",
        "set_ok": "تم ضبط اللغة.",
        "unknown": "لم أفهم. استخدم الأزرار أو اكتب /help",
        "catalog_empty": "الكاتالوج فارغ. إذا كنت مديراً، استخدم /sync.",
        "sync_ok": "تم تحديث الكاتالوج: {n} عنصر.",
        "sync_fail": "فشل! تحقق من رابط الـSheet أو تنسيق CSV.",
        "no_perm": "ليست لديك صلاحية.",
        "broadcast_ok": "تم الإرسال إلى {n} مستخدم.",
        "not_config": "غير مُعدّ بعد.",
        "phone_ok": "تم حفظ رقم هاتفك وسنتواصل معك قريباً.",
        "choose": "اختر خياراً:",
        "back": "العودة ↩️",
        "btn_prices": "الأسعار 💵",
        "btn_about": "من نحن ℹ️",
        "btn_send_phone": "إرسال الرقم 📞",
    },
}

# ---------- کیبورد ----------
def reply_keyboard(lang):
    if lang == "AR":
        return {"keyboard":[[{"text":"القائمة 🗂"},{"text":"الدعم 🛟"}],[{"text":"اللغة 🌐"}]],"resize_keyboard":True}
    if lang == "EN":
        return {"keyboard":[[{"text":"Menu 🗂"},{"text":"Support 🛟"}],[{"text":"Language 🌐"}]],"resize_keyboard":True}
    return {"keyboard":[[{"text":"منو 🗂"},{"text":"پشتیبانی 🛟"}],[{"text":"زبان 🌐"}]],"resize_keyboard":True}

def menu_keyboard(lang):
    if lang == "AR":
        return {"keyboard":[
            [{"text":TEXT["AR"]["btn_prices"]},{"text":TEXT["AR"]["btn_about"]}],
            [{"text":TEXT["AR"]["btn_send_phone"], "request_contact": True}],
            [{"text":TEXT["AR"]["back"]}]
        ], "resize_keyboard": True}
    if lang == "EN":
        return {"keyboard":[
            [{"text":TEXT["EN"]["btn_prices"]},{"text":TEXT["EN"]["btn_about"]}],
            [{"text":TEXT["EN"]["btn_send_phone"], "request_contact": True}],
            [{"text":TEXT["EN"]["back"]}]
        ], "resize_keyboard": True}
    # FA
    return {"keyboard":[
        [{"text":TEXT["FA"]["btn_prices"]},{"text":TEXT["FA"]["btn_about"]}],
        [{"text":TEXT["FA"]["btn_send_phone"], "request_contact": True}],
        [{"text":TEXT["FA"]["back"]}]
    ], "resize_keyboard": True}

def lang_keyboard():
    return {"keyboard": [[{"text":"FA"},{"text":"EN"},{"text":"AR"}]], "resize_keyboard": True}

# ---------- ارسال پیام ----------
def send_text(chat_id, text, keyboard=None):
    if not API: return
    payload = {"chat_id": chat_id, "text": text}
    if keyboard: payload["reply_markup"] = keyboard
    r = requests.post(API, json=payload, timeout=10)
    return r

# ---------- Silver: کاتالوگ از CSV ----------
CATALOG = []   # list[dict]

def _download_sheet_csv(url:str)->str:
    r = requests.get(url, timeout=15)
    r.raise_for_status()
    return r.text

def sync_catalog_from_sheet():
    if not SHEET_URL:
        raise RuntimeError("SHEET_URL missing")
    csv_text = _download_sheet_csv(SHEET_URL)
    f = io.StringIO(csv_text)
    reader = csv.DictReader(f)
    items = []
    for row in reader:
        items.append({
            "category": (row.get("category") or "").strip(),
            "name": (row.get("item_name") or "").strip(),
            "price": (row.get("price") or "").strip(),
            "image": (row.get("image_url") or "").strip(),
            "desc": (row.get("description") or "").strip(),
            "avail": (row.get("is_available") or "1").strip() in ["1","true","True","YES","yes","available"]
        })
    global CATALOG
    CATALOG = items
    return len(items)

def show_menu_from_catalog(lang):
    if not CATALOG:
        return TEXT[lang]["catalog_empty"]
    cats = {}
    for it in CATALOG:
        cats.setdefault(it["category"] or "General", []).append(it)
    parts = []
    for cat, items in list(cats.items())[:5]:
        parts.append(f"— {cat} —")
        for it in items[:3]:
            price = f" — {it['price']}" if it["price"] else ""
            parts.append(f"• {it['name']}{price}")
    return "\n".join(parts)

# ---------- Helper برای خواندن متن‌های پلن برنز از ENV ----------
def get_section(section: str, lang: str) -> str:
    # مثال: PRICES_FA, ABOUT_AR
    return (os.environ.get(f"{section}_{lang}", "") or "").strip()

# ---------- ریت‌لیمیت ساده ----------
from collections import defaultdict, deque
from time import time as now
BUCKET = defaultdict(lambda: deque(maxlen=10))
def rate_ok(uid:int, limit=5, window=5):
    q = BUCKET[uid]; t = now(); q.append(t)
    recent = [x for x in q if t - x <= window]
    return len(recent) <= limit

# ---------- وب ----------
@app.route("/health", methods=["GET","HEAD"])
def health(): return jsonify(status="ok")

@app.route("/", methods=["GET"])
def root(): return "Arabia bot is running."

@app.route("/telegram", methods=["GET","POST"])
def telegram():
    if request.method == "GET": return "OK", 200
    if not BOT_TOKEN: return jsonify({"error":"TELEGRAM_BOT_TOKEN missing"}), 500

    update = request.get_json(silent=True) or {}
    message = update.get("message") or update.get("edited_message") or {}
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    text = (message.get("text") or "").strip()
    contact = message.get("contact") or {}

    # ذخیره شماره تماس
    if contact and contact.get("phone_number"):
        set_user_phone(chat_id, contact.get("phone_number"))
        lang = get_user_lang(chat_id)
        send_text(chat_id, TEXT[lang]["phone_ok"], keyboard=reply_keyboard(lang))
        return jsonify({"ok": True})

    if not chat_id or not (text or contact):
        return jsonify({"ok": True})  # ignore non-text

    # ریت‌لیمیت
    if not rate_ok(chat_id):
        return jsonify({"ok": True})

    # ثبت کاربر + زبان
    name = (chat.get("first_name") or "") + " " + (chat.get("last_name") or "")
    upsert_user(chat_id, name.strip())
    lang = get_user_lang(chat_id)

    # deep-link منبع جذب
    if text.startswith("/start"):
        parts = text.split(" ", 1)
        if len(parts) == 2 and parts[1].strip():
            try: set_user_source(chat_id, parts[1].strip()[:64])
            except: pass
        send_text(chat_id, TEXT[lang]["welcome"], keyboard=reply_keyboard(lang))
        log_message(chat_id, text, "in"); log_message(chat_id, "welcome", "out")
        return jsonify({"ok": True})

    low = text.lower()

    # ---------- انتخاب زبان با دکمه یا تایپ ----------
    norm = text.strip().upper()
    fa_words = ["FA","FARSI","فارسی"]
    en_words = ["EN","ENG","ENGLISH","انگلیسی"]
    ar_words = ["AR","ARA","ARABIC","العربية","عربی"]

    if norm in fa_words or text.strip() in ["فارسی"]:
        set_user_lang(chat_id, "FA"); lang = "FA"
        send_text(chat_id, TEXT[lang]["set_ok"], keyboard=reply_keyboard(lang))
        return jsonify({"ok": True})

    if norm in en_words or text.strip() in ["انگلیسی"]:
        set_user_lang(chat_id, "EN"); lang = "EN"
        send_text(chat_id, TEXT[lang]["set_ok"], keyboard=reply_keyboard(lang))
        return jsonify({"ok": True})

    if norm in ar_words or text.strip() in ["العربية","عربی"]:
        set_user_lang(chat_id, "AR"); lang = "AR"
        send_text(chat_id, TEXT[lang]["set_ok"], keyboard=reply_keyboard(lang))
        return jsonify({"ok": True})

    # ---------- دستورات ادمین ----------
    is_admin = str(chat_id) in ADMINS
    if low.startswith("/stats") and is_admin:
        st = get_stats()
        msg = f"Users: {st['users_total']}\nMessages: {st['messages_total']} (24h: {st['messages_24h']})\nLangs: {st['langs']}"
        send_text(chat_id, msg)
        return jsonify({"ok": True})

    if low.startswith("/broadcast") and is_admin:
        msg = text[len("/broadcast"):].strip()
        if not msg:
            send_text(chat_id, "Usage: /broadcast your message")
            return jsonify({"ok": True})
        ids = list_user_ids(10000)
        sent = 0
        for uid in ids:
            try:
                send_text(uid, msg)
                sent += 1
                time.sleep(0.03)  # ملایم
            except: pass
        send_text(chat_id, TEXT[lang]["broadcast_ok"].format(n=sent))
        return jsonify({"ok": True})

    if low.startswith("/setlang"):
        parts = low.split()
        if len(parts) >= 2 and parts[1].upper() in ["FA","EN","AR"]:
            set_user_lang(chat_id, parts[1].upper())
            lang = parts[1].upper()
            send_text(chat_id, TEXT[lang]["set_ok"], keyboard=reply_keyboard(lang))
            return jsonify({"ok": True})
        else:
            send_text(chat_id, TEXT[lang]["language"], keyboard=lang_keyboard())
            return jsonify({"ok": True})

    # ---------- Silver: /sync ----------
    if low.startswith("/sync"):
        if not is_admin:
            send_text(chat_id, TEXT[lang]["no_perm"]); return jsonify({"ok": True})
        if PLAN in ["silver","gold","diamond"]:
            try:
                n = sync_catalog_from_sheet()
                send_text(chat_id, TEXT[lang]["sync_ok"].format(n=n))
            except Exception as e:
                send_text(chat_id, TEXT[lang]["sync_fail"] + f"\n{e}")
        else:
            send_text(chat_id, "Not available in your plan.")
        return jsonify({"ok": True})

    # ---------- Intentها ----------
    # منوی اصلی: نمایش زیرمنو (برنز)
    if text in ["منو 🗂","القائمة 🗂","Menu 🗂","منو","القائمة","Menu"]:
        send_text(chat_id, TEXT[lang]["choose"], keyboard=menu_keyboard(lang))
        log_message(chat_id, text, "in"); log_message(chat_id, "menu", "out")
        return jsonify({"ok": True})

    # برگشت از زیرمنو
    if text in [TEXT[lang]["back"]]:
        send_text(chat_id, TEXT[lang]["welcome"], keyboard=reply_keyboard(lang))
        return jsonify({"ok": True})

    # قیمت‌ها
    if text in [TEXT["FA"]["btn_prices"], TEXT["EN"]["btn_prices"], TEXT["AR"]["btn_prices"], "قیمت‌ها", "Prices", "الأسعار"]:
        msg = get_section("PRICES", lang) or TEXT[lang]["not_config"]
        send_text(chat_id, msg, keyboard=menu_keyboard(lang))
        return jsonify({"ok": True})

    # درباره ما
    if text in [TEXT["FA"]["btn_about"], TEXT["EN"]["btn_about"], TEXT["AR"]["btn_about"], "درباره ما", "About", "من نحن"]:
        msg = get_section("ABOUT", lang) or TEXT[lang]["not_config"]
        send_text(chat_id, msg, keyboard=menu_keyboard(lang))
        return jsonify({"ok": True})

    # پشتیبانی
    if text in ["پشتیبانی 🛟","الدعم 🛟","Support 🛟","پشتیبانی","الدعم","Support"]:
        send_text(chat_id, TEXT[lang]["support"], keyboard=reply_keyboard(lang))
        return jsonify({"ok": True})

    # زبان
    if text in ["زبان 🌐","اللغة 🌐","Language 🌐","زبان","اللغة","Language"]:
        send_text(chat_id, TEXT[lang]["language"], keyboard=lang_keyboard())
        return jsonify({"ok": True})

    # پاسخ پیش‌فرض
    log_message(chat_id, text, "in")
    send_text(chat_id, TEXT[lang]["unknown"], keyboard=reply_keyboard(lang))
    log_message(chat_id, "unknown", "out")
    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
