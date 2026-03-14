-- 1. สร้างตาราง trades (ประวัติการเทรด)
CREATE TABLE IF NOT EXISTS trades (
    id SERIAL PRIMARY KEY,
    coin TEXT NOT NULL,
    side TEXT NOT NULL,
    price DOUBLE PRECISION NOT NULL,
    amount DOUBLE PRECISION NOT NULL,
    profit DOUBLE PRECISION DEFAULT 0,
    ts TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 2. สร้างตาราง daily_snapshots (สถิติรายวัน)
CREATE TABLE IF NOT EXISTS daily_snapshots (
    ts DATE PRIMARY KEY,
    total_equity DOUBLE PRECISION NOT NULL,
    today_profit DOUBLE PRECISION NOT NULL,
    balance_thb DOUBLE PRECISION NOT NULL
);

-- 3. สร้างตาราง layers (สถานะไม้ค้าง)
CREATE TABLE IF NOT EXISTS layers (
    id SERIAL PRIMARY KEY,
    coin TEXT NOT NULL,
    price DOUBLE PRECISION NOT NULL,
    amount DOUBLE PRECISION NOT NULL
);

-- 4. สร้างตาราง bot_history (ราคาสำหรับการคำนวณ Z-Score)
CREATE TABLE IF NOT EXISTS bot_history (
    coin TEXT PRIMARY KEY,
    history_json TEXT NOT NULL
);

-- เพิ่ม Index เพื่อให้ Query เร็วขึ้น
CREATE INDEX IF NOT EXISTS idx_trades_coin ON trades(coin);
CREATE INDEX IF NOT EXISTS idx_trades_ts ON trades(ts);
