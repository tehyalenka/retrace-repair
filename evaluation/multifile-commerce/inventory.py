STOCK = {
    "laptop": 5,
    "mouse": 10,
    "keyboard": 8,
}


def available(product):
    return STOCK.get(product, 0)


def reserve(product, quantity):
    raise NotImplementedError("Implement stock reservation")
