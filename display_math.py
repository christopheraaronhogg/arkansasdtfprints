from decimal import Decimal, ROUND_HALF_UP

def get_display_value(actual: float) -> str:
    """Round to 2 decimals for display using proper rounding"""
    display_decimal = Decimal(str(actual)).quantize(
        Decimal('0.00'), 
        rounding=ROUND_HALF_UP
    )
    return f"{display_decimal:.2f}"

def calculate_from_display(display_str: str) -> Decimal:
    """Use exact displayed value for calculations"""
    return Decimal(display_str)

def price_round(d: Decimal) -> int:
    """Round to nearest whole number using displayed value"""
    return int(d.quantize(Decimal('1'), rounding=ROUND_HALF_UP))

# Usage example:
raw_width = 8.4989376327959  # From image analysis
raw_height = 12.0

# 1. Get display values
display_w = get_display_value(raw_width)  # "8.50"
display_h = get_display_value(raw_height)  # "12.00"

# 2. Use EXACT display values for math
calc_w = calculate_from_display(display_w)  # 8.50 exactly
calc_h = calculate_from_display(display_h)  # 12.00 exactly

# 3. Round dimensions for pricing
final_w = price_round(calc_w)  # 9 (8.50 → 9)
final_h = price_round(calc_h)  # 12

# Calculate area and price
area = final_w * final_h  # 9 * 12 = 108
price = area * Decimal('0.02')  # 108 * 0.02 = 2.16 