import sqlite3
import os

# Base paths to check
DB_PATHS = [
    "data/reposter.db",
    "app/data/reposter.db",
    "data/test_chaos.db",
    "data/test_stuck.db",
    "data/test_gap.db",
    "data/test_features.db"
]

def migrate_db(path):
    if not os.path.exists(path):
        return
    
    print(f"Checking {path}...")
    conn = sqlite3.connect(path)
    cursor = conn.cursor()
    
    # Check if columns already exist
    cursor.execute("PRAGMA table_info(repost_pairs)")
    columns = [row[1] for row in cursor.fetchall()]
    
    try:
        if "loop_history" not in columns:
            print(f"  + Adding loop_history")
            cursor.execute("ALTER TABLE repost_pairs ADD COLUMN loop_history BOOLEAN DEFAULT 0")
        
        if "alerted_3d" not in columns:
            print(f"  + Adding alerted_3d")
            cursor.execute("ALTER TABLE repost_pairs ADD COLUMN alerted_3d BOOLEAN DEFAULT 0")
            
        if "total_posts_source" not in columns:
            print(f"  + Adding total_posts_source")
            cursor.execute("ALTER TABLE repost_pairs ADD COLUMN total_posts_source INTEGER DEFAULT 0")
            
        conn.commit()
    except Exception as e:
        print(f"  ! Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    print("Mister Reposter Database Migrator")
    print("=================================")
    for p in DB_PATHS:
        migrate_db(p)
    print("Done.")
