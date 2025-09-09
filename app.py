# app.py — Arabia Social / Jawab (clean, 3-lang, orders)
import os, re, io, csv, time, requests
from flask import Flask, request, jsonify

# ============== ENV ==============
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("TG_BOT_TOKEN")
API_SEND  = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage" if BOT_TOKEN else None
BRAND_NAME   = os.getenv("BRAND_NAME", "Arabia Social")
DEFAULT_LANG = (os.getenv("DEFAULT_LANG") or "FA").upper()
SHOW_PRODUCTS = os.getenv("SHOW_PRODUCTS","0").strip().lower() in ["1","true","yes","on"]
PLAN = (os.getenv("PLAN") or "bronze").lower()
SHEET_URL = (os.getenv("SHEET_URL") or "").strip()
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET","")

SUPPORT_TG        = (os.getenv("SUPPORT_TG")        or "").strip()
SUPPORT_EMAIL     = (os.getenv("SUPPORT_EMAIL")     or "").strip()
SUPPORT_WHATSAPP  = (os.getenv("SUPPORT_WHATSAPP")  or "").strip()
SUPPORT_INSTAGRAM = (os.getenv("SUPPORT_INSTAGRAM") or "").strip()

ADMINS = [x.strip() for x in (os.getenv("ADMINS") or "").split(",") if x.strip()]

# ============== Optional storage (safe fallbacks) ==============
try:
    from storage.db import (
        init_db, upsert_user, get_user_lang, set_user_lang,
        log_message, get_stats, list_user_ids, set_user_source,
        set_user_phone, get_user_phone, create_order
    )
    init_db()
except Exception:
    _langs, _phones = {}, {}
    def init_db(): pass
    def upsert_user(uid, name): pass
    def get_user_lang(uid): return _langs.get(uid)
    def set_user_lang(uid, lang): _langs[uid]=lang
    def log_message(uid, text, direction): pass
    def get_stats(): return {"users_total":0,"messages_total":0,"messages_24h":0,"langs":{}}
    def list_user_ids(n): return []
    def set_user_source(uid, src): pass
    def set_user_phone(uid, p): _phones[uid]=p
    def get_user_phone(uid): return _phones.get(uid)
    def create_order(uid, item, qty, price): return int(time.time())

# ============== Flask ==============
app = Flask(__name__)

# ============== Utils ==============
def send_text(chat_id, text, keyboard=None, parse_mode=None):
    if not BOT_TOKEN: return
    payload = {"chat_id": chat_id, "text": text}
    if keyboard:   payload["reply_markup"] = keyboard
    if parse_mode: payload["parse_mode"] = parse_mode
    try:
        requests.post(API_SEND, json=payload, timeout=10)
    except Exception as e:
        print("send_text error:", e)

def reply_keyboard_layout(rows):
    # rows:list[list[str]]
    return {"keyboard": [[{"text": c} for c in r] for r in rows], "resize_keyboard": True}

def contains_any(text, needles):
    # حذف ایموجی‌ها و نرمال‌سازی فاصله/حروف
    t = (text or "")
    for emo in ["🧩","🤖","💵","ℹ️","📞","🛟","🗂","✅","❌"]:
        t = t.replace(emo, "")
    t = " ".join(t.split()).strip().lower()
    return any(n in t for n in [s.lower() for s in needles if s])

def get_lang(user_lang=None):
    lang = (user_lang or DEFAULT_LANG or "EN").upper()
    return lang if lang in ("FA","EN","AR") else "EN"

def get_welcome(lang):
    return os.getenv(f"WELCOME_{lang}", os.getenv("WELCOME_EN", f"Welcome to {BRAND_NAME}"))

def get_section(prefix, lang):
    suf = (lang or "EN").upper()
    for key in [f"{prefix}_{suf}", f"{prefix}_TEXT_{suf}", prefix]:
        v = (os.getenv(key) or "").strip()
        if v: return v
    return ""

def build_support_text(lang):
    L = {
        "FA":{"title":"پشتیبانی 🛟","tg":"تلگرام","mail":"ایمیل","wa":"واتساپ","ig":"اینستاگرام"},
        "EN":{"title":"Support 🛟","tg":"Telegram","mail":"Email","wa":"WhatsApp","ig":"Instagram"},
        "AR":{"title":"الدعم 🛟","tg":"تيليجرام","mail":"البريد","wa":"واتساب","ig":"إنستغرام"},
    }[lang]
    lines = [L["title"]]
    if SUPPORT_TG:
        u = SUPPORT_TG.lstrip("@")
        lines.append(f'{L["tg"]}: @{u} (https://t.me/{u})')
    if SUPPORT_EMAIL:
        lines.append(f'{L["mail"]}: {SUPPORT_EMAIL}')
    if SUPPORT_WHATSAPP:
        digits = "".join(ch for ch in SUPPORT_WHATSAPP if ch.isdigit() or ch=="+").lstrip("+")
        lines.append(f'{L["wa"]}: {SUPPORT_WHATSAPP} (https://wa.me/{digits})')
    if SUPPORT_INSTAGRAM:
        u = SUPPORT_INSTAGRAM.replace("https://instagram.com/","").replace("http://instagram.com/","").lstrip("@")
        lines.append(f'{L["ig"]}: @{u} (https://instagram.com/{u})')
    return "\n".join(lines)

