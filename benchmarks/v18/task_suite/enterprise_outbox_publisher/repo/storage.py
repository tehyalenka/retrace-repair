import sqlite3

def connect():
    db = sqlite3.connect(":memory:")
    db.execute("""
        CREATE TABLE outbox (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            aggregate_type TEXT,
            aggregate_id TEXT,
            payload TEXT,
            status TEXT DEFAULT 'PENDING',
            attempts INTEGER DEFAULT 0,
            created_at REAL,
            published_at REAL
        )
    """)
    db.commit()
    return db
