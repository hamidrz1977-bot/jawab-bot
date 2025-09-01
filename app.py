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
    log_message, get_stats, list_user_ids, set_user_source
)
init_db()

app = Flask(__name__)

# ---------- متن‌ها ----------
TEXT = {
    "FA": {
        "welcome": f"سلام! من {BRAND_NAME} هستم 👋\nگزینه‌ها: 1) منو 🗂  2) پشتیبانی 🛟  3) زبان 🌐",
        "menu": "📋 منو:\n- قیمت‌ها\n- دربارهٔ ما\n- پشتیبانی",
        "support": "پشتیبانی 🛟\nبرای گفتگو پیام بده: @welluroo_support" + (f"\nواتساپ: {SUPPORT_WHATSAPP}" if SUPPORT_WHATSAPP else ""),
        "language": "لطفاً زبان را انتخاب کنید: FA / EN / AR",
        "set_ok": "زبان تنظیم شد.",
        "unknown": "متوجه نشدم. از دکمه‌ها استفاده کن یا بنویس: /help",
        "catalog_empty": "کاتالوگ خالی است. اگر مدیر هستی، /sync را بزن.",
        "sync_ok": "کاتالوگ به‌روزرسانی شد: {n} قلم.",
        "sync_fail": "نشد! آدرس Sheet یا فرمت CSV را چک کن.",
        "no_perm": "دسترسی نداری.",
        "broadcast_ok": "ارسال شد به {n} کاربر.",
    },
    "EN": {
        "welcome": f"Hello! I’m {BRAND_NAME} 👋\nOptions: 1) Menu 🗂  2) Support 🛟  3) Language 🌐",
        "menu": "📋 Menu:\n- Prices\n- About us\n- Support",
        "support": "Support 🛟\nDM: @welluroo_support" + (f"\nWhatsApp: {SUPPORT_WHATSAPP}" if SUPPORT_WHATSAPP else ""),
        "language": "Choose a language: FA / EN / AR",
        "set_ok": "Language set.",
        "unknown": "Sorry, I didn’t get that. Use the buttons or type /help"