# ============== Static text / keyboards ==============
TEXT = {
    "FA":{
        "choose":"یک گزینه را انتخاب کن:","back":"↩️ بازگشت",
        "btn_content":"🧩 پکیج‌های محتوا","btn_app":"🤖 پلان‌های اپ Jawab",
        "btn_prices":"💵 قیمت‌ها","btn_about":"ℹ️ دربارهٔ ما","btn_send_phone":"📞 ارسال شماره",
        "btn_order":"✅ ثبت سفارش","btn_cancel":"❌ انصراف",
        "phone_ok":"شماره‌ات ثبت شد.","need_phone":"برای ثبت سفارش، «📞 ارسال شماره» را بزن.",
        "order_saved":"سفارش شما ثبت شد. کد: #{oid}\nهمکاران ما به‌زودی تماس می‌گیرند.",
        "unknown":"متوجه نشدم.","language":"FA / EN / AR"
    },
    "EN":{
        "choose":"Please choose:","back":"↩️ Back",
        "btn_content":"🧩 Content Packages","btn_app":"🤖 Jawab App Plans",
        "btn_prices":"💵 Prices","btn_about":"ℹ️ About us","btn_send_phone":"📞 Share phone",
        "btn_order":"✅ Place order","btn_cancel":"❌ Cancel",
        "phone_ok":"Your phone is saved.","need_phone":"To place the order, tap “📞 Share phone”.",
        "order_saved":"Your order is placed. ID: #{oid}\nWe’ll contact you shortly.",
        "unknown":"Sorry, I didn’t get that.","language":"FA / EN / AR"
    },
    "AR":{
        "choose":"اختر خياراً:","back":"↩️ رجوع",
        "btn_content":"🧩 باقات المحتوى","btn_app":"🤖 خطط تطبيق Jawab",
        "btn_prices":"💵 الأسعار","btn_about":"ℹ️ من نحن","btn_send_phone":"📞 إرسال الرقم",
        "btn_order":"✅ تأكيد الطلب","btn_cancel":"❌ إلغاء",
        "phone_ok":"تم حفظ رقم هاتفك.","need_phone":"لإتمام الطلب اضغط «📞 إرسال الرقم».",
        "order_saved":"تم تسجيل طلبك. الرقم: #{oid}\nسنتواصل معك قريباً.",
        "unknown":"لم أفهم.","language":"FA / EN / AR"
    },
}

PKG_LABELS = {
    "FA":{"bronze":"Bronze","silver":"Silver","gold":"Gold","diamond":"Diamond","back":"↩️ بازگشت"},
    "EN":{"bronze":"Bronze","silver":"Silver","gold":"Gold","diamond":"Diamond","back":"↩️ Back"},
    "AR":{"bronze":"Bronze","silver":"Silver","gold":"Gold","diamond":"Diamond","back":"↩️ رجوع"},
}

def reply_keyboard(lang):
    T = TEXT[lang]
    rows = [
        [T["btn_content"], T["btn_app"]],
        [T["btn_prices"],  T["btn_about"]],
        [T["btn_send_phone"]],
        [T["back"]]
    ]
    return reply_keyboard_layout(rows)

def content_packages_keyboard(lang):
    L = PKG_LABELS[lang]
    return reply_keyboard_layout([
        [f"🧩 {L['bronze']}", f"🧩 {L['silver']}"],
        [f"🧩 {L['gold']}",   f"🧩 {L['diamond']}"],
        [L["back"]]
    ])

def app_plans_keyboard(lang):
    L = PKG_LABELS[lang]
    return reply_keyboard_layout([
        [f"🤖 {L['bronze']}", f"🤖 {L['silver']}"],
        [f"🤖 {L['gold']}",   f"🤖 {L['diamond']}"],
        [L["back"]]
    ])

# ============== Catalog (optional) ==============
CATALOG, SELECTED, LEAD_CONTEXT = [], {}, {}  # LEAD_CONTEXT[chat_id] = "content:bronze" / "app:silver" / "lead"

