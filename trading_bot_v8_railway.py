import os
import json
import time
import asyncio
import logging
import psycopg2
from psycopg2 import pool
from psycopg2.extras import DictCursor
import threading
import numpy as np
import aiohttp
import websockets
import telebot
from flask import Flask, jsonify
import signal
from datetime import datetime
from bitkub_async import BitkubAsyncDriver
from dotenv import load_dotenv

# Load .env for local testing, Railway will use its own Env Vars
load_dotenv()

# --- SETTINGS & ENV VARS ---
# Priority: Environment Variables > config.json
if os.path.exists("config.json"):
    with open("config.json") as f:
        cfg = json.load(f)
else:
    cfg = {}

API_KEY = os.environ.get("API_KEY", cfg.get("api_key", ""))
API_SECRET = os.environ.get("API_SECRET", cfg.get("api_secret", ""))
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", cfg.get("telegram_token", ""))
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", cfg.get("telegram_chat_id", ""))
DATABASE_URL = os.environ.get("DATABASE_URL") # Required for Railway/Supabase

SYMBOLS = ["thb_btc"]
MIN_TRADE_THB = 10 
DEFAULT_GRID_STEP = float(os.environ.get("GRID_STEP_PCT", cfg.get("grid_step_pct", 0.5))) / 100
BUDGET_UTILIZATION = float(os.environ.get("BUDGET_UTILIZATION_PCT", cfg.get("budget_utilization_pct", 0.95)))
MAX_AMT_PER_LAYER = float(os.environ.get("MAX_AMOUNT_PER_LAYER", cfg.get("max_amount_per_layer", 2000.0)))
auto_trade_enabled = True # 🟢 เริ่มต้นให้ทำงานอัตโนมัติ

# --- LOGGING ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("TurboDGT-Railway")

# --- DATABASE (Postgres / Supabase) ---
class DatabaseManager:
    def __init__(self, db_url):
        self.db_url = db_url
        self.pool = None
        if self.db_url:
            self._init_pool()
        else:
            logger.error("❌ DATABASE_URL not found! Database features will be disabled.")

    def _init_pool(self):
        try:
            self.pool = psycopg2.pool.ThreadedConnectionPool(
                1, 20, self.db_url, sslmode='prefer'
            )
            logger.info("✅ Database connection pool initialized.")
        except Exception as e:
            logger.error(f"❌ Failed to initialize DB pool: {e}")

    def get_conn(self, retries=3):
        for i in range(retries):
            try:
                if not self.pool: self._init_pool()
                if self.pool: return self.pool.getconn()
            except Exception as e:
                logger.warning(f"⚠️ DB Connection retry {i+1}/{retries}: {e}")
                time.sleep(2)
        return None

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
            logger.error(f"❌ Query Error: {e} | Query: {query}")
            if commit: conn.rollback()
        finally:
            self.put_conn(conn)
        return result

db = DatabaseManager(DATABASE_URL)

