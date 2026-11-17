class Authorization:
 def __init__(self,db):self.db=db;self.cache={}
 def set_permission(self,tenant,user,resource,allowed):
  self.db.execute('INSERT INTO permissions VALUES (?,?,?,?) ON CONFLICT(tenant,user,resource) DO UPDATE SET allowed=excluded.allowed',(tenant,user,resource,int(bool(allowed))))
  self.db.commit()
 def can_read(self,tenant,user,resource):
  key=(user,resource)
  if key not in self.cache:
   row=self.db.execute('SELECT allowed FROM permissions WHERE tenant=? AND user=? AND resource=?',(tenant,user,resource)).fetchone()
   self.cache[key]=bool(row and row[0])
  return self.cache[key]
