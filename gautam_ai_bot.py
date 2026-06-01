import asyncio, random, urllib.request, json, logging
from datetime import datetime, timedelta
import pytz
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

BOT_TOKEN = "8484514308:AAFHcHzvYkPNimCYMXavRKd-MqhCb0hsTfo"
TWELVEDATA_KEY = "b2596471acff4a7f81e076080975e5b4"
ADMIN_ID = "5661696123"  # Replace with your Telegram user ID
CHANNEL_ID = -1003934319946
USERS_FILE = "users.txt"
PAIRS_FILE = "pairs.txt"
IST = pytz.timezone("Asia/Kolkata")
logging.basicConfig(level=logging.WARNING)

DEFAULT_PAIRS = [
    ("EUR/USD (OTC)", "EUR/USD"),
    ("GBP/USD (OTC)", "GBP/USD"),
    ("USD/JPY (OTC)", "USD/JPY"),
    ("AUD/USD (OTC)", "AUD/USD"),
    ("USD/CAD (OTC)", "USD/CAD"),
    ("EUR/GBP (OTC)", "EUR/GBP"),
]

PAIR_MAP = {
    "EURUSD": ("EUR/USD (OTC)", "EUR/USD"),
    "GBPUSD": ("GBP/USD (OTC)", "GBP/USD"),
    "USDJPY": ("USD/JPY (OTC)", "USD/JPY"),
    "AUDUSD": ("AUD/USD (OTC)", "AUD/USD"),
    "USDCAD": ("USD/CAD (OTC)", "USD/CAD"),
    "EURGBP": ("EUR/GBP (OTC)", "EUR/GBP"),
    "GBPJPY": ("GBP/JPY (OTC)", "GBP/JPY"),
    "EURJPY": ("EUR/JPY (OTC)", "EUR/JPY"),
    "AUDJPY": ("AUD/JPY (OTC)", "AUD/JPY"),
    "NZDUSD": ("NZD/USD (OTC)", "NZD/USD"),
    "USDCHF": ("USD/CHF (OTC)", "USD/CHF"),
    "EURCAD": ("EUR/CAD (OTC)", "EUR/CAD"),
}

DIRECTIONS = [("UP 🔝", "call"), ("DOWN 🔻", "put")]

# ── USER MANAGEMENT ──────────────────────────────────────────────────────────
def load_users():
    try:
        with open(USERS_FILE) as f:
            return set(l.strip() for l in f if l.strip())
    except:
        return set()

def save_user(uid):
    if uid not in load_users():
        with open(USERS_FILE, "a") as f:
            f.write(uid + "\n")

def remove_user(uid):
    u = load_users()
    u.discard(uid)
    with open(USERS_FILE, "w") as f:
        f.write("\n".join(u) + "\n")

# ── PAIRS MANAGEMENT ─────────────────────────────────────────────────────────
def load_pairs():
    try:
        with open(PAIRS_FILE) as f:
            keys = [l.strip().upper() for l in f if l.strip()]
        pairs = [PAIR_MAP[k] for k in keys if k in PAIR_MAP]
        return pairs if pairs else DEFAULT_PAIRS
    except:
        return DEFAULT_PAIRS

def save_pairs(keys):
    with open(PAIRS_FILE, "w") as f:
        f.write("\n".join(keys) + "\n")

# ── BROADCAST ────────────────────────────────────────────────────────────────
async def broadcast(bot, text):
    # Send to channel
    try:
        await bot.send_message(chat_id=CHANNEL_ID, text=text, parse_mode="Markdown")
    except Exception as e:
        print(f"  [CHANNEL WARN] {e}")
    # Send to individual subscribers
    for uid in list(load_users()):
        try:
            await bot.send_message(chat_id=uid, text=text, parse_mode="Markdown")
        except Exception as e:
            print(f"  [WARN] {uid}: {e}")

# ── TIME ─────────────────────────────────────────────────────────────────────
def get_next_entry():
    now = datetime.now(IST)
    e = now.replace(second=0, microsecond=0) + timedelta(minutes=1)
    if (e - now).total_seconds() < 30:
        e += timedelta(minutes=1)
    return e

