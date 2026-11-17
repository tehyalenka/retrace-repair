import sqlite3

def connect():
    db = sqlite3.connect(':memory:')
    db.execute('CREATE TABLE stock (sku TEXT PRIMARY KEY, available INTEGER NOT NULL CHECK(available>=0))')
    db.execute('CREATE TABLE orders (request_id TEXT PRIMARY KEY, sku TEXT NOT NULL, qty INTEGER NOT NULL, status TEXT NOT NULL)')
    db.execute('CREATE TABLE outbox (event_id TEXT PRIMARY KEY, kind TEXT NOT NULL, payload TEXT NOT NULL)')
    return db
