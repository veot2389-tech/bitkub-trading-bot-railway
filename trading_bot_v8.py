import os
import json
import time
import asyncio
import logging
import sqlite3
import threading
import numpy as np
import aiohttp
import websockets
import telebot
from flask import Flask, jsonify
import signal
from datetime import datetime
from bitkub_async import BitkubAsyncDriver

# --- SETTINGS ---
with open("config.json") as f:
    cfg = json.load(f)

API_KEY = cfg.get("api_key", "")
API_SECRET = cfg.get("api_secret", "")
TELEGRAM_TOKEN = cfg.get("telegram_token", "")
TELEGRAM_CHAT_ID = cfg.get("telegram_chat_id", "")
SYMBOLS = ["thb_btc"]
MIN_TRADE_THB = 10 
DEFAULT_GRID_STEP = cfg.get("grid_step_pct", 0.5) / 100

def get_max_layers(total_equity, num_coins):
    usage_limit = cfg.get("budget_utilization_pct", 0.95)
    if num_coins <= 0 or total_equity <= 0: return 1
    max_l = int((total_equity * usage_limit) / (MIN_TRADE_THB * num_coins))
    return max(1, max_l)
AUTO_TRADE_ENABLED = True

# --- LOGGING ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("TurboDGT-Math-v8.8")

# --- DATABASE ---
DB_STATS = "bot_stats.db" # 📊 เก็บประวัติ/กำไร/สถิติ
DB_STATE = "bot_state.db" # 🛠️ เก็บสถานะไม้ที่เปิดค้างไว้ (Current State)

def init_db():
    # 📊 Database สถิติ
    conn_stats = sqlite3.connect(DB_STATS)
    c_stats = conn_stats.cursor()
    c_stats.execute('''CREATE TABLE IF NOT EXISTS trades 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, coin TEXT, side TEXT, price REAL, amount REAL, profit REAL, ts DATETIME)''')
    c_stats.execute('''CREATE TABLE IF NOT EXISTS daily_snapshots 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, ts DATE UNIQUE, total_equity REAL, today_profit REAL, balance_thb REAL)''')
    conn_stats.commit()
    conn_stats.close()

    # 🛠️ Database สถานะปัจจุบัน
    conn_state = sqlite3.connect(DB_STATE)
    c_state = conn_state.cursor()
    c_state.execute('''CREATE TABLE IF NOT EXISTS layers 
                 (coin TEXT, price REAL, amount REAL)''')
    conn_state.commit()
    conn_state.close()

def save_snapshot(equity, profit, thb):
    try:
        conn = sqlite3.connect(DB_STATS)
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO daily_snapshots (ts, total_equity, today_profit, balance_thb) VALUES (date('now', 'localtime'), ?, ?, ?)",
                  (equity, profit, thb))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Snapshot Error: {e}")

def save_trade(coin, side, price, amount, profit=0):
    conn = sqlite3.connect(DB_STATS)
    c = conn.cursor()
    ts_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    c.execute("INSERT INTO trades (coin, side, price, amount, profit, ts) VALUES (?, ?, ?, ?, ?, ?)",
              (coin, side, price, amount, profit, ts_str))
    conn.commit()
    conn.close()

def update_db_layers(coin, layers):
    conn = sqlite3.connect(DB_STATE)
    c = conn.cursor()
    c.execute("DELETE FROM layers WHERE coin = ?", (coin,))
    for l in layers:
        c.execute("INSERT INTO layers (coin, price, amount) VALUES (?, ?, ?)", (coin, l['price'], l['amount']))
    conn.commit()
    conn.close()

def load_db_layers():
    conn = sqlite3.connect(DB_STATE)
    c = conn.cursor()
    c.execute("SELECT coin, price, amount FROM layers")
    rows = c.fetchall()
    conn.close()
    data = {}
    for coin, price, amount in rows:
        if coin not in data: data[coin] = []
        data[coin].append({"price": price, "amount": amount})
    return data

def get_today_profit():
    try:
        conn = sqlite3.connect(DB_STATS)
        c = conn.cursor()
        c.execute("SELECT SUM(profit) FROM trades WHERE side='SELL' AND date(ts) = date('now', 'localtime')")
        res = c.fetchone()[0]
        conn.close()
        return float(res) if res else 0.0
    except: return 0.0

