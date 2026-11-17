import sqlite3

def connect():
    d = sqlite3.connect(':memory:')
    d.execute('''
        CREATE TABLE circuit_states (
            service TEXT PRIMARY KEY,
            state TEXT NOT NULL,
            failure_count INTEGER NOT NULL,
            last_failure_time REAL,
            tripped_at REAL
        )
    ''')
    d.commit()
    return d
