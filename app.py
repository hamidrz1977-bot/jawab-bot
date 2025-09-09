# app.py — Jawab/Arabia Social (Flask + Telegram Webhook)
import os, re, io, csv, time, requests
from flask import Flask, request, jsonify
from collections import defaultdict, deque
from time import time as now

# ---------- ENV ----------
# === PATCH 1: helpers for welcome & support ===
import os

def get_lang(user_lang=None):
    # اگر در کدت زبان کاربر را داری، همان را بده؛ وگرنه از DEFAULT_LANG
    lang = (user_lang or os.getenv("DEFAULT_LANG", "FA")).upper()
    return "FA" if lang not in ("FA","EN","AR") else lang

def get_welcome(lang):
    # متون WELCOME_* را از ENV می‌خواند؛ EN فالبک است
    fallback = os.getenv("WELCOME_EN") or "Welcome to Arabia Social"
    return os.getenv(f"WELCOME_{lang}", fallback)

def support_message():
    # چهار کانال پشتیبانی را از ENV می‌سازد (هرکدام خالی بود، نمایش نمی‌دهد)
    tg  = (os.getenv("SUPPORT_TG") or "").strip()
    wa  = (os.getenv("SUPPORT_WHATSAPP") or "").strip()
    ig  = (os.getenv("SUPPORT_INSTAGRAM") or "").strip()
    em  = (os.getenv("SUPPORT_EMAIL") or "").strip()

    lines = ["🛟 راه‌های ارتباطی:"]
    if tg:
        if not tg.startswith("@"): tg = "@"+tg
        lines.append(f"• Telegram: {tg}")
    if wa:
        lines.append(f"• WhatsApp: {wa}")
    if ig:
        if not ig.startswith("@"): ig = "@"+ig
        lines.append(f"• Instagram: {ig}")
    if em:
        lines.append(f"• Email: {em}")

    return "\n".join(lines)

SHOW_PRODUCTS = os.getenv("SHOW_PRODUCTS", "0").strip().lower() in ["1","true","yes","on"]

BOT_TOKEN = os.environ.get("TG_BOT_TOKEN") or os.environ.get("TELEGRAM_BOT_TOKEN")
API = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage" if BOT_TOKEN else None

BRAND_NAME = os.environ.get("BRAND_NAME", "Jawab")
DEFAULT_LANG = (os.environ.get("DEFAULT_LANG") or "FA").upper()

SUPPORT_WHATSAPP = (os.environ.get("SUPPORT_WHATSAPP") or "").strip()
SUPPORT_TG = (os.environ.get("SUPPORT_TG") or "").strip()
SUPPORT_EMAIL = (os.environ.get("SUPPORT_EMAIL") or "").strip()
SUPPORT_INSTAGRAM = (os.environ.get("SUPPORT_INSTAGRAM") or "").strip()

CATALOG_TITLE_AR = (os.getenv("CATALOG_TITLE_AR") or "").strip()
CATALOG_TITLE_EN = (os.getenv("CATALOG_TITLE_EN") or "").strip()
CATALOG_TITLE_FA = (os.getenv("CATALOG_TITLE_FA") or "").strip()

ADMINS = [x.strip() for x in (os.environ.get("ADMINS") or "").split(",") if x.strip()]
PLAN = (os.environ.get("PLAN") or "bronze").lower()
SHEET_URL = (os.environ.get("SHEET_URL") or "").strip()  # برای پلن Silver+

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
        "btn_content": "🧩 باقات المحتوى",
        "btn_app": "🤖 خطط تطبيق Jawab",
        "btn_request": "✅ تسجيل طلب",
        "lead_saved": "تم تسجيل طلبك، وسنتواصل معك قريباً.",
    },
}

# ---------- Utilities ----------
def btn_products_label(lang: str) -> str:
    labels = {"FA": "محصولات 🛍", "EN": "Products 🛍", "AR": "المنتجات 🛍"}
    return labels.get((lang or "").upper(), labels["EN"])

def reply_keyboard(lang: str):
    if lang == "AR":
        return {"keyboard":[[{"text":"القائمة 🗂"},{"text":"الدعم 🛟"}],[{"text":"اللغة 🌐"}]],"resize_keyboard":True}
    if lang == "EN":
        return {"keyboard":[[{"text":"Menu 🗂"},{"text":"Support 🛟"}],[{"text":"Language 🌐"}]],"resize_keyboard":True}
    return {"keyboard":[[{"text":"منو 🗂"},{"text":"پشتیبانی 🛟"}],[{"text":"زبان 🌐"}]],"resize_keyboard":True}

