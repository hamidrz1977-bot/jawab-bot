# app.py — Arabia Social (Flask + Telegram Webhook)
import os, requests, time, csv, io, re
from flask import Flask, request, jsonify
from collections import defaultdict, deque
from time import time as now

# ---------- ENV ----------
BOT_TOKEN = os.environ.get("TG_BOT_TOKEN") or os.environ.get("TELEGRAM_BOT_TOKEN")
API = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage" if BOT_TOKEN else None

BRAND_NAME = os.environ.get("BRAND_NAME", "Jawab")
DEFAULT_LANG = (os.environ.get("DEFAULT_LANG") or "FA").upper()
SUPPORT_WHATSAPP = os.environ.get("SUPPORT_WHATSAPP", "")
SUPPORT_TG = (os.environ.get("SUPPORT_TG") or "").strip()
SUPPORT_EMAIL = (os.environ.get("SUPPORT_EMAIL") or "").strip()
# SUPPORT_WHATSAPP موجود است و همان را استفاده می‌کنیم
SUPPORT_INSTAGRAM = (os.environ.get("SUPPORT_INSTAGRAM") or "").strip()
CATALOG_TITLE_AR = (os.getenv("CATALOG_TITLE_AR") or "").strip()
CATALOG_TITLE_EN = (os.getenv("CATALOG_TITLE_EN") or "").strip()
CATALOG_TITLE_FA = (os.getenv("CATALOG_TITLE_FA") or "").strip()

BTN_PRODUCTS_AR = (os.getenv("BTN_PRODUCTS_AR") or "").strip()
BTN_PRODUCTS_EN = (os.getenv("BTN_PRODUCTS_EN") or "").strip()
BTN_PRODUCTS_FA = (os.getenv("BTN_PRODUCTS_FA") or "").strip()
ADMINS = [x.strip() for x in (os.environ.get("ADMINS") or "").split(",") if x.strip()]
PLAN = (os.environ.get("PLAN") or "bronze").lower()
SHEET_URL = os.environ.get("SHEET_URL", "").strip()   # برای Silver

# ---------- DB ----------
from storage.db import (
    init_db, upsert_user, get_user_lang, set_user_lang,
    log_message, get_stats, list_user_ids, set_user_source,
    set_user_phone, get_user_phone, create_order
)
init_db()

app = Flask(__name__)

