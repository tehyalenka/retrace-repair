import sqlite3

def connect():
    d = sqlite3.connect(':memory:')
    d.execute('CREATE TABLE accounts (id TEXT PRIMARY KEY, balance INTEGER)')
    d.execute('CREATE TABLE transfers (id TEXT PRIMARY KEY, source TEXT, destination TEXT, amount INTEGER, status TEXT)')
    d.commit()
    return d
