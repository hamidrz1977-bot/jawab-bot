# storage/db.py
import os
import sqlite3

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DB = os.path.join(BASE_DIR, "data", "jawab.sqlite3")
DB_PATH = os.environ.get("DB_PATH", DEFAULT_DB)
DEFAULT_LANG = (os.environ.get("DEFAULT_LANG") or "FA").upper()

def _conn():
    return sqlite3.connect(DB_PATH)

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with _conn() as c:
        # users
        c.execute("""
        CREATE TABLE IF NOT EXISTS users(
            chat_id     INTEGER PRIMARY KEY,
            name        TEXT,
            lang        TEXT DEFAULT 'FA',
            source      TEXT,
            phone       TEXT,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        # messages
        c.execute("""
        CREATE TABLE IF NOT EXISTS messages(
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER,
            direction TEXT,
            text    TEXT,
            ts      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        # orders
        c.execute("""
        CREATE TABLE IF NOT EXISTS orders(
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER,
            item    TEXT,
            qty     INTEGER DEFAULT 1,
            price   TEXT,
            status  TEXT DEFAULT 'new',
            ts      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        c.execute("CREATE INDEX IF NOT EXISTS idx_messages_chat_ts ON messages(chat_id, ts)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_users_lang ON users(lang)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_orders_chat_ts ON orders(chat_id, ts)")

        # ستون های قدیمی را در صورت نبود اضافه کن
        cols = [r[1] for r in c.execute("PRAGMA table_info(users)").fetchall()]
        if "source" not in cols:
            c.execute("ALTER TABLE users ADD COLUMN source TEXT")
        if "phone" not in cols:
            c.execute("ALTER TABLE users ADD COLUMN phone TEXT")

# ---- users
def upsert_user(chat_id:int, name:str|None):
    with _conn() as c:
        c.execute("""
        INSERT INTO users(chat_id, name) VALUES(?,?)
        ON CONFLICT(chat_id) DO UPDATE SET name=excluded.name
        """, (chat_id, name or ""))

def get_user_lang(chat_id:int)->str:
    with _conn() as c:
        row = c.execute("SELECT lang FROM users WHERE chat_id=?", (chat_id,)).fetchone()
    return row[0] if row and row[0] else DEFAULT_LANG

def set_user_lang(chat_id:int, lang:str):
    with _conn() as c:
        c.execute("""
        INSERT INTO users(chat_id, lang) VALUES(?,?)
        ON CONFLICT(chat_id) DO UPDATE SET lang=excluded.lang
        """, (chat_id, (lang or DEFAULT_LANG).upper()))

def set_user_source(chat_id:int, source:str):
    if not source: return
    with _conn() as c:
        c.execute("""
        INSERT INTO users(chat_id, source) VALUES(?,?)
        ON CONFLICT(chat_id) DO UPDATE SET source=excluded.source
        """, (chat_id, source[:64]))

def set_user_phone(chat_id:int, phone:str):
    if not phone: return
    with _conn() as c:
        c.execute("UPDATE users SET phone=? WHERE chat_id=?", (phone, chat_id))

def get_user_phone(chat_id:int)->str|None:
    with _conn() as c:
        row = c.execute("SELECT phone FROM users WHERE chat_id=?", (chat_id,)).fetchone()
    return row[0] if row and row[0] else None

# ---- messages
def log_message(chat_id:int, text:str, direction:str):
    with _conn() as c:
        c.execute("INSERT INTO messages(chat_id, text, direction) VALUES(?,?,?)",
                  (chat_id, text or "", direction))

def get_stats()->dict:
    with _conn() as c:
        users_total = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        msgs_total  = c.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
        msgs_24h    = c.execute("SELECT COUNT(*) FROM messages WHERE ts >= datetime('now','-1 day')").fetchone()[0]
        langs       = c.execute("SELECT lang, COUNT(*) FROM users GROUP BY lang").fetchall()
    return {"users_total":users_total,"messages_total":msgs_total,"messages_24h":msgs_24h,"langs":{k or "FA":v for k,v in langs}}

def list_user_ids(limit:int=200)->list[int]:
    with _conn() as c:
        rows = c.execute("SELECT chat_id FROM users ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
    return [r[0] for r in rows]

# ---- orders
def create_order(chat_id:int, item:str, qty:int=1, price:str="")->int:
    with _conn() as c:
        cur = c.execute("INSERT INTO orders(chat_id,item,qty,price) VALUES(?,?,?,?)",
                        (chat_id, item, qty, price))
        return cur.lastrowid

init_db()
