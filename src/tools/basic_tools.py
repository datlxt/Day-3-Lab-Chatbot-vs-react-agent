"""
Tool implementations for the E-commerce Shopping Assistant.

Each tool is a plain Python function returning a human-readable string.
The agent calls these by name via the TOOL_REGISTRY at the bottom.
"""

# ---------------------------------------------------------------------------
# Mock datasets (pretend these come from a real database / API)
# ---------------------------------------------------------------------------

# Product catalog: name -> {price USD, weight kg, category}
PRODUCTS = {
    # Phones
    "iphone":        {"price": 999,  "weight": 0.2, "category": "phone"},
    "samsung":       {"price": 850,  "weight": 0.2, "category": "phone"},
    "pixel":         {"price": 699,  "weight": 0.2, "category": "phone"},
    "xiaomi":        {"price": 499,  "weight": 0.2, "category": "phone"},
    # Computers
    "laptop":        {"price": 1200, "weight": 2.0, "category": "computer"},
    "macbook":       {"price": 1999, "weight": 1.4, "category": "computer"},
    "tablet":        {"price": 600,  "weight": 0.5, "category": "computer"},
    "monitor":       {"price": 300,  "weight": 4.5, "category": "computer"},
    # Accessories
    "headphones":    {"price": 150,  "weight": 0.3, "category": "accessory"},
    "earbuds":       {"price": 120,  "weight": 0.1, "category": "accessory"},
    "keyboard":      {"price": 80,   "weight": 0.6, "category": "accessory"},
    "mouse":         {"price": 40,   "weight": 0.1, "category": "accessory"},
    "smartwatch":    {"price": 250,  "weight": 0.1, "category": "accessory"},
    "charger":       {"price": 30,   "weight": 0.2, "category": "accessory"},
    "speaker":       {"price": 130,  "weight": 1.0, "category": "accessory"},
    "webcam":        {"price": 90,   "weight": 0.2, "category": "accessory"},
}

# Coupon codes: code -> discount percent
DISCOUNTS = {
    "WINNER":  10,
    "SALE20":  20,
    "VIP50":   50,
    "BLACKFRIDAY": 30,
    "NEWYEAR": 25,
    "STUDENT": 15,
    "FREESHIP": 0,   # special: handled as free shipping in description, 0% off goods
    "WELCOME5": 5,
}

# Shipping fee (USD) by destination city
SHIPPING = {
    "hanoi":     5,
    "hcm":       7,
    "danang":    6,
    "haiphong":  6,
    "cantho":    8,
    "hue":       7,
    "nhatrang":  8,
    "vungtau":   7,
    "singapore": 15,
    "bangkok":   18,
    "tokyo":     25,
}

# Stock availability: product -> units in stock
STOCK = {
    "iphone": 12, "samsung": 8, "pixel": 0, "xiaomi": 25,
    "laptop": 5, "macbook": 3, "tablet": 0, "monitor": 10,
    "headphones": 40, "earbuds": 60, "keyboard": 100, "mouse": 0,
    "smartwatch": 7, "charger": 200, "speaker": 15, "webcam": 9,
}


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

import ast
import operator

# Only these AST node operators are allowed -> no eval(), no attribute access,
# no calls, no name lookups. Power (**) is intentionally excluded to block
# DoS expressions like 2**99999999 that would freeze the process.
_ALLOWED_BINOPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Mod: operator.mod,
    ast.FloorDiv: operator.floordiv,
}
_ALLOWED_UNARYOPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


