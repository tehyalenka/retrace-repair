def transfer(balances, source, destination, amount):
    if source not in balances or destination not in balances:
        raise ValueError('unknown account')
    if not isinstance(amount, int) or isinstance(amount, bool) or amount <= 0:
        raise ValueError('invalid amount')
    if balances[source] < amount:
        raise ValueError('insufficient funds')
    balances[source] -= amount
    balances[destination] += amount
