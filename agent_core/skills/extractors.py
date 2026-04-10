from __future__ import annotations
import re


def extract_number(text: str) -> float | None:
    """
    Pulls the first meaningful number out of a text string.

    "Veterans Administration: 507 million dollars" → 507000000.0
    "Highest claim: 103,375 million dollars"       → 103375000000.0
    "Page 42"                                      → 42.0
    "3.5 percent"                                  → 0.035
    """
    text = text.lower().replace(",", "")

    patterns = [
        (r"([\d.]+)\s*trillion", lambda m: float(m.group(1)) * 1_000_000_000_000),
        (r"([\d.]+)\s*billion",  lambda m: float(m.group(1)) * 1_000_000_000),
        (r"([\d.]+)\s*million",  lambda m: float(m.group(1)) * 1_000_000),
        (r"([\d.]+)\s*percent",  lambda m: float(m.group(1)) / 100),
        (r"([\d.]+)%",           lambda m: float(m.group(1)) / 100),
        (r"([\d.]+)",            lambda m: float(m.group(1))),
    ]

    for pattern, converter in patterns:
        match = re.search(pattern, text)
        if match:
            return converter(match)

    return None


def extract_date(text: str) -> tuple[int, int | None] | None:
    """
    Pulls a year and optional month out of text.

    "January 1985"   → (1985, 1)
    "Fiscal Year 1934" → (1934, None)
    "December 1998"  → (1998, 12)
    "Calendar Year 1995" → (1995, None)
    """
    months = {
        "january": 1, "february": 2, "march": 3,
        "april": 4, "may": 5, "june": 6,
        "july": 7, "august": 8, "september": 9,
        "october": 10, "november": 11, "december": 12,
    }

    text_lower = text.lower()

    for month_name, month_num in months.items():
        pattern = rf"{month_name}\s+(\d{{4}})"
        match = re.search(pattern, text_lower)
        if match:
            return (int(match.group(1)), month_num)

    year_match = re.search(r"\b(\d{4})\b", text)
    if year_match:
        return (int(year_match.group(1)), None)

    return None


def extract_table_value(text: str, label: str) -> float | None:
    """
    Finds a labeled value in a table row.

    text  = "Veterans Administration (includes public works): 507"
    label = "Veterans Administration"
    → 507.0

    text  = "Highest claim on a single country: 103,375"
    label = "Highest claim"
    → 103375.0
    """
    pattern = rf"{re.escape(label.lower())}[^:]*:\s*([\d,\.]+)"
    match = re.search(pattern, text.lower())
    if match:
        return float(match.group(1).replace(",", ""))
    return None