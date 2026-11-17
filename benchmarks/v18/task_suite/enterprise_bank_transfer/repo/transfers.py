import sqlite3
from storage import connect

class BankTransferService:
    def __init__(self, db):
        self.db = db

    def seed(self, account_id, balance):
        self.db.execute('INSERT INTO accounts VALUES (?,?)', (account_id, balance))
        self.db.commit()

    def transfer(self, transfer_id, source, destination, amount):
        if amount <= 0:
            raise ValueError('amount must be positive')
        # Buggy implementation: no idempotency checks, allows self transfer, no atomic rollback
        s_row = self.db.execute('SELECT balance FROM accounts WHERE id=?', (source,)).fetchone()
        if not s_row or s_row[0] < amount:
            return False
        self.db.execute('UPDATE accounts SET balance=balance-? WHERE id=?', (amount, source))
        self.db.execute('UPDATE accounts SET balance=balance+? WHERE id=?', (amount, destination))
        self.db.execute('INSERT INTO transfers VALUES (?,?,?,?,?)', (transfer_id, source, destination, amount, 'completed'))
        self.db.commit()
        return True

    def balance(self, account_id):
        row = self.db.execute('SELECT balance FROM accounts WHERE id=?', (account_id,)).fetchone()
        return row[0] if row else 0

    def transfer_count(self):
        return self.db.execute('SELECT count(*) FROM transfers').fetchone()[0]
