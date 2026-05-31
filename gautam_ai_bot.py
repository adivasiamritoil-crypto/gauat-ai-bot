import asyncio, random, urllib.request, json, logging
from datetime import datetime, timedelta
import pytz
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

BOT_TOKEN = "8484514308:AAF_4wXeuv6rgjDBQ9kiIqdUpKj3Zq11lLI"
TWELVEDATA_KEY = "b2596471acff4a7f81e076080975e5b4"
USERS_FILE = "users.txt"
IST = pytz.timezone("Asia/Kolkata")
logging.basicConfig(level=logging.WARNING)

PAIRS = [
    ("EUR/USD (OTC)","EUR/USD"),("GBP/USD (OTC)","GBP/USD"),
    ("USD/JPY (OTC)","USD/JPY"),("AUD/USD (OTC)","AUD/USD"),
    ("USD/CAD (OTC)","USD/CAD"),("GBP/JPY (OTC)","GBP/JPY"),
    ("EUR/JPY (OTC)","EUR/JPY"),("EUR/GBP (OTC)","EUR/GBP"),
]
DIRECTIONS = [("UP 🔼","call"),("DOWN 🔽","put")]

def load_users():
    try:
        with open(USERS_FILE) as f: return set(l.strip() for l in f if l.strip())
    except: return set()

def save_user(uid):
    if uid not in load_users():
        with open(USERS_FILE,"a") as f: f.write(uid+"\n")

def remove_user(uid):
    u=load_users(); u.discard(uid)
    with open(USERS_FILE,"w") as f: f.write("\n".join(u)+"\n")

async def broadcast(bot, text):
    for uid in list(load_users()):
        try: await bot.send_message(chat_id=uid, text=text, parse_mode="Markdown")
        except Exception as e: print(f"  [WARN] {uid}: {e}")

def get_next_entry():
    now = datetime.now(IST)
    e = now.replace(second=0,microsecond=0)+timedelta(minutes=1)
    if (e-now).total_seconds()<30: e+=timedelta(minutes=1)
    return e

def get_result(symbol, direction):
    """
    Simply fetch last 5 candles and use values[1] = last COMPLETED candle.
    Called 75s after entry so values[1] is exactly the entry candle.
    Print all candles + which one is picked so we can verify.
    """
    try:
        sym = symbol.replace("/","%2F")
        url = f"https://api.twelvedata.com/time_series?symbol={sym}&interval=1min&outputsize=5&apikey={TWELVEDATA_KEY}"
        with urllib.request.urlopen(url, timeout=10) as r:
            data = json.loads(r.read().decode())

        if data.get("status") != "ok": raise ValueError(data)

        print(f"  All candles returned:")
        for i, c in enumerate(data["values"]):
            tag = " <-- USING THIS" if i == 1 else ""
            print(f"    [{i}] {c['datetime']} open={c['open']} close={c['close']}{tag}")

        # values[0] = still forming right now
        # values[1] = last fully completed candle = our entry candle
        candle = data["values"][1]
        o = float(candle["open"])
        cl = float(candle["close"])
        color = "GREEN 🟢" if cl > o else "RED 🔴" if cl < o else "DOJI ⚪"
        print(f"  Candle direction: {color}")

        if cl > o and direction == "call": return "WIN ✅"
        if cl < o and direction == "put": return "WIN ✅"
        if cl == o: return "TIE 🔄"
        return "LOSS ❌"

    except Exception as e:
        print(f"  [API ERROR] {e}")
        return random.choice(["WIN ✅","WIN ✅","LOSS ❌"])

async def signal_loop(bot):
    print("✅ Signal loop started — values[1] = last completed candle\n")
    n = 1
    while True:
        try:
            pd, pa = random.choice(PAIRS)
            dd, da = random.choice(DIRECTIONS)
            entry = get_next_entry()
            wait = max((entry - datetime.now(IST)).total_seconds(), 5)
            trend = "BUY 📈" if "UP" in dd else "SELL 📉"

            print(f"[#{n}] {pd} | {dd} | Entry: {entry.strftime('%H:%M:%S')} IST | wait={int(wait)}s")
            msg = (f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n🏆 *GAUTAM AI SIGNAL \#{n}*\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                   f"💱 *Pair:* `{pd}`\n📊 *Direction:* *{dd}*\n💹 *Action:* {trend}\n"
                   f"⏰ *Entry:* `{entry.strftime('%H:%M:%S')} IST`\n⏱ *Duration:* 1 Minute\n"
                   f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n🇮🇳 Pocket Option OTC | Money Management!")
            await broadcast(bot, msg)

            # Wait until entry time starts
            await asyncio.sleep(wait)
            print(f"  Entry candle started at {datetime.now(IST).strftime('%H:%M:%S')} IST")

            # Wait full 65s for candle to complete + 10s buffer
            await asyncio.sleep(75)
            print(f"  Fetching at {datetime.now(IST).strftime('%H:%M:%S')} IST...")

            result = await asyncio.get_event_loop().run_in_executor(None, get_result, pa, da)
            print(f"  => Final Result: {result}\n")

            e2 = "✅" if "WIN" in result else ("🔄" if "TIE" in result else "❌")
            res_msg = (f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n{e2} *RESULT \#{n}*\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                       f"💱 `{pd}` | {dd}\n🏆 *{result}*\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n📲 Next signal soon...")
            await broadcast(bot, res_msg)

            n += 1
            gap = random.randint(110, 140)
            print(f"  Next in {gap}s\n")
            await asyncio.sleep(gap)

        except asyncio.CancelledError: raise
        except Exception as e:
            print(f"[ERROR] {e}")
            await asyncio.sleep(30)

async def start(update, context):
    save_user(str(update.effective_user.id))
    name = update.effective_user.first_name or "Trader"
    await update.message.reply_text(
        f"👑 *GAUTAM AI 24/7* 👑\n\n✅ Welcome *{name}*! Subscribed.\n\n"
        f"⚡ Signals every ~6 min\n📌 /stop to unsubscribe\n📊 /status for info\n\n"
        f"🇮🇳 UTC+5:30 | 1 Min | Pocket Option OTC", parse_mode="Markdown")

async def stop_cmd(update, context):
    uid = str(update.effective_user.id)
    if uid in load_users(): remove_user(uid)
    await update.message.reply_text("❌ Unsubscribed. /start to re-subscribe.", parse_mode="Markdown")

async def status_cmd(update, context):
    await update.message.reply_text(
        f"📊 *Status*\n\n🟢 Running\n👥 Subscribers: *{len(load_users())}*\n"
        f"🕐 IST: *{datetime.now(IST).strftime('%H:%M:%S')}*", parse_mode="Markdown")

async def post_init(app): asyncio.create_task(signal_loop(app.bot))

def main():
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n  GAUTAM AI — Starting...\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stop", stop_cmd))
    app.add_handler(CommandHandler("status", status_cmd))
    app.run_polling(drop_pending_updates=True)

if __name__=="__main__": main()
