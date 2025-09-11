# app.py
# Arabia Social -> WORK1BOT full-stack single-file prototype
# Features: Bronze->Silver->Gold->Diamond (catalog from ENV or Google Sheet, cart, checkout, orders, stock, reports)
#
# Requirements: python 3.9+, packages: flask, requests
# Deploy notes: set TELEGRAM_BOT_TOKEN (new bot for isolation), ADMINS (comma separated chat_ids),
# SHEET_URL (for silver+), PLAN (bronze/silver/gold/diamond), SHOW_PRODUCTS=1
# Data persistence: SQLite file data.sqlite (created automatically)
# ----------------------------------------------------------------------------

import os, re, io, csv, json, time, sqlite3, requests
from datetime import datetime, timedelta
from flask import Flask, request, jsonify

# ---------------- ENV / CONFIG ----------------
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
API_SEND = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage" if BOT_TOKEN else None
BRAND_NAME = os.getenv("BRAND_NAME", "Work1 Shop")
DEFAULT_LANG = (os.getenv("DEFAULT_LANG") or "FA").upper()
PLAN = (os.getenv("PLAN") or "bronze").lower()
SHOW_PRODUCTS = os.getenv("SHOW_PRODUCTS","0").strip().lower() in ["1","true","yes","on"]
SHEET_URL = (os.getenv("SHEET_URL") or "").strip()
ADMINS = [x.strip() for x in (os.getenv("ADMINS") or "").split(",") if x.strip()]
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET","")

DB_FILE = os.getenv("DATA_DB_FILE", "data.sqlite")

# Support channels
SUPPORT_TG = (os.getenv("SUPPORT_TG") or "").strip()
SUPPORT_EMAIL = (os.getenv("SUPPORT_EMAIL") or "").strip()
SUPPORT_WHATSAPP = (os.getenv("SUPPORT_WHATSAPP") or "").strip()
SUPPORT_INSTAGRAM = (os.getenv("SUPPORT_INSTAGRAM") or "").strip()

# ---------------- App ----------------
app = Flask(__name__)

# ---------------- Helpers: DB ----------------
def db_connect():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

DB = db_connect()
def init_db():
    cur = DB.cursor()
    # products for Gold (persisted optionally) ; if using sheet, we'll sync into this table
    cur.execute("""CREATE TABLE IF NOT EXISTS products (
        sku TEXT PRIMARY KEY,
        category TEXT,
        name TEXT,
        price REAL,
        stock INTEGER DEFAULT -1,
        is_available INTEGER DEFAULT 1
    )""")
    # orders
    cur.execute("""CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id TEXT,
        contact_phone TEXT,
        contact_name TEXT,
        address_text TEXT,
        location_lat REAL,
        location_lon REAL,
        items_json TEXT,
        total REAL,
        status TEXT,
        created_at TEXT
    )""")
    DB.commit()

init_db()

# ---------------- Utilities ----------------
def send_text(chat_id, text, keyboard=None, parse_mode=None):
    if not BOT_TOKEN:
        print("BOT_TOKEN not set, can't send message.")
        return
    payload = {"chat_id": chat_id, "text": text}
    if keyboard:
        payload["reply_markup"] = keyboard
    if parse_mode:
        payload["parse_mode"] = parse_mode
    try:
        requests.post(API_SEND, json=payload, timeout=10)
    except Exception as e:
        print("send_text error:", e)

def now_ts():
    return datetime.utcnow().isoformat()

def safe_float(x, default=0.0):
    try: return float(x)
    except: return default

# normalize and strip emojis for matching
def normalize_text(txt):
    if not txt: return ""
    t = str(txt)
    for emo in ["🧩","🤖","💵","ℹ️","📞","🛟","🗂","✅","❌","🧺","📍","🧹"]:
        t = t.replace(emo, "")
    t = " ".join(t.split()).strip().lower()
    return t

def contains_any(text, needles):
    t = normalize_text(text)
    for n in needles:
        if not n: continue
        if normalize_text(n) in t: return True
    return False