def _download_sheet_csv(url): 
    r = requests.get(url, timeout=15); r.raise_for_status(); return r.text

def sync_catalog_from_sheet():
    f = io.StringIO(_download_sheet_csv(SHEET_URL))
    reader = csv.DictReader(f); items=[]
    for row in reader:
        if (row.get("is_available") or "1").strip().lower() in ["1","true","yes","available"]:
            items.append({"name": (row.get("item_name") or "").strip(),
                          "price": (row.get("price") or "").strip()})
    CATALOG[:] = items; return len(items)

def parse_env_products(lang):
    raw = os.getenv(f"PRODUCTS_{lang}", "") or ""
    out=[]
    for ln in raw.splitlines():
        ln=ln.strip()
        if not ln: continue
        parts=[p.strip() for p in ln.split("|")]
        if len(parts)==3: _,name,price = parts
        elif len(parts)==2: name,price = parts
        else: name,price = ln,""
        out.append({"name":name,"price":price})
    return out

def load_products(lang):
    if PLAN in ["silver","gold","diamond"] and CATALOG: return CATALOG
    return parse_env_products(lang)

# ============== Health / Root ==============
@app.get("/healthz")
@app.get("/health")
def health():
    return jsonify(ok=True)

@app.get("/")
def root():
    return "OK"

