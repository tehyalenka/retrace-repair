import sqlite3

def connect():
 d=sqlite3.connect(':memory:')
 d.execute('CREATE TABLE ledger (event_id TEXT PRIMARY KEY, account TEXT, cents INTEGER)')
 d.execute('CREATE TABLE balances (account TEXT PRIMARY KEY, cents INTEGER NOT NULL)')
 return d
