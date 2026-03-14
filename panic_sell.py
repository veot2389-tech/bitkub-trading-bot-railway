import json
import asyncio
import logging
from bitkub_async import BitkubAsyncDriver

# --- LOGGING ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("Panic-Sell")

async def do_panic_sell():
    try:
        with open("config.json") as f:
            cfg = json.load(f)
        
        API_KEY = cfg.get("api_key", "")
        API_SECRET = cfg.get("api_secret", "")
        
        driver = BitkubAsyncDriver(API_KEY, API_SECRET)
        
        logger.info("🔥 [PANIC SELL] กำลังดึงข้อมูลกระเป๋าเพื่อเทขายทั้งหมด...")
        
        # 1. ดึง Balance ทั้งหมด
        bal_res = await driver.send_request("GET", "/api/v3/market/balances")
        if bal_res.get("error") != 0:
            logger.error(f"❌ ดึงยอดเงินไม่สำเร็จ: {bal_res.get('message')}")
            return

        balances = bal_res.get("result", [])
        if not balances:
            logger.info("ℹ️ ไม่พบเหรียญในพอร์ต")
            return

        for item in balances:
            coin = item['symbol'].upper()
            if coin == "THB": continue
            
            avail = float(item.get('available', 0))
            if avail > 0:
                v3_sym = f"{coin.lower()}_thb"
                amt_clean = driver.clean_amount(avail)
                
                # ตรวจสอบขั้นต่ำ (ประมาณ 5 บาท) เพื่อไม่ให้ Error
                # ดึงราคาทิกเกอร์ก่อน
                ticker = await driver.send_request("GET", f"/api/v3/market/ticker?sym={v3_sym}")
                if ticker.get("error") == 0:
                    last_price = float(ticker.get("result", {}).get("last", 0))
                    if last_price * avail < 5:
                        logger.info(f"⏭️ ข้าม {coin} (มูลค่าน้อยกว่า 5 บาท)")
                        continue
                
                logger.info(f"🚀 กำลังขาย {coin}: {amt_clean} หน่วยที่ราคาตลาด...")
                res = await driver.send_request("POST", "/api/v3/market/place-ask", {
                    "sym": v3_sym,
                    "amt": amt_clean,
                    "rat": 0, # 0 = Market Price
                    "typ": "market"
                })
                
                if res.get("error") == 0:
                    logger.info(f"✅ ขาย {coin} สำเร็จ!")
                else:
                    logger.error(f"❌ ขาย {coin} พลาด: {res.get('message')}")
        
        logger.info("🏁 [FINISHED] ดำเนินการ Panic Sell เรียบร้อยแล้ว")
        
        # ล้างไฟล์ DB state เพื่อให้บอทเริ่มใหม่ถ้าจะรันอีกครั้ง
        if os.path.exists("bot_state.db"):
            import sqlite3
            conn = sqlite3.connect("bot_state.db")
            c = conn.cursor()
            c.execute("DELETE FROM layers")
            conn.commit()
            conn.close()
            logger.info("🛠️ ล้างสถานะกริตค้างใน DB เรียบร้อย")

    except Exception as e:
        logger.error(f"⚠️ เกิดข้อผิดพลาด: {e}")

if __name__ == "__main__":
    import os
    asyncio.run(do_panic_sell())
