# app.py — Arabia Social / Jawab (clean)
import os, re, io, csv, time, requests
from flask import Flask, request, jsonify
from collections import defaultdict, deque
from time import time as now

# ---------- ENV ----------
BOT_TOKEN = os.getenv("TG_BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN")
API = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage" if BOT_TOKEN else None
BRAND_NAME = os.getenv("BRAND_NAME", "Arabia Social")
DEFAULT_LANG = (os.getenv("DEFAULT_LANG") or "FA").upper()
SHOW_PRODUCTS = (os.getenv("SHOW_PRODUCTS", "0").strip().lower() in ["1","true","yes","on"])

# support channels
SUPPORT_WHATSAPP  = (os.getenv("SUPPORT_WHATSAPP")  or "").strip()
SUPPORT_TG        = (os.getenv("SUPPORT_TG")        or "").strip()
SUPPORT_EMAIL     = (os.getenv("SUPPORT_EMAIL")     or "").strip()
SUPPORT_INSTAGRAM = (os.getenv("SUPPORT_INSTAGRAM") or "").strip()

# optional catalog title overrides
CATALOG_TITLE_AR = (os.getenv("CATALOG_TITLE_AR") or "").strip()
CATALOG_TITLE_EN = (os.getenv("CATALOG_TITLE_EN") or "").strip()
CATALOG_TITLE_FA = (os.getenv("CATALOG_TITLE_FA") or "").strip()

ADMINS = [x.strip() for x in (os.getenv("ADMINS") or "").split(",") if x.strip()]
PLAN = (os.getenv("PLAN") or "bronze").lower()
SHEET_URL = (os.getenv("SHEET_URL") or "").strip()  # for Silver+

# ---------- DB ----------
from storage.db import (
    init_db, upsert_user, get_user_lang, set_user_lang,
    log_message, get_stats, list_user_ids, set_user_source,
    set_user_phone, get_user_phone, create_order
)
init_db()

app = Flask(__name__)

# ---------- helpers ----------
def contains_any(text, needles):
    t = (text or "").strip().lower()
    return any(n in t for n in [s.lower() for s in needles if s])

def get_lang(user_lang=None):
    lang = (user_lang or DEFAULT_LANG or "EN").upper()
    return lang if lang in ("FA","EN","AR") else "EN"

def get_welcome(lang):
    return os.getenv(f"WELCOME_{lang}", os.getenv("WELCOME_EN", f"Welcome to {BRAND_NAME}"))

def reply_keyboard_layout(rows):
    """rows: list[list[str]] -> Telegram keyboard JSON"""
    return {"keyboard": [[{"text": c} for c in r] for r in rows], "resize_keyboard": True}

def btn_products_label(lang):
    labels = {"FA":"محصولات 🛍","EN":"Products 🛍","AR":"المنتجات 🛍"}
    return labels.get(lang, labels["EN"])

def build_support_text(lang: str) -> str:
    labels = {
        "FA": {"title":"پشتیبانی 🛟","tg":"تلگرام","mail":"ایمیل","wa":"واتساپ","ig":"اینستاگرام"},
        "EN": {"title":"Support 🛟","tg":"Telegram","mail":"Email","wa":"WhatsApp","ig":"Instagram"},
        "AR": {"title":"الدعم 🛟","tg":"تيليجرام","mail":"البريد","wa":"واتساب","ig":"إنستغرام"},
    }
    L = labels.get(lang, labels["EN"])
    lines = [L["title"]]

    # Telegram
    if SUPPORT_TG:
        handle = SUPPORT_TG.lstrip("@")
        lines.append(f"{L['tg']}: @{handle} (https://t.me/{handle})")

    # Email
    if SUPPORT_EMAIL:
        lines.append(f"{L['mail']}: {SUPPORT_EMAIL}")

    # WhatsApp
    if SUPPORT_WHATSAPP:
        digits = "".join(ch for ch in SUPPORT_WHATSAPP if ch.isdigit() or ch == "+").lstrip("+")
        lines.append(f"{L['wa']}: {SUPPORT_WHATSAPP} (https://wa.me/{digits})")

    # Instagram
    if SUPPORT_INSTAGRAM:
        handle = SUPPORT_INSTAGRAM.replace("https://instagram.com/","").replace("http://instagram.com/","").lstrip("@")
        lines.append(f"{L['ig']}: @{handle} (https://instagram.com/{handle})")

    return "\n".join(lines)

