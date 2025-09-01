# storage/db.py
import os, sqlite3

# مسیر مطلق بر اساس ریشه پروژه
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DB = os.path.join(BASE_DIR, "data", "jawab.sqlite3")
DB_PATH = os.environ.get("DB_PATH", DEFAULT_DB)

def _conn():
    return sqlite3.connect(DB_PATH)

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with _conn() as c:
        c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            chat_id INTEGER PRIMARY KEY,
            name TEXT,
            lang TEXT DEFAULT 'FA',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")
        c.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER,
            direction TEXT,
            text TEXT,
            ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")
        c.execute("CREATE INDEX IF NOT EXISTS idx_messages_chat_ts ON messages(chat_id, ts)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_users_lang ON users(lang)")
        c.commit()

def upsert_user(chat_id:int, name:str):
    with _conn() as c:
        c.execute("""
        INSERT INTO users(chat_id, name) VALUES(?,?)
        ON CONFLICT(chat_id) DO UPDATE SET name=excluded.name
        """, (chat_id, name or ""))

def get_user_lang(chat_id:int)->str:
    with _conn() as c:
        row = c.execute("SELECT lang FROM users WHERE chat_id=?", (chat_id,)).fetchone()
    return row[0] if row and row[0] else "FA"  # اگر خواستی پیش‌فرض EN باشد "EN" کن

def set_user_lang(chat_id:int, lang:str):
    with _conn() as c:
        c.execute("""
        INSERT INTO users(chat_id, lang) VALUES(?,?)
        ON CONFLICT(chat_id) DO UPDATE SET lang=excluded.lang
        """, (chat_id, lang))

def log_message(chat_id:int, text:str, direction:str):
    with _conn() as c:
        c.execute("INSERT INTO messages(chat_id, text, direction) VALUES(?,?,?)",
                  (chat_id, text or "", direction))

def get_stats():
    with _conn() as c:
        users_total = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        msgs_total = c.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
        msgs_24h = c.execute("""
            SELECT COUNT(*) FROM messages
            WHERE ts >= datetime('now','-1 day')
        """).fetchone()[0]
        langs = c.execute("""
            SELECT lang, COUNT(*) FROM users GROUP BY lang
        """).fetchall()
    return {
        "users_total": users_total,
        "messages_total": msgs_total,
        "messages_24h": msgs_24h,
        "langs": {k or "FA": v for k,v in langs}
    }

def list_user_ids(limit:int=200):
    with _conn() as c:
        rows = c.execute("SELECT chat_id FROM users ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
    return [r[0] for r in rows]