# --- STATE MANAGEMENT ---
class CoinState:
    def __init__(self, coin):
        self.coin = coin
        self.layers = []
        self.current_price = 0.0
        self.price_history = []  # เก็บราคาย้อนหลังเพื่อคำนวณสถิติ
        self.window_size = 30    # จำนวนตัวอย่างสำหรับวิเคราะห์ (เช่น 30 นาทีถ้าอัปเดตทุกนาที)
        self.grid_step = DEFAULT_GRID_STEP
        self.is_trading = False # 🔒 Lock กันรันซ้อนในระดับตัวแปร

    def update_price(self, price):
        self.current_price = price
        self.price_history.append(price)
        if len(self.price_history) > self.window_size:
            self.price_history.pop(0)

    def get_stats(self):
        """คำนวณค่าสถิติขั้นสูง: Mean, Standard Deviation, Z-Score"""
        if len(self.price_history) < 5:
            return 0.0, 0.0, 0.0 # ข้อมูลไม่พอ
        
        arr = np.array(self.price_history)
        mean = np.mean(arr)
        std = np.std(arr)
        z_score = (self.current_price - mean) / std if std > 0 else 0
        return mean, std, z_score

    def get_fib_multiplier(self, layer_count):
        # Fibonacci Multipliers: [Base, Fibonacci 1, Fib 2, Fib 3...]
        # 0:1.0, 1:1.0, 2:1.382, 3:1.618, 4:2.618, 5:4.236
        fib_ratios = [1.0, 1.0, 1.382, 1.618, 2.618, 4.236, 6.854]
        if layer_count < len(fib_ratios):
            return fib_ratios[layer_count]
        return fib_ratios[-1]

    def get_dynamic_grid_step(self, layer_count=0):
        mean, std, z = self.get_stats()
        if mean == 0: return DEFAULT_GRID_STEP
        
        # 1. คำนวณความผันผวน (Volatility)
        volatility_pct = (std / mean)
        
        # 2. ปรับระยะพื้นฐาน (Base Step) ตามตลาด (ขั้นต่ำ DEFAULT_GRID_STEP)
        adaptive_base = max(DEFAULT_GRID_STEP, volatility_pct)
        
        # 3. ใช้ Fibonacci Multiplier ตามจำนวน Layer จริง
        multiplier = self.get_fib_multiplier(layer_count)
        
        final_step = adaptive_base * multiplier
        return min(final_step, 0.10) # Cap สูงสุด 10% กันไม้ห่างเกินไปจนไม่ทำงาน

    def to_dict(self):
        return self.price_history

    def from_list(self, data):
        self.price_history = data[-self.window_size:]

