"""
Deduct value lookup table and interpolation for rut severity scoring.

Based on density percentage and severity level (Low/Medium/High),
returns a deduct value used in pavement condition assessment.
"""

# Deduct value lookup table (Density % -> Low/Medium/High deduct values)
DEDUCT_TABLE = {
    0: {"Low": 0, "Medium": 0, "High": 0},
    2: {"Low": 3, "Medium": 4, "High": 5},
    4: {"Low": 6, "Medium": 7, "High": 8},
    6: {"Low": 9, "Medium": 10, "High": 12},
    8: {"Low": 12, "Medium": 14, "High": 16},
    10: {"Low": 15, "Medium": 17, "High": 20},
    12: {"Low": 17, "Medium": 19, "High": 22},
    14: {"Low": 18, "Medium": 21, "High": 24},
    16: {"Low": 19, "Medium": 22, "High": 26},
    18: {"Low": 20, "Medium": 23, "High": 27},
    20: {"Low": 21, "Medium": 24, "High": 28},
    22: {"Low": 22, "Medium": 26, "High": 29},
    24: {"Low": 23, "Medium": 27, "High": 31},
    26: {"Low": 23, "Medium": 28, "High": 32},
    28: {"Low": 24, "Medium": 29, "High": 33},
    30: {"Low": 24, "Medium": 29, "High": 33},
    32: {"Low": 25, "Medium": 30, "High": 34},
    34: {"Low": 25, "Medium": 31, "High": 36},
    36: {"Low": 26, "Medium": 31, "High": 37},
    38: {"Low": 26, "Medium": 32, "High": 38},
    40: {"Low": 26, "Medium": 32, "High": 38},
    42: {"Low": 27, "Medium": 33, "High": 39},
    44: {"Low": 27, "Medium": 33, "High": 40},
    46: {"Low": 27, "Medium": 34, "High": 41},
    48: {"Low": 27, "Medium": 34, "High": 42},
    50: {"Low": 27, "Medium": 34, "High": 42},
    52: {"Low": 28, "Medium": 35, "High": 43},
    54: {"Low": 28, "Medium": 35, "High": 44},
    56: {"Low": 28, "Medium": 35, "High": 45},
    58: {"Low": 28, "Medium": 35, "High": 45},
    60: {"Low": 28, "Medium": 35, "High": 46},
    62: {"Low": 28, "Medium": 36, "High": 47},
    64: {"Low": 29, "Medium": 36, "High": 48},
    66: {"Low": 29, "Medium": 36, "High": 48},
    68: {"Low": 29, "Medium": 36, "High": 49},
    70: {"Low": 29, "Medium": 36, "High": 50},
    72: {"Low": 29, "Medium": 37, "High": 50},
    74: {"Low": 29, "Medium": 37, "High": 51},
    76: {"Low": 29, "Medium": 37, "High": 51},
    78: {"Low": 29, "Medium": 37, "High": 52},
    80: {"Low": 29, "Medium": 37, "High": 52},
    82: {"Low": 30, "Medium": 37, "High": 53},
    84: {"Low": 30, "Medium": 37, "High": 53},
    86: {"Low": 30, "Medium": 38, "High": 54},
    88: {"Low": 30, "Medium": 38, "High": 54},
    90: {"Low": 30, "Medium": 37, "High": 54},
    92: {"Low": 30, "Medium": 38, "High": 55},
    94: {"Low": 30, "Medium": 38, "High": 55},
    96: {"Low": 30, "Medium": 38, "High": 56},
    98: {"Low": 30, "Medium": 38, "High": 56},
    100: {"Low": 30, "Medium": 38, "High": 56}
}


def get_deduct_value(density_percent: float, severity: str) -> int:
    """
    Get deduct value from lookup table based on density percentage and severity.
    Uses linear interpolation for values between table entries.

    Args:
        density_percent: Density percentage (0-100)
        severity: 'Low', 'Medium', or 'High'

    Returns:
        Deduct value (integer)
    """
    density_percent = max(0, min(100, density_percent))

    lower_key = int(density_percent // 2) * 2
    upper_key = min(100, lower_key + 2)

    if density_percent == lower_key:
        return DEDUCT_TABLE[lower_key][severity]

    lower_val = DEDUCT_TABLE[lower_key][severity]
    upper_val = DEDUCT_TABLE[upper_key][severity]
    fraction = (density_percent - lower_key) / 2.0
    interpolated = lower_val + fraction * (upper_val - lower_val)

    return int(round(interpolated))
