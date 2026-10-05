"""Phone cleanup: 10 US digits or None, never a guess."""

import re

from bob_resolve.config import PHONE_DIGITS, US_COUNTRY_CODE


def normalize_phone(raw: str | None) -> str | None:
    digits = re.sub(r"\D", "", raw or "")
    if len(digits) == PHONE_DIGITS + len(US_COUNTRY_CODE) and digits.startswith(US_COUNTRY_CODE):
        digits = digits[len(US_COUNTRY_CODE) :]
    return digits if len(digits) == PHONE_DIGITS else None