# ---------- static text ----------
TEXT = {
    "FA": {
        "welcome": f"سلام! من {BRAND_NAME} هستم 👋",
        "menu": "یک گزینه را انتخاب کن:",
        "support": "پشتیبانی 🛟",
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
        "back": "↩️ بازگشت",
        "btn_prices": "💵 قیمت‌ها",
        "btn_about": "ℹ️ دربارهٔ ما",
        "btn_send_phone": "📞 ارسال شماره",
        "btn_products": "🛍 محصولات",
        "list_products": "لیست محصولات (شماره را انتخاب کن):",
        "btn_confirm": "✅ ثبت درخواست",
        "order_saved": "درخواستت ثبت شد. کد سفارش: #{oid}\nهمکاران ما با شما هماهنگ می‌کنند.",
        "need_phone": "برای ثبت سفارش، لطفاً «📞 ارسال شماره» را بزن.",
        "need_phone_lead": "برای ثبت درخواست، لطفاً «📞 ارسال شماره» را بزن.",
        "selected": "انتخاب شد: {name} — {price}",
        "btn_content": "🧩 پکیج‌های محتوا",
        "btn_app": "🤖 پلان‌های اپ Jawab",
        "btn_request": "✅ ثبت درخواست",
        "lead_saved": "درخواست شما ثبت شد؛ به‌زودی با شما تماس می‌گیریم.",
    },
    "EN": {
        "welcome": f"Hello! I’m {BRAND_NAME} 👋",
        "menu": "Please choose:",
        "support": "Support 🛟",
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
        "back": "↩️ Back",
        "btn_prices": "💵 Prices",
        "btn_about": "ℹ️ About us",
        "btn_send_phone": "📞 Share phone",
        "btn_products": "🛍 Products",
        "list_products": "Products list (pick a number):",
        "btn_confirm": "✅ Confirm request",
        "order_saved": "Your request is saved. Order ID: #{oid}\nWe will contact you shortly.",
        "need_phone": "To place the order, tap “📞 Share phone”.",
        "need_phone_lead": "To submit your request, tap “📞 Share phone”.",
        "selected": "Selected: {name} — {price}",
        "btn_content": "🧩 Content Packages",
        "btn_app": "🤖 Jawab App Plans",
        "btn_request": "✅ Request Quote",
        "lead_saved": "Your request is recorded. We'll contact you shortly.",
    },
    "AR": {
        "welcome": f"مرحباً! أنا {BRAND_NAME} 👋",
        "menu": "اختر خياراً:",
        "support": "الدعم 🛟",
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
        "back": "↩️ رجوع",
        "btn_prices": "💵 الأسعار",
        "btn_about": "ℹ️ من نحن",
        "btn_send_phone": "📞 إرسال الرقم",
        "btn_products": "🛍 المنتجات",
        "list_products": "قائمة المنتجات (اختر رقماً):",
        "btn_confirm": "✅ تأكيد الطلب",
        "order_saved": "تم حفظ طلبك. رقم الطلب: #{oid}\nسنتواصل معك قريباً.",
        "need_phone": "لإتمام الطلب، اضغط «📞 إرسال الرقم».",
        "need_phone_lead": "لإتمام طلبك، اضغط «📞 إرسال الرقم».",
        "selected": "تم اختيار: {name} — {price}",
        "btn_content": "🧩 باقات المحتوى",
        "btn_app": "🤖 خطط تطبيق Jawab",
        "btn_request": "✅ تسجيل طلب",
        "lead_saved": "تم تسجيل طلبك، وسنتواصل معك قريباً.",
    },
}

# ---------- keyboards ----------
PKG_LABELS = {
    "FA": {"bronze":"Bronze","silver":"Silver","gold":"Gold","diamond":"Diamond","back":"↩️ بازگشت"},
    "EN": {"bronze":"Bronze","silver":"Silver","gold":"Gold","diamond":"Diamond","back":"↩️ Back"},
    "AR": {"bronze":"Bronze","silver":"Silver","gold":"Gold","diamond":"Diamond","back":"↩️ رجوع"},
}