# ---------------- Static text (defaults) ----------------
TEXT = {
 "FA": {
  "welcome": f"✨ به {BRAND_NAME} خوش آمدید ✨\nبرای شروع منو 🗂 را بزنید.",
  "choose": "یک گزینه را انتخاب کنید:",
  "back":"↩️ بازگشت",
  "btn_products":"🛍 محصولات",
  "btn_cart":"🧺 سبد خرید",
  "btn_prices":"💵 قیمت‌ها",
  "btn_about":"ℹ️ درباره ما",
  "btn_send_phone":"📞 ارسال شماره",
  "btn_order":"✅ ثبت سفارش",
  "btn_cancel":"❌ انصراف",
  "need_phone":"برای ثبت سفارش، لطفاً «📞 ارسال شماره» را بزنید.",
  "order_saved":"سفارش شما ثبت شد. شماره سفارش: #{oid}\nمتشکریم.",
  "phone_ok":"شماره شما ثبت شد.",
  "unknown":"متوجه نشدم. از دکمه‌ها استفاده کنید.",
  "catalog_empty":"کالکشن خالی است.",
  "ask_address":"لطفاً آدرس خود را ارسال کنید یا از «ارسال لوکیشن» استفاده کنید."
 },
 "EN": {
  "welcome": f"✨ Welcome to {BRAND_NAME} ✨\nTap Menu 🗂 to start.",
  "choose":"Please choose:",
  "back":"↩️ Back",
  "btn_products":"🛍 Products",
  "btn_cart":"🧺 Cart",
  "btn_prices":"💵 Prices",
  "btn_about":"ℹ️ About",
  "btn_send_phone":"📞 Share phone",
  "btn_order":"✅ Place order",
  "btn_cancel":"❌ Cancel",
  "need_phone":"To place the order, tap “📞 Share phone”.",
  "order_saved":"Your order was saved. Order ID: #{oid}\nThank you.",
  "phone_ok":"Your phone is saved.",
  "unknown":"Sorry, I didn't get that. Use the buttons.",
  "catalog_empty":"Catalog is empty.",
  "ask_address":"Please send your address or use Send Location."
 },
 "AR": {
  "welcome": f"✨ مرحباً بـ {BRAND_NAME} ✨\nاضغط القائمة 🗂 للبدء.",
  "choose":"اختر خياراً:",
  "back":"↩️ رجوع",
  "btn_products":"🛍 المنتجات",
  "btn_cart":"🧺 سلة التسوق",
  "btn_prices":"💵 الأسعار",
  "btn_about":"ℹ️ من نحن",
  "btn_send_phone":"📞 إرسال الرقم",
  "btn_order":"✅ تأكيد الطلب",
  "btn_cancel":"❌ إلغاء",
  "need_phone":"لإتمام الطلب اضغط «📞 إرسال الرقم».",
  "order_saved":"تم حفظ طلبك. رقم الطلب: #{oid}\nشكراً.",
  "phone_ok":"تم حفظ رقمك.",
  "unknown":"لم أفهم. استخدم الأزرار.",
  "catalog_empty":"الكاتالوج فارغ.",
  "ask_address":"الرجاء إرسال العنوان أو استخدام إرسال الموقع."
 }
}

# ENV overrides for welcome/about/prices are supported via get_section below
def get_section(prefix, lang):
    suf = (lang or DEFAULT_LANG).upper()
    for key in [f"{prefix}_{suf}", f"{prefix}_TEXT_{suf}", prefix]:
        v = (os.getenv(key) or "").strip()
        if v: return v
    # default fallback
    return TEXT[lang].get(prefix.lower(), "")

# ---------------- Keyboard builder ----------------
def reply_keyboard_layout(rows):
    # rows: list[list[str|dict]]
    kb_rows = []
    for r in rows:
        row=[]
        for c in r:
            if isinstance(c, dict):
                row.append(c)
            else:
                row.append({"text": str(c)})
        kb_rows.append(row)
    return {"keyboard": kb_rows, "resize_keyboard": True}