def menu_keyboard(lang: str):
    show_products = str(os.getenv("SHOW_PRODUCTS", "0")).strip().lower() in ("1", "true", "yes")

    L = (lang or "FA").upper()
    T = TEXT[L]  # متن‌های زبان فعلی

    # برچسب «محصولات» بر اساس زبان
    btn_products = btn_products_label(L)

    rows = []
    if show_products:
        # ردیف 1: محصولات | قیمت‌ها | درباره ما
        rows.append([{"text": btn_products}, {"text": T["btn_prices"]}, {"text": T["btn_about"]}])
        # ردیف 2: پکیج‌های محتوا | پلان‌های اپ
        rows.append([{"text": T["btn_content"]}, {"text": T["btn_app"]}])
    else:
        # بدون محصولات
        rows.append([{"text": T["btn_content"]}, {"text": T["btn_app"]}])
        rows.append([{"text": T["btn_prices"]}, {"text": T["btn_about"]}])

    # ردیف 3: ارسال شماره
    rows.append([{"text": T["btn_send_phone"], "request_contact": True}])
    # ردیف 4: بازگشت
    rows.append([{"text": T["back"]}])

    return {"keyboard": rows, "resize_keyboard": True}

def confirm_keyboard(lang: str):
    return {"keyboard":[[{"text":TEXT[lang]["btn_confirm"]}],[{"text":TEXT[lang]["back"]}]], "resize_keyboard": True}

def lang_keyboard():
    return {"keyboard": [[{"text":"FA"},{"text":"EN"},{"text":"AR"}]], "resize_keyboard": True}

def send_text(chat_id, text, keyboard=None):
    if not API:
        return None
    payload = {"chat_id": chat_id, "text": text}
    if keyboard:
        payload["reply_markup"] = keyboard
    try:
        return requests.post(API, json=payload, timeout=10)
    except Exception:
        return None

def get_env_text(keys:list[str]) -> str:
    parts = []
    for k in keys:
        v = (os.getenv(k) or "").strip()
        if v:
            parts.append(v)
    return "\n\n".join(parts) if parts else ""

def content_text(lang: str) -> str:
    suf = (lang or "").upper()
    keys = [f"CONTENT_BRONZE_{suf}", f"CONTENT_SILVER_{suf}", f"CONTENT_GOLD_{suf}", f"CONTENT_DIAMOND_{suf}"]
    return get_env_text(keys)

def app_plans_text(lang: str) -> str:
    suf = (lang or "").upper()
    keys = [f"APP_BRONZE_{suf}", f"APP_SILVER_{suf}", f"APP_GOLD_{suf}", f"APP_DIAMOND_{suf}"]
    return get_env_text(keys)

def get_section(sec: str, lang: str) -> str:
    suf = (lang or "").strip().upper()
    if suf not in ("FA","EN","AR"):
        suf = "EN"
    candidates = [f"{sec}_{suf}", f"{sec}_TEXT_{suf}", f"{sec}"]
    return get_env_text(candidates) or ""

def catalog_title(lang: str) -> str:
    fallback = TEXT[lang]["list_products"]
    if lang == "AR":
        return CATALOG_TITLE_AR or fallback
    if lang == "EN":
        return CATALOG_TITLE_EN or fallback
    return CATALOG_TITLE_FA or fallback

def build_support_text(lang: str) -> str:
    labels = {
        "FA": {"title": "پشتیبانی 🛟", "tg": "تلگرام", "mail": "ایمیل", "wa": "واتساپ", "ig": "اینستاگرام"},
        "EN": {"title": "Support 🛟", "tg": "Telegram", "mail": "Email", "wa": "WhatsApp", "ig": "Instagram"},
        "AR": {"title": "الدعم 🛟", "tg": "تيليجرام", "mail": "البريد", "wa": "واتساب", "ig": "إنستغرام"},
    }
    L = labels.get(lang, labels["FA"])
    lines = [L["title"]]

    # Telegram
    if SUPPORT_TG:
        handle = SUPPORT_TG[1:] if SUPPORT_TG.startswith("@") else SUPPORT_TG
        tg_link = f"https://t.me/{handle}"
        lines.append(f"{L['tg']}: @{handle}  ({tg_link})")

    # Email
    if SUPPORT_EMAIL:
        lines.append(f"{L['mail']}: {SUPPORT_EMAIL}")

    # WhatsApp
    if SUPPORT_WHATSAPP:
        digits = "".join(ch for ch in SUPPORT_WHATSAPP if ch.isdigit() or ch == "+").lstrip("+")
        wa_link = f"https://wa.me/{digits}"
        lines.append(f"{L['wa']}: {SUPPORT_WHATSAPP}  ({wa_link})")

    # Instagram
    if SUPPORT_INSTAGRAM:
        handle = SUPPORT_INSTAGRAM.replace("https://instagram.com/", "").replace("http://instagram.com/", "").strip().lstrip("@")
        ig_link = f"https://instagram.com/{handle}"
        lines.append(f"{L['ig']}: @{handle}  ({ig_link})")

    return "\n".join(lines)

