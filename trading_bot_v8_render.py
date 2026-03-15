import os
import json
import time
import asyncio
import logging
import psycopg2
from psycopg2 import pool
from psycopg2.extras import DictCursor
import threading
import math
import aiohttp
import websockets
import telebot
from flask import Flask, jsonify, request, abort
import signal
import argparse
from datetime import datetime, timedelta, timezone
from bitkub_async import BitkubAsyncDriver
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table
from rich import print as rprint

# Load .env
load_dotenv()
console = Console()

# --- ARGUMENTS ---
parser = argparse.ArgumentParser(description="TurboDGT Render v8.8")
parser.add_argument("-logFile", "--log-file", help="Path to the log file")
args, unknown = parser.parse_known_args()

# --- LOGGING ---
log_handlers = [logging.StreamHandler()]
if args.log_file:
    log_handlers.append(logging.FileHandler(args.log_file, encoding='utf-8'))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=log_handlers
)
logger = logging.getLogger("TurboDGT-Rich")

# --- SETTINGS & ENV VARS ---
API_KEY = os.environ.get("API_KEY")
API_SECRET = os.environ.get("API_SECRET")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
DATABASE_URL = os.environ.get("DATABASE_URL")

SYMBOLS = ["thb_btc"]
MIN_TRADE_THB = 10 
DEFAULT_GRID_STEP = float(os.environ.get("GRID_STEP_PCT", 0.5)) / 100
BUDGET_UTILIZATION = float(os.environ.get("BUDGET_UTILIZATION_PCT", 0.95))
MAX_AMT_PER_LAYER = float(os.environ.get("MAX_AMOUNT_PER_LAYER", 2000.0))
auto_trade_enabled = True

# --- MATH UTILS ---
def calculate_stats(data):
    n = len(data)
    if n < 5: return 0.0, 0.0, 0.0
    mean = sum(data) / n
    variance = sum((x - mean) ** 2 for x in data) / n
    std_dev = math.sqrt(variance)
    z_score = (data[-1] - mean) / std_dev if std_dev > 0 else 0
    return mean, std_dev, z_score

def print_status_table(states, total_equity):
    table = Table(title="🚀 Turbo DGT Status Report")
    table.add_column("Coin", style="cyan")
    table.add_column("Price", justify="right")
    table.add_column("Layers", justify="center")
    table.add_column("Z-Score", justify="right")
    table.add_column("Profit (%)", justify="right")

    for coin, s in states.items():
        _, _, z = s.get_stats()
        net_pl_pct = 0.0
        if s.layers:
            total_cost = sum(l['price'] * l['amount'] * 1.0025 for l in s.layers)
            total_amt = sum(l['amount'] for l in s.layers)
            avg_cost = total_cost / total_amt if total_amt > 0 else 0
            net_pl_pct = ((s.current_price * 0.9975 / avg_cost) - 1) * 100 if avg_cost > 0 else 0
        
        profit_style = "green" if net_pl_pct >= 0 else "red"
        table.add_row(coin, f"{s.current_price:,.2f}", str(len(s.layers)), f"{z:+.2f}", f"[{profit_style}]{net_pl_pct:+.2f}%[/{profit_style}]")
    
    console.print(table)
    rprint(f"💰 [bold white]Total Equity:[/bold white] [yellow]{total_equity:,.2f} THB[/yellow]\n")

# --- DATABASE ---
class DatabaseManager:
    def __init__(self, db_url):
        self.db_url = db_url
        self.pool = None
        if self.db_url: self._init_pool()

    def _init_pool(self):
        try:
            self.pool = psycopg2.pool.ThreadedConnectionPool(1, 4, self.db_url, sslmode='require', options='-c client_encoding=utf8', client_encoding='utf8')
            logger.info("✅ Database Pool Ready.")
        except Exception as e: logger.error(f"❌ DB Error: {e}")

    def get_conn(self):
        try: return self.pool.getconn() if self.pool else None
        except: return None

    def put_conn(self, conn):
        if self.pool and conn: self.pool.putconn(conn)

    def execute(self, query, params=None, commit=True, fetch=False):
        conn = self.get_conn()
        if not conn: return None
        result = None
        try:
            with conn.cursor(cursor_factory=DictCursor) as cur:
                cur.execute(query, params)
                if fetch: result = cur.fetchall()
                if commit: conn.commit()
        except Exception as e:
            logger.error(f"❌ Query Error: {e}")
            if commit: conn.rollback()
        finally: self.put_conn(conn)
        return result

