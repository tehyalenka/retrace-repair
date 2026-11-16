from accounts import Account


def transfer(source: Account, destination: Account, amount: int):
    """Transfer a positive integer amount between two accounts."""

    if type(amount) is not int:
        raise ValueError("Amount must be an integer and not a boolean.")

    if amount <= 0:
        raise ValueError("Transfer amount must be positive.")

    if source is destination:
        raise ValueError("Cannot transfer to the same account.")

    if source.balance < amount:
        raise ValueError("Insufficient funds.")

    source.balance -= amount
    destination.balance += amount