# ---------- محصولات ----------
CATALOG = []           # Silver+
SELECTED = {}          # chat_id -> {name, price}
LEAD_CONTEXT = {}      # chat_id -> "content" | "app"
LEAD_PENDING = {}      # chat_id -> waiting for phone

def _download_sheet_csv(url: str) -> str:
    r = requests.get(url, timeout=15)
    r.raise_for_status()
    return r.text

def sync_catalog_from_sheet():
    if not SHEET_URL:
        raise RuntimeError("SHEET_URL missing")
    f = io.StringIO(_download_sheet_csv(SHEET_URL))
    reader = csv.DictReader(f)
    items = []
    for row in reader:
        avail = (row.get("is_available") or "1").strip().lower() in ["1","true","yes","available"]
        if not avail:
            continue
        items.append({
            "category": (row.get("category") or "").strip(),
            "name": (row.get("item_name") or "").strip(),
            "price": (row.get("price") or "").strip(),
        })
    global CATALOG
    CATALOG = items
    return len(items)

def parse_env_products(lang: str) -> list[dict]:
    raw = os.environ.get(f"PRODUCTS_{(lang or '').upper()}", "") or ""
    lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
    items = []
    for ln in lines:
        parts = [p.strip() for p in ln.split("|")]
        if len(parts) == 3:
            _, name, price = parts
        elif len(parts) == 2:
            name, price = parts
        else:
            name, price = ln, ""
        items.append({"name": name, "price": price})
    return items

def load_products(lang: str) -> list[dict]:
    if PLAN in ["silver","gold","diamond"] and CATALOG:
        return CATALOG
    return parse_env_products(lang)

def build_product_keyboard(items: list, lang: str):
    rows = []
    for i, it in enumerate(items[:10], start=1):
        rows.append([{"text": f"{i}) {it['name']}"}])
    rows.append([{"text": TEXT[lang]["back"]}])
    return {"keyboard": rows, "resize_keyboard": True}

# ---------- Rate limit ----------
BUCKET = defaultdict(lambda: deque(maxlen=10))
def rate_ok(uid: int, limit=5, window=5):
    q = BUCKET[uid]; t = now(); q.append(t)
    recent = [x for x in q if t - x <= window]
    return len(recent) <= limit

# ---------- Web ----------
@app.get("/healthz")
@app.get("/health")
def health():
    return jsonify(status="ok")

@app.get("/")
def root():
    return "Jawab bot is running."