# ---------- متن‌ها ----------
TEXT = {
    "FA": {
        "welcome": f"سلام! من {BRAND_NAME} هستم 👋\nگزینه‌ها: 1) منو 🗂  2) پشتیبانی 🛟  3) زبان 🌐",
        "menu": "یک گزینه را انتخاب کن:",
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
        "btn_products": "محصولات 🛍",
        "list_products": "لیست محصولات (شماره را انتخاب کن):",
        "btn_confirm": "✅ ثبت درخواست",
        "order_saved": "درخواستت ثبت شد. کد سفارش: #{oid}\nهمکاران ما با شما هماهنگ می‌کنند.",
        "need_phone": "برای ثبت سفارش، لطفاً با دکمه «📞 ارسال شماره» شماره‌ات را ارسال کن.",
        "need_phone_lead": "برای ثبت درخواست، لطفاً با دکمه «📞 ارسال شماره» شماره‌ات را ارسال کن.",
        "selected": "انتخاب شد: {name} — {price}",
        # جدید:
        "btn_content": "🧩 پکیج‌های محتوا",
        "btn_app": "🤖 پلان‌های اپ Jawab",
        "btn_request": "✅ ثبت درخواست",
        "lead_saved": "درخواست شما ثبت شد؛ به‌زودی با شما تماس می‌گیریم.",
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
        "btn_products": "Products 🛍",
        "list_products": "Products list (pick a number):",
        "btn_confirm": "✅ Confirm request",
        "order_saved": "Your request is saved. Order ID: #{oid}\nWe will contact you shortly.",
        "need_phone": "To place the order, please tap “📞 Share phone”.",
        "need_phone_lead": "To submit your request, please tap “📞 Share phone”.",
        "selected": "Selected: {name} — {price}",
        # new:
        "btn_content": "🧩 Content Packages",
        "btn_app": "🤖 Jawab App Plans",
        "btn_request": "✅ Request Quote",
        "lead_saved": "Your request is recorded. We'll contact you shortly.",
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
        "btn_products": "المنتجات 🛍",
        "list_products": "قائمة المنتجات (اختر رقماً):",
        "btn_confirm": "✅ تأكيد الطلب",
        "order_saved": "تم حفظ طلبك. رقم الطلب: #{oid}\nسنتواصل معك قريباً.",
        "need_phone": "لإتمام الطلب، الرجاء الضغط على «📞 إرسال الرقم».",
        "need_phone_lead": "لإتمام طلبك، الرجاء الضغط على «📞 إرسال الرقم».",
        "selected": "تم اختيار: {name} — {price}",
        # جديد:
        "btn_content": "🧩 باقات المحتوى",
        "btn_app": "🤖 خطط تطبيق Jawab",
        "btn_request": "✅ تسجيل طلب",
        "lead_saved": "تم تسجيل طلبك، وسنتواصل معك قريباً.",
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
            [ {"text": btn_products_label("AR")}, {"text":TEXT["AR"]["btn_prices"]}, {"text":TEXT["AR"]["btn_about"]} ],
            [ {"text":TEXT["AR"]["btn_content"]}, {"text":TEXT["AR"]["btn_app"]} ],
            [ {"text":TEXT["AR"]["btn_send_phone"], "request_contact": True} ],
            [ {"text":TEXT["AR"]["back"]} ]
        ], "resize_keyboard": True}
    if lang == "EN":
        return {"keyboard":[
            [ {"text": btn_products_label("EN")}, {"text":TEXT["EN"]["btn_prices"]}, {"text":TEXT["EN"]["btn_about"]} ],
            [ {"text":TEXT["EN"]["btn_content"]}, {"text":TEXT["EN"]["btn_app"]} ],
            [ {"text":TEXT["EN"]["btn_send_phone"], "request_contact": True} ],
            [ {"text":TEXT["EN"]["back"]} ]
        ], "resize_keyboard": True}
    return {"keyboard":[
        [ {"text": btn_products_label("FA")}, {"text":TEXT["FA"]["btn_prices"]}, {"text":TEXT["FA"]["btn_about"]} ],
        [ {"text":TEXT["FA"]["btn_content"]}, {"text":TEXT["FA"]["btn_app"]} ],
        [ {"text":TEXT["FA"]["btn_send_phone"], "request_contact": True} ],
        [ {"text":TEXT["FA"]["back"]} ]
    ], "resize_keyboard": True}

def confirm_keyboard(lang):
    return {"keyboard":[[{"text":TEXT[lang]["btn_confirm"]}],[{"text":TEXT[lang]["back"]}]], "resize_keyboard": True}

def lang_keyboard():
    return {"keyboard": [[{"text":"FA"},{"text":"EN"},{"text":"AR"}]], "resize_keyboard": True}

# ---------- ارسال پیام ----------
def send_text(chat_id, text, keyboard=None):
    if not API: return
    payload = {"chat_id": chat_id, "text": text}
    if keyboard: payload["reply_markup"] = keyboard
    try:
        return requests.post(API, json=payload, timeout=10)
    except Exception:
        return None

# ---------- Helpers برای گام۴ ----------
def get_env_text(keys:list[str]) -> str:
    parts = []
    for k in keys:
        v = (os.getenv(k) or "").strip()
        if v:
            parts.append(v)
    return "\n\n".join(parts) if parts else ""

def content_text(lang: str) -> str:
    suf = lang.upper()
    keys = [
        f"CONTENT_BRONZE_{suf}",
        f"CONTENT_SILVER_{suf}",
        f"CONTENT_GOLD_{suf}",
        f"CONTENT_DIAMOND_{suf}",
    ]
    return get_env_text(keys)

def app_plans_text(lang: str) -> str:
    suf = lang.upper()
    keys = [f"APP_BRONZE_{suf}", f"APP_SILVER_{suf}", f"APP_GOLD_{suf}", f"APP_DIAMOND_{suf}"]
    return get_env_text(keys)