def menu_keyboard(lang):
    L = TEXT[lang]
    rows = []
    if SHOW_PRODUCTS:
        rows.append([L["btn_products"], L["btn_cart"]])
    else:
        rows.append([L["btn_cart"]])
    rows.append([L["btn_prices"], L["btn_about"]])
    rows.append([{"text": L["btn_send_phone"], "request_contact": True}])
    rows.append([L["back"]])
    return reply_keyboard_layout(rows)

# ---------------- Catalog: in-memory and DB sync ----------------
CATALOG = []  # list of dicts {sku,category,name,price,stock,is_available}

def load_products_from_env(lang):
    raw = os.getenv(f"PRODUCTS_{lang}", "") or os.getenv("PRODUCTS", "") or ""
    items=[]
    for ln in raw.splitlines():
        ln = ln.strip()
        if not ln: continue
        parts = [p.strip() for p in ln.split("|")]
        if len(parts) == 3:
            sku,name,price = parts
        elif len(parts) == 2:
            name,price = parts; sku = name
        else:
            name = parts[0]; price=""
            sku = name
        items.append({"sku": sku, "category":"Uncategorized", "name":name, "price":safe_float(price), "stock":-1, "is_available":1})
    return items

def sync_catalog_from_sheet():
    if not SHEET_URL:
        raise RuntimeError("SHEET_URL missing")
    r = requests.get(SHEET_URL, timeout=15)
    r.raise_for_status()
    f = io.StringIO(r.text)
    reader = csv.DictReader(f)
    items=[]
    for row in reader:
        # expected keys: sku, category, item_name or name, price, is_available, stock
        sku = (row.get("sku") or row.get("id") or "").strip()
        cat = (row.get("category") or "").strip()
        name = (row.get("item_name") or row.get("name") or "").strip()
        price = safe_float(row.get("price") or row.get("price_usd") or 0)
        avail = str(row.get("is_available") or "1").strip().lower() in ["1","true","yes","available"]
        stock = -1
        try:
            stock = int(row.get("stock")) if row.get("stock") not in (None,"") else -1
        except:
            stock = -1
        if not name:
            continue
        items.append({"sku": sku or name, "category": cat or "Uncategorized", "name": name, "price": price, "stock": stock, "is_available": 1 if avail else 0})
    # persist into DB table products (replace)
    cur = DB.cursor()
    for it in items:
        cur.execute("""INSERT OR REPLACE INTO products (sku,category,name,price,stock,is_available) VALUES (?,?,?,?,?,?)""",
                    (it["sku"], it["category"], it["name"], it["price"], it["stock"] if it["stock"]>=0 else -1, it["is_available"]))
    DB.commit()
    # Also update in-memory CATALOG from DB
    load_catalog_from_db()
    return len(items)

def load_catalog_from_db():
    cur = DB.cursor()
    cur.execute("SELECT sku,category,name,price,stock,is_available FROM products WHERE is_available=1")
    rows = cur.fetchall()
    items=[]
    for r in rows:
        items.append({"sku": r["sku"], "category": r["category"], "name": r["name"], "price": r["price"], "stock": r["stock"], "is_available": r["is_available"]})
    global CATALOG
    CATALOG = items
    return len(items)

def ensure_catalog():
    # load from DB or ENV fallback
    if PLAN in ["silver","gold","diamond"] and SHEET_URL:
        try:
            # try to load from DB first; if empty, sync
            n = load_catalog_from_db()
            if n == 0:
                sync_catalog_from_sheet()
                n = load_catalog_from_db()
            return n
        except Exception as e:
            print("sync error:", e)
            # fallback to ENV
    # fallback to ENV
    items = load_products_from_env(DEFAULT_LANG)
    global CATALOG
    CATALOG = items
    return len(CATALOG)

