import os
import json
import time
import asyncio
import logging
import psycopg2
from psycopg2 import pool
from psycopg2.extras import DictCursor
import threading
import math # ใช้ math แทน numpy เพื่อประหยัด RAM
import aiohttp
import websockets
import telebot
from flask import Flask, jsonify
import signal
from datetime import datetime
from bitkub_async import BitkubAsyncDriver
from dotenv import load_dotenv

# Load .env for local testing
load_dotenv()

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

# --- LOGGING ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("TurboDGT-Render-Lite")

# --- MATH UTILS (Pure Python for RAM Optimization) ---
def calculate_stats(data):
    """คำนวณ Mean, Std Dev, และ Z-Score โดยไม่ใช้ NumPy"""
    n = len(data)
    if n < 5: return 0.0, 0.0, 0.0
    
    mean = sum(data) / n
    variance = sum((x - mean) ** 2 for x in data) / n
    std_dev = math.sqrt(variance)
    
    current_price = data[-1]
    z_score = (current_price - mean) / std_dev if std_dev > 0 else 0
    return mean, std_dev, z_score

# --- DATABASE (Supabase Optimized) ---
class DatabaseManager:
    def __init__(self, db_url):
        self.db_url = db_url
        self.pool = None
        if self.db_url: self._init_pool()

    def _init_pool(self):
        try:
            # ใช้ Pool ขนาดเล็กมาก (1-3) เพื่อประหยัด RAM สุดๆ
            self.pool = psycopg2.pool.ThreadedConnectionPool(1, 3, self.db_url, sslmode='require')
            logger.info("✅ Database Pool (Lite) initialized.")
        except Exception as e:
            logger.error(f"❌ DB Pool Error: {e}")

    def get_conn(self):
        try:
            if not self.pool: self._init_pool()
            return self.pool.getconn()
        except: return None

    def put_conn(self, conn):
        if self.pool and conn:
            try: self.pool.putconn(conn)
            except: pass

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
        finally:
            self.put_conn(conn)
        return result

db = DatabaseManager(DATABASE_URL)