def get_section(sec: str, lang: str) -> str:
    """Return section text from env by language suffix; empty string if missing."""
    lang = (lang or "").strip().upper()
    suf = lang if lang in ("FA", "AR", "EN") else "EN"
    # سعی می‌کنیم چند کلید محتمل را امتحان کنیم، بسته به نام سکشن
    candidates = [f"{sec}_{suf}", f"{sec}_TEXT_{suf}", f"{sec}"]
    return get_env_text(candidates) or ""
    # برچسب دکمه «محصولات» بر اساس زبان
    labels = {
        "FA": "محصولات 🛍",
        "AR": "المنتجات 🛍",
        "EN": "Products 🛍",
    }
    code = (lang or "").strip().upper()
    return labels.get(code, labels["EN"])


def catalog_title(lang: str) -> str:
    fallback = TEXT[lang]["list_products"]
    if lang == "AR":
        return CATALOG_TITLE_AR or fallback
    if lang == "EN":
        return CATALOG_TITLE_EN or fallback
    return CATALOG_TITLE_FA or fallback
    return (os.environ.get(f"{sec}_{lang}", "") or "").strip()
def build_support_text(lang: str) -> str:
    # برچسب‌های چندزبانه
    labels = {
        "FA": {"title": "پشتیبانی 🛟", "tg": "تلگرام", "mail": "ایمیل", "wa": "واتساپ", "ig": "اینستاگرام"},
        "EN": {"title": "Support 🛟", "tg": "Telegram", "mail": "Email", "wa": "WhatsApp", "ig": "Instagram"},
        "AR": {"title": "الدعم 🛟", "tg": "تيليجرام", "mail": "البريد", "wa": "واتساب", "ig": "إنستغرام"},
    }
    L = labels.get(lang, labels["FA"])

    lines = [L["title"]]

    # Telegram
    tg = SUPPORT_TG
    if tg:
        handle = tg[1:] if tg.startswith("@") else tg
        tg_display = f"@{handle}"
        tg_link = f"https://t.me/{handle}"
        lines.append(f"{L['tg']}: {tg_display}  ({tg_link})")

    # Email
    if SUPPORT_EMAIL:
        lines.append(f"{L['mail']}: {SUPPORT_EMAIL}")

    # WhatsApp
    if SUPPORT_WHATSAPP:
        digits = "".join(ch for ch in SUPPORT_WHATSAPP if ch.isdigit() or ch == "+").lstrip("+")
        wa_link = f"https://wa.me/{digits}"
        lines.append(f"{L['wa']}: {SUPPORT_WHATSAPP}  ({wa_link})")

    # Instagram
    ig = SUPPORT_INSTAGRAM
    if ig:
        handle = ig.replace("https://instagram.com/", "").replace("http://instagram.com/", "").strip().lstrip("@")
        ig_link = f"https://instagram.com/{handle}"
        lines.append(f"{L['ig']}: @{handle}  ({ig_link})")

    return "\n".join(lines)

# ---------- محصولات (Bronze via ENV / Silver via Sheet) ----------
CATALOG = []   # Silver+
SELECTED = {}  # chat_id -> {name, price}

# Leads (content/app)
LEAD_CONTEXT = {}   # chat_id -> "content" | "app"
LEAD_PENDING = {}   # chat_id -> waiting for phone

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
        avail = (row.get("is_available") or "1").strip().lower() in ["1","true","yes","available"]
        if not avail:
            continue
        items.append({
            "category": (row.get("category") or "").strip(),
            "name": (row.get("item_name") or "").strip(),
            "price": (row.get("price") or "").strip()
        })
    global CATALOG
    CATALOG = items
    return len(items)

def parse_env_products(lang:str)->list[dict]:
    raw = os.environ.get(f"PRODUCTS_{lang}", "") or ""
    lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
    items = []
    for ln in lines:
        parts = [p.strip() for p in ln.split("|")]  # category|name|price یا name|price
        if len(parts) == 3:
            _, name, price = parts
        elif len(parts) == 2:
            name, price = parts
        else:
            name, price = ln, ""
        items.append({"name": name, "price": price})
    return items

def load_products(lang:str)->list[dict]:
    if PLAN in ["silver","gold","diamond"] and CATALOG:
        return CATALOG
    return parse_env_products(lang)