def reply_keyboard(lang: str):
    if lang == "AR":
        return reply_keyboard_layout([["القائمة 🗂","الدعم 🛟"],["اللغة 🌐"]])
    if lang == "EN":
        return reply_keyboard_layout([["Menu 🗂","Support 🛟"],["Language 🌐"]])
    return reply_keyboard_layout([["منو 🗂","پشتیبانی 🛟"],["زبان 🌐"]])

def content_packages_keyboard(lang):
    L = PKG_LABELS.get(lang, PKG_LABELS["EN"])
    return reply_keyboard_layout([
        [f"🧩 {L['bronze']}", f"🧩 {L['silver']}"],
        [f"🧩 {L['gold']}",   f"🧩 {L['diamond']}"],
        [L["back"]]
    ])

def app_plans_keyboard(lang):
    L = PKG_LABELS.get(lang, PKG_LABELS["EN"])
    return reply_keyboard_layout([
        [f"🤖 {L['bronze']}", f"🤖 {L['silver']}"],
        [f"🤖 {L['gold']}",   f"🤖 {L['diamond']}"],
        [L["back"]]
    ])

def menu_keyboard(lang: str):
    L = (lang or "FA").upper()
    T = TEXT[L]
    rows = []
    if SHOW_PRODUCTS:
        rows.append([btn_products_label(L), T["btn_prices"], T["btn_about"]])
        rows.append([T["btn_content"], T["btn_app"]])
    else:
        rows.append([T["btn_content"], T["btn_app"]])
        rows.append([T["btn_prices"], T["btn_about"]])
    rows.append([T["btn_send_phone"]])
    rows.append([T["back"]])
    return reply_keyboard_layout(rows)

# ---------- products / catalog ----------
CATALOG = []
SELECTED = {}      # chat_id -> {name, price}
LEAD_CONTEXT = {}  # chat_id -> "content" | "app"
LEAD_PENDING = {}  # chat_id -> waiting for phone

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
        if not avail: continue
        items.append({
            "category": (row.get("category") or "").strip(),
            "name": (row.get("item_name") or "").strip(),
            "price": (row.get("price") or "").strip(),
        })
    global CATALOG; CATALOG = items
    return len(items)

def parse_env_products(lang: str):
    raw = os.getenv(f"PRODUCTS_{(lang or '').upper()}", "") or ""
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

def load_products(lang: str):
    if PLAN in ["silver","gold","diamond"] and CATALOG:
        return CATALOG
    return parse_env_products(lang)

def build_product_keyboard(items, lang):
    rows = [[f"{i}) {it['name']}"] for i, it in enumerate(items[:10], start=1)]
    rows.append([TEXT[lang]["back"]])
    return reply_keyboard_layout(rows)

# ---------- rate limit ----------
BUCKET = defaultdict(lambda: deque(maxlen=10))
def rate_ok(uid: int, limit=5, window=5):
    q = BUCKET[uid]; t = now(); q.append(t)
    recent = [x for x in q if t - x <= window]
    return len(recent) <= limit

# ---------- helpers: env text sections ----------
def get_env_text(keys):
    parts = []
    for k in keys:
        v = (os.getenv(k) or "").strip()
        if v: parts.append(v)
    return "\n\n".join(parts) if parts else ""

def content_text(lang: str) -> str:
    suf = (lang or "").upper()
    return get_env_text([f"CONTENT_BRONZE_{suf}", f"CONTENT_SILVER_{suf}", f"CONTENT_GOLD_{suf}", f"CONTENT_DIAMOND_{suf}"])

def app_plans_text(lang: str) -> str:
    suf = (lang or "").upper()
    return get_env_text([f"APP_BRONZE_{suf}", f"APP_SILVER_{suf}", f"APP_GOLD_{suf}", f"APP_DIAMOND_{suf}"])

def get_section(sec: str, lang: str) -> str:
    suf = (lang or "").strip().upper()
    if suf not in ("FA","EN","AR"): suf = "EN"
    candidates = [f"{sec}_{suf}", f"{sec}_TEXT_{suf}", f"{sec}"]
    return get_env_text(candidates) or ""