# ---------------- Cart & Flow ----------------
CARTS = {}  # chat_id -> list of items {sku,name,price,qty}
LEAD_CONTEXT = {}  # chat_id -> flow state e.g. "cart_order"

def cart_add(chat_id, item):
    lst = CARTS.get(str(chat_id), [])
    for it in lst:
        if it["sku"] == item["sku"]:
            it["qty"] += item.get("qty",1)
            CARTS[str(chat_id)] = lst; return
    cp = {"sku": item["sku"], "name": item["name"], "price": item["price"], "qty": item.get("qty",1)}
    lst.append(cp); CARTS[str(chat_id)] = lst

def cart_get(chat_id):
    return CARTS.get(str(chat_id), [])

def cart_clear(chat_id):
    CARTS.pop(str(chat_id), None)

def cart_total(chat_id):
    total=0.0
    for it in cart_get(chat_id):
        total += safe_float(it.get("price",0)) * it.get("qty",1)
    return total

def build_cart_message(lang, chat_id):
    items = cart_get(chat_id)
    if not items:
        return (TEXT[lang]["catalog_empty"], reply_keyboard_layout([[TEXT[lang]["back"]]]))
    lines=[]
    for i,it in enumerate(items, start=1):
        lines.append(f"{i}) {it['name']} x{it['qty']} — ${safe_float(it['price']):.2f}")
    lines.append(f"\nTotal: ${cart_total(chat_id):.2f}")
    kb = reply_keyboard_layout([[TEXT[lang]["btn_order"], "🧹 Empty cart"], [TEXT[lang]["back"]]])
    return ("\n".join(lines), kb)

# ---------------- Orders ----------------
def create_order_db(chat_id, contact_phone, contact_name, address_text, location_lat, location_lon, items, total):
    cur = DB.cursor()
    cur.execute("""INSERT INTO orders (chat_id,contact_phone,contact_name,address_text,location_lat,location_lon,items_json,total,status,created_at)
                VALUES (?,?,?,?,?,?,?,?,?)""", (str(chat_id), contact_phone or "", contact_name or "", address_text or "", location_lat or None, location_lon or None, json.dumps(items), total, "new", now_ts()))
    DB.commit()
    return cur.lastrowid

def report_summary(period="daily"):
    cur = DB.cursor()
    if period=="daily":
        since = datetime.utcnow() - timedelta(days=1)
    else:
        since = datetime.utcnow() - timedelta(days=30)
    cur.execute("SELECT COUNT(*) as cnt, SUM(total) as revenue FROM orders WHERE created_at > ?", (since.isoformat(),))
    r = cur.fetchone()
    return {"orders": r["cnt"] or 0, "revenue": float(r["revenue"] or 0.0)}

# ---------------- Support text builder ----------------
def build_support_text(lang):
    L = {
        "FA":{"title":"پشتیبانی 🛟","tg":"تلگرام","mail":"ایمیل","wa":"واتساپ","ig":"اینستاگرام"},
        "EN":{"title":"Support 🛟","tg":"Telegram","mail":"Email","wa":"WhatsApp","ig":"Instagram"},
        "AR":{"title":"الدعم 🛟","tg":"تيليجرام","mail":"البريد","wa":"واتساب","ig":"إنستغرام"},
    }[lang]
    lines=[L["title"]]
    if SUPPORT_TG:
        handle = SUPPORT_TG.lstrip("@")
        lines.append(f"{L['tg']}: @{handle} (https://t.me/{handle})")
    if SUPPORT_EMAIL:
        lines.append(f"{L['mail']}: {SUPPORT_EMAIL}")
    if SUPPORT_WHATSAPP:
        lines.append(f"{L['wa']}: {SUPPORT_WHATSAPP}")
    if SUPPORT_INSTAGRAM:
        lines.append(f"{L['ig']}: @{SUPPORT_INSTAGRAM.replace('https://instagram.com/','').lstrip('@')}")
    return "\n".join(lines)

# ---------------- Handlers (core) ----------------
@app.get("/health")
def health():
    return jsonify({"ok": True, "plan": PLAN})