def build_product_keyboard(items:list, lang:str):
    rows = []
    for i, it in enumerate(items[:10], start=1):
        label = f"{i}) {it['name']}"
        rows.append([{"text": label}])
    rows.append([{"text": TEXT[lang]["back"]}])
    return {"keyboard": rows, "resize_keyboard": True}

# ---------- ریت‌لیمیت ----------
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

    # ذخیره شماره تماس (همراه با پشتیبانی لید)
    if contact and contact.get("phone_number"):
        set_user_phone(chat_id, contact.get("phone_number"))
        lang = get_user_lang(chat_id)

        # اگر درخواست لید در انتظار بود، به ادمین اعلان بده
        src = LEAD_PENDING.pop(chat_id, None)
        if src:
            display_name = ((chat.get("first_name") or "") + " " + (chat.get("last_name") or "")).strip() or str(chat_id)
            admin_text = f"NEW Lead\nSource: {src}\nUser: {display_name}\nID: {chat_id}\nPhone: {contact.get('phone_number')}"
            for admin in ADMINS:
                try:
                    requests.post(API, json={"chat_id": int(admin), "text": admin_text}, timeout=10)
                except Exception:
                    pass
            send_text(chat_id, TEXT[lang]["lead_saved"], keyboard=reply_keyboard(lang))
            return jsonify({"ok": True})

        # حالت عادی
        send_text(chat_id, TEXT[lang]["phone_ok"], keyboard=reply_keyboard(lang))
        return jsonify({"ok": True})

    if not chat_id or not (text or contact):
        return jsonify({"ok": True})

    if not rate_ok(chat_id):
        return jsonify({"ok": True})

    name = (chat.get("first_name") or "") + " " + (chat.get("last_name") or "")
    upsert_user(chat_id, name.strip() or str(chat_id))
    lang = get_user_lang(chat_id) or DEFAULT_LANG

    # /start
    if text.startswith("/start"):
        parts = text.split(" ", 1)
        if len(parts) == 2 and parts[1].strip():
            try: set_user_source(chat_id, parts[1].strip()[:64])
            except: pass
        send_text(chat_id, TEXT[lang]["welcome"], keyboard=reply_keyboard(lang))
        log_message(chat_id, text, "in"); log_message(chat_id, "welcome", "out")
        return jsonify({"ok": True})

    low = text.lower()

    # انتخاب زبان با دکمه یا تایپ
    norm = text.strip().upper()
    if norm in ["FA","FARSI","فارسی"]:
        set_user_lang(chat_id, "FA"); lang="FA"
        send_text(chat_id, TEXT[lang]["set_ok"], keyboard=reply_keyboard(lang)); return jsonify({"ok": True})
    if norm in ["EN","ENG","ENGLISH","انگلیسی"]:
        set_user_lang(chat_id, "EN"); lang="EN"
        send_text(chat_id, TEXT[lang]["set_ok"], keyboard=reply_keyboard(lang)); return jsonify({"ok": True})
    if norm in ["AR","ARA","ARABIC","العربية","عربی"]:
        set_user_lang(chat_id, "AR"); lang="AR"
        send_text(chat_id, TEXT[lang]["set_ok"], keyboard=reply_keyboard(lang)); return jsonify({"ok": True})

    # ادمین
    is_admin = str(chat_id) in ADMINS
    if low.startswith("/stats") and is_admin:
        st = get_stats()
        msg = f"Users: {st['users_total']}\nMessages: {st['messages_total']} (24h: {st['messages_24h']})\nLangs: {st['langs']}"
        send_text(chat_id, msg); return jsonify({"ok": True})

    if low.startswith("/broadcast") and is_admin:
        msg = text[len("/broadcast"):].strip()
        if not msg:
            send_text(chat_id, "Usage: /broadcast your message"); return jsonify({"ok": True})
        ids = list_user_ids(10000); sent = 0
        for uid in ids:
            try: send_text(uid, msg); sent += 1; time.sleep(0.03)
            except: pass
        send_text(chat_id, TEXT[lang]["broadcast_ok"].format(n=sent)); return jsonify({"ok": True})

    if low.startswith("/setlang"):
        parts = low.split()
        if len(parts)>=2 and parts[1].upper() in ["FA","EN","AR"]:
            set_user_lang(chat_id, parts[1].upper()); lang=parts[1].upper()
            send_text(chat_id, TEXT[lang]["set_ok"], keyboard=reply_keyboard(lang)); return jsonify({"ok": True})
        else:
            send_text(chat_id, TEXT[lang]["language"], keyboard=lang_keyboard()); return jsonify({"ok": True})

    # Silver: sync
    if low.startswith("/sync"):
        if not is_admin: send_text(chat_id, TEXT[lang]["no_perm"]); return jsonify({"ok": True})
        if PLAN in ["silver","gold","diamond"]:
            try: n=sync_catalog_from_sheet(); send_text(chat_id, TEXT[lang]["sync_ok"].format(n=n))
            except Exception as e: send_text(chat_id, TEXT[lang]["sync_fail"]+f"\n{e}")
        else: send_text(chat_id, "Not available in your plan.")
        return jsonify({"ok": True})

    # ---------- Intentها ----------
    # منوی اصلی
    if text in ["منو 🗂","القائمة 🗂","Menu 🗂","منو","القائمة","Menu"]:
        send_text(chat_id, TEXT[lang]["choose"], keyboard=menu_keyboard(lang))
        log_message(chat_id, text, "in"); log_message(chat_id, "menu", "out")
        return jsonify({"ok": True})

    # برگشت: به منوی اصلی (نه صفحه‌ی خوش‌آمد)
    if text in [TEXT[lang]["back"]]:
        send_text(chat_id, TEXT[lang]["choose"], keyboard=menu_keyboard(lang))
        return jsonify({"ok": True})

    # قیمت‌ها / درباره ما
    if text in [TEXT["FA"]["btn_prices"], TEXT["EN"]["btn_prices"], TEXT["AR"]["btn_prices"], "قیمت‌ها","Prices","الأسعار"]:
        body = get_section("PRICES", lang) or TEXT[lang]["not_config"]
        send_text(chat_id, body, keyboard=menu_keyboard(lang)); return jsonify({"ok": True})
    if text in [TEXT["FA"]["btn_about"], TEXT["EN"]["btn_about"], TEXT["AR"]["btn_about"], "درباره ما","About","من نحن"]:
        body = get_section("ABOUT", lang) or TEXT[lang]["not_config"]
        send_text(chat_id, body, keyboard=menu_keyboard(lang)); return jsonify({"ok": True})

    # 🧩 پکیج‌های محتوا
    if text in [TEXT["FA"]["btn_content"], TEXT["EN"]["btn_content"], TEXT["AR"]["btn_content"]]:
        LEAD_CONTEXT[chat_id] = "content"
        body = content_text(lang) or TEXT[lang]["not_config"]
        kb = {"keyboard":[[{"text": TEXT[lang]["btn_request"]}], [{"text": TEXT[lang]["back"]}]], "resize_keyboard": True}
        send_text(chat_id, body, keyboard=kb); return jsonify({"ok": True})

    # 🤖 پلان‌های اپ Jawab
    if text in [TEXT["FA"]["btn_app"], TEXT["EN"]["btn_app"], TEXT["AR"]["btn_app"]]:
        LEAD_CONTEXT[chat_id] = "app"
        body = app_plans_text(lang) or TEXT[lang]["not_config"]
        kb = {"keyboard":[[{"text": TEXT[lang]["btn_request"]}], [{"text": TEXT[lang]["back"]}]], "resize_keyboard": True}
        send_text(chat_id, body, keyboard=kb); return jsonify({"ok": True})

    # ✅ ثبت درخواست (Lead)
    if text == TEXT[lang]["btn_request"]:
        src = LEAD_CONTEXT.get(chat_id, "unknown")
        phone_val = get_user_phone(chat_id)
        if phone_val:
            display_name = ((chat.get("first_name") or "") + " " + (chat.get("last_name") or "")).strip() or str(chat_id)
            admin_text = f"NEW Lead\nSource: {src}\nUser: {display_name}\nID: {chat_id}\nPhone: {phone_val}"
            for admin in ADMINS:
                try:
                    requests.post(API, json={"chat_id": int(admin), "text": admin_text}, timeout=10)
                except Exception:
                    pass
            send_text(chat_id, TEXT[lang]["lead_saved"], keyboard=reply_keyboard(lang))
        else:
            LEAD_PENDING[chat_id] = src
            kb = {"keyboard":[[{"text": TEXT[lang]["btn_send_phone"], "request_contact": True}], [{"text": TEXT[lang]["back"]}]], "resize_keyboard": True}
            send_text(chat_id, TEXT[lang].get("need_phone_lead", TEXT[lang]["need_phone"]), keyboard=kb)
        return jsonify({"ok": True})