# ============== Core handler ==============
def process_update(update: dict):
    msg = update.get("message") or update.get("edited_message") or {}
    chat = msg.get("chat") or {}; chat_id = chat.get("id")
    text = (msg.get("text") or "").strip()
    contact = msg.get("contact") or {}

    if not chat_id: return {"ok": True}
    print(f"[DBG] text={repr(text)}")

    # contact flow
    if contact and contact.get("phone_number"):
        set_user_phone(chat_id, contact["phone_number"])
        lang = get_user_lang(chat_id) or get_lang()

        # اگر در جریان سفارش بود، بعد از دریافت شماره سفارش را نهایی کن
        ctx = LEAD_CONTEXT.pop(chat_id, None)
        if ctx:
            oid = create_order(chat_id, ctx, 1, "")
            send_text(chat_id, TEXT[lang]["order_saved"].format(oid=oid), keyboard=reply_keyboard(lang))
            display_name = ((chat.get("first_name") or "") + " " + (chat.get("last_name") or "")).strip() or str(chat_id)
            admin_msg = f"NEW ORDER\nID: #{oid}\nUser: {display_name} ({chat_id})\nPhone: {contact.get('phone_number')}\nContext: {ctx}"
            for admin in ADMINS:
                try: requests.post(API_SEND, json={"chat_id": int(admin), "text": admin_msg}, timeout=10)
                except Exception: pass
            return {"ok": True}

        send_text(chat_id, TEXT[lang]["phone_ok"], keyboard=reply_keyboard(lang))
        return {"ok": True}

    if not text: return {"ok": True}
    lang = get_user_lang(chat_id) or get_lang()
    upsert_user(chat_id, (chat.get("first_name") or "") + " " + (chat.get("last_name") or ""))

    # /start (ref)
    if text.startswith("/start"):
        parts = text.split(" ",1)
        if len(parts)==2 and parts[1].strip():
            try: set_user_source(chat_id, parts[1].strip()[:64])
            except Exception: pass
        send_text(chat_id, get_welcome(lang), keyboard=reply_keyboard(lang))
        return {"ok": True}

    # language quick set
    if text.upper() in ["FA","EN","AR","FARSI","ENGLISH","ARABIC","العربية","فارسی","انگلیسی","عربی"]:
        target = "FA" if "FA" in text.upper() or "فار" in text else ("EN" if "EN" in text.upper() or "ENGLISH" in text.upper() else "AR")
        set_user_lang(chat_id, target); lang = target
        send_text(chat_id, TEXT[lang]["language"], keyboard=reply_keyboard(lang)); return {"ok": True}

    # menu
    if contains_any(text, ["منو","menu","القائمة"]):
        send_text(chat_id, TEXT[lang]["choose"], keyboard=reply_keyboard(lang)); return {"ok": True}

    # back (robust)
    if contains_any(text, ["بازگشت","رجوع","back"]):
        send_text(chat_id, TEXT[lang]["choose"], keyboard=reply_keyboard(lang)); return {"ok": True}

    # prices / about
    if contains_any(text, ["قیمت","prices","الأسعار","السعر"]):
        send_text(chat_id, get_section("PRICES", lang) or "—", keyboard=reply_keyboard(lang)); return {"ok": True}
    if contains_any(text, ["درباره","about","من نحن"]):
        send_text(chat_id, get_section("ABOUT", lang) or "—", keyboard=reply_keyboard(lang)); return {"ok": True}

    # submenus
    if contains_any(text, ["پکیج‌های محتوا","content packages","باقات المحتوى"]):
        send_text(chat_id, TEXT[lang]["choose"], keyboard=content_packages_keyboard(lang)); return {"ok": True}
    if contains_any(text, ["پلان‌های اپ","jawab app plans","خطط تطبيق"]):
        send_text(chat_id, TEXT[lang]["choose"], keyboard=app_plans_keyboard(lang)); return {"ok": True}

    # content details (with order buttons)
    for key in ["bronze","silver","gold","diamond"]:
        if contains_any(text, [f"🧩 {key}", key]):
            msg = os.getenv(f"CONTENT_{key.upper()}_{lang}") or "—"
            LEAD_CONTEXT[chat_id] = f"content:{key}"
            kb = reply_keyboard_layout([
                [TEXT[lang]["btn_order"]],
                [TEXT[lang]["btn_send_phone"]],
                [PKG_LABELS[lang]["back"], TEXT[lang]["btn_cancel"]]
            ])
            send_text(chat_id, msg, keyboard=kb); return {"ok": True}

    # app details (with order buttons)
    for key in ["bronze","silver","gold","diamond"]:
        if contains_any(text, [f"🤖 {key}", key]):
            msg = os.getenv(f"APP_{key.upper()}_{lang}") or "—"
            LEAD_CONTEXT[chat_id] = f"app:{key}"
            kb = reply_keyboard_layout([
                [TEXT[lang]["btn_order"]],
                [TEXT[lang]["btn_send_phone"]],
                [PKG_LABELS[lang]["back"], TEXT[lang]["btn_cancel"]]
            ])
            send_text(chat_id, msg, keyboard=kb); return {"ok": True}

    # confirm order
    if text == TEXT[lang]["btn_order"]:
        phone = get_user_phone(chat_id)
        if not phone:
            LEAD_CONTEXT[chat_id] = (LEAD_CONTEXT.get(chat_id) or "lead")
            send_text(chat_id, TEXT[lang]["need_phone"],
                      keyboard=reply_keyboard_layout([[TEXT[lang]["btn_send_phone"]],[PKG_LABELS[lang]["back"]]]))
            return {"ok": True}
        ctx = LEAD_CONTEXT.get(chat_id, "lead")
        oid = create_order(chat_id, ctx, 1, "")
        send_text(chat_id, TEXT[lang]["order_saved"].format(oid=oid), keyboard=reply_keyboard(lang))
        display_name = ((chat.get("first_name") or "") + " " + (chat.get("last_name") or "")).strip() or str(chat_id)
        admin_msg = f"NEW ORDER\nID: #{oid}\nUser: {display_name} ({chat_id})\nPhone: {phone}\nContext: {ctx}"
        for admin in ADMINS:
            try: requests.post(API_SEND, json={"chat_id": int(admin), "text": admin_msg}, timeout=10)
            except Exception: pass
        LEAD_CONTEXT.pop(chat_id, None)
        return {"ok": True}

    # cancel
    if text == TEXT[lang]["btn_cancel"]:
        LEAD_CONTEXT.pop(chat_id, None)
        send_text(chat_id, TEXT[lang]["choose"], keyboard=reply_keyboard(lang)); return {"ok": True}

    # support
    if contains_any(text, ["پشتیبانی","support","الدعم"]):
        send_text(chat_id, build_support_text(lang), keyboard=reply_keyboard(lang)); return {"ok": True}

    # default
    send_text(chat_id, TEXT[lang]["unknown"], keyboard=reply_keyboard(lang))
    return {"ok": True}

# ============== Routes ==============
@app.route("/telegram", methods=["GET","POST"])
@app.route("/webhook/telegram", methods=["GET","POST"])
def telegram():
    if request.method == "GET": return "OK", 200
    if not BOT_TOKEN: return jsonify({"error":"TELEGRAM_BOT_TOKEN missing"}), 500

    if WEBHOOK_SECRET:
        secret_hdr = request.headers.get("X-Telegram-Bot-Api-Secret-Token","")
        if secret_hdr != WEBHOOK_SECRET: return "unauthorized", 401

    upd = request.get_json(silent=True) or {}
    try:
        return jsonify(process_update(upd))
    except Exception as e:
        print("handler error:", e)
        try:
            chat_id = ((upd.get("message") or {}).get("chat") or {}).get("id")
            if chat_id: send_text(chat_id, "⚠️ Temporary error. Please try again.")
        except Exception: pass
        return jsonify({"ok": True})

# ============== Run (local) ==============
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