@app.route("/telegram", methods=["GET","POST"])
@app.route("/webhook/telegram", methods=["GET","POST"])
def webhook():
    if request.method == "GET":
        return "OK", 200
    if WEBHOOK_SECRET:
        secret_hdr = request.headers.get("X-Telegram-Bot-Api-Secret-Token","")
        if secret_hdr != WEBHOOK_SECRET:
            return "unauthorized", 401
    update = request.get_json(silent=True) or {}
    try:
        return jsonify(process_update(update))
    except Exception as e:
        print("handler exception:", e)
        # best-effort notify user
        chat_id = ((update.get("message") or {}).get("chat") or {}).get("id")
        if chat_id:
            send_text(chat_id, "⚠️ Temporary error. Try again.")
        return jsonify({"ok": True})

def process_update(update):
    msg = update.get("message") or update.get("edited_message") or {}
    chat = msg.get("chat") or {}
    chat_id = chat.get("id")
    text = (msg.get("text") or "") or ""
    contact = msg.get("contact") or {}
    location = msg.get("location") or {}

    if not chat_id:
        return {"ok": True}

    # simple logging for debug
    print("[DBG]", {"chat_id":chat_id, "text": text[:200], "contact": bool(contact), "loc": bool(location)})

    # determine language for user: fallback to DEFAULT_LANG
    lang = get_user_lang = lambda cid: (DEFAULT_LANG)  # quick - could be extended to per-user lang
    user_lang = get_user_lang(chat_id)
    LANG = user_lang if user_lang in TEXT else DEFAULT_LANG

    # CONTACT flow (request_contact)
    if contact and contact.get("phone_number"):
        set_user_phone(chat_id, contact.get("phone_number"))
        send_text(chat_id, TEXT[LANG]["phone_ok"], keyboard=menu_keyboard(LANG))
        # If user was in cart_order flow, ask for address next
        if LEAD_CONTEXT.get(str(chat_id)) == "cart_order":
            send_text(chat_id, TEXT[LANG]["ask_address"], keyboard=reply_keyboard_layout([[{"text":"📍 Send Location","request_location": True}], [TEXT[LANG]["back"]]]))
        return {"ok": True}

    # LOCATION flow (request_location)
    if location:
        # finalize if in cart_order
        if LEAD_CONTEXT.get(str(chat_id)) == "cart_order":
            items = cart_get(chat_id)
            if not items:
                send_text(chat_id, "Cart empty", keyboard=menu_keyboard(LANG)); return {"ok": True}
            total = cart_total(chat_id)
            oid = create_order_db(chat_id, get_user_phone(chat_id), chat.get("first_name") or "", "", location.get("latitude"), location.get("longitude"), items, total)
            # admin notify
            admin_msg = f"NEW ORDER #{oid}\nUser: {chat.get('first_name','-')} ({chat_id})\nPhone: {get_user_phone(chat_id) or '-'}\nLocation: {location.get('latitude')},{location.get('longitude')}\nItems:\n"
            for it in items:
                admin_msg += f"- {it['name']} x{it['qty']} — ${safe_float(it['price'])*it['qty']:.2f}\n"
            admin_msg += f"Total: ${total:.2f}"
            for admin in ADMINS:
                try: requests.post(API_SEND, json={"chat_id": int(admin), "text": admin_msg}, timeout=10)
                except: pass
            cart_clear(chat_id); LEAD_CONTEXT.pop(str(chat_id), None)
            send_text(chat_id, TEXT[LANG]["order_saved"].format(oid=oid), keyboard=menu_keyboard(LANG))
            return {"ok": True}
        # otherwise ignore
        return {"ok": True}

    # text handlers
    tnorm = normalize_text(text)

    # /start
    if text.strip().startswith("/start"):
        send_text(chat_id, os.getenv(f"WELCOME_{LANG}") or TEXT[LANG]["welcome"], keyboard=menu_keyboard(LANG))
        return {"ok": True}

    # admin commands
    if tnorm.startswith("/sync") and str(chat_id) in ADMINS:
        try:
            n = sync_catalog_from_sheet()
            send_text(chat_id, f"Catalog synced: {n} items.", keyboard=menu_keyboard(LANG))
        except Exception as e:
            send_text(chat_id, f"Sync failed: {e}", keyboard=menu_keyboard(LANG))
        return {"ok": True}

    if tnorm.startswith("/report") and str(chat_id) in ADMINS:
        # /report daily|monthly
        parts = tnorm.split()
        period = parts[1] if len(parts)>1 else "daily"
        rep = report_summary(period=period)
        send_text(chat_id, f"Report ({period}): Orders {rep['orders']} | Revenue ${rep['revenue']:.2f}", keyboard=menu_keyboard(LANG))
        return {"ok": True}

    # menu
    if contains_any(text, [TEXT[LANG]["btn_products"], "محصول", "products", "المنتجات"]):
        n = ensure_catalog()
        if n==0:
            send_text(chat_id, TEXT[LANG]["catalog_empty"], keyboard=menu_keyboard(LANG)); return {"ok": True}
        # show categories
        cats = sorted(list({it.get("category") or "Uncategorized" for it in CATALOG}))
        rows = [[c] for c in cats[:10]]
        rows.append([TEXT[LANG]["back"]])
        send_text(chat_id, "Categories:", keyboard=reply_keyboard_layout(rows))
        LEAD_CONTEXT.pop(str(chat_id), None)
        return {"ok": True}

    # If user clicked category
    # find best matching category
    cats = sorted(list({it.get("category") or "Uncategorized" for it in CATALOG}))
    for c in cats:
        if normalize_text(c) == tnorm or normalize_text(c) in tnorm or tnorm in normalize_text(c):
            # show products in category
            prods = [p for p in CATALOG if p.get("category")==c and p.get("is_available",1)]
            if not prods:
                send_text(chat_id, "No products in this category.", keyboard=menu_keyboard(LANG)); return {"ok": True}
            rows = []
            for i,p in enumerate(prods[:10], start=1):
                rows.append([f"{i}) {p.get('name')} — ${safe_float(p.get('price')):.2f}"])
            rows.append([TEXT[LANG]["back"]])
            send_text(chat_id, f"Products in {c}:", keyboard=reply_keyboard_layout(rows))
            LEAD_CONTEXT[str(chat_id)] = json.dumps({"category": c})
            return {"ok": True}

    # product selection by number when inside a category
    m = re.match(r"^\s*(\d+)\s*\)?", text)
    if m and LEAD_CONTEXT.get(str(chat_id)):
        ctx = json.loads(LEAD_CONTEXT.get(str(chat_id)) or "{}")
        cat = ctx.get("category")
        prods = [p for p in CATALOG if p.get("category")==cat and p.get("is_available",1)]
        idx = int(m.group(1)) - 1
        if 0 <= idx < len(prods):
            p = prods[idx]
            # if product out of stock (stock >=0 indicates tracked)
            if PLAN in ["gold","diamond"] and p.get("stock", -1) >= 0 and p.get("stock",0) <= 0:
                send_text(chat_id, "Sorry, out of stock.", keyboard=menu_keyboard(LANG)); return {"ok": True}
            cart_add(chat_id, {"sku": p.get("sku"), "name": p.get("name"), "price": p.get("price"), "qty": 1})
            send_text(chat_id, f"Added to cart: {p.get('name')} — ${safe_float(p.get('price')):.2f}", keyboard=menu_keyboard(LANG))
            return {"ok": True}

    # view cart
    if contains_any(text, [TEXT[LANG]["btn_cart"], "سبد", "cart", "🧺"]):
        msg,kb = build_cart_message(LANG, chat_id)
        send_text(chat_id, msg, keyboard=kb); return {"ok": True}

    # empty cart (simple trigger)
    if contains_any(text, ["empty cart","خالی"]):
        cart_clear(chat_id); send_text(chat_id, "Cart cleared.", keyboard=menu_keyboard(LANG)); return {"ok": True}

    # checkout / place order
    if text == TEXT[LANG]["btn_order"] or contains_any(text, ["ثبت سفارش","place order","confirm order"]):
        items = cart_get(chat_id)
        if not items:
            send_text(chat_id, "Your cart is empty.", keyboard=menu_keyboard(LANG)); return {"ok": True}
        # ensure contact
        phone = get_user_phone(chat_id)
        if not phone:
            LEAD_CONTEXT[str(chat_id)] = "cart_order"
            send_text(chat_id, TEXT[LANG]["need_phone"], keyboard=reply_keyboard_layout([[{"text":TEXT[LANG]["btn_send_phone"], "request_contact":True}], [TEXT[LANG]["back"]]]))
            return {"ok": True}
        # ask for address
        LEAD_CONTEXT[str(chat_id)] = "cart_order"
        send_text(chat_id, TEXT[LANG]["ask_address"], keyboard=reply_keyboard_layout([[{"text":"📍 Send Location","request_location": True}], [TEXT[LANG]["back"]]]))
        return {"ok": True}

    # when user sends plain address while in cart_order
    if LEAD_CONTEXT.get(str(chat_id)) == "cart_order" and text and not contact and not location:
        items = cart_get(chat_id)
        if not items:
            send_text(chat_id, "Cart empty.", keyboard=menu_keyboard(LANG)); return {"ok": True}
        total = cart_total(chat_id)
        oid = create_order_db(chat_id, get_user_phone(chat_id), chat.get("first_name") or "", text, None, None, items, total)
        # notify admins
        admin_msg = f"NEW ORDER #{oid}\nUser: {chat.get('first_name','-')} ({chat_id})\nPhone: {get_user_phone(chat_id) or '-'}\nAddress: {text}\nItems:\n"
        for it in items:
            admin_msg += f"- {it['name']} x{it['qty']} — ${safe_float(it['price'])*it['qty']:.2f}\n"
        admin_msg += f"Total: ${total:.2f}"
        for admin in ADMINS:
            try: requests.post(API_SEND, json={"chat_id": int(admin), "text": admin_msg}, timeout=10)
            except: pass
        cart_clear(chat_id); LEAD_CONTEXT.pop(str(chat_id), None)
        send_text(chat_id, TEXT[LANG]["order_saved"].format(oid=oid), keyboard=menu_keyboard(LANG))
        return {"ok": True}

    # prices / about
    if contains_any(text, [TEXT[LANG]["btn_prices"], "price","قیمت","الأسعار"]):
        send_text(chat_id, get_section("PRICES", LANG) or "—", keyboard=menu_keyboard(LANG)); return {"ok": True}
    if contains_any(text, [TEXT[LANG]["btn_about"], "about","درباره","من نحن"]):
        send_text(chat_id, get_section("ABOUT", LANG) or "—", keyboard=menu_keyboard(LANG)); return {"ok": True}

    # support
    if contains_any(text, ["پشتیبانی","support","الدعم"]):
        send_text(chat_id, build_support_text(LANG), keyboard=menu_keyboard(LANG)); return {"ok": True}

    # back
    if contains_any(text, ["back","بازگشت","رجوع"]):
        send_text(chat_id, TEXT[LANG]["choose"], keyboard=menu_keyboard(LANG)); return {"ok": True}

    # default
    send_text(chat_id, TEXT[LANG]["unknown"], keyboard=menu_keyboard(LANG))
    return {"ok": True}

# ---------------- Simple per-user phone persistence (very small) ----------------
# For production you might use dedicated user table; here minimal local storage via SQLite orders table and a small runtime map
_USER_PHONES = {}
def set_user_phone(chat_id, phone):
    _USER_PHONES[str(chat_id)] = phone

def get_user_phone(chat_id):
    return _USER_PHONES.get(str(chat_id))

# ---------------- Run ----------------
if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
