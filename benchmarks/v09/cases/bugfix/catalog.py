from pricing import discounted_total
from tax import add_tax

def checkout(lines, discount, tax_rate):
    subtotal = sum(price * qty for price, qty in lines)
    return add_tax(discounted_total(subtotal, discount), tax_rate)
