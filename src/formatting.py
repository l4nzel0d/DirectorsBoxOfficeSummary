"""Money formatting shared by the render layers (PDF and HTML).

Amounts are plain ints where 0 means "missing or genuinely zero" (see
models), so both formats print 0 as "-" rather than "$0".
"""

# (size, suffix, decimals), largest first.
_UNITS = ((1_000_000_000, "B", 2), (1_000_000, "M", 1), (1_000, "K", 0))


def money(amount: int) -> str:
    """Format an amount as USD, or '-' when it's 0 (missing/unknown)."""
    return "-" if amount == 0 else f"${amount:,}"


def money_short(amount: int) -> str:
    """Compact USD: $6.12B, $975.8M, $48K, $500; '-' when it's 0. Rounds
    before picking the unit, so 999,950,000 reads $1.00B, not $1000.0M."""
    if amount == 0:
        return "-"
    for size, suffix, decimals in _UNITS:
        value = round(amount / size, decimals)
        if abs(value) >= 1:
            return f"${value:,.{decimals}f}{suffix}"
    return f"${amount:,}"
