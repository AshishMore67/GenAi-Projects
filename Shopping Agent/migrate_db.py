import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(__file__), "store.db")


def migrate():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("PRAGMA table_info(orders)")
    cols = [r[1] for r in cur.fetchall()]
    if "user_id" not in cols:
        cur.execute(
            "ALTER TABLE orders ADD COLUMN user_id TEXT NOT NULL DEFAULT 'default_user'"
        )
        print("Added user_id column to orders")
    else:
        print("orders.user_id already exists, skipping")

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS preferences (
            user_id TEXT PRIMARY KEY,
            prefers_organic INTEGER,
            max_price REAL,
            updated_at TEXT DEFAULT (datetime('now'))
        )
        """
    )
    print("Ensured preferences table exists")

    conn.commit()
    conn.close()
    print("Migration complete.")


if __name__ == "__main__":
    migrate()