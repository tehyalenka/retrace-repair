import sqlite3

def connect():
    d = sqlite3.connect(':memory:')
    d.execute('''
        CREATE TABLE buckets (
            key TEXT PRIMARY KEY,
            capacity REAL NOT NULL,
            refill_rate REAL NOT NULL,
            tokens REAL NOT NULL,
            last_updated REAL NOT NULL
        )
    ''')
    d.commit()
    return d