# --- BOT CORE ---
class TurboDGT:
    def __init__(self):
        self.driver = BitkubAsyncDriver(API_KEY, API_SECRET)
        self.bot = telebot.TeleBot(TELEGRAM_TOKEN)
        self.states = {s.split('_')[1].upper(): CoinState(s.split('_')[1].upper()) for s in SYMBOLS}
        self.running = True
        self.ws_url = "wss://api.bitkub.com/websocket-api/1"
        self.current_balances = {}
        self.price_update_count = 0 # ตัวนับชีพจรบอท
        self.loop = None # 🔧 เก็บ Loop สำหรับ Thread-safe calls
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
        # ตัวเลือก: แจ้งเตือน Telegram ก่อนปิด
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.run_coroutine_threadsafe(self.send_tg("⚠️ *[SYSTEM]* บอทกำลังหยุดการทำงาน (Graceful Shutdown)"), loop)
        except: pass

    def _setup_flask(self):
        @self.app.route("/")
        def index():
            return "⚡ Turbo DGT v9.0 'Grid All' Active"

        @self.app.route("/status")
        def status():
            data = {
                "bot_version": "9.0",
                "status": "RUNNING" if self.running else "STOPPING",
                "last_update": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "coins": {coin: {"price": s.current_price, "layers": len(s.layers), "z_score": s.get_stats()[2]} for coin, s in self.states.items()}
            }
            return jsonify(data)

    def _setup_telegram(self):
        @self.bot.message_handler(commands=['start'])
        def start(m):
            markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
            markup.add('📊 สถานะบอท', '💰 ยอดเงิน')
            markup.add('🟢 เริ่มระบบ', '🔴 หยุดระบบ')
            markup.add('🔥 ขายด่วน (Panic Sell)')
            self.bot.send_message(m.chat.id, "🚀 Turbo DGT v8.0 Dynamic Math พร้อม!", reply_markup=markup)

        @self.bot.message_handler(func=lambda m: True)
        def handle(m):
            global AUTO_TRADE_ENABLED
            if m.text == '🔥 ขายด่วน (Panic Sell)':
                markup = telebot.types.InlineKeyboardMarkup()
                markup.add(telebot.types.InlineKeyboardButton("✅ ยืนยันขายทั้งหมด", callback_data="panic_confirm"))
                markup.add(telebot.types.InlineKeyboardButton("❌ ยกเลิก", callback_data="panic_cancel"))
                self.bot.send_message(m.chat.id, "⚠️ *[PANIC SELL]* คุณแน่ใจหรือไม่ที่จะขายเหรียญทั้งหมดในพอร์ตทันทีที่ราคาตลาด?", parse_mode="Markdown", reply_markup=markup)
            elif m.text == '📊 สถานะบอท':
                # 🔧 FIX: Try to fetch balance if cache is empty
                if not self.current_balances and self.loop:
                    try:
                        res = asyncio.run_coroutine_threadsafe(self.driver.send_request("POST", "/api/v3/market/balances"), self.loop).result(timeout=10)
                        if res.get("error") == 0:
                            raw_result = res.get("result", {})
                            if isinstance(raw_result, list):
                                self.current_balances = { item['symbol'].upper(): item for item in raw_result if 'symbol' in item }
                            else:
                                self.current_balances = { k.upper(): {**v, 'symbol': k} for k, v in raw_result.items() }
                    except: pass

                status_msg = "🚀 *[TURBO DGT v9.5 Fibonacci Quant]*\n"
                status_msg += f"📅 `{datetime.now().strftime('%H:%M:%S')}` | 💓 ชีพจร: `ปกติ ({self.price_update_count})` \n"
                status_msg += "----------------------------\n"
                
                total_unrealized_thb = 0.0
                total_asset_value = 0.0
                
                # Fetch balance for total equity calculation
                thb_balance = 0.0
                if self.current_balances:
                    thb_avail = float(self.current_balances.get("THB", {}).get("available", 0))
                    thb_res = float(self.current_balances.get("THB", {}).get("reserved", 0))
                    thb_balance = thb_avail + thb_res

                whitelist_coins = [sym.split("_")[1].upper() for sym in SYMBOLS]
                for coin, s in self.states.items():
                    # 🔧 แสดงเฉพาะเหรียญใน Whitelist (BTC) หรือเหรียญที่มีไม้ค้างรอขาย (Exit Only)
                    if coin not in whitelist_coins and len(s.layers) == 0:
                        continue
                        
                    price_str = f"{s.current_price:,.2f}" if s.current_price > 0 else "รอราคา..."
                    mean, std, z = s.get_stats()
                    
                    # คำนวณ P/L และ Portfolio Value
                    coin_unrealized = 0.0
                    net_pl_pct = 0.0
                    emoji = ""
                    
                    # 🔧 รวมมูลค่า Total Asset แม้ยังไม่มีการเทรด (Layer=0)
                    coin_data = self.current_balances.get(coin, {})
                    coin_avail = float(coin_data.get("available", 0))
                    coin_res = float(coin_data.get("reserved", 0))
                    coin_total = coin_avail + coin_res
                    if s.current_price > 0:
                        total_asset_value += (coin_total * s.current_price)
                    
                    if len(s.layers) > 0 and s.current_price > 0:
                        total_cost_thb = sum(l.get('price', 0) * l.get('amount', 0) for l in s.layers)
                        total_amount = sum(l.get('amount', 0) for l in s.layers)
                        avg_cost = total_cost_thb / total_amount if total_amount > 0 else s.layers[0]['price']
                        
                        val_net_sell = s.current_price * 0.9975
                        val_net_buy = avg_cost * 1.0025
                        net_pl_pct = ((val_net_sell / val_net_buy) - 1) * 100
                        
                        emoji = "🟢" if net_pl_pct >= 0 else "🔴"
                        # 🔧 คิดกำไร/ขาดทุน (P/L) **เฉพาะเหรียญที่บอทถืออยู่จริงใน Grid (total_amount)** ไม่รวมเศษเหรียญตกค้าง
                        total_unrealized_thb += (total_amount * (s.current_price - avg_cost))

                    # คำนวณ Next Buy (แบบเงียบๆ)
                    next_buy_str = ""
                    if s.current_price > 0:
                        layer_count = len(s.layers)
                        next_step_pct = s.get_dynamic_grid_step(layer_count)
                        target_price = min(l['price'] for l in s.layers) * (1 - next_step_pct) if s.layers else s.current_price
                        fib_symbol = "Φ" if layer_count > 1 else "○"
                        next_buy_str = f" » {fib_symbol}`{target_price:,.2f}`"

                    if len(s.layers) > 0:
                        # แสดง Z-Score เพื่อดูความถูก/แพงเชิงสถิติ
                        z_str = f" | Z:{z:+.1f}" if abs(z) > 0 else ""
                        status_msg += f"{emoji} *{coin}*: `{price_str}` [{len(s.layers)}/∞]{next_buy_str}{z_str} ({net_pl_pct:+.2f}%)\n"
                    else:
                        status_msg += f"⚪ *{coin}*: `{price_str}` [0/∞]{next_buy_str} (Z:{z:+.1f})\n"

                # สรุปภาพรวม
                today_profit = get_today_profit()
                total_equity = thb_balance + total_asset_value
                
                status_msg += "----------------------------\n"
                status_msg += f"💰 *กำไรที่เก็บได้วันนี้:* `{today_profit:,.2f}` THB\n"
                status_msg += f"📊 *Unrealized P/L:* `{total_unrealized_thb:+.2f}` THB\n"
                status_msg += f"💵 *Total Equity:* `{total_equity:,.2f}` THB\n"
                status_msg += "----------------------------\n"
                status_msg += "💡 _Next Step ตามระยะ Dynamic Grid_"
                
                try:
                    self.bot.send_message(m.chat.id, status_msg, parse_mode="Markdown")
                except Exception as e:
                    logger.error(f"Failed to send status message: {e}")
            elif m.text == '💰 ยอดเงิน':
                msg = "💰 *[BALANCE]*\n"
                total_equity = 0.0
                if self.current_balances:
                    sorted_assets = sorted(self.current_balances.items(), key=lambda x: x[0] != 'THB')
                    for a, d in sorted_assets:
                        val_avail = float(d.get('available', 0))
                        val_res = float(d.get('reserved', 0))
                        total = val_avail + val_res
                        
                        if total > 0.00000001: 
                            fmt = ",.2f" if a == 'THB' else ",.6f"
                            line = f"• `{a}`: `{total:{fmt}}`"
                            
                            # คำนวณมูลค่าเป็น THB
                            if a == 'THB':
                                total_equity += total
                            else:
                                price = self.states.get(a, CoinState(a)).current_price
                                if price > 0:
                                    value_thb = total * price
                                    total_equity += value_thb
                                    line += f" (≈ `{value_thb:,.2f}` THB)"
                            
                            msg += line + "\n"
                    
                    msg += "----------------------------\n"
                    msg += f"💵 *รวมมูลค่าพอร์ตทั้งหมด:* `{total_equity:,.2f}` THB"
                else: 
                    msg += "⚠️ _ดึงข้อมูลจาก Bitkub ไม่สำเร็จ_"
                try:
                    self.bot.send_message(m.chat.id, msg, parse_mode="Markdown")
                except Exception as e:
                    logger.error(f"Failed to send balance message: {e}")
            elif m.text == '🟢 เริ่มระบบ':
                AUTO_TRADE_ENABLED = True
                self.bot.send_message(m.chat.id, "🟢 ระบบเริ่มทำงาน (Dynamic Math Mode)")
            elif m.text == '🔴 หยุดระบบ':
                AUTO_TRADE_ENABLED = False
                self.bot.send_message(m.chat.id, "🔴 หยุดระบบชั่วคราว")

        @self.bot.callback_query_handler(func=lambda call: True)
        def callback_query(call):
            if call.data == "panic_confirm":
                global AUTO_TRADE_ENABLED
                AUTO_TRADE_ENABLED = False
                self.bot.answer_callback_query(call.id, "🚀 กำลังดำเนินการ Panic Sell และหยุดระบบ...")
                self.bot.edit_message_text("🔥 *[PANIC SELL]* กำลังเทขายเหรียญทั้งหมดและหยุดการเทรดอัตโนมัติ...", call.message.chat.id, call.message.message_id, parse_mode="Markdown")
                
                async def do_panic_sell():
                    results = []
                    # ดึง Balance ล่าสุดก่อนขาย
                    bal_res = await self.driver.send_request("POST", "/api/v3/market/balances")
                    balances = {}
                    if bal_res.get("error") == 0:
                        raw_result = bal_res.get("result", {})
                        if isinstance(raw_result, list):
                            balances = { item['symbol'].upper(): item for item in raw_result if 'symbol' in item }
                        else:
                            balances = { k.upper(): {**v, 'symbol': k} for k, v in raw_result.items() }

                    for coin, state in self.states.items():
                        coin_data = balances.get(coin, {})
                        coin_avail = float(coin_data.get("available", 0))
                        
                        if coin_avail > 0:
                            v3_sym = f"{coin.lower()}_thb"
                            amt_clean = self.driver.clean_amount(coin_avail)
                            # ส่งคำสั่งขาย Market ทันที
                            res = await self.driver.send_request("POST", "/api/v3/market/place-ask", {"sym":v3_sym,"amt":amt_clean,"rat":0,"typ":"market"})
                            if res.get("error") == 0:
                                results.append(f"✅ ขาย `{coin}` สำเร็จ: `{amt_clean}`")
                                # ล้างข้อมูลใน DB และ State
                                state.layers = []
                                update_db_layers(coin, [])
                            else:
                                results.append(f"❌ ขาย `{coin}` พลาด: {res.get('message')}")
                        else:
                            # แม้ไม่มีเหรียญ แต่ถ้ามีไม้ค้างในระบบ ก็ให้ล้างทิ้งด้วย
                            if state.layers:
                                state.layers = []
                                update_db_layers(coin, [])
                    
                    report = "🏁 *[PANIC SELL COMPLETED]*\n" + "\n".join(results) if results else "ℹ️ ไม่พบเหรียญที่ต้องขาย"
                    await self.send_tg(report)

                if self.loop:
                    asyncio.run_coroutine_threadsafe(do_panic_sell(), self.loop)

            elif call.data == "panic_cancel":
                self.bot.answer_callback_query(call.id, "ยกเลิกแล้ว")
                self.bot.edit_message_text("❌ ยกเลิกการ Panic Sell เรียบร้อย", call.message.chat.id, call.message.message_id)

    async def send_tg(self, text):
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, lambda: self.bot.send_message(TELEGRAM_CHAT_ID, text, parse_mode="Markdown"))
        except: pass

    async def ws_handler(self):
        while self.running:
            try:
                async with websockets.connect(self.ws_url) as ws:
                    # Subscribe to all current coins
                    for sym in self.states.keys():
                        v3_sym = f"thb_{sym.lower()}"
                        await ws.send(json.dumps({"op": "sub", "id": f"t_{sym}", "topic": f"market.ticker.{v3_sym}"}))
                    
                    logger.info(f"📡 WebSocket Connected (Subscribed to {len(self.states)} coins)")
                    async for message in ws:
                        data = json.loads(message)
                        inner_data = data.get("data", {})
                        if isinstance(inner_data, dict):
                            stream = inner_data.get("stream", "") or data.get("stream", "")
                            last_price = float(inner_data.get("last") or data.get("last", 0))
                            
                            if "market.ticker" in stream and last_price > 0:
                                coin_part = stream.split(".")[-1].replace("thb_", "").upper()
                                if coin_part in self.states:
                                    self.states[coin_part].update_price(last_price)
                                    self.price_update_count += 1 # กระตุ้นชีพจร
                                    if int(time.time()) % 30 == 0:
                                        logger.info(f"✅ [MATCHED] {coin_part}: {last_price:,.2f}")
                                else:
                                    # สำหรับเหรียญอื่นๆ ที่แถมมากับ stream
                                    pass
            except Exception as e:
                logger.error(f"WS Error: {e}")
                await asyncio.sleep(5)

    async def trading_logic(self):
        await asyncio.sleep(5)
        logger.info("🎯 Trading Logic Started (Dynamic Balance)")
        
        while self.running:
            try:
                if not AUTO_TRADE_ENABLED:
                    await asyncio.sleep(5)
                    continue

                bal_res = await self.driver.send_request("POST", "/api/v3/market/balances")
                if bal_res.get("error") == 0:
                    raw_result = bal_res.get("result", {})
                    if isinstance(raw_result, list):
                        self.current_balances = { item['symbol'].upper(): item for item in raw_result if 'symbol' in item }
                    else:
                        self.current_balances = { k.upper(): {**v, 'symbol': k} for k, v in raw_result.items() }
                else:
                    logger.error(f"Balance Error: {bal_res}")
                    await asyncio.sleep(5)
                    continue
                
                balances = self.current_balances
                thb_avail = float(balances.get("THB", {}).get("available", 0))

                # --- 1. DYNAMIC COIN DISCOVERY (Filter Dust & Whitelist) ---
                allowed_labels = [s.split('_')[1].upper() for s in SYMBOLS]
                for c_symbol in balances.keys():
                    if c_symbol == "THB": continue
                    
                    if c_symbol not in self.states:
                        c_data = balances.get(c_symbol, {})
                        c_total = float(c_data.get("available", 0)) + float(c_data.get("reserved", 0))
                        
                        # ถ้ายอดเหรียญมีมูลค่า > 10 บาท ให้รับเข้าสู่ระบบ (เพื่อรอขาย)
                        if c_total > 0:
                            self.states[c_symbol] = CoinState(c_symbol)
                            if c_symbol in allowed_labels:
                                logger.info(f"✨ [WHITELIST] พบ {c_symbol} เริ่มระบบ Grid")
                            else:
                                logger.info(f"⚠️ [EXIT ONLY] พบ {c_symbol} (ของเก่า) - รอขายออกอย่างเดียว ไม่ซื้อเพิ่ม")

                # 📐 Total Equity Based Math
                total_asset_value = 0.0
                for c, s in self.states.items():
                    c_data = balances.get(c, {})
                    c_total = float(c_data.get("available", 0)) + float(c_data.get("reserved", 0))
                    if s.current_price > 0:
                        total_asset_value += c_total * s.current_price
                
                total_equity = thb_avail + total_asset_value
                
                # 📐 Dynamic Grid Scaling
                num_coins = len(self.states)
                current_max_layers = get_max_layers(total_equity, num_coins)
                total_possible_slots = num_coins * current_max_layers
                usage_limit = cfg.get("budget_utilization_pct", 0.95)
                max_cap = cfg.get("max_amount_per_layer", 2000.0)
                
                dynamic_amt = (total_equity * usage_limit) / total_possible_slots if total_possible_slots > 0 else MIN_TRADE_THB
                dynamic_amt = max(MIN_TRADE_THB, min(dynamic_amt, max_cap))
                for coin, state in self.states.items():
                    mean, std, z = state.get_stats()
                    vol_pct = (std / mean * 100) if mean > 0 else 0
                    
                    z_flag = ""
                    if z < -2.0: z_flag = " 📉 [OVERSOLD]"
                    elif z > 2.0: z_flag = " 📈 [OVERBOUGHT]"
                    
                    if int(time.time()) % 60 < 2:
                        logger.info(f"📊 [{coin}] Price: {state.current_price:,.2f} | Z-Score: {z:+.2f} | Vol: {vol_pct:.2f}%{z_flag}")
                
                if int(time.time()) % 60 == 0:
                    logger.info(f"💰 [SYSTEM] Equity: {total_equity:,.2f} | Coins: {num_coins} | Amt/Layer: {dynamic_amt:,.2f} THB")

                # --- 2. GRID EXECUTION ---
                for coin, state in self.states.items():
                    if state.current_price == 0 or state.is_trading: continue
                    coin_data = balances.get(coin, {})
                    coin_avail = float(coin_data.get("available", 0))
                    coin_total = coin_avail + float(coin_data.get("reserved", 0))
                    v3_sym = f"{coin.lower()}_thb"

                    # --- 🔄 AUTO-SYNC: ตรวจสอบความจริงจากกระเป๋า (Wallet Sync) ---
                    total_coin_value = coin_total * state.current_price
                    memory_total_amount = sum(l.get('amount', 0) for l in state.layers)
                    
                    # 1. กรณีเหรียญหาย (Sync Down): ล้างไม้ที่จำไว้ถ้าในกระเป๋าไม่มีเหรียญเหลือแล้ว
                    if total_coin_value < MIN_TRADE_THB and len(state.layers) > 0:
                        logger.warning(f"⚠️ [SYNC] {coin} หายไปจากกระเป๋า -> ล้างข้อมูลไม้เดิม")
                        state.layers = []
                        update_db_layers(coin, [])
                    
                    # 2. กรณีเจอเหรียญเกิน (Sync Up): ถ้ามีเหรียญในกระเป๋ามากกว่าที่บอทจำได้
                    # เราจะเพิ่มไม้ใหม่ (Layer) ให้บอทเข้าไปคุมเหรียญส่วนที่เกินมาทันที
                    elif (coin_total - memory_total_amount) * state.current_price >= MIN_TRADE_THB:
                        extra_amt = coin_total - memory_total_amount
                        # Unlimited Grid: เพิ่มไม้ใหม่ได้เสมอ (ไม่มีเพดาน)
                        logger.info(f"🔄 [SYNC UP] พบ {coin} เกินมาในกระเป๋า: {extra_amt:.4f} -> เพิ่มเข้าไม้ที่ {len(state.layers)+1}")
                        state.layers.append({"price": state.current_price, "amount": extra_amt})
                        update_db_layers(coin, state.layers)

                    # 1. SELL LOGIC (Aggregate Position - ขายยกพอร์ตเมื่อกำไรเฉลี่ยถึงเป้า)
                    if state.layers:
                        total_amount = sum(l.get('amount', 0) for l in state.layers)
                        # คำนวณต้นทุนรวมทั้งหมด (รวมค่าธรรมเนียมซื้อ 0.25% ของแต่ละไม้)
                        total_cost_with_fees = sum(l.get('price', 0) * l.get('amount', 0) * 1.0025 for l in state.layers)
                        
                        if total_amount > 0:
                            avg_net_buy_price = total_cost_with_fees / total_amount
                            val_net_sell = state.current_price * 0.9975 # หักค่าธรรมเนียมขาย 0.25%
                            
                            # 📐 PROFIT CALCULATION (NET)
                            # ต้นทุนรวม (บวกค่าธรรมเนียมซื้อ 0.25%) -> avg_net_buy_price
                            # ราคาขายหักค่าธรรมเนียม 0.25% -> val_net_sell
                            profit_ratio_net = (val_net_sell / avg_net_buy_price) - 1
                            
                            # ปรับเป้าหมายกำไรเป็น 1.0% สุทธิ (หลังหักค่าธรรมเนียมทั้งหมดแล้ว)
                            # เพื่อให้คุ้มค่าธรรมเนียมและเห็นกำไรชัดเจนขึ้น
                            if profit_ratio_net >= 0.01:
                                state.is_trading = True
                                try:
                                    amt_clean = self.driver.clean_amount(coin_avail)
                                    if amt_clean * state.current_price >= MIN_TRADE_THB:
                                        res = await self.driver.send_request("POST", "/api/v3/market/place-ask", {"sym":v3_sym,"amt":amt_clean,"rat":0,"typ":"market"})
                                        if res.get("error") == 0:
                                            thb_received = amt_clean * state.current_price * 0.9975
                                            actual_profit_thb = thb_received - total_cost_with_fees
                                            
                                            layers_count = len(state.layers)
                                            state.layers = []
                                            update_db_layers(coin, [])
                                            save_trade(coin, "SELL", state.current_price, amt_clean, actual_profit_thb)
                                            await self.send_tg(f"💰 *[PROFIT ALL]* ขาย {coin} ล้างพอร์ตสำเร็จ! ({layers_count} ไม้)\n📈 กำไรสุทธิรวม: `+{actual_profit_thb:.2f}` THB (`{profit_ratio_net*100:.2f}%`) ✅")
                                finally:
                                    state.is_trading = False

                    # 2. BUY LOGIC (เฉพาะเหรียญใน Whitelist เท่านั้น)
                    if coin in allowed_labels:
                        if not state.layers and thb_avail >= dynamic_amt:
                            state.is_trading = True
                            try:
                                # อัปเดต State หลอกไว้ก่อนกันซื้อซ้ำ (Optimistic Update)
                                temp_entry = {"price": state.current_price, "amount": 0}
                                state.layers.append(temp_entry) 
                                
                                res = await self.driver.send_request("POST", "/api/v3/market/place-bid", {"sym":v3_sym,"amt":dynamic_amt,"rat":0,"typ":"market"})
                                if res.get("error") == 0:
                                    received_amt = (dynamic_amt * 0.9975) / state.current_price
                                    temp_entry['amount'] = received_amt # ใส่จำนวนเหรียญจริง
                                    update_db_layers(coin, state.layers)
                                    save_trade(coin, "BUY", state.current_price, dynamic_amt)
                                    asyncio.create_task(self.send_tg(f"🎯 *[DYNAMIC BUY]* เริ่มไม้แรก {coin}\n💰 ยอด: `{dynamic_amt:.2f}` THB | ได้เหรียญ: `{received_amt:.4f}`"))
                                else:
                                    state.layers.remove(temp_entry) # ถ้าซื้อพลาดให้เอาออก
                            finally:
                                state.is_trading = False

                        elif state.layers and len(state.layers) < current_max_layers and thb_avail >= dynamic_amt:
                            min_p = min(l['price'] for l in state.layers)
                            current_step = state.get_dynamic_grid_step(len(state.layers))
                            target = min_p * (1 - current_step)
                            
                            if state.current_price <= target:
                                state.is_trading = True
                                try:
                                    # อัปเดต State หลอกไว้ก่อนกันซื้อซ้ำ
                                    temp_entry = {"price": state.current_price, "amount": 0}
                                    state.layers.append(temp_entry)
                                    
                                    res = await self.driver.send_request("POST", "/api/v3/market/place-bid", {"sym":v3_sym,"amt":dynamic_amt,"rat":0,"typ":"market"})
                                    if res.get("error") == 0:
                                        received_amt = (dynamic_amt * 0.9975) / state.current_price
                                        temp_entry['amount'] = received_amt
                                        update_db_layers(coin, state.layers)
                                        save_trade(coin, "BUY", state.current_price, dynamic_amt)
                                        await self.send_tg(f"🚀 *[GRID FILL]* ช้อน {coin} ไม้ที่ {len(state.layers)}\n📉 Step: `{current_step*100:.2f}%` | ยอด: `{dynamic_amt:.2f}` THB")
                                    else:
                                        state.layers.remove(temp_entry) # ถ้าซื้อพลาดให้เอาออก
                                finally:
                                    state.is_trading = False

                # --- 3. เก็บสถิติรายวัน (Snapshot) และบันทึกประวัติราคา ---
                today_profit = get_today_profit()
                if int(time.time()) % 3600 < 2: 
                    save_snapshot(total_equity, today_profit, thb_avail)
                    self.save_history()

                await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"Logic Error: {e}")
                await asyncio.sleep(5)

    def save_history(self):
        try:
            data = {coin: s.to_dict() for coin, s in self.states.items()}
            with open("history.json", "w") as f:
                json.dump(data, f)
        except: pass

    def load_history(self):
        try:
            if os.path.exists("history.json"):
                with open("history.json", "r") as f:
                    data = json.load(f)
                    for coin, hist in data.items():
                        if coin in self.states: self.states[coin].from_list(hist)
                logger.info("🧠 Loaded price history from disk.")
        except: pass
    async def run_all(self):
        self.loop = asyncio.get_running_loop() # 🔧 จำ Loop หลักไว้
        init_db()
        stored_layers = load_db_layers()
        for coin, layers in stored_layers.items():
            if coin not in self.states:
                self.states[coin] = CoinState(coin)
            self.states[coin].layers = layers
        self.load_history()
        
        # 🚀 โหลด Balance และข้อมูลครั้งแรกทันที (Pre-load) เพื่อให้ Telegram กดแล้วเห็นเลย
        try:
            bal_res = await self.driver.send_request("POST", "/api/v3/market/balances")
            if bal_res.get("error") == 0:
                raw_result = bal_res.get("result", {})
                if isinstance(raw_result, list):
                    self.current_balances = { item['symbol'].upper(): item for item in raw_result if 'symbol' in item }
                else:
                    self.current_balances = { k.upper(): {**v, 'symbol': k} for k, v in raw_result.items() }
            logger.info("💰 Initial Balance Loaded.")
        except Exception as e:
            logger.error(f"Initial Balance Error: {e}")

        await self.send_tg("🚀 *Turbo DGT v9.0* (Grid All) Online!")
        await asyncio.gather(self.ws_handler(), self.trading_logic())