# محصولات (با دکمهٔ سفارشی از ENV)
if text in [
    TEXT["FA"]["btn_products"], TEXT["EN"]["btn_products"], TEXT["AR"]["btn_products"],
    btn_products_label(lang), "Products", "محصولات", "المنتجات"
]:
    items = load_products(lang)
    if not items:
        send_text(chat_id, TEXT[lang]["catalog_empty"], keyboard=menu_keyboard(lang)); return jsonify({"ok": True})
    kb = build_product_keyboard(items, lang)
    send_text(chat_id, catalog_title(lang), keyboard=kb)
    return jsonify({"ok": True})

        items = load_products(lang)
        if not items:
            send_text(chat_id, TEXT[lang]["catalog_empty"], keyboard=menu_keyboard(lang)); return jsonify({"ok": True})
        kb = build_product_keyboard(items, lang)
        send_text(chat_id, TEXT[lang]["list_products"], keyboard=kb); return jsonify({"ok": True})

    # انتخاب آیتم: الگوی "n) name" یا فقط "n"
    m = re.match(r"^\s*(\d+)\s*\)?", text)
    if m:
        idx = int(m.group(1)) - 1
        items = load_products(lang)
        if 0 <= idx < len(items[:10]):
            item = items[idx]
            SELECTED[chat_id] = {"name": item["name"], "price": item.get("price", "")}
            msg = TEXT[lang]["selected"].format(name=item["name"], price=item.get("price",""))
            send_text(chat_id, msg, keyboard=confirm_keyboard(lang)); return jsonify({"ok": True})

    # تأیید سفارش (برای محصولات)
    if text == TEXT[lang]["btn_confirm"]:
        sel = SELECTED.get(chat_id)
        if not sel:
            send_text(chat_id, TEXT[lang]["list_products"], keyboard=menu_keyboard(lang)); return jsonify({"ok": True})
        phone = get_user_phone(chat_id)
        if not phone:
            send_text(chat_id, TEXT[lang]["need_phone"], keyboard=menu_keyboard(lang)); return jsonify({"ok": True})
        # ایجاد سفارش
        oid = create_order(chat_id, sel["name"], 1, sel.get("price",""))
        send_text(chat_id, TEXT[lang]["order_saved"].format(oid=oid), keyboard=reply_keyboard(lang))

        # --- Admin notification (سفارش) ---
        phone_val = get_user_phone(chat_id) or "-"
        display_name = (name or "").strip() or str(chat_id)
        admin_text = "NEW Order #{}\nUser: {}\nID: {}\nPhone: {}\nItem: {}\nPrice: {}".format(
            oid, display_name, chat_id, phone_val, sel["name"], sel.get("price", "")
        )
        for admin in ADMINS:
            try:
                requests.post(API, json={"chat_id": int(admin), "text": admin_text}, timeout=10)
            except Exception:
                pass

        SELECTED.pop(chat_id, None)
        return jsonify({"ok": True})

    # پشتیبانی (داینامیک از ENV)
    if text in ["پشتیبانی 🛟","الدعم 🛟","Support 🛟","پشتیبانی","الدعم","Support"]:
        body = build_support_text(lang)
        send_text(chat_id, body, keyboard=reply_keyboard(lang))
        return jsonify({"ok": True})


    # زبان
    if text in ["زبان 🌐","اللغة 🌐","Language 🌐","زبان","اللغة","Language"]:
        send_text(chat_id, TEXT[lang]["language"], keyboard=lang_keyboard()); return jsonify({"ok": True})

    # پیش‌فرض
    log_message(chat_id, text, "in")
    send_text(chat_id, TEXT[lang]["unknown"], keyboard=reply_keyboard(lang))
    log_message(chat_id, "unknown", "out")
    return jsonify({"ok": True})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
