import sqlite3
from storage import connect

class OrderService:
    def __init__(self, db): self.db=db
    def seed(self,sku,qty): self.db.execute('INSERT INTO stock VALUES (?,?)',(sku,qty));self.db.commit()
    def place(self,request_id,sku,qty):
        if qty<=0: raise ValueError('quantity must be positive')
        row=self.db.execute('SELECT available FROM stock WHERE sku=?',(sku,)).fetchone()
        if not row or row[0]<qty: return False
        self.db.execute('UPDATE stock SET available=available-? WHERE sku=?',(qty,sku))
        self.db.execute('INSERT OR REPLACE INTO orders VALUES (?,?,?,?)',(request_id,sku,qty,'placed'))
        self.db.execute('INSERT OR REPLACE INTO outbox VALUES (?,?,?)',(request_id,'order_placed',sku))
        self.db.commit()
        return True
    def available(self,sku): return self.db.execute('SELECT available FROM stock WHERE sku=?',(sku,)).fetchone()[0]
    def event_count(self): return self.db.execute('SELECT count(*) FROM outbox').fetchone()[0]
