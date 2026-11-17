import sqlite3

def connect():
 d=sqlite3.connect(':memory:')
 d.execute('CREATE TABLE permissions (tenant TEXT, user TEXT, resource TEXT, allowed INTEGER, PRIMARY KEY(tenant,user,resource))')
 return d