def catalog_title(lang: str) -> str:
    fallback = TEXT[lang]["list_products"]
    if lang == "AR": return CATALOG_TITLE_AR or fallback
    if lang == "EN": return CATALOG_TITLE_EN or fallback
    return CATALOG_TITLE_FA or fallback

# ---------- web ----------
@app.get("/healthz")
@app.get("/health")
def health():
    return jsonify(status="ok")

@app.get("/")
def root():
    return "Jawab bot is running."

# ---------- core handler ----------
def process_update(update: dict):
    message = update.get("message") or update.get("edited_message") or {}
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    text = (message.get("text") or "").strip()
    contact = message.get("contact") or {}

    if not chat_id: return {"ok": True}

    # share contact
    if contact and contact.get("phone_number"):
        set_user_phone(chat_id, contact.get("phone_number"))
        lang_now = get_user_lang(chat_id) or DEFAULT_LANG
        # lead auto-funnel
        src = LEAD_PENDING.pop(chat_id, None)
        if src:
            display_name = ((chat.get("first_name") or "") + " " + (chat.get("last_name") or "")).strip() or str(chat_id)
            admin_text = f"NEW Lead\nSource: {src}\nUser: {display_name}\nID: {chat_id}\nPhone: {contact.get('phone_number')}"
            for admin in ADMINS:
                try: requests.post(API, json={"chat_id": int(admin), "text": admin_text}, timeout=10)
                except Exception: pass
            send_text(chat_id, TEXT[lang_now]["lead_saved"], keyboard=reply_keyboard(lang_now))
            return {"ok": True}
        send_text(chat_id, TEXT[lang_now]["phone_ok"], keyboard=reply_keyboard(lang_now))
        return {"ok": True}

    if not text: return {"ok": True}
    if not rate_ok(chat_id): return {"ok": True}

    # ensure user + lang
    name = (chat.get("first_name") or "") + " " + (chat.get("last_name") or "")
    upsert_user(chat_id, name.strip() or str(chat_id))
    lang = get_user_lang(chat_id) or DEFAULT_LANG

    # /start (+ ref source)
    if text.startswith("/start"):
        parts = text.split(" ", 1)
        if len(parts) == 2 and parts[1].strip():
            try: set_user_source(chat_id, parts[1].strip()[:64])
            except Exception: pass
        send_text(chat_id, get_welcome(lang), keyboard=reply_keyboard(lang))
        log_message(chat_id, text, "in"); log_message(chat_id, "welcome", "out")
        return {"ok": True}

    low = text.lower(); norm = text.upper()

    # language switches
    if norm in ["FA","FARSI","فارسی"]:
        set_user_lang(chat_id, "FA"); lang = "FA"
        send_text(chat_id, TEXT[lang]["set_ok"], keyboard=reply_keyboard(lang)); return {"ok": True}
    if norm in ["EN","ENG","ENGLISH","انگلیسی"]:
        set_user_lang(chat_id, "EN"); lang = "EN"
        send_text(chat_id, TEXT[lang]["set_ok"], keyboard=reply_keyboard(lang)); return {"ok": True}
    if norm in ["AR","ARA","ARABIC","العربية","عربی"]:
        set_user_lang(chat_id, "AR"); lang = "AR"
        send_text(chat_id, TEXT[lang]["set_ok"], keyboard=reply_keyboard(lang)); return {"ok": True}

    # admins
    is_admin = str(chat_id) in ADMINS

    # /stats
    if low.startswith("/stats") and is_admin:
        st = get_stats()
        msg = f"Users: {st['users_total']}\nMessages: {st['messages_total']} (24h: {st['messages_24h']})\nLangs: {st['langs']}"
        send_text(chat_id, msg); return {"ok": True}

    # /share
    if low.startswith("/share"):
        bot_user = os.getenv("BOT_USERNAME", "").strip()
        if not bot_user:
            send_text(chat_id, "برای /share، BOT_USERNAME لازم است. مثال: ArabiaSocialBot (بدون @)")
            return {"ok": True}
        link = f"https://t.me/{bot_user}?start=ref{chat_id}"
        send_text(chat_id, "📣 لینک معرفی شما:\n" + link + "\nهر ورودی از این لینک در Source ذخیره می‌شود.")
        return {"ok": True}

    # /broadcast
    if low.startswith("/broadcast") and is_admin:
        msg = text[len("/broadcast"):].strip()
        if not msg:
            send_text(chat_id, "Usage: /broadcast your message"); return {"ok": True}
        ids = list_user_ids(10000); sent = 0
        for uid in ids:
            try: send_text(uid, msg); sent += 1; time.sleep(0.03)
            except Exception: pass
        send_text(chat_id, TEXT[lang]["broadcast_ok"].format(n=sent)); return {"ok": True}

    # /setlang
    if low.startswith("/setlang"):
        parts = low.split()
        if len(parts)>=2 and parts[1].upper() in ["FA","EN","AR"]:
            set_user_lang(chat_id, parts[1].upper()); lang = parts[1].upper()
            send_text(chat_id, TEXT[lang]["set_ok"], keyboard=reply_keyboard(lang)); return {"ok": True}
        send_text(chat_id, TEXT[lang]["language"], keyboard=reply_keyboard(lang)); return {"ok": True}

    # /sync (Silver+)
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

    # ----- menu intents -----
    MENU_ALIASES = ["منو 🗂","القائمة 🗂","Menu 🗂","منو","القائمة","Menu"]
    if text in MENU_ALIASES:
        send_text(chat_id, TEXT[lang]["choose"], keyboard=menu_keyboard(lang)); return {"ok": True}

    BACK_ALIASES = [
        TEXT["FA"]["back"], TEXT["EN"]["back"], TEXT["AR"]["back"],
        "بازگشت","العودة","رجوع","Back"
    ]
    if text.strip() in BACK_ALIASES:
        send_text(chat_id, TEXT[lang]["choose"], keyboard=menu_keyboard(lang)); return {"ok": True}

    # Prices
    if contains_any(text, ["قیمت","prices","الأسعار"]):
        send_text(chat_id, get_section("PRICES", lang) or TEXT[lang]["not_config"], keyboard=menu_keyboard(lang)); return {"ok": True}

    # About
    if contains_any(text, ["درباره","about","من نحن","من احنا","من نحنُ"]):
        send_text(chat_id, get_section("ABOUT", lang) or TEXT[lang]["not_config"], keyboard=menu_keyboard(lang)); return {"ok": True}

    # Content packages (submenu)
    if contains_any(text, ["پکیج‌های محتوا","content packages","باقات المحتوى"]):
        send_text(chat_id, "یک پکیج را انتخاب کنید:", keyboard=content_packages_keyboard(lang)); return {"ok": True}

    # App plans (submenu)
    if contains_any(text, ["پلان‌های اپ","jawab app plans","خطط تطبيق"]):
        send_text(chat_id, "یک پلن را انتخاب کنید:", keyboard=app_plans_keyboard(lang)); return {"ok": True}

    # Content detail: 🧩 Bronze/Silver/Gold/Diamond
    for key in ["bronze","silver","gold","diamond"]:
        if contains_any(text, [f"🧩 {key}", key]):
            msg = os.getenv(f"CONTENT_{key.upper()}_{lang}") or TEXT[lang]["not_config"]
            LEAD_CONTEXT[chat_id] = "content"
            # add CTA button (request phone + back)
            kb = reply_keyboard_layout([[TEXT[lang]["btn_request"]],[TEXT[lang]["btn_send_phone"]],[PKG_LABELS[lang]["back"]]])
            send_text(chat_id, msg, keyboard=kb); return {"ok": True}

    # App detail: 🤖 Bronze/Silver/Gold/Diamond
    for key in ["bronze","silver","gold","diamond"]:
        if contains_any(text, [f"🤖 {key}", key]):
            msg = os.getenv(f"APP_{key.upper()}_{lang}") or TEXT[lang]["not_config"]
            LEAD_CONTEXT[chat_id] = "app"
            kb = reply_keyboard_layout([[TEXT[lang]["btn_request"]],[TEXT[lang]["btn_send_phone"]],[PKG_LABELS[lang]["back"]]])
            send_text(chat_id, msg, keyboard=kb); return {"ok": True}

    # Products (optional)
    if SHOW_PRODUCTS and contains_any(text, ["products","محصولات","المنتجات"] + MENU_ALIASES):
        items = load_products(lang)
        if not items:
            send_text(chat_id, TEXT[lang]["catalog_empty"], keyboard=menu_keyboard(lang)); return {"ok": True}
        kb = build_product_keyboard(items, lang)
        send_text(chat_id, catalog_title(lang), keyboard=kb); return {"ok": True}

    # Select item by number
    m = re.match(r"^\s*(\d+)\s*\)?", text)
    if m:
        idx = int(m.group(1)) - 1
        items = load_products(lang)
        top10 = items[:10]
        if 0 <= idx < len(top10):
            it = top10[idx]
            SELECTED[chat_id] = {"name": it.get("name",""), "price": it.get("price","")}
            msg = TEXT[lang]["selected"].format(name=it.get("name",""), price=it.get("price",""))
            send_text(chat_id, msg, keyboard=reply_keyboard_layout([[TEXT[lang]["btn_confirm"]],[TEXT[lang]["back"]]]))
            return {"ok": True}

    # Confirm order / lead
    if text == TEXT[lang]["btn_confirm"]:
        sel = SELECTED.get(chat_id)
        if not sel:
            send_text(chat_id, TEXT[lang]["list_products"], keyboard=menu_keyboard(lang)); return {"ok": True}
        phone = get_user_phone(chat_id)
        if not phone:
            send_text(chat_id, TEXT[lang].get("need_phone_lead", TEXT[lang]["need_phone"]),
                      keyboard=reply_keyboard_layout([[TEXT[lang]["btn_send_phone"]],[TEXT[lang]["back"]]]))
            return {"ok": True}
        oid = create_order(chat_id, sel["name"], 1, sel.get("price",""))
        send_text(chat_id, TEXT[lang]["order_saved"].format(oid=oid), keyboard=reply_keyboard(lang))
        # notify admins
        phone_val = get_user_phone(chat_id) or "-"
        display_name = (name or "").strip() or str(chat_id)
        admin_text = "NEW Order #{}\nUser: {}\nID: {}\nPhone: {}\nItem: {}\nPrice: {}".format(
            oid, display_name, chat_id, phone_val, sel["name"], sel.get("price",""))
        for admin in ADMINS:
            try: requests.post(API, json={"chat_id": int(admin), "text": admin_text}, timeout=10)
            except Exception: pass
        SELECTED.pop(chat_id, None)
        return {"ok": True}

    # Support
    if contains_any(text, ["پشتیبانی","support","الدعم"]):
        send_text(chat_id, build_support_text(lang), keyboard=reply_keyboard(lang)); return {"ok": True}

    # Language menu
    if contains_any(text, ["زبان","language","اللغة"]):
        send_text(chat_id, TEXT[lang]["language"], keyboard=reply_keyboard_layout([["FA","EN","AR"],[TEXT[lang]["back"]]])); return {"ok": True}

    # default
    log_message(chat_id, text, "in")
    send_text(chat_id, TEXT[lang]["unknown"], keyboard=reply_keyboard(lang))
    log_message(chat_id, "unknown", "out")
    return {"ok": True}

# ---------- routes ----------
@app.route("/webhook/telegram", methods=["GET","POST"])
@app.route("/telegram", methods=["GET","POST"])
def telegram():
    if request.method == "GET":
        return "OK", 200
    if not BOT_TOKEN:
        return jsonify({"error":"TELEGRAM_BOT_TOKEN missing"}), 500

    # optional secret
    secret_env = os.getenv("WEBHOOK_SECRET", "")
    secret_hdr = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if secret_env and secret_hdr != secret_env:
        return "unauthorized", 401

    update = request.get_json(silent=True) or {}
    try:
        return jsonify(process_update(update))
    except Exception as e:
        # basic fail-safe to avoid crashing gunicorn
        try:
            chat_id = ((update.get("message") or {}).get("chat") or {}).get("id")
            if chat_id: send_text(chat_id, "⚠️ A temporary error occurred. Please try again.")
        except Exception:
            pass
        return jsonify({"ok": True})

# ---------- run ----------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
