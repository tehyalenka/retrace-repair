class Ledger:
 def __init__(self,db):self.db=db
 def balance(self,account):
  row=self.db.execute('SELECT cents FROM balances WHERE account=?',(account,)).fetchone()
  return row[0] if row else 0
 def post(self,event_id,account,cents):
  if not isinstance(cents,int):raise ValueError('integer cents required')
  self.db.execute('INSERT OR REPLACE INTO ledger VALUES (?,?,?)',(event_id,account,cents))
  self.db.execute('INSERT INTO balances VALUES (?,?) ON CONFLICT(account) DO UPDATE SET cents=cents+excluded.cents',(account,cents))
  self.db.commit()
  return self.balance(account)
