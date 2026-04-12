import sqlite3
import os

DB_PATH = "data/reposter.db"
TEST_DB_PATH = "data/test_chaos.db"
TEST_STUCK_PATH = "data/test_stuck.db"
TEST_GAP_PATH = "data/test_gap.db"
TEST_PRIVATE_PATH = "data/test_private.db"

def migrate_db(path):
    if not os.path.exists(path):
        print(f"Skipping {path} (not found)")
        return
    
    conn = sqlite3.connect(path)
    cursor = conn.cursor()
    
    # Check if columns already exist
    cursor.execute("PRAGMA table_info(repost_pairs)")
    columns = [row[1] for row in cursor.fetchall()]
    
    try:
        if "loop_history" not in columns:
            print(f"Adding loop_history to {path}...")
            cursor.execute("ALTER TABLE repost_pairs ADD COLUMN loop_history BOOLEAN DEFAULT 0")
        
        if "alerted_3d" not in columns:
            print(f"Adding alerted_3d to {path}...")
            cursor.execute("ALTER TABLE repost_pairs ADD COLUMN alerted_3d BOOLEAN DEFAULT 0")
            
        conn.commit()
        print(f"Migration successful for {path}")
    except Exception as e:
        print(f"Error migrating {path}: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    migrate_db(DB_PATH)
    # Also migrate test DBs if they exist for consistent testing
    for t_path in [TEST_DB_PATH, TEST_STUCK_PATH, TEST_GAP_PATH, TEST_PRIVATE_PATH]:
        migrate_db(t_path)
