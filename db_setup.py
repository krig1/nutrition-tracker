"""
Sets up the local SQLite cache for USDA FoodData Central results.
Run once: python db_setup.py
"""
import sqlite3

DB_PATH = "foods.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS foods (
            fdc_id INTEGER PRIMARY KEY,
            description TEXT NOT NULL,
            data_type TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS nutrients (
            fdc_id INTEGER NOT NULL,
            nutrient_name TEXT NOT NULL,
            unit TEXT,
            amount_per_100g REAL,
            FOREIGN KEY (fdc_id) REFERENCES foods (fdc_id)
        )
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_nutrients_fdc_id
        ON nutrients (fdc_id)
    """)

    conn.commit()
    conn.close()
    print(f"Database ready at {DB_PATH}")

if __name__ == "__main__":
    init_db()