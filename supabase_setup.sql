-- 1. ตารางเก็บประวัติการเทรด (Trades History)
CREATE TABLE IF NOT EXISTS trades (
    id SERIAL PRIMARY KEY,
    coin TEXT NOT NULL,
    side TEXT NOT NULL,         -- 'BUY' หรือ 'SELL'
    price DOUBLE PRECISION,
    amount DOUBLE PRECISION,
    profit DOUBLE PRECISION DEFAULT 0,
    ts TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 2. ตารางเก็บไม้ที่ค้างอยู่ในพอร์ต (Active Layers)
CREATE TABLE IF NOT EXISTS layers (
    id SERIAL PRIMARY KEY,
    coin TEXT NOT NULL,
    price DOUBLE PRECISION NOT NULL,
    amount DOUBLE PRECISION NOT NULL,
    ts TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 3. ตารางเก็บประวัติกำไรและพอร์ตรายวัน (Daily Snapshots)
CREATE TABLE IF NOT EXISTS daily_snapshots (
    ts DATE PRIMARY KEY,
    total_equity DOUBLE PRECISION,
    today_profit DOUBLE PRECISION,
    balance_thb DOUBLE PRECISION
);

-- 4. ตารางเก็บประวัติราคาสำหรับคำนวณสถิติ (Price History JSON)
CREATE TABLE IF NOT EXISTS bot_history (
    coin TEXT PRIMARY KEY,
    history_json TEXT,          -- เก็บประวัติราคาเป็น JSON Array
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- เพิ่ม Index เพื่อให้บอทเรียกดูข้อมูลได้รวดเร็วขึ้น
CREATE INDEX IF NOT EXISTS idx_trades_coin ON trades(coin);
CREATE INDEX IF NOT EXISTS idx_layers_coin ON layers(coin);
CREATE INDEX IF NOT EXISTS idx_trades_ts ON trades(ts desc);