# ── CANDLE RESULT ────────────────────────────────────────────────────────────
def get_result(symbol, direction):
    try:
        sym = symbol.replace("/", "%2F")
        url = f"https://api.twelvedata.com/time_series?symbol={sym}&interval=1min&outputsize=5&apikey={TWELVEDATA_KEY}"
        with urllib.request.urlopen(url, timeout=10) as r:
            data = json.loads(r.read().decode())
        if data.get("status") != "ok":
            raise ValueError(data)
        candle = data["values"][1]
        o, cl = float(candle["open"]), float(candle["close"])
        color = "GREEN 🟢" if cl > o else "RED 🔴" if cl < o else "DOJI"
        print(f"  => {color}")
        if cl > o and direction == "call": return "WIN"
        if cl < o and direction == "put": return "WIN"
        if cl == o: return "TIE"
        return "LOSS"
    except Exception as e:
        print(f"  [API ERROR] {e}")
        return "UNAVAILABLE"

# ── MESSAGE BUILDERS ─────────────────────────────────────────────────────────
def build_signal(pair, direction, entry, n):
    trend = "Buy 📈" if "UP" in direction else "Sell 📉"
    return (
        f"👑 *GAUTAM AI 24/7* 👑\n"
        f"🅿️ *POCKET OPTION SIGNAL* 🔵\n"
        f"━━━━━━━━━━━━\n"
        f"📌 *Pair:* *{pair}*\n"
        f"🕐 *Timeframe:* *1 Minute*\n"
        f"🕰 *Entry Time:* *{entry.strftime('%H:%M:%S')}*\n"
        f"📍 *Direction:* *{direction}*\n"
        f"🚦 *Trend:* *{trend}*\n"
        f"━━━━━━━━━━━━\n"
        f"🇮🇳 *All times are in UTC+5:30 (India Standard Time)*\n"
        f"💲 *Follow Proper Money Management.*\n"
        f"⏳ *Always Select 1 Minute time frame.*"
    )

def build_result(result, mtg=False):
    if result == "WIN":
        if mtg:
            return "✅ *1 MTG WIN*"
        return "✅ *WIN*"
    elif result == "TIE":
        return "🔄 *TIE*"
    elif result == "UNAVAILABLE":
        return "⚠️ *Result unavailable*"
    else:
        return "❌ *LOSS*"

# ── SIGNAL LOOP ──────────────────────────────────────────────────────────────
async def signal_loop(bot):
    print("✅ Signal loop started\n")
    n = 1
    while True:
        try:
            pairs = load_pairs()
            pd, pa = random.choice(pairs)
            dd, da = random.choice(DIRECTIONS)
            entry = get_next_entry()
            wait = max((entry - datetime.now(IST)).total_seconds(), 5)

            print(f"[#{n}] {pd} | {dd} | {entry.strftime('%H:%M:%S')} IST | wait={int(wait)}s")
            await broadcast(bot, build_signal(pd, dd, entry, n))
            await asyncio.sleep(wait)

            print(f"  Candle running 75s...")
            await asyncio.sleep(75)

            result = await asyncio.get_event_loop().run_in_executor(None, get_result, pa, da)
            print(f"  Result: {result}")

            if result == "LOSS":
                # ── 1 MTG STEP ──────────────────────────────────────────────
                print(f"  LOSS — Applying 1 MTG, waiting 60s for next candle...")
                await asyncio.sleep(60)
                mtg_result = await asyncio.get_event_loop().run_in_executor(None, get_result, pa, da)
                print(f"  MTG Result: {mtg_result}\n")
                if mtg_result == "WIN":
                    await broadcast(bot, build_result("WIN", mtg=True))
                else:
                    # Both trades lost — send LOSS only (no "MTG LOSS")
                    await broadcast(bot, build_result("LOSS", mtg=False))
            else:
                await broadcast(bot, build_result(result, mtg=False))

            n += 1
            gap = random.randint(110, 140)
            print(f"  Next in {gap}s\n")
            await asyncio.sleep(gap)

        except asyncio.CancelledError:
            raise
        except Exception as e:
            print(f"[ERROR] {e}")
            await asyncio.sleep(30)

