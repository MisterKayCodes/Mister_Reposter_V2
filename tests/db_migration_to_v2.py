"""
DATABASE MIGRATION: V1 -> V2
Adds the 'next_allowed_post_at' column to the 'repost_pairs' table.
"""
import sqlite3
import os

DB_PATH = "data/reposter.db"

def migrate():
    if not os.path.exists(DB_PATH):
        print(f"❌ Database not found at {DB_PATH}")
        return

    print(f"🚀 Starting migration on {DB_PATH}...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Check if column exists
        cursor.execute("PRAGMA table_info(repost_pairs)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if "next_allowed_post_at" not in columns:
            print("  Adding 'next_allowed_post_at' column...")
            cursor.execute("ALTER TABLE repost_pairs ADD COLUMN next_allowed_post_at DATETIME")
            conn.commit()
            print("  ✅ Column added successfully.")
        else:
            print("  ℹ️ Column 'next_allowed_post_at' already exists. Skipping.")

    except Exception as e:
        print(f"  ❌ Migration failed: {e}")
    finally:
        conn.close()
        print("🏁 Migration complete.")

if __name__ == "__main__":
    migrate()
