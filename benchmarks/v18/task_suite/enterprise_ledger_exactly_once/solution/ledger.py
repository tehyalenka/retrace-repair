class Ledger:
 def __init__(self,db):self.db=db
 def balance(self,account):
  row=self.db.execute('SELECT cents FROM balances WHERE account=?',(account,)).fetchone()
  return row[0] if row else 0
 def post(self,event_id,account,cents):
  if not event_id or not account or type(cents) is not int or cents==0:raise ValueError('invalid ledger entry')
  try:
   self.db.execute('BEGIN IMMEDIATE')
   row=self.db.execute('SELECT account,cents FROM ledger WHERE event_id=?',(event_id,)).fetchone()
   if row:
    if row!=(account,cents):raise ValueError('conflicting event replay')
    self.db.rollback();return self.balance(account)
   self.db.execute('INSERT INTO ledger VALUES (?,?,?)',(event_id,account,cents))
   self.db.execute('INSERT INTO balances VALUES (?,?) ON CONFLICT(account) DO UPDATE SET cents=cents+excluded.cents',(account,cents))
   self.db.commit();return self.balance(account)
  except Exception:
   self.db.rollback();raise
