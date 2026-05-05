import os
import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()
DB_URL = os.getenv("DATABASE_URL")

try:
    db_pool = pool.SimpleConnectionPool(1, 10, DB_URL)
    print("✅ PostgreSQL Connection Pool Initialized.")
except Exception as e:
    print(f"❌ Connection Pool Error: {e}")
    db_pool = None

def get_connection():
    """Fetches a connection and ensures it is still alive."""
    global db_pool
    if not db_pool:
        return None
    
    try:
        conn = db_pool.getconn()
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
        return conn
    except Exception:
        if conn:
            db_pool.putconn(conn, close=True)
        return db_pool.getconn()

def init_db():
    conn = get_connection()
    if not conn: return
    cursor = conn.cursor()
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY,
        access_token TEXT,
        refresh_token TEXT,
        expires_at REAL,
        height REAL,
        weight REAL,
        goal TEXT,
        daily_calorie_target INTEGER
    )
    """)

    cursor.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name='users' AND column_name='last_active';
    """)
    if not cursor.fetchone():
        cursor.execute("ALTER TABLE users ADD COLUMN last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
        print("✅ Migration: added 'last_active' column.")
    else:
        print("ℹ️ Migration: 'last_active' already exists, skipping.")

    conn.commit()
    cursor.close()
    database.release_connection(conn)
def update_tokens(access_token, refresh_token, expires_at):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET access_token = %s, refresh_token = %s, expires_at = %s WHERE id = 1", 
                   (access_token, refresh_token, expires_at))
    conn.commit()
    cursor.close()
    release_connection(conn)

def get_tokens():
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute("SELECT access_token, refresh_token, expires_at FROM users WHERE id=1")
    row = cursor.fetchone()
    cursor.close()
    release_connection(conn)
    
    if row and row['access_token']:
         return {"access_token": row['access_token'], "refresh_token": row['refresh_token'], "expires_at": row['expires_at']}
    return None

def mark_user_active():
    """Updates the last_active timestamp (Feedback Point 5)."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET last_active = CURRENT_TIMESTAMP WHERE id = 1")
    conn.commit()
    cursor.close()
    release_connection(conn)