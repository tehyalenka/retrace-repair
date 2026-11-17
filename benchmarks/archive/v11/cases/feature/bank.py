from accounts import Accounts
from transfers import transfer

class Bank:
    def __init__(self, balances):
        self.accounts = Accounts(balances)

    def balance(self, account_id):
        return self.accounts.balance(account_id)

    def transfer(self, source, destination, amount):
        transfer(self.accounts.balances, source, destination, amount)

    def transfer_many(self, transfers):
        raise NotImplementedError('batch transfers not implemented')
