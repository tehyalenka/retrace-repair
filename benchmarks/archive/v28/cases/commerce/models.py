from dataclasses import dataclass

@dataclass(frozen=True)
class LineItem:
    sku: str
    quantity: int

@dataclass(frozen=True)
class Receipt:
    order_id: str
    total: int
    status: str
