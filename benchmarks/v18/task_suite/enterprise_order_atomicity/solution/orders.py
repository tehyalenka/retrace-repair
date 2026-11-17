import sqlite3
from storage import connect

class OrderService:
    def __init__(self, db): self.db=db
    def seed(self,sku,qty): self.db.execute('INSERT INTO stock VALUES (?,?)',(sku,qty));self.db.commit()
    def place(self,request_id,sku,qty):
        if not isinstance(qty,int) or isinstance(qty,bool) or qty<=0: raise ValueError('quantity must be positive integer')
        if not request_id: raise ValueError('request_id required')
        try:
            self.db.execute('BEGIN IMMEDIATE')
            prior=self.db.execute('SELECT sku,qty FROM orders WHERE request_id=?',(request_id,)).fetchone()
            if prior:
                self.db.rollback()
                if prior != (sku,qty): raise ValueError('idempotency key reused with different request')
                return True
            changed=self.db.execute('UPDATE stock SET available=available-? WHERE sku=? AND available>=?',(qty,sku,qty)).rowcount
            if not changed:
                self.db.rollback();return False
            self.db.execute('INSERT INTO orders VALUES (?,?,?,?)',(request_id,sku,qty,'placed'))
            self.db.execute('INSERT INTO outbox VALUES (?,?,?)',(request_id,'order_placed',sku))
            self.db.commit();return True
        except Exception:
            self.db.rollback();raise
    def available(self,sku): return self.db.execute('SELECT available FROM stock WHERE sku=?',(sku,)).fetchone()[0]
    def event_count(self): return self.db.execute('SELECT count(*) FROM outbox').fetchone()[0]