def init_db():
    db.execute('''CREATE TABLE IF NOT EXISTS trades 
                 (id SERIAL PRIMARY KEY, coin TEXT, side TEXT, price DOUBLE PRECISION, amount DOUBLE PRECISION, profit DOUBLE PRECISION, ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    db.execute('''CREATE TABLE IF NOT EXISTS daily_snapshots 
                 (ts DATE PRIMARY KEY, total_equity DOUBLE PRECISION, today_profit DOUBLE PRECISION, balance_thb DOUBLE PRECISION)''')
    db.execute('''CREATE TABLE IF NOT EXISTS layers 
                 (id SERIAL PRIMARY KEY, coin TEXT, price DOUBLE PRECISION, amount DOUBLE PRECISION)''')
    db.execute('''CREATE TABLE IF NOT EXISTS bot_history 
                 (coin TEXT PRIMARY KEY, history_json TEXT)''')

def save_snapshot(equity, profit, thb):
    query = "INSERT INTO daily_snapshots (ts, total_equity, today_profit, balance_thb) VALUES (CURRENT_DATE, %s, %s, %s) ON CONFLICT (ts) DO UPDATE SET total_equity=EXCLUDED.total_equity, today_profit=EXCLUDED.today_profit, balance_thb=EXCLUDED.balance_thb"
    db.execute(query, (equity, profit, thb))

def save_trade(coin, side, price, amount, profit=0):
    db.execute("INSERT INTO trades (coin, side, price, amount, profit) VALUES (%s, %s, %s, %s, %s)", (coin, side, price, amount, profit))

def update_db_layers(coin, layers):
    db.execute("DELETE FROM layers WHERE coin = %s", (coin,))
    for l in layers:
        db.execute("INSERT INTO layers (coin, price, amount) VALUES (%s, %s, %s)", (coin, float(l['price']), float(l['amount'])))

def load_db_layers():
    rows = db.execute("SELECT coin, price, amount FROM layers", fetch=True)
    data = {}
    if rows:
        for r in rows:
            c = r['coin']
            if c not in data: data[c] = []
            data[c].append({"price": float(r['price']), "amount": float(r['amount'])})
    return data

def get_today_profit():
    res = db.execute("SELECT SUM(profit) FROM trades WHERE side='SELL' AND ts::date = CURRENT_DATE", fetch=True)
    return float(res[0][0]) if res and res[0][0] else 0.0

def save_bot_history(coin, history_list):
    db.execute("INSERT INTO bot_history (coin, history_json) VALUES (%s, %s) ON CONFLICT (coin) DO UPDATE SET history_json = EXCLUDED.history_json", (coin, json.dumps(history_list)))

def load_bot_history():
    rows = db.execute("SELECT coin, history_json FROM bot_history", fetch=True)
    return {r['coin']: json.loads(r['history_json']) for r in rows} if rows else {}

# --- STATE MANAGEMENT ---
class CoinState:
    def __init__(self, coin):
        self.coin, self.layers, self.current_price, self.price_history = coin, [], 0.0, []
        self.window_size = 30
        self.is_trading = False

    def update_price(self, price):
        self.current_price = price
        self.price_history.append(price)
        if len(self.price_history) > self.window_size: self.price_history.pop(0)

    def get_stats(self):
        return calculate_stats(self.price_history)

    def get_fib_multiplier(self, layer_count):
        fib = [1.0, 1.0, 1.382, 1.618, 2.618, 4.236, 6.854]
        return fib[min(layer_count, 6)]

    def get_dynamic_grid_step(self, layer_count=0):
        mean, std, z = self.get_stats()
        if mean == 0: return DEFAULT_GRID_STEP
        vol = (std / mean)
        return min(max(DEFAULT_GRID_STEP, vol) * self.get_fib_multiplier(layer_count), 0.10)

# --- BOT CORE ---
class TurboDGT:
    def __init__(self):
        self.driver = BitkubAsyncDriver(API_KEY, API_SECRET)
        self.bot = telebot.TeleBot(TELEGRAM_TOKEN)
        self.states = {s.split('_')[1].upper(): CoinState(s.split('_')[1].upper()) for s in SYMBOLS}
        self.running, self.current_balances, self.price_update_count, self.loop = True, {}, 0, None
        self.app = Flask(__name__)
        self._setup_flask()
        self._setup_telegram()

    def _setup_flask(self):
        @self.app.route("/")
        def index(): return "⚡ Turbo DGT Render Lite Active"
        @self.app.route("/health")
        def health(): return jsonify({"status": "healthy", "time": datetime.now().isoformat()}), 200

    def _setup_telegram(self):
        @self.bot.message_handler(commands=['start'])
        def start(m): self.bot.send_message(m.chat.id, "🚀 Turbo DGT Render Lite Ready!")
        @self.bot.message_handler(func=lambda m: m.text == '📊 สถานะบอท')
        def status(m): self.bot.send_message(m.chat.id, f"📊 สถานะ: {'🟢 ปกติ' if self.running else '🔴 หยุด'}\n💰 กำไรวันนี้: {get_today_profit():,.2f} THB")

    async def send_tg(self, text):
        try: self.bot.send_message(TELEGRAM_CHAT_ID, text, parse_mode="Markdown")
        except: pass

    async def ws_handler(self):
        while self.running:
            try:
                async with websockets.connect("wss://api.bitkub.com/websocket-api/1") as ws:
                    for sym in self.states.keys():
                        await ws.send(json.dumps({"op": "sub", "id": sym, "topic": f"market.ticker.thb_{sym.lower()}"}))
                    async for msg in ws:
                        data = json.loads(msg)
                        inner = data.get("data", {})
                        if isinstance(inner, dict) and inner.get("last"):
                            coin = data.get("stream", "").split(".")[-1].replace("thb_", "").upper()
                            if coin in self.states:
                                self.states[coin].update_price(float(inner["last"]))
                                self.price_update_count += 1
            except: await asyncio.sleep(5)

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
                total_equity = thb_avail + sum( (float(self.current_balances.get(c,{}).get("available",0)) + float(self.current_balances.get(c,{}).get("reserved",0))) * s.current_price for c,s in self.states.items() )
                
                max_l = int((total_equity * BUDGET_UTILIZATION) / (MIN_TRADE_THB * len(self.states))) if len(self.states)>0 else 1
                dynamic_amt = max(MIN_TRADE_THB, min((total_equity * BUDGET_UTILIZATION) / (len(self.states) * max_l), MAX_AMT_PER_LAYER))

                for coin, state in self.states.items():
                    if state.current_price <= 0 or state.is_trading: continue
                    v3_sym = f"{coin.lower()}_thb"
                    coin_total = float(self.current_balances.get(coin,{}).get("available",0)) + float(self.current_balances.get(coin,{}).get("reserved",0))
                    
                    # Sell Logic
                    if state.layers:
                        total_cost = sum(l['price'] * l['amount'] * 1.0025 for l in state.layers)
                        total_amt = sum(l['amount'] for l in state.layers)
                        if total_amt > 0 and (state.current_price * 0.9975 / (total_cost/total_amt)) - 1 >= 0.01:
                            state.is_trading = True
                            avail = float(self.current_balances.get(coin,{}).get("available",0))
                            res = await self.driver.send_request("POST", "/api/v3/market/place-ask", {"sym":v3_sym,"amt":self.driver.clean_amount(avail),"rat":0,"typ":"market"})
                            if res.get("error") == 0:
                                save_trade(coin, "SELL", state.current_price, avail, (avail * state.current_price * 0.9975) - total_cost)
                                state.layers = []
                                update_db_layers(coin, [])
                                await self.send_tg(f"💰 *PROFIT* {coin} สำเร็จ!")
                            state.is_trading = False

                    # Buy Logic
                    if thb_avail >= dynamic_amt:
                        can_buy = False
                        if not state.layers: can_buy = True
                        elif len(state.layers) < max_l and state.current_price <= min(l['price'] for l in state.layers) * (1 - state.get_dynamic_grid_step(len(state.layers))):
                            can_buy = True
                        
                        if can_buy:
                            state.is_trading = True
                            res = await self.driver.send_request("POST", "/api/v3/market/place-bid", {"sym":v3_sym,"amt":dynamic_amt,"rat":0,"typ":"market"})
                            if res.get("error") == 0:
                                bought = (dynamic_amt * 0.9975) / state.current_price
                                state.layers.append({"price": state.current_price, "amount": bought})
                                update_db_layers(coin, state.layers)
                                save_trade(coin, "BUY", state.current_price, dynamic_amt)
                                await self.send_tg(f"🎯 *BUY* {coin} ไม้ที่ {len(state.layers)}")
                            state.is_trading = False

                if int(time.time()) % 3600 < 10:
                    save_snapshot(total_equity, get_today_profit(), thb_avail)
                    for c, s in self.states.items(): save_bot_history(c, s.price_history)

                await asyncio.sleep(5)
            except: await asyncio.sleep(10)

    async def run_all(self):
        self.loop = asyncio.get_running_loop()
        init_db()
        stored = load_db_layers()
        for c, l in stored.items(): 
            if c in self.states: self.states[c].layers = l
        histories = load_bot_history()
        for c, h in histories.items():
            if c in self.states: self.states[c].price_history = h
        await self.send_tg("🚀 *Turbo DGT Render Lite* Online!")
        await asyncio.gather(self.ws_handler(), self.trading_logic())

if __name__ == "__main__":
    bot = TurboDGT()
    threading.Thread(target=lambda: bot.bot.infinity_polling(skip_pending=True), daemon=True).start()
    port = int(os.environ.get("PORT", 8080))
    threading.Thread(target=lambda: bot.app.run(host="0.0.0.0", port=port, use_reloader=False), daemon=True).start()
    try: asyncio.run(bot.run_all())
    except KeyboardInterrupt: bot.running = False