if __name__ == "__main__":
    # 🔒 DIAGNOSTIC LOCK: ใส่กลับมาเพื่อเช็คว่ามีตัวอื่นรันซ้อนไหม
    import socket
    import sys
    try:
        _lock_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        _lock_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        _lock_socket.bind(("127.0.0.1", 25006))
        _lock_socket.listen(1)
        print("✅ Lock Port 25006 successful. No other instances found.")
    except Exception:
        print("🚨 [DIAGNOSTIC] มีบอทตัวอื่นรันอยู่แน่นอน! (Port 25006 in use)")
        sys.exit(1)

    bot_v8 = TurboDGT()
    print("🚀 Turbo DGT v9.0 'Grid All' is starting in FOREGROUND mode...")
    print("📌 You can see live logs below. Press Ctrl+C to stop.")
    # 🧵 แยก Thread สำหรับ Telegram โดยเฉพาะ (ทำให้กดปุ่มแล้วตอบทันที)
    def run_tele():
        while bot_v8.running:
            try:
                # 🔧 FIX: ล้างการเชื่อมต่อเก่าและรอให้ Server Telegram เคลียร์ Cache
                bot_v8.bot.remove_webhook()
                time.sleep(5) 
                logger.info("🗑️ Cleared existing Telegram connections.")
                bot_v8.bot.infinity_polling(timeout=20, long_polling_timeout=10, skip_pending=True)
            except Exception as e:
                logger.error(f"Telegram Error: {e}")
                time.sleep(5)

    threading.Thread(target=run_tele, daemon=True).start()
    
    # 🌐 รัน Dashboard ใน Thread แยก (เปลี่ยนเป็นพอร์ต 5005)
    threading.Thread(target=lambda: bot_v8.app.run(host="0.0.0.0", port=5005, use_reloader=False), daemon=True).start()
    
    # 🎯 รัน Trading Logic หลัก
    asyncio.run(bot_v8.run_all())