db = DatabaseManager(DATABASE_URL)

def init_db():
    db.execute('''CREATE TABLE IF NOT EXISTS trades (id SERIAL PRIMARY KEY, coin TEXT, side TEXT, price DOUBLE PRECISION, amount DOUBLE PRECISION, profit DOUBLE PRECISION, ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    db.execute('''CREATE TABLE IF NOT EXISTS daily_snapshots (ts DATE PRIMARY KEY, total_equity DOUBLE PRECISION, today_profit DOUBLE PRECISION, balance_thb DOUBLE PRECISION)''')
    db.execute('''CREATE TABLE IF NOT EXISTS layers (id SERIAL PRIMARY KEY, coin TEXT, price DOUBLE PRECISION, amount DOUBLE PRECISION)''')
    db.execute('''CREATE TABLE IF NOT EXISTS bot_history (coin TEXT PRIMARY KEY, history_json TEXT)''')

def save_snapshot(equity, profit, thb):
    db.execute("INSERT INTO daily_snapshots (ts, total_equity, today_profit, balance_thb) VALUES (CURRENT_DATE, %s, %s, %s) ON CONFLICT (ts) DO UPDATE SET total_equity=EXCLUDED.total_equity, today_profit=EXCLUDED.today_profit, balance_thb=EXCLUDED.balance_thb", (equity, profit, thb))

def save_trade(coin, side, price, amount, profit=0):
    db.execute("INSERT INTO trades (coin, side, price, amount, profit) VALUES (%s, %s, %s, %s, %s)", (coin, side, price, amount, profit))

def update_db_layers(coin, layers):
    db.execute("DELETE FROM layers WHERE coin = %s", (coin,))
    for l in layers: db.execute("INSERT INTO layers (coin, price, amount) VALUES (%s, %s, %s)", (coin, float(l['price']), float(l['amount'])))

def load_db_layers():
    rows = db.execute("SELECT coin, price, amount FROM layers", fetch=True)
    data = {}
    if rows:
        logger.info(f"📊 Found {len(rows)} total records in 'layers' table.")
        for r in rows:
            c = str(r['coin']).strip().upper()
            if c not in data: data[c] = []
            data[c].append({"price": float(r['price']), "amount": float(r['amount'])})
        for c, l in data.items():
            logger.info(f"✅ Loaded {len(l)} layers for {c}")
    else:
        logger.warning("⚠️ No layers found in database.")
    return data

def get_today_profit():
    res = db.execute("SELECT SUM(profit) FROM trades WHERE side='SELL' AND ts::date = CURRENT_DATE", fetch=True)
    return float(res[0][0]) if res and res[0][0] else 0.0

def save_bot_history(coin, history_list):
    db.execute("INSERT INTO bot_history (coin, history_json) VALUES (%s, %s) ON CONFLICT (coin) DO UPDATE SET history_json = EXCLUDED.history_json", (coin, json.dumps(history_list)))

def load_bot_history():
    rows = db.execute("SELECT coin, history_json FROM bot_history", fetch=True)
    return {r['coin']: json.loads(r['history_json']) for r in rows} if rows else {}

# --- STATE ---
class CoinState:
    def __init__(self, coin):
        self.coin, self.layers, self.current_price, self.price_history, self.is_trading = coin, [], 0.0, [], False
    def update_price(self, price):
        self.current_price = price
        self.price_history.append(price)
        if len(self.price_history) > 30: self.price_history.pop(0)
    def get_stats(self): return calculate_stats(self.price_history)
    def get_dynamic_grid_step(self, layer_count=0):
        mean, std, _ = self.get_stats()
        vol = (std / mean) if mean > 0 else DEFAULT_GRID_STEP
        fib = [1.0, 1.382, 1.618, 2.618, 4.236, 6.854]
        return min(max(DEFAULT_GRID_STEP, vol) * fib[min(layer_count, 5)], 0.10)

# --- BOT CORE ---
class TurboDGT:
    def __init__(self):
        self.driver = BitkubAsyncDriver(API_KEY, API_SECRET)
        self.bot = telebot.TeleBot(TELEGRAM_TOKEN)
        self.states = {s.split('_')[1].upper(): CoinState(s.split('_')[1].upper()) for s in SYMBOLS}
        self.running, self.current_balances, self.price_update_count = True, {}, 0
        self.app = Flask(__name__)
        self._setup_flask()
        self._setup_telegram()
        # ตั้ง Webhook ทันทีตอน Init เพื่อฆ่า Polling ทุกตัว
        self._setup_webhook()

    def _setup_webhook(self):
        try:
            render_url = os.getenv("RENDER_EXTERNAL_URL", "https://bitkub-trading-bot-railway.onrender.com")
            webhook_url = f"{render_url}/webhook"
            logger.info(f"🌐 Setting Telegram Webhook to: {webhook_url}")
            self.bot.remove_webhook()
            time.sleep(1)
            result = self.bot.set_webhook(url=webhook_url)
            if result:
                logger.info("✅ Webhook set successfully! Polling is now DEAD.")
            else:
                logger.error("❌ Webhook setup FAILED!")
        except Exception as e:
            logger.error(f"❌ Webhook error: {e}")

    def _setup_flask(self):
        @self.app.route("/")
        def index(): return "⚡ Turbo DGT Rich Active"
        @self.app.route("/health")
        def health(): return jsonify({"status": "healthy", "time": datetime.now().isoformat()}), 200

        @self.app.route("/webhook", methods=['POST'])
        def webhook():
            if request.headers.get('content-type') == 'application/json':
                json_string = request.get_data().decode('utf-8')
                update = telebot.types.Update.de_json(json_string)
                self.bot.process_new_updates([update])
                return ''
            else:
                abort(403)

    def _setup_telegram(self):
        @self.bot.message_handler(commands=['start'])
        def start(m):
            markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
            markup.add('📊 สถานะบอท', '💰 ยอดเงิน', '🟢 เริ่มระบบ', '🔴 หยุดระบบ', '🔥 ขายด่วน')
            self.bot.send_message(m.chat.id, "🚀 *[TURBO DGT v9.5 Render Quant]* พร้อมใช้งาน!", reply_markup=markup, parse_mode="Markdown")

        @self.bot.message_handler(func=lambda m: True)
        def handle(m):
            global auto_trade_enabled
            if m.text == '📊 สถานะบอท':
                try:
                    thb_avail = float(self.current_balances.get("THB", {}).get("available", 0))
                    total_asset_value = sum((float(self.current_balances.get(c,{}).get("available",0)) + float(self.current_balances.get(c,{}).get("reserved",0))) * s.current_price for c,s in self.states.items())
                    total_equity = thb_avail + total_asset_value
                    
                    txt = f"🚀 *[TURBO DGT v9.9 ULTRA-AGGRESSIVE]*\n"
                    # ปรับเป็นเวลาไทย (UTC+7)
                    thai_now = datetime.now(timezone(timedelta(hours=7)))
                    txt += f"📅 {thai_now.strftime('%H:%M:%S')} | 💓 Pulse: `{self.price_update_count}`\n"
                    txt += f"----------------------------\n"
                    
                    unrealized_total = 0.0
                    for coin, s in self.states.items():
                        mean, std, z = s.get_stats()
                        l_count = len(s.layers)
                        
                        # Z-Score Visual
                        z_dots = "⬜" * 5
                        if z < -2: z_dots = "🔴🔴⬜⬜⬜"
                        elif z < -1: z_dots = "🟨⬜⬜⬜⬜"
                        elif z > 2: z_dots = "🟦🟦🟦🟦🟦"
                        elif z > 1: z_dots = "🟦🟦⬜⬜⬜"

                        txt += f"🔴 *{coin}*: `{s.current_price:,.2f}`\n"
                        txt += f"Layer: `{l_count}/∞` | Z: `{z:+.1f}` {z_dots}\n"
                        txt += f"----------------------------\n"
                        txt += f"🎯 *Trading Targets:*\n"

                        if s.layers:
                            total_cost = sum(l['price'] * l['amount'] * 1.0025 for l in s.layers)
                            total_amt = sum(l['amount'] for l in s.layers)
                            avg_buy = total_cost / total_amt
                            current_val = (total_amt * s.current_price * 0.9975)
                            pl_amt = current_val - total_cost
                            unrealized_total += pl_amt
                            
                            # Next Sell Target (1% profit net)
                            next_sell = (avg_buy * 1.01) / 0.9975
                            sell_dist = ((next_sell / s.current_price) - 1) * 100
                            
                            # Next Buy Target (Dynamic Grid)
                            min_p = min(l['price'] for l in s.layers)
                            next_buy = min_p * (1 - s.get_dynamic_grid_step(l_count))
                            buy_dist = ((next_buy / s.current_price) - 1) * 100
                            
                            txt += f"• 🟢 Buy Target:  `{next_buy:,.2f}` ({buy_dist:+.2f}%)\n"
                            txt += f"• 🔴 Sell Target: `{next_sell:,.2f}` ({sell_dist:+.2f}%)\n"
                            txt += f"• 📊 Curr. P/L: `{pl_amt:+.2f} THB`\n"
                        else:
                            txt += f"• 🟢 Next Buy: `{s.current_price:,.2f}` (Entry 1)\n"
                            txt += f"• ⚖️ Status: `Waiting for Entry`\n"
                        
                        txt += f"----------------------------\n"

                    txt += f"💰 Today Profit: `{get_today_profit():,.2f}` THB\n"
                    txt += f"📊 Unrealized P/L: `{unrealized_total:+.2f} THB`\n"
                    txt += f"💵 Total Equity: `{total_equity:,.2f} THB`\n"
                    txt += f"----------------------------\n"
                    txt += f"💡 *Next Step:* ตามระยะ Dynamic Grid"
                    
                    self.bot.send_message(m.chat.id, txt, parse_mode="Markdown")
                except Exception as e:
                    logger.error(f"Status Error: {e}")
                    self.bot.send_message(m.chat.id, "❌ ไม่สามารถดึงข้อมูลสถานะได้ในขณะนี้")
            
            elif m.text == '💰 ยอดเงิน':
                try:
                    import requests as req, hmac, hashlib, json as _json
                    ts = int(req.get("https://api.bitkub.com/api/v3/servertime", timeout=5).json())
                    path = "/api/v3/market/balances"
                    body = {"ts": ts}
                    body_str = _json.dumps(body, separators=(',', ':'))
                    message = f"{ts}POST{path}{body_str}"
                    sig = hmac.new(API_SECRET.encode('utf-8'), message.encode('utf-8'), hashlib.sha256).hexdigest()
                    headers = {
                        "Accept": "application/json",
                        "Content-Type": "application/json",
                        "X-BTK-APIKEY": API_KEY,
                        "X-BTK-TIMESTAMP": str(ts),
                        "X-BTK-SIGN": sig
                    }
                    r = req.post(f"https://api.bitkub.com{path}", headers=headers, data=body_str, timeout=10)
                    res = r.json()
                    if res.get('error') == 0:
                        txt = "💰 *Balance Summary (สด):*\n"
                        result = res.get('result', {})
                        # Bitkub v3 returns dict: {"BTC": {"available": x, "reserved": y}, ...}
                        for symbol in ['THB', 'BTC']:
                            if symbol in result:
                                data = result[symbol]
                                avail = float(data.get('available', 0))
                                reserved = float(data.get('reserved', 0))
                                total = avail + reserved
                                txt += f"• *{symbol}*:\n"
                                txt += f"    ├ Avail: `{avail:.8f}`\n"
                                txt += f"    ├ Rsrv:  `{reserved:.8f}`\n"
                                txt += f"    └ Total: `{total:.8f}`\n"
                        self.bot.send_message(m.chat.id, txt, parse_mode="Markdown")
                    else:
                        self.bot.send_message(m.chat.id, f"❌ Bitkub Error: {res.get('error')} | {res}")
                except Exception as e:
                    self.bot.send_message(m.chat.id, f"❌ ดึงยอดไม่ได้: {e}")
            
            elif m.text == '🟢 เริ่มระบบ':
                auto_trade_enabled = True
                self.bot.send_message(m.chat.id, "🟢 *เริ่มการเทรดอัตโนมัติ*", parse_mode="Markdown")
            
            elif m.text == '🔴 หยุดระบบ':
                auto_trade_enabled = False
                self.bot.send_message(m.chat.id, "🔴 *หยุดการเทรดอัตโนมัติ*", parse_mode="Markdown")
            
            elif m.text == '🔥 ขายด่วน':
                markup = telebot.types.InlineKeyboardMarkup()
                markup.add(telebot.types.InlineKeyboardButton("✅ ยืนยันขายล้างพอร์ต", callback_data="panic_confirm"), 
                           telebot.types.InlineKeyboardButton("❌ ยกเลิก", callback_data="panic_cancel"))
                self.bot.send_message(m.chat.id, "⚠️ *Panic Sell?* คุณต้องการขายเหรียญทั้งหมดที่ราคาตลาดทันทีหรือไม่?", reply_markup=markup, parse_mode="Markdown")

        @self.bot.callback_query_handler(func=lambda call: True)
        def callback(call):
            if call.data == "panic_confirm":
                global auto_trade_enabled
                auto_trade_enabled = False
                asyncio.run_coroutine_threadsafe(self.do_panic_sell(), asyncio.get_event_loop())
                self.bot.edit_message_text("🔥 *กำลังขายล้างพอร์ต...*", call.message.chat.id, call.message.message_id, parse_mode="Markdown")
            elif call.data == "panic_cancel":
                self.bot.edit_message_text("❌ ยกเลิกการขายด่วน", call.message.chat.id, call.message.message_id)

    async def do_panic_sell(self):
        for c, s in self.states.items():
            bal = float(self.current_balances.get(c, {}).get("available", 0))
            if bal > 1e-6: # เกิน 0
                res = await self.driver.send_request("POST", "/api/v3/market/place-ask", {"sym":f"{c.lower()}_thb","amt":self.driver.clean_amount(bal),"rat":0,"typ":"market"})
                if res.get("error") == 0:
                    s.layers = []
                    update_db_layers(c, [])
                    await self.send_tg(f"🔥 *Panic Sold {c}* สำเร็จ!")
        await self.send_tg("🏁 *จบภารกิจล้างพอร์ต*")

    async def send_tg(self, text):
        try: self.bot.send_message(TELEGRAM_CHAT_ID, text, parse_mode="Markdown")
        except: pass

    async def price_poller(self):
        """Primary price updater: polls REST API every 5s (reliable on Render free tier)"""
        logger.info("📡 Starting REST price poller (primary price source)...")
        while self.running:
            try:
                ticker = await self.driver.send_request("GET", "/api/market/ticker")
                if ticker and isinstance(ticker, dict):
                    for coin, state in self.states.items():
                        # ค้นหาเหรียญแบบยืดหยุ่น (เช่น THB_BTC หรือ BTC_THB)
                        price = 0
                        for sym, data in ticker.items():
                            if coin.upper() in sym.upper() and "THB" in sym.upper():
                                price = float(data.get("last", 0))
                                break
                        
                        if price > 0:
                            state.update_price(price)
                            self.price_update_count += 1
                            if self.price_update_count % 5 == 0:
                                logger.info(f"💓 Pulse: {self.price_update_count} | {coin}: {price:,.2f}")
            except Exception as e:
                logger.warning(f"⚠️ Price poll error: {e}")
            await asyncio.sleep(5)

    async def ws_handler(self):
        """Secondary price source via WebSocket (bonus, may disconnect on free tier)"""
        logger.info(f"🌐 Starting WebSocket (secondary source) for: {list(self.states.keys())}")
        while self.running:
            try:
                async with websockets.connect("wss://api.bitkub.com/websocket-api/1", ping_interval=20, ping_timeout=10) as ws:
                    for i, sym in enumerate(self.states.keys()):
                        await ws.send(json.dumps({
                            "op": "sub", 
                            "id": i+1, 
                            "topic": f"market.ticker.thb_{sym.lower()}"
                        }))
                    logger.info("✅ WebSocket Subscribed (secondary source).")
                    async for msg in ws:
                        try:
                            data = json.loads(msg)
                            stream = data.get("stream", "")
                            inner = data.get("data", {})
                            if isinstance(inner, dict) and inner.get("last"):
                                coin = ""
                                for c in self.states.keys():
                                    if c.lower() in stream.lower():
                                        coin = c
                                        break
                                if coin:
                                    self.states[coin].update_price(float(inner["last"]))
                                    self.price_update_count += 1
                                    if self.price_update_count % 10 == 0:
                                        logger.info(f"💓 WS Pulse: {self.price_update_count} | {coin}: {inner['last']}")
                        except: continue
            except Exception as e:
                logger.warning(f"⚠️ WS disconnected: {e}. Reconnecting in 15s...")
                await asyncio.sleep(15)

    async def trading_logic(self):
        await asyncio.sleep(5)
        while self.running:
            try:
                if not auto_trade_enabled: await asyncio.sleep(5); continue
                res = await self.driver.send_request("POST", "/api/v3/market/balances")
                if res.get("error") == 0:
                    raw = res.get("result", {})
                    self.current_balances = { k.upper(): v for k, v in (raw.items() if isinstance(raw, dict) else [(i['symbol'], i) for i in raw]) }
                
                thb_avail = float(self.current_balances.get("THB", {}).get("available", 0))
                total_equity = thb_avail + sum((float(self.current_balances.get(c,{}).get("available",0)) + float(self.current_balances.get(c,{}).get("reserved",0))) * s.current_price for c,s in self.states.items())
                
                # Render Rich Table to logs
                if int(time.time()) % 60 < 5: print_status_table(self.states, total_equity)

                # --- ULTRA AGGRESSIVE FIBONACCI LOGIC ---
                fib_scale = [1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, 233, 377, 610]
                base_unit_pct = 0.02 # เริ่มต้นที่ 2% ของพอร์ตเพื่อความดุดัน
                
                if int(time.time()) % 60 < 5: print_status_table(self.states, total_equity)

                for coin, state in self.states.items():
                    if state.current_price <= 0 or state.is_trading: continue
                    v3_sym = f"{coin.lower()}_thb"
                    
                    l_idx = len(state.layers)
                    fib_factor = fib_scale[min(l_idx, len(fib_scale)-1)]
                    
                    # คำนวณเงินซื้อแบบทุ่มสุดตัว: (Equity * base) * fib
                    dynamic_amt = (total_equity * base_unit_pct) * fib_factor
                    # ปรับให้เหมาะสมกับเงินสดที่มีจริง (ใช้ให้เกลี้ยง)
                    dynamic_amt = max(MIN_TRADE_THB, min(dynamic_amt, thb_avail)) 

                    # Sell Logic: ต้องคุ้มค่าธรรมเนียม (หัก 0.5% แล้วต้องกำไร > 1%)
                    if state.layers:
                        # ทุนรวมสะสม (รวมค่าธรรมเนียมขาซื้อ 0.25% แล้ว)
                        total_cost = sum(l['price'] * l['amount'] * 1.0025 for l in state.layers)
                        total_amt = sum(l['amount'] for l in state.layers)
                        
                        # คำนวณเงินที่จะได้รับหลังหักขาขาย 0.25%
                        expected_revenue = (total_amt * state.current_price) * 0.9975
                        
                        # กำไรสุทธิหลังหักทุกอย่าง
                        net_profit = expected_revenue - total_cost
                        net_profit_pct = (net_profit / total_cost) * 100 if total_cost > 0 else 0
                        
                        if net_profit_pct >= 1.0: # กำไรเนื้อๆ 1% หลังหักค่าธรรมเนียม
                            state.is_trading = True
                            logger.info(f"💰 Selling {coin} | Net Profit: {net_profit:,.2f} THB ({net_profit_pct:+.2f}%)")
                            avail = float(self.current_balances.get(coin,{}).get("available",0))
                            if await self.driver.send_request("POST", "/api/v3/market/place-ask", {"sym":v3_sym,"amt":self.driver.clean_amount(avail),"rat":0,"typ":"market"}):
                                update_db_layers(coin, []); state.layers = []
                                await self.send_tg(f"💰 *PROFIT TAKEN!* {coin}\n📈 Net Profit: `{net_profit:,.2f}` THB (`{net_profit_pct:+.2f}%`)")
                            state.is_trading = False

                    # Buy Logic: Fibonacci Dynamic Grid
                    if thb_avail >= dynamic_amt and thb_avail >= MIN_TRADE_THB:
                        if not state.layers or (state.current_price <= min(l['price'] for l in state.layers)*(1-state.get_dynamic_grid_step(l_idx))):
                            state.is_trading = True
                            logger.info(f"⚔️ Aggressive Buy {coin} Layer {l_idx+1} | Amt: {dynamic_amt:,.2f} THB (Fib: {fib_factor}x)")
                            buy_res = await self.driver.send_request("POST", "/api/v3/market/place-bid", {"sym":v3_sym,"amt":dynamic_amt,"rat":0,"typ":"market"})
                            if buy_res.get("error") == 0:
                                bought = (dynamic_amt * 0.9975) / state.current_price
                                state.layers.append({"price": state.current_price, "amount": bought})
                                update_db_layers(coin, state.layers)
                                await self.send_tg(f"⚔️ *Aggressive Buy L{l_idx+1}*: {coin}\n💸 Amt: `{dynamic_amt:,.2f}` THB\n💓 Pulse: `{self.price_update_count}`")
                            state.is_trading = False

                if int(time.time()) % 3600 < 10:
                    save_snapshot(total_equity, get_today_profit(), thb_avail)
                    for c, s in self.states.items(): save_bot_history(c, s.price_history)
                await asyncio.sleep(5)
            except: await asyncio.sleep(10)

    async def keep_alive(self):
        url = os.environ.get("RENDER_EXTERNAL_URL")
        if not url: return
        while self.running:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url) as resp:
                        if resp.status == 200: logger.info("💓 Keep-alive ping sent successfully.")
            except: pass
            await asyncio.sleep(600) # 10 mins

    async def fetch_initial_prices(self):
        logger.info("📡 Fetching initial prices from Bitkub...")
        try:
            ticker = await self.driver.send_request("GET", "/api/market/ticker")
            if ticker and isinstance(ticker, dict):
                # Bitkub Ticker returns UPPERCASE keys like 'THB_BTC'
                for coin, state in self.states.items():
                    sym = f"THB_{coin.upper()}"
                    if sym in ticker:
                        price = float(ticker[sym].get("last", 0))
                        state.update_price(price)
                        logger.info(f"✅ Initial price for {coin}: {price:,.2f}")
                    else:
                        # ลองเช็คแบบ lowercase หรือ keys อื่นๆ
                        for key in ticker.keys():
                            if coin.lower() in key.lower():
                                price = float(ticker[key].get("last", 0))
                                state.update_price(price)
                                logger.info(f"✅ Initial price for {coin} (found as {key}): {price:,.2f}")
                                break
            else:
                logger.warning(f"⚠️ Unexpected ticker response format: {type(ticker)}")
        except Exception as e:
            logger.error(f"❌ Could not fetch initial prices: {e}")

        # 2. เริ่มต้นฐานข้อมูล (ย้ายมาไว้หลังดึงราคาเพื่อไม่ให้บล็อกราคา)
        logger.info("🗄️ Initializing Supabase database...")
        try:
            init_db()
            stored, histories = load_db_layers(), load_bot_history()
            for c, l in stored.items(): 
                coin_key = c.upper()
                if coin_key in self.states: 
                    self.states[coin_key].layers = l
                    logger.info(f"💾 Applied {len(l)} layers to {coin_key} state.")
            for c, h in histories.items():
                coin_key = c.upper()
                if coin_key in self.states: self.states[coin_key].price_history = h
            logger.info("✅ Database and history fully applied.")
        except Exception as e:
            logger.error(f"⚠️ Database init failed but continuing: {e}")

    async def run_all(self):
        # Setup Webhook before starting tasks
        render_url = os.getenv("RENDER_EXTERNAL_URL", "https://bitkub-trading-bot-railway.onrender.com")
        webhook_url = f"{render_url}/webhook"
        logger.info(f"🌐 Setting Telegram Webhook: {webhook_url}")
        
        # Clear old webhook and set new one (solves 409 conflict 100%)
        try:
            self.bot.remove_webhook()
            await asyncio.sleep(1)
            self.bot.set_webhook(url=webhook_url)
        except Exception as e:
            logger.error(f"⚠️ Webhook setup failed: {e}")

        # 1. Fetch initial prices
        await self.fetch_initial_prices()

        # 2. Initialize database
        logger.info("🗄️ Initializing Supabase database...")
        try:
            init_db()
            stored, histories = load_db_layers(), load_bot_history()
            for c, l in stored.items(): 
                coin_key = c.upper()
                if coin_key in self.states: 
                    self.states[coin_key].layers = l
                    logger.info(f"💾 Applied {len(l)} layers to {coin_key} state.")
            for c, h in histories.items():
                coin_key = c.upper()
                if coin_key in self.states: self.states[coin_key].price_history = h
            logger.info("✅ Database and history fully applied.")
        except Exception as e:
            logger.error(f"⚠️ Database init failed but continuing: {e}")

        # 3. Run all async tasks
        logger.info("🚀 Starting all background tasks...")
        await asyncio.gather(
            self.price_poller(),
            self.ws_handler(),
            self.trading_logic(),
            self.keep_alive()
        )

if __name__ == "__main__":
    bot = TurboDGT()
    # Run Flask in background thread for Webhooks/Health
    threading.Thread(target=lambda: bot.app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)), use_reloader=False), daemon=True).start()
    # Run the main async loop
    try:
        asyncio.run(bot.run_all())
    except KeyboardInterrupt:
        pass