def _handle_telegram_update(update: dict):
    message = update.get("message") or update.get("edited_message") or {}
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    text = (message.get("text") or "").strip()
    contact = message.get("contact") or {}

    if not chat_id:
        return {"ok": True}

    # ذخیره شماره تماس + لید
    if contact and contact.get("phone_number"):
        set_user_phone(chat_id, contact.get("phone_number"))
        lang = get_user_lang(chat_id) or DEFAULT_LANG

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
            return {"ok": True}

        send_text(chat_id, TEXT[lang]["phone_ok"], keyboard=reply_keyboard(lang))
        return {"ok": True}

    if not text:
        return {"ok": True}

    if not rate_ok(chat_id):
        return {"ok": True}

    name = (chat.get("first_name") or "") + " " + (chat.get("last_name") or "")
    upsert_user(chat_id, name.strip() or str(chat_id))
    lang = get_user_lang(chat_id) or DEFAULT_LANG

    # /start
    if text.startswith("/start"):
        parts = text.split(" ", 1)
        if len(parts) == 2 and parts[1].strip():
            try:
                set_user_source(chat_id, parts[1].strip()[:64])
            except Exception:
                pass
        send_text(chat_id, get_welcome(lang), keyboard=reply_keyboard(lang))
        log_message(chat_id, text, "in"); log_message(chat_id, "welcome", "out")
        return {"ok": True}

    low = text.lower()
    norm = text.upper()

    # تغییر زبان
    if norm in ["FA","FARSI","فارسی"]:
        set_user_lang(chat_id, "FA"); lang = "FA"
        send_text(chat_id, TEXT[lang]["set_ok"], keyboard=reply_keyboard(lang)); return {"ok": True}
    if norm in ["EN","ENG","ENGLISH","انگلیسی"]:
        set_user_lang(chat_id, "EN"); lang = "EN"
        send_text(chat_id, TEXT[lang]["set_ok"], keyboard=reply_keyboard(lang)); return {"ok": True}
    if norm in ["AR","ARA","ARABIC","العربية","عربی"]:
        set_user_lang(chat_id, "AR"); lang = "AR"
        send_text(chat_id, TEXT[lang]["set_ok"], keyboard=reply_keyboard(lang)); return {"ok": True}

    # ادمین
    is_admin = str(chat_id) in ADMINS

    # /stats (admins only)
    if low.startswith("/stats") and is_admin:
        st = get_stats()
        msg = f"Users: {st['users_total']}\nMessages: {st['messages_total']} (24h: {st['messages_24h']})\nLangs: {st['langs']}"
        send_text(chat_id, msg)
        return jsonify({"ok": True})

    # /share — لینک معرفی اختصاصی (برای همه)
    if low.startswith("/share"):
        bot_user = os.getenv("BOT_USERNAME", "").strip()
        if not bot_user:
            msg = (
                "برای ساخت لینک معرفی، کلید ENV به نام BOT_USERNAME لازم است.\n"
                "مثال: BOT_USERNAME = ArabiaSocialBot (بدون @)"
            )
            send_text(chat_id, msg)
            return jsonify({"ok": True})

        # ساخت لینک با پارامتر ref<ID> (در /start ذخیره می‌شود)
        ref = f"ref{chat_id}"
        link = f"https://t.me/{bot_user}?start={ref}"
        msg = (
            "📣 لینک معرفی اختصاصی شما آماده است:\n"
            f"{link}\n\n"
            "هر کسی از این لینک وارد شود، در ادمین «Source» با همین کد دیده می‌شود."
        )
        send_text(chat_id, msg)
        return jsonify({"ok": True})

    # /broadcast (admins only)
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
                time.sleep(0.03)
            except Exception:
                pass
        send_text(chat_id, TEXT[lang]["broadcast_ok"].format(n=sent))
        return jsonify({"ok": True})

    if low.startswith("/setlang"):
        parts = low.split()
        if len(parts)>=2 and parts[1].upper() in ["FA","EN","AR"]:
            set_user_lang(chat_id, parts[1].upper()); lang = parts[1].upper()
            send_text(chat_id, TEXT[lang]["set_ok"], keyboard=reply_keyboard(lang)); return {"ok": True}
        else:
            send_text(chat_id, TEXT[lang]["language"], keyboard=lang_keyboard()); return {"ok": True}

    if low.startswith("/sync"):
        if not is_admin:
            send_text(chat_id, TEXT[lang]["no_perm"]); return {"ok": True}
        if PLAN in ["silver","gold","diamond"]:
            try:
                n = sync_catalog_from_sheet()
                send_text(chat_id, TEXT[lang]["sync_ok"].format(n=n))
            except Exception as e:
                send_text(chat_id, TEXT[lang]["sync_fail"] + f"\n{e}")
        else:
            send_text(chat_id, "Not available in your plan.")
        return {"ok": True}

    # منوی اصلی
    if text in ["منو 🗂","القائمة 🗂","Menu 🗂","منو","القائمة","Menu"]:
        send_text(chat_id, TEXT[lang]["choose"], keyboard=menu_keyboard(lang))
        log_message(chat_id, text, "in"); log_message(chat_id, "menu", "out")
        return {"ok": True}

    # برگشت: چند برچسب/ایموجی را بپذیر (FA/AR/EN)
    BACK_ALIASES = [
        TEXT["FA"]["back"], TEXT["AR"]["back"], TEXT["EN"]["back"],
        "بازگشت", "↩️ بازگشت",
        "العودة", "🔙 رجوع", "رجوع",
        "Back", "🔙 Back"
    ]
    if text.strip() in BACK_ALIASES:
        # برگرد به منوی اصلی (نه صفحه خوش‌آمد)
        send_text(chat_id, TEXT[lang]["choose"], keyboard=menu_keyboard(lang))
        return jsonify({"ok": True})

    # قیمت‌ها / درباره ما
    if text in [TEXT["FA"]["btn_prices"], TEXT["EN"]["btn_prices"], TEXT["AR"]["btn_prices"], "قیمت‌ها","Prices","الأسعار"]:
        body = get_section("PRICES", lang) or TEXT[lang]["not_config"]
        send_text(chat_id, body, keyboard=menu_keyboard(lang)); return {"ok": True}
    if text in [TEXT["FA"]["btn_about"], TEXT["EN"]["btn_about"], TEXT["AR"]["btn_about"], "درباره ما","About","من نحن"]:
        body = get_section("ABOUT", lang) or TEXT[lang]["not_config"]
        send_text(chat_id, body, keyboard=menu_keyboard(lang)); return {"ok": True}

    # پکیج‌های محتوا
    if text in [TEXT["FA"]["btn_content"], TEXT["EN"]["btn_content"], TEXT["AR"]["btn_content"]]:
        LEAD_CONTEXT[chat_id] = "content"
        body = content_text(lang) or TEXT[lang]["not_config"]
        kb = {"keyboard":[[{"text": TEXT[lang]["btn_request"]}], [{"text": TEXT[lang]["back"]}]], "resize_keyboard": True}
        send_text(chat_id, body, keyboard=kb); return {"ok": True}

    # پلان‌های اپ
    if text in [TEXT["FA"]["btn_app"], TEXT["EN"]["btn_app"], TEXT["AR"]["btn_app"]]:
        LEAD_CONTEXT[chat_id] = "app"
        body = app_plans_text(lang) or TEXT[lang]["not_config"]
        kb = {"keyboard":[[{"text": TEXT[lang]["btn_request"]}], [{"text": TEXT[lang]["back"]}]], "resize_keyboard": True}
        send_text(chat_id, body, keyboard=kb); return {"ok": True}

    # ثبت درخواست (Lead)
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
        return {"ok": True}

    # محصولات
    if text in [
        TEXT["FA"]["btn_products"], TEXT["EN"]["btn_products"], TEXT["AR"]["btn_products"],
        btn_products_label(lang), "Products", "محصولات", "المنتجات"
    ]:
        items = load_products(lang)
        if not items:
            send_text(chat_id, TEXT[lang]["catalog_empty"], keyboard=menu_keyboard(lang)); return {"ok": True}
        kb = build_product_keyboard(items, lang)
        send_text(chat_id, catalog_title(lang), keyboard=kb); return {"ok": True}

    # انتخاب آیتم: n) name یا فقط n
    m = re.match(r"^\s*(\d+)\s*\)?", text)
    if m:
        idx = int(m.group(1)) - 1
        items = load_products(lang)
        if 0 <= idx < len(items[:10]):
            item = items[idx]
            SELECTED[chat_id] = {"name": item["name"], "price": item.get("price", "")}
            msg = TEXT[lang]["selected"].format(name=item["name"], price=item.get("price",""))
            send_text(chat_id, msg, keyboard=confirm_keyboard(lang)); return {"ok": True}

    # تایید سفارش
    if text == TEXT[lang]["btn_confirm"]:
        sel = SELECTED.get(chat_id)
        if not sel:
            send_text(chat_id, TEXT[lang]["list_products"], keyboard=menu_keyboard(lang)); return {"ok": True}
        phone = get_user_phone(chat_id)
        if not phone:
            send_text(chat_id, TEXT[lang]["need_phone"], keyboard=menu_keyboard(lang)); return {"ok": True}
        oid = create_order(chat_id, sel["name"], 1, sel.get("price",""))
        send_text(chat_id, TEXT[lang]["order_saved"].format(oid=oid), keyboard=reply_keyboard(lang))

        # admin notify
        phone_val = get_user_phone(chat_id) or "-"
        display_name = ( ((update.get("message") or {}).get("chat") or {}).get("first_name") or "" )  # حداقل نام
        admin_text = "NEW Order #{}\nUser: {}\nID: {}\nPhone: {}\nItem: {}\nPrice: {}".format(
            oid, display_name or chat_id, chat_id, phone_val, sel["name"], sel.get("price", "")
        )
        for admin in ADMINS:
            try:
                requests.post(API, json={"chat_id": int(admin), "text": admin_text}, timeout=10)
            except Exception:
                pass
        SELECTED.pop(chat_id, None)
        return {"ok": True}

    # پشتیبانی
    if text in ["پشتیبانی 🛟","الدعم 🛟","Support 🛟","پشتیبانی","الدعم","Support"]:
        send_text(chat_id, build_support_text(lang), keyboard=reply_keyboard(lang)); return {"ok": True}

    # زبان (نمایش گزینه‌ها)
    if text in ["زبان 🌐","اللغة 🌐","Language 🌐","زبان","اللغة","Language"]:
        send_text(chat_id, TEXT[lang]["language"], keyboard=lang_keyboard()); return {"ok": True}

    # پیش‌فرض
    log_message(chat_id, text, "in")
    send_text(chat_id, TEXT[lang]["unknown"], keyboard=reply_keyboard(lang))
    log_message(chat_id, "unknown", "out")
    return {"ok": True}