# ── ERROR HANDLER ─────────────────────────────────────────────────────────────
async def error_handler(update, context):
    print(f"[BOT ERROR] {context.error}")

# ── COMMANDS ─────────────────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_user(str(update.effective_user.id))
    name = update.effective_user.first_name or "Trader"
    await update.message.reply_text(
        f"👑 *GAUTAM AI 24/7* 👑\n\n"
        f"🅿️ *POCKET OPTION SIGNAL* 🔵\n"
        f"━━━━━━━━━━━━\n"
        f"👋 *Welcome {name}!*\n\n"
        f"✅ *Subscribed to live signals.*\n\n"
        f"⚡ *Signals every ~6 min 24/7*\n\n"
        f"📌 /stop — *Unsubscribe*\n"
        f"📊 /status — *Bot info*\n"
        f"💱 /pairs — *See active pairs*\n"
        f"━━━━━━━━━━━━\n"
        f"⚠️ *RISK WARNING*\n"
        f"*Binary options involve risk.*\n"
        f"*Only trade what you can afford to lose.*\n"
        f"━━━━━━━━━━━━\n"
        f"🇮🇳 *UTC+5:30 IST | 1 Min | Pocket Option OTC*",
        parse_mode="Markdown"
    )

async def stop_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    if uid in load_users():
        remove_user(uid)
    await update.message.reply_text(
        "❌ *Unsubscribed.*\n\nUse /start to re-subscribe.",
        parse_mode="Markdown"
    )

async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pairs = load_pairs()
    await update.message.reply_text(
        f"👑 *GAUTAM AI Status*\n\n"
        f"🟢 *Running 24/7*\n"
        f"👥 *Subscribers:* *{len(load_users())}*\n"
        f"🕐 *IST:* *{datetime.now(IST).strftime('%H:%M:%S')}*\n"
        f"💱 *Active Pairs:* *{len(pairs)}*\n"
        f"📊 *Data:* *Twelve Data API*",
        parse_mode="Markdown"
    )

async def pairs_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pairs = load_pairs()
    pair_list = "\n".join([f"• *{p[0]}*" for p in pairs])
    await update.message.reply_text(
        f"👑 *GAUTAM AI — Active Pairs*\n\n"
        f"{pair_list}\n\n"
        f"_Use /setpairs to change_",
        parse_mode="Markdown"
    )

async def setpairs_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) != ADMIN_ID:
        await update.message.reply_text("⛔ *Admin only.*", parse_mode="Markdown")
        return

    if not context.args:
        available = " ".join(PAIR_MAP.keys())
        await update.message.reply_text(
            f"👑 *Set Active Pairs*\n\n"
            f"Usage: `/setpairs EURUSD GBPUSD USDJPY`\n\n"
            f"*Available pairs:*\n`{available}`",
            parse_mode="Markdown"
        )
        return

    keys = [a.upper() for a in context.args]
    valid = [k for k in keys if k in PAIR_MAP]
    invalid = [k for k in keys if k not in PAIR_MAP]

    if not valid:
        await update.message.reply_text(
            "❌ *No valid pairs found.* Use /setpairs to see available pairs.",
            parse_mode="Markdown"
        )
        return

    save_pairs(valid)
    pair_list = "\n".join([f"✅ *{PAIR_MAP[k][0]}*" for k in valid])
    msg = f"👑 *Pairs Updated!*\n\n{pair_list}"
    if invalid:
        msg += f"\n\n⚠️ *Ignored (invalid):* {', '.join(invalid)}"
    await update.message.reply_text(msg, parse_mode="Markdown")

async def post_init(app):
    asyncio.create_task(signal_loop(app.bot))

# ── MAIN ─────────────────────────────────────────────────────────────────────
def main():
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("  GAUTAM AI 24/7 — Starting...")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stop", stop_cmd))
    app.add_handler(CommandHandler("status", status_cmd))
    app.add_handler(CommandHandler("pairs", pairs_cmd))
    app.add_handler(CommandHandler("setpairs", setpairs_cmd))
    app.add_error_handler(error_handler)
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
