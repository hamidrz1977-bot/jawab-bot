# storage/db.py
import os
import sqlite3

# ---------- تنظیمات مسیر دیتابیس ----------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DB = os.path.join(BASE_DIR, "data", "jawab.sqlite3")
DB_PATH = os.environ.get("DB_PATH", DEFAULT_DB)

# زبان پیش‌فرض از ENV (FA/EN/AR). اگر نبود: FA
DEFAULT_LANG = (os.environ.get("DEFAULT_LANG") or "FA").upper()


# ---------- اتصال ----------
def _conn():
    # اتصال ساده به SQLite
    return sqlite3.connect(DB_PATH)


# ---------- آماده‌سازی دیتابیس ----------
def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with _conn() as c:
        # جدول کاربران (برای نصب‌های تازه، ستون phone را هم از ابتدا داریم)
        c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            chat_id     INTEGER PRIMARY KEY,
            name        TEXT,
            lang        TEXT DEFAULT 'FA',
            source      TEXT,                               -- منبع جذب/دیپ‌لینک (اختیاری)
            phone       TEXT,                               -- شماره تماس کاربر (اختیاری)
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        # جدول پیام‌ها
        c.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id   INTEGER,
            direction TEXT,                                 -- in/out
            text      TEXT,
            ts        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        # اگر دیتابیس قبلاً بوده، ستون‌های جدید را اضافه کن
        cols = [r[1] for r in c.execute("PRAGMA table_info(users)").fetchall()]

        if "source" not in cols:
            c.execute("ALTER TABLE users ADD COLUMN source TEXT")

        if "phone" not in cols:
            c.execute("ALTER TABLE users ADD COLUMN phone TEXT")

        # ایندکس‌ها
        c.execute("CREATE INDEX IF NOT EXISTS idx_messages_chat_ts ON messages(chat_id, ts)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_users_lang ON users(lang)")
        # ایندکس روی phone (بعد از اطمینان از وجود ستون)
        c.execute("CREATE INDEX IF NOT EXISTS idx_users_phone ON users(phone)")


# ---------- عملیات کاربر ----------
def upsert_user(chat_id: int, name: str | None):
    with _conn() as c:
        c.execute("""
        INSERT INTO users (chat_id, name) VALUES (?, ?)
        ON CONFLICT(chat_id) DO UPDATE SET name=excluded.name
        """, (chat_id, name or ""))


def get_user_lang(chat_id: int) -> str:
    with _conn() as c:
        row = c.execute("SELECT lang FROM users WHERE chat_id=?", (chat_id,)).fetchone()
    # اگر هنوز زبان برای کاربر ذخیره نشده باشد، از ENV برمی‌گرداند
    return (row[0] if row and row[0] else DEFAULT_LANG)


def set_user_lang(chat_id: int, lang: str):
    lang = (lang or DEFAULT_LANG).upper()
    with _conn() as c:
        c.execute("""
        INSERT INTO users (chat_id, lang) VALUES (?, ?)
        ON CONFLICT(chat_id) DO UPDATE SET lang=excluded.lang
        """, (chat_id, lang))


def set_user_source(chat_id: int, source: str):
    """برای ذخیرهٔ منبع جذب کاربر (مثلاً ?start=as_bio)"""
    if not source:
        return
    with _conn() as c:
        c.execute("""
        INSERT INTO users (chat_id, source) VALUES (?, ?)
        ON CONFLICT(chat_id) DO UPDATE SET source=excluded.source
        """, (chat_id, (source or "")[:64]))


def set_user_phone(chat_id: int, phone: str):
    """ذخیره/به‌روزرسانی شمارهٔ تماس کاربر"""
    if not phone:
        return
    with _conn() as c:
        c.execute("""
        INSERT INTO users (chat_id, phone) VALUES (?, ?)
        ON CONFLICT(chat_id) DO UPDATE SET phone=excluded.phone
        """, (chat_id, phone.strip()))


def get_user_phone(chat_id: int) -> str | None:
    """(اختیاری) دریافت شمارهٔ کاربر"""
    with _conn() as c:
        row = c.execute("SELECT phone FROM users WHERE chat_id=?", (chat_id,)).fetchone()
    return row[0] if row and row[0] else None


# ---------- لاگ پیام ----------
def log_message(chat_id: int, text: str, direction: str):
    with _conn() as c:
        c.execute(
            "INSERT INTO messages (chat_id, text, direction) VALUES (?,?,?)",
            (chat_id, text or "", direction)
        )


# ---------- آمار ----------
def get_stats() -> dict:
    with _conn() as c:
        users_total = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        msgs_total = c.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
        msgs_24h = c.execute(
            "SELECT COUNT(*) FROM messages WHERE ts >= datetime('now','-1 day')"
        ).fetchone()[0]
        langs = c.execute("SELECT lang, COUNT(*) FROM users GROUP BY lang").fetchall()
    return {
        "users_total": users_total,
        "messages_total": msgs_total,
        "messages_24h": msgs_24h,
        "langs": { (k or "FA"): v for k, v in langs },
    }


def list_user_ids(limit: int = 200) -> list[int]:
    with _conn() as c:
        rows = c.execute(
            "SELECT chat_id FROM users ORDER BY created_at DESC LIMIT ?",
            (limit,)
        ).fetchall()
    return [r[0] for r in rows]


# هنگام import شدن ماژول، دیتابیس را آماده کن
init_db()
