import os
import psycopg2
from dotenv import load_dotenv

# Load Environment Variables
load_dotenv()
DATABASE_URL = os.environ.get("DATABASE_URL")

def apply_migrations():
    if not DATABASE_URL:
        print("❌ Error: DATABASE_URL not found in environment variables.")
        print("   Please set DATABASE_URL (e.g., export DATABASE_URL=...)")
        return

    print("🔍 Connecting to Supabase...")
    try:
        conn = psycopg2.connect(DATABASE_URL, sslmode='require')
        cur = conn.cursor()
        
        # Read migration file
        migration_path = os.path.join("supabase", "migrations", "20240314000000_init_schema.sql")
        if not os.path.exists(migration_path):
            print(f"❌ Error: Migration file not found at {migration_path}")
            return
            
        with open(migration_path, "r", encoding="utf-8") as f:
            sql = f.read()
            
        print("🚀 Applying migrations...")
        cur.execute(sql)
        conn.commit()
        
        print("✅ Migration applied successfully!")
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    apply_migrations()