def init_db():
    # 📊 trades table
    db.execute('''CREATE TABLE IF NOT EXISTS trades 
                 (id SERIAL PRIMARY KEY, coin TEXT, side TEXT, price DOUBLE PRECISION, amount DOUBLE PRECISION, profit DOUBLE PRECISION, ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    # 📊 daily_snapshots table
    db.execute('''CREATE TABLE IF NOT EXISTS daily_snapshots 
                 (ts DATE PRIMARY KEY, total_equity DOUBLE PRECISION, today_profit DOUBLE PRECISION, balance_thb DOUBLE PRECISION)''')
    
    # 🛠️ layers table
    db.execute('''CREATE TABLE IF NOT EXISTS layers 
                 (id SERIAL PRIMARY KEY, coin TEXT, price DOUBLE PRECISION, amount DOUBLE PRECISION)''')
    
    # 🧠 history table (Persistence across restarts)
    db.execute('''CREATE TABLE IF NOT EXISTS bot_history 
                 (coin TEXT PRIMARY KEY, history_json TEXT)''')
                 
    logger.info("🗄️ Database tables initialized.")

def save_snapshot(equity, profit, thb):
    query = """
    INSERT INTO daily_snapshots (ts, total_equity, today_profit, balance_thb) 
    VALUES (CURRENT_DATE, %s, %s, %s)
    ON CONFLICT (ts) DO UPDATE SET 
        total_equity = EXCLUDED.total_equity,
        today_profit = EXCLUDED.today_profit,
        balance_thb = EXCLUDED.balance_thb
    """
    db.execute(query, (equity, profit, thb))

def save_trade(coin, side, price, amount, profit=0):
    query = "INSERT INTO trades (coin, side, price, amount, profit) VALUES (%s, %s, %s, %s, %s)"
    db.execute(query, (coin, side, price, amount, profit))

def update_db_layers(coin, layers):
    db.execute("DELETE FROM layers WHERE coin = %s", (coin,))
    for l in layers:
        db.execute("INSERT INTO layers (coin, price, amount) VALUES (%s, %s, %s)", (coin, float(l['price']), float(l['amount'])))

def load_db_layers():
    rows = db.execute("SELECT coin, price, amount FROM layers", fetch=True)
    data = {}
    if rows:
        for r in rows:
            coin = r['coin']
            if coin not in data: data[coin] = []
            data[coin].append({"price": float(r['price']), "amount": float(r['amount'])})
    return data

def get_today_profit():
    query = "SELECT SUM(profit) FROM trades WHERE side='SELL' AND ts::date = CURRENT_DATE"
    res = db.execute(query, fetch=True)
    if res and res[0][0]:
        return float(res[0][0])
    return 0.0

def save_bot_history(coin, history_list):
    query = """
    INSERT INTO bot_history (coin, history_json) VALUES (%s, %s)
    ON CONFLICT (coin) DO UPDATE SET history_json = EXCLUDED.history_json
    """
    db.execute(query, (coin, json.dumps(history_list)))

def load_bot_history():
    rows = db.execute("SELECT coin, history_json FROM bot_history", fetch=True)
    data = {}
    if rows:
        for r in rows:
            data[r['coin']] = json.loads(r['history_json'])
    return data

# --- MATH UTILS ---
def get_max_layers(total_equity, num_coins):
    if num_coins <= 0 or total_equity <= 0: return 1
    max_l = int((total_equity * BUDGET_UTILIZATION) / (MIN_TRADE_THB * num_coins))
    return max(1, max_l)

# --- STATE MANAGEMENT ---
class CoinState:
    def __init__(self, coin):
        self.coin = coin
        self.layers = []
        self.current_price = 0.0
        self.price_history = []
        self.window_size = 30
        self.is_trading = False

    def update_price(self, price):
        self.current_price = price
        self.price_history.append(price)
        if len(self.price_history) > self.window_size:
            self.price_history.pop(0)

    def get_stats(self):
        if len(self.price_history) < 5: return 0.0, 0.0, 0.0
        arr = np.array(self.price_history)
        mean, std = np.mean(arr), np.std(arr)
        z_score = (self.current_price - mean) / std if std > 0 else 0
        return mean, std, z_score

    def get_fib_multiplier(self, layer_count):
        fib_ratios = [1.0, 1.0, 1.382, 1.618, 2.618, 4.236, 6.854]
        return fib_ratios[min(layer_count, len(fib_ratios)-1)]

    def get_dynamic_grid_step(self, layer_count=0):
        mean, std, z = self.get_stats()
        if mean == 0: return DEFAULT_GRID_STEP
        volatility_pct = (std / mean)
        adaptive_base = max(DEFAULT_GRID_STEP, volatility_pct)
        multiplier = self.get_fib_multiplier(layer_count)
        return min(adaptive_base * multiplier, 0.10)

# --- BOT CORE ---
class TurboDGT:
    def __init__(self):
        self.driver = BitkubAsyncDriver(API_KEY, API_SECRET)
        self.bot = telebot.TeleBot(TELEGRAM_TOKEN)
        self.states = {s.split('_')[1].upper(): CoinState(s.split('_')[1].upper()) for s in SYMBOLS}
        self.running = True
        self.ws_url = "wss://api.bitkub.com/websocket-api/1"
        self.current_balances = {}
        self.price_update_count = 0
        self.loop = None
        self.app = Flask(__name__)
        self._setup_flask()
        self._setup_telegram()
        self._setup_signals()

    def _setup_signals(self):
        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, self._handle_exit)

    def _handle_exit(self, signum, frame):
        logger.info(f"📥 Received signal {signum}. Shutting down gracefully...")
        self.running = False

    def _setup_flask(self):
        @self.app.route("/")
        def index():
            return "⚡ Turbo DGT Railway Active"

        @self.app.route("/health")
        def health():
            return jsonify({"status": "healthy", "timestamp": datetime.now().isoformat()}), 200

        @self.app.route("/status")
        def status():
            return jsonify({
                "status": "RUNNING" if self.running else "STOPPING",
                "coins": {c: {"price": s.current_price, "layers": len(s.layers), "z": s.get_stats()[2]} for c, s in self.states.items()}
            })

    def _setup_telegram(self):
        @self.bot.message_handler(commands=['start'])
        def start(m):
            markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
            markup.add('📊 สถานะบอท', '💰 ยอดเงิน')
            markup.add('🟢 เริ่มระบบ', '🔴 หยุดระบบ')
            markup.add('🔥 ขายด่วน (Panic Sell)')
            self.bot.send_message(m.chat.id, "🚀 Turbo DGT Railway พร้อม!", reply_markup=markup)

        @self.bot.message_handler(func=lambda m: True)
        def handle(m):
            global auto_trade_enabled
            if m.text == '🔥 ขายด่วน (Panic Sell)':
                markup = telebot.types.InlineKeyboardMarkup()
                markup.add(telebot.types.InlineKeyboardButton("✅ ยืนยันขายทั้งหมด", callback_data="panic_confirm"))
                markup.add(telebot.types.InlineKeyboardButton("❌ ยกเลิก", callback_data="panic_cancel"))
                self.bot.send_message(m.chat.id, "⚠️ *[PANIC SELL]* ยันยืนขายเหรียญทั้งหมดและหยุดระบบ?", reply_markup=markup, parse_mode="Markdown")
            
            elif m.text == '📊 สถานะบอท':
                status_msg = "🚀 *[TURBO DGT RAILWAY]*\n"
                status_msg += f"📅 `{datetime.now().strftime('%H:%M:%S')}` | 💓 ชีพจร: `{self.price_update_count}`\n"
                status_msg += "----------------------------\n"
                
                total_unrealized = 0.0
                total_asset_val = 0.0
                thb_balance = 0.0
                
                if self.current_balances:
                    thb_balance = float(self.current_balances.get("THB", {}).get("available", 0)) + float(self.current_balances.get("THB", {}).get("reserved", 0))

                for coin, s in self.states.items():
                    price_str = f"{s.current_price:,.2f}" if s.current_price > 0 else "รอราคา..."
                    net_pl_pct = 0.0
                    emoji = "⚪"
                    
                    coin_data = self.current_balances.get(coin, {})
                    coin_total = float(coin_data.get("available", 0)) + float(coin_data.get("reserved", 0))
                    total_asset_val += (coin_total * s.current_price)
                    
                    if s.layers and s.current_price > 0:
                        total_cost = sum(l['price'] * l['amount'] * 1.0025 for l in s.layers)
                        total_amt = sum(l['amount'] for l in s.layers)
                        avg_cost = total_cost / total_amt if total_amt > 0 else s.layers[0]['price']
                        net_pl_pct = ((s.current_price * 0.9975 / avg_cost) - 1) * 100
                        emoji = "🟢" if net_pl_pct >= 0 else "🔴"
                        total_unrealized += (total_amt * (s.current_price * 0.9975 - avg_cost))

                    status_msg += f"{emoji} *{coin}*: `{price_str}` [{len(s.layers)}/∞] ({net_pl_pct:+.2f}%)\n"

                total_equity = thb_balance + total_asset_val
                status_msg += "----------------------------\n"
                status_msg += f"💰 กำไรสะสมวันนี้: `{get_today_profit():,.2f}` THB\n"
                status_msg += f"📊 Unrealized: `{total_unrealized:+.2f}` THB\n"
                status_msg += f"💵 Total Equity: `{total_equity:,.2f}` THB\n"
                self.bot.send_message(m.chat.id, status_msg, parse_mode="Markdown")

            elif m.text == '💰 ยอดเงิน':
                msg = "💰 *[BALANCE]*\n"
                if self.current_balances:
                    for a, d in self.current_balances.items():
                        total = float(d.get('available', 0)) + float(d.get('reserved', 0))
                        if total > 0.000001:
                            msg += f"• `{a}`: `{total:,.4f}`\n"
                else: msg += "⚠️ ดึงยอดเงินไม่สำเร็จ"
                self.bot.send_message(m.chat.id, msg, parse_mode="Markdown")

            elif m.text == '🟢 เริ่มระบบ':
                auto_trade_enabled = True
                self.bot.send_message(m.chat.id, "🟢 ระบบเริ่มทำงาน")

            elif m.text == '🔴 หยุดระบบ':
                auto_trade_enabled = False
                self.bot.send_message(m.chat.id, "🔴 หยุดระบบ")

        @self.bot.callback_query_handler(func=lambda call: True)
        def callback_query(call):
            if call.data == "panic_confirm":
                global auto_trade_enabled
                auto_trade_enabled = False
                self.bot.edit_message_text("🔥 *[PANIC SELL]* กำลังเทขายเหรียญทั้งหมด...", call.message.chat.id, call.message.message_id, parse_mode="Markdown")
                asyncio.run_coroutine_threadsafe(self.do_panic_sell(), self.loop)
            elif call.data == "panic_cancel":
                self.bot.edit_message_text("❌ ยกเลิก Panic Sell", call.message.chat.id, call.message.message_id)

    async def do_panic_sell(self):
        results = []
        for coin, state in self.states.items():
            coin_data = self.current_balances.get(coin, {})
            avail = float(coin_data.get("available", 0))
            if avail > 0:
                res = await self.driver.send_request("POST", "/api/v3/market/place-ask", {"sym":f"{coin.lower()}_thb","amt":self.driver.clean_amount(avail),"rat":0,"typ":"market"})
                if res.get("error") == 0:
                    results.append(f"✅ ขาย `{coin}` สำเร็จ")
                    state.layers = []
                    update_db_layers(coin, [])
                else:
                    results.append(f"❌ ขาย `{coin}` พลาด: {res.get('message')}")
        await self.send_tg("🏁 *PANIC SELL REPORT*\n" + "\n".join(results))

    async def send_tg(self, text):
        try:
            self.bot.send_message(TELEGRAM_CHAT_ID, text, parse_mode="Markdown")
        except: pass

    async def ws_handler(self):
        while self.running:
            try:
                async with websockets.connect(self.ws_url) as ws:
                    for sym in self.states.keys():
                        await ws.send(json.dumps({"op": "sub", "id": sym, "topic": f"market.ticker.thb_{sym.lower()}"}))
                    async for message in ws:
                        if not self.running: break
                        data = json.loads(message)
                        inner = data.get("data", {})
                        if isinstance(inner, dict) and inner.get("last"):
                            coin = data.get("stream", "").split(".")[-1].replace("thb_", "").upper()
                            if coin in self.states:
                                self.states[coin].update_price(float(inner["last"]))
                                self.price_update_count += 1
            except Exception as e:
                logger.error(f"WS Error: {e}")
                await asyncio.sleep(5)

    async def trading_logic(self):
        await asyncio.sleep(5)
        while self.running:
            try:
                if not auto_trade_enabled:
                    await asyncio.sleep(5)
                    continue

                # 1. Fetch Balances
                res = await self.driver.send_request("POST", "/api/v3/market/balances")
                if res.get("error") == 0:
                    raw = res.get("result", {})
                    self.current_balances = { k.upper(): v for k, v in (raw.items() if isinstance(raw, dict) else [(i['symbol'], i) for i in raw]) }
                
                thb_avail = float(self.current_balances.get("THB", {}).get("available", 0))
                
                # 2. Dynamic Math
                total_asset_val = 0.0
                for c, s in self.states.items():
                    c_total = float(self.current_balances.get(c, {}).get("available", 0)) + float(self.current_balances.get(c, {}).get("reserved", 0))
                    total_asset_val += c_total * s.current_price
                
                total_equity = thb_avail + total_asset_val
                max_l = get_max_layers(total_equity, len(self.states))
                dynamic_amt = max(MIN_TRADE_THB, min((total_equity * BUDGET_UTILIZATION) / (len(self.states) * max_l), MAX_AMT_PER_LAYER))

                # 3. Grid Logic
                for coin, state in self.states.items():
                    if state.current_price <= 0 or state.is_trading: continue
                    v3_sym = f"{coin.lower()}_thb"
                    
                    coin_total = float(self.current_balances.get(coin, {}).get("available", 0)) + float(self.current_balances.get(coin, {}).get("reserved", 0))
                    mem_amt = sum(l['amount'] for l in state.layers)
                    
                    if coin_total * state.current_price < MIN_TRADE_THB and state.layers:
                        state.layers = []
                        update_db_layers(coin, [])
                    elif (coin_total - mem_amt) * state.current_price >= MIN_TRADE_THB:
                        state.layers.append({"price": state.current_price, "amount": coin_total - mem_amt})
                        update_db_layers(coin, state.layers)

                    # Sell Logic
                    if state.layers:
                        total_cost = sum(l['price'] * l['amount'] * 1.0025 for l in state.layers)
                        total_amt = sum(l['amount'] for l in state.layers)
                        if total_amt > 0:
                            avg_buy = total_cost / total_amt
                            profit_net = (state.current_price * 0.9975 / avg_buy) - 1
                            if profit_net >= 0.01: # 1% Net Target
                                state.is_trading = True
                                avail = float(self.current_balances.get(coin,{}).get("available",0))
                                res = await self.driver.send_request("POST", "/api/v3/market/place-ask", {"sym":v3_sym,"amt":self.driver.clean_amount(avail),"rat":0,"typ":"market"})
                                if res.get("error") == 0:
                                    save_trade(coin, "SELL", state.current_price, avail, (avail * state.current_price * 0.9975) - total_cost)
                                    state.layers = []
                                    update_db_layers(coin, [])
                                    await self.send_tg(f"💰 *PROFIT* ขาย {coin} สำเร็จ! ({profit_net*100:.2f}%)")
                                state.is_trading = False

                    # Buy Logic
                    if thb_avail >= dynamic_amt:
                        can_buy = False
                        if not state.layers: can_buy = True
                        elif len(state.layers) < max_l:
                            min_p = min(l['price'] for l in state.layers)
                            if state.current_price <= min_p * (1 - state.get_dynamic_grid_step(len(state.layers))):
                                can_buy = True
                        
                        if can_buy:
                            state.is_trading = True
                            res = await self.driver.send_request("POST", "/api/v3/market/place-bid", {"sym":v3_sym,"amt":dynamic_amt,"rat":0,"typ":"market"})
                            if res.get("error") == 0:
                                bought = (dynamic_amt * 0.9975) / state.current_price
                                state.layers.append({"price": state.current_price, "amount": bought})
                                update_db_layers(coin, state.layers)
                                save_trade(coin, "BUY", state.current_price, dynamic_amt)
                                await self.send_tg(f"🎯 *BUY* {coin} ไม้ที่ {len(state.layers)} ({state.current_price:,.2f})")
                            state.is_trading = False

                if int(time.time()) % 3600 < 10:
                    save_snapshot(total_equity, get_today_profit(), thb_avail)
                    for c, s in self.states.items(): save_bot_history(c, s.price_history)

                await asyncio.sleep(2)
            except Exception as e:
                logger.error(f"Logic Error: {e}")
                await asyncio.sleep(10)

    async def run_all(self):
        self.loop = asyncio.get_running_loop()
        init_db()
        stored = load_db_layers()
        for c, l in stored.items():
            if c in self.states: self.states[c].layers = l
        histories = load_bot_history()
        for c, h in histories.items():
            if c in self.states: self.states[c].price_history = h

        await self.send_tg("🚀 *Turbo DGT Railway* Online!")
        await asyncio.gather(self.ws_handler(), self.trading_logic())

if __name__ == "__main__":
    bot = TurboDGT()
    threading.Thread(target=lambda: bot.bot.infinity_polling(skip_pending=True), daemon=True).start()
    port = int(os.environ.get("PORT", 8080))
    threading.Thread(target=lambda: bot.app.run(host="0.0.0.0", port=port, use_reloader=False), daemon=True).start()
    try: asyncio.run(bot.run_all())
    except KeyboardInterrupt: bot.running = False