@app.route("/webhook/telegram", methods=["GET","POST"])
@app.route("/telegram", methods=["GET", "POST"])
def telegram():
    # --- health / token guard ---
    if request.method == "GET":
        return "OK", 200
    if not BOT_TOKEN:
        return jsonify({"error": "TELEGRAM_BOT_TOKEN missing"}), 500

    # (اختیاری) Secret-Token برای وبهوک امن
    secret_env = os.getenv("WEBHOOK_SECRET", "")
    secret_hdr = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if secret_env and secret_hdr != secret_env:
        return "unauthorized", 401

    # --- parse update ---
    update = request.get_json(silent=True) or {}
    message = update.get("message") or update.get("edited_message") or {}
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    text = (message.get("text") or "").strip()
    contact = message.get("contact") or {}

    if not chat_id:
        return jsonify({"ok": True})

    # ذخیره شماره تماس (share contact)
    if contact and contact.get("phone_number"):
        set_user_phone(chat_id, contact.get("phone_number"))
        lang_now = get_user_lang(chat_id)
        send_text(chat_id, TEXT[lang_now]["phone_ok"], keyboard=reply_keyboard(lang_now))
        return jsonify({"ok": True})

    if not text:
        return jsonify({"ok": True})

    # ریت‌لیمیت
    if not rate_ok(chat_id):
        return jsonify({"ok": True})

    # ثبت/به‌روزرسانی کاربر + زبان
    name = (chat.get("first_name") or "") + " " + (chat.get("last_name") or "")
    upsert_user(chat_id, name.strip())
    lang = get_user_lang(chat_id)
    low = text.lower()
    norm = text.strip().upper()

    # /start (+ tracking source)
    if text.startswith("/start"):
        parts = text.split(" ", 1)
        if len(parts) == 2 and parts[1].strip():
            try:
                set_user_source(chat_id, parts[1].strip()[:64])
            except Exception:
                pass
        send_text(chat_id, get_welcome(lang), keyboard=reply_keyboard(lang))
        log_message(chat_id, text, "in")
        log_message(chat_id, "welcome", "out")
        return jsonify({"ok": True})

    # انتخاب زبان با تایپ
    if norm in ["FA", "FARSI", "فارسی"]:
        set_user_lang(chat_id, "FA"); lang = "FA"
        send_text(chat_id, TEXT[lang]["set_ok"], keyboard=reply_keyboard(lang))
        return jsonify({"ok": True})
    if norm in ["EN", "ENG", "ENGLISH", "انگلیسی"]:
        set_user_lang(chat_id, "EN"); lang = "EN"
        send_text(chat_id, TEXT[lang]["set_ok"], keyboard=reply_keyboard(lang))
        return jsonify({"ok": True})
    if norm in ["AR", "ARA", "ARABIC", "العربية", "عربی"]:
        set_user_lang(chat_id, "AR"); lang = "AR"
        send_text(chat_id, TEXT[lang]["set_ok"], keyboard=reply_keyboard(lang))
        return jsonify({"ok": True})

    # --- admin tools ---
    is_admin = str(chat_id) in ADMINS

    # /stats
    if low.startswith("/stats") and is_admin:
        st = get_stats()
        msg = f"Users: {st['users_total']}\nMessages: {st['messages_total']} (24h: {st['messages_24h']})\nLangs: {st['langs']}"
        send_text(chat_id, msg)
        return jsonify({"ok": True})

    # /share — لینک معرفی اختصاصی
    if low.startswith("/share"):
        bot_user = os.getenv("BOT_USERNAME", "").strip()
        if not bot_user:
            send_text(chat_id,
                      "برای ساخت لینک معرفی، کلید ENV به نام BOT_USERNAME لازم است.\n"
                      "مثال: BOT_USERNAME = ArabiaSocialBot (بدون @)")
            return jsonify({"ok": True})
        ref = f"ref{chat_id}"
        link = f"https://t.me/{bot_user}?start={ref}"
        send_text(chat_id,
                  "📣 لینک معرفی اختصاصی شما آماده است:\n"
                  f"{link}\n\n"
                  "هر کسی از این لینک وارد شود، در ادمین «Source» با همین کد دیده می‌شود.")
        return jsonify({"ok": True})

    # /broadcast <msg>
    if low.startswith("/broadcast") and is_admin:
        msg = text[len("/broadcast"):].strip()
        if not msg:
            send_text(chat_id, "Usage: /broadcast your message")
            return jsonify({"ok": True})
        ids = list_user_ids(10000); sent = 0
        for uid in ids:
            try:
                send_text(uid, msg); sent += 1; time.sleep(0.03)
            except Exception:
                pass
        send_text(chat_id, TEXT[lang]["broadcast_ok"].format(n=sent))
        return jsonify({"ok": True})

    # /setlang
    if low.startswith("/setlang"):
        parts = low.split()
        if len(parts) >= 2 and parts[1].upper() in ["FA", "EN", "AR"]:
            set_user_lang(chat_id, parts[1].upper()); lang = parts[1].upper()
            send_text(chat_id, TEXT[lang]["set_ok"], keyboard=reply_keyboard(lang))
            return jsonify({"ok": True})
        send_text(chat_id, TEXT[lang]["language"], keyboard=lang_keyboard())
        return jsonify({"ok": True})

    # Silver: /sync از شیت
    if low.startswith("/sync"):
        if not is_admin:
            send_text(chat_id, TEXT[lang]["no_perm"])
            return jsonify({"ok": True})
        if PLAN in ["silver", "gold", "diamond"]:
            try:
                n = sync_catalog_from_sheet()
                send_text(chat_id, TEXT[lang]["sync_ok"].format(n=n))
            except Exception as e:
                send_text(chat_id, TEXT[lang]["sync_fail"] + f"\n{e}")
        else:
            send_text(chat_id, "Not available in your plan.")
        return jsonify({"ok": True})

    # ---------- Intentها ----------

    MENU_ALIASES = ["منو 🗂", "القائمة 🗂", "Menu 🗂", "منو", "القائمة", "Menu"]

    BACK_ALIASES = [
        TEXT["FA"]["back"], TEXT["AR"]["back"], TEXT["EN"]["back"],
        "بازگشت", "↩️ بازگشت", "رجوع", "العودة", "🔙 رجوع", "Back", "🔙 Back"
    ]

    PRICES_ALIASES = [
        TEXT["FA"]["btn_prices"], TEXT["EN"]["btn_prices"], TEXT["AR"]["btn_prices"],
        "قیمت‌ها", "Prices", "الأسعار"
    ]

    ABOUT_ALIASES = [
        TEXT["FA"]["btn_about"], TEXT["EN"]["btn_about"], TEXT["AR"]["btn_about"],
        "درباره ما", "دربارهٔ ما", "About", "من نحن"
    ]

    PRODUCTS_ALIASES = [
        TEXT["FA"]["btn_products"], TEXT["EN"]["btn_products"], TEXT["AR"]["btn_products"],
        btn_products_label(lang),  # از ENV
        "Products", "محصولات", "المنتجات", "القائمة", "Menu", "منو"
    ]

    CONTENT_ALIASES = [
        TEXT["FA"].get("btn_content", "🧩 پکیج‌های محتوا"),
        TEXT["EN"].get("btn_content", "🧩 Content Packages"),
        TEXT["AR"].get("btn_content", "🧩 باقات المحتوى"),
        "🧩 پکیج‌های محتوا", "Content Packages", "باقات المحتوى"
    ]

    APP_ALIASES = [
        TEXT["FA"].get("btn_app", "🤖 پلان‌های اپ Jawab"),
        TEXT["EN"].get("btn_app", "🤖 Jawab App Plans"),
        TEXT["AR"].get("btn_app", "🤖 خطط تطبيق Jawab"),
        "Jawab App Plans", "خطط تطبيق Jawab", "پلان‌های اپ Jawab"
    ]

    def _get_section(sec: str) -> str:
        return (os.environ.get(f"{sec}_{lang}", "") or "").strip()

    # منو
    if text in MENU_ALIASES:
        send_text(chat_id, TEXT[lang]["choose"], keyboard=menu_keyboard(lang))
        return jsonify({"ok": True})

    # بازگشت (همیشه به صفحه اصلی)
    elif text.strip() in BACK_ALIASES:
        send_text(chat_id, TEXT[lang]["choose"], keyboard=menu_keyboard(lang))
        return jsonify({"ok": True})

    # قیمت‌ها
    if text in PRICES_ALIASES:
        send_text(chat_id, _get_section("PRICES") or TEXT[lang]["not_config"], keyboard=menu_keyboard(lang))
        return jsonify({"ok": True})

    # درباره‌ما
    if text in ABOUT_ALIASES:
        send_text(chat_id, _get_section("ABOUT") or TEXT[lang]["not_config"], keyboard=menu_keyboard(lang))
        return jsonify({"ok": True})

    # محصولات
    if text in PRODUCTS_ALIASES:
        items = load_products(lang)
        if not items:
            send_text(chat_id, TEXT[lang]["catalog_empty"], keyboard=menu_keyboard(lang))
            return jsonify({"ok": True})
        kb = build_product_keyboard(items, lang)
        send_text(chat_id, catalog_title(lang), keyboard=kb)
        return jsonify({"ok": True})

    # پکیج‌های محتوا
    if text in CONTENT_ALIASES:
        body = content_text(lang)
        send_text(chat_id, (body or "").strip() or TEXT[lang]["not_config"], keyboard=menu_keyboard(lang))
        return jsonify({"ok": True})

    # پلان‌های اپ
    if text in APP_ALIASES:
        body = app_plans_text(lang)
        send_text(chat_id, (body or "").strip() or TEXT[lang]["not_config"], keyboard=menu_keyboard(lang))
        return jsonify({"ok": True})

    # انتخاب آیتم: "n" یا "n) ..."
    m = re.match(r"^\s*(\d+)\s*\)?", text)
    if m:
        idx = int(m.group(1)) - 1
        items = load_products(lang)
        top10 = items[:10]
        if 0 <= idx < len(top10):
            it = top10[idx]
            SELECTED[chat_id] = {"name": it.get("name", ""), "price": it.get("price", "")}
            msg = TEXT[lang]["selected"].format(name=it.get("name", ""), price=it.get("price", ""))
            send_text(chat_id, msg, keyboard=confirm_keyboard(lang))
            return jsonify({"ok": True})

    # تأیید سفارش/درخواست
    if text == TEXT[lang]["btn_confirm"]:
        sel = SELECTED.get(chat_id)
        if not sel:
            send_text(chat_id, TEXT[lang]["list_products"], keyboard=menu_keyboard(lang))
            return jsonify({"ok": True})
        phone = get_user_phone(chat_id)
        if not phone:
            need_msg = TEXT[lang].get("need_phone_lead", TEXT[lang]["need_phone"])
            send_text(chat_id, need_msg, keyboard=menu_keyboard(lang))
            return jsonify({"ok": True})

        # ایجاد سفارش و اعلام به ادمین
        oid = create_order(chat_id, sel["name"], 1, sel.get("price", ""))
        send_text(chat_id, TEXT[lang]["order_saved"].format(oid=oid), keyboard=reply_keyboard(lang))

        phone_val = get_user_phone(chat_id) or "-"
        display_name = (name or "").strip() or str(chat_id)
        admin_text = (
            "NEW Order #{}\nUser: {}\nID: {}\nPhone: {}\nItem: {}\nPrice: {}"
        ).format(oid, display_name, chat_id, phone_val, sel["name"], sel.get("price", ""))
        for admin in ADMINS:
            try:
                requests.post(API, json={"chat_id": int(admin), "text": admin_text}, timeout=10)
            except Exception:
                pass

        SELECTED.pop(chat_id, None)
        return jsonify({"ok": True})

    # پشتیبانی
    if text in ["پشتیبانی 🛟", "الدعم 🛟", "Support 🛟", "پشتیبانی", "الدعم", "Support"]:
        send_text(chat_id, build_support_text(lang), keyboard=reply_keyboard(lang))
        return jsonify({"ok": True})

    # زبان (نمایش انتخاب)
    if text in ["زبان 🌐", "اللغة 🌐", "Language 🌐", "زبان", "اللغة", "Language"]:
        send_text(chat_id, TEXT[lang]["language"], keyboard=lang_keyboard())
        return jsonify({"ok": True})

    # پیش‌فرض
    log_message(chat_id, text, "in")
    send_text(chat_id, TEXT[lang]["unknown"], keyboard=reply_keyboard(lang))
    log_message(chat_id, "unknown", "out")
    return jsonify({"ok": True})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
