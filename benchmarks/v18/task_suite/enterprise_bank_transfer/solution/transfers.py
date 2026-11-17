import sqlite3
from storage import connect

class BankTransferService:
    def __init__(self, db):
        self.db = db

    def seed(self, account_id, balance):
        if not isinstance(balance, int) or isinstance(balance, bool) or balance < 0:
            raise ValueError('balance must be nonnegative integer')
        self.db.execute('INSERT INTO accounts VALUES (?,?)', (account_id, balance))
        self.db.commit()

    def transfer(self, transfer_id, source, destination, amount):
        if not transfer_id or not source or not destination:
            raise ValueError('identities required')
        if source == destination:
            raise ValueError('self-transfer forbidden')
        if not isinstance(amount, int) or isinstance(amount, bool) or amount <= 0:
            raise ValueError('amount must be positive integer')

        try:
            self.db.execute('BEGIN IMMEDIATE')
            prior = self.db.execute('SELECT source, destination, amount FROM transfers WHERE id=?', (transfer_id,)).fetchone()
            if prior:
                self.db.rollback()
                if prior != (source, destination, amount):
                    raise ValueError('conflicting payload on duplicate transfer')
                return True

            s_row = self.db.execute('SELECT balance FROM accounts WHERE id=?', (source,)).fetchone()
            d_row = self.db.execute('SELECT balance FROM accounts WHERE id=?', (destination,)).fetchone()
            if not s_row or not d_row:
                self.db.rollback()
                raise ValueError('account not found')

            if s_row[0] < amount:
                self.db.rollback()
                return False

            self.db.execute('UPDATE accounts SET balance=balance-? WHERE id=?', (amount, source))
            self.db.execute('UPDATE accounts SET balance=balance+? WHERE id=?', (amount, destination))
            self.db.execute('INSERT INTO transfers VALUES (?,?,?,?,?)', (transfer_id, source, destination, amount, 'completed'))
            self.db.commit()
            return True
        except Exception:
            self.db.rollback()
            raise

    def balance(self, account_id):
        row = self.db.execute('SELECT balance FROM accounts WHERE id=?', (account_id,)).fetchone()
        if not row:
            raise ValueError('unknown account')
        return row[0]

    def transfer_count(self):
        return self.db.execute('SELECT count(*) FROM transfers').fetchone()[0]