def _safe_eval(node):
    """Recursively evaluate a parsed arithmetic AST, rejecting anything unsafe."""
    if isinstance(node, ast.Expression):
        return _safe_eval(node.body)
    if isinstance(node, ast.Constant):  # numbers only
        if isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            return node.value
        raise ValueError("only numeric literals are allowed")
    if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_BINOPS:
        return _ALLOWED_BINOPS[type(node.op)](_safe_eval(node.left), _safe_eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_UNARYOPS:
        return _ALLOWED_UNARYOPS[type(node.op)](_safe_eval(node.operand))
    raise ValueError("unsupported expression")


def calculator(expression: str) -> str:
    """Evaluate a basic arithmetic expression safely (no eval, AST-based)."""
    allowed_chars = set("0123456789+-*/%(). ")
    if not expression or any(char not in allowed_chars for char in expression):
        return "Invalid expression. Only numbers and basic math operators are allowed."
    try:
        tree = ast.parse(expression, mode="eval")
        result = _safe_eval(tree)
    except ZeroDivisionError:
        return "Calculation error: division by zero."
    except Exception as exc:
        return f"Calculation error: {exc}"
    # Show integers without a trailing .0 (e.g. 144 instead of 144.0).
    if isinstance(result, float) and result.is_integer():
        result = int(result)
    return str(result)


def lookup_product_price(product_name: str) -> str:
    """Look up a product's price in USD."""
    key = product_name.strip().lower()
    if key not in PRODUCTS:
        available = ", ".join(sorted(PRODUCTS.keys()))
        return f"No price found for '{product_name}'. Available products: {available}."
    return f"{key}: ${PRODUCTS[key]['price']}"


def get_discount(coupon_code: str) -> str:
    """Look up the discount percentage for a coupon code."""
    key = coupon_code.strip().upper()
    if key not in DISCOUNTS:
        available = ", ".join(sorted(DISCOUNTS.keys()))
        return f"Invalid coupon '{coupon_code}'. No discount (0%). Valid codes: {available}."
    if key == "FREESHIP":
        return "FREESHIP: 0% off goods, but shipping is free."
    return f"{key}: {DISCOUNTS[key]}% off"


def calc_shipping(destination: str) -> str:
    """Calculate the shipping fee (USD) for a destination city."""
    key = destination.strip().lower().replace(" ", "")
    if key not in SHIPPING:
        available = ", ".join(sorted(SHIPPING.keys()))
        return f"No shipping info for '{destination}'. Default fee: $10. Known cities: {available}."
    return f"Shipping to {key}: ${SHIPPING[key]}"


def check_stock(product_name: str) -> str:
    """Check how many units of a product are in stock."""
    key = product_name.strip().lower()
    if key not in STOCK:
        available = ", ".join(sorted(STOCK.keys()))
        return f"No stock info for '{product_name}'. Known products: {available}."
    qty = STOCK[key]
    if qty == 0:
        return f"{key}: OUT OF STOCK (0 units)."
    return f"{key}: {qty} units in stock."


def get_product_weight(product_name: str) -> str:
    """Get the shipping weight (kg) of a product."""
    key = product_name.strip().lower()
    if key not in PRODUCTS:
        available = ", ".join(sorted(PRODUCTS.keys()))
        return f"No weight info for '{product_name}'. Available products: {available}."
    return f"{key}: {PRODUCTS[key]['weight']} kg"


# ---------------------------------------------------------------------------
# Tool registry (what the agent sees)
# ---------------------------------------------------------------------------

TOOL_REGISTRY = [
    {
        "name": "calculator",
        "description": "Run basic arithmetic. Input is a math expression string, e.g. calculator(2 * 999 + 10).",
        "function": calculator,
    },
    {
        "name": "lookup_product_price",
        "description": (
            "Look up a product price in USD. Input is a single product name, e.g. lookup_product_price(iphone). "
            "Available products: iphone, samsung, pixel, xiaomi, laptop, macbook, tablet, monitor, "
            "headphones, earbuds, keyboard, mouse, smartwatch, charger, speaker, webcam."
        ),
        "function": lookup_product_price,
    },
    {
        "name": "get_discount",
        "description": (
            "Look up the discount percentage of a coupon code. Input is a single code, e.g. get_discount(WINNER). "
            "Valid codes: WINNER, SALE20, VIP50, BLACKFRIDAY, NEWYEAR, STUDENT, FREESHIP, WELCOME5."
        ),
        "function": get_discount,
    },
    {
        "name": "calc_shipping",
        "description": (
            "Calculate shipping fee in USD for a destination city. Input is a single city name, e.g. calc_shipping(hanoi). "
            "Known cities: hanoi, hcm, danang, haiphong, cantho, hue, nhatrang, vungtau, singapore, bangkok, tokyo."
        ),
        "function": calc_shipping,
    },
    {
        "name": "check_stock",
        "description": (
            "Check how many units of a product are in stock. Input is a single product name, e.g. check_stock(iphone)."
        ),
        "function": check_stock,
    },
    {
        "name": "get_product_weight",
        "description": (
            "Get the shipping weight in kg of a product. Input is a single product name, e.g. get_product_weight(laptop)."
        ),
        "function": get_product_weight,
    },
]
