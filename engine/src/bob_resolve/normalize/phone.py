"""Phone cleanup: 10 US digits or None, never a guess. Placeholder numbers become None."""

import re

from bob_resolve.config import PHONE_DIGITS, PLACEHOLDER_PHONES, US_COUNTRY_CODE


def normalize_phone(raw: str | None) -> str | None:
    digits = re.sub(r"\D", "", raw or "")
    if len(digits) == PHONE_DIGITS + len(US_COUNTRY_CODE) and digits.startswith(US_COUNTRY_CODE):
        digits = digits[len(US_COUNTRY_CODE) :]
    if len(digits) != PHONE_DIGITS or digits in PLACEHOLDER_PHONES or len(set(digits)) == 1:
        return None
    return digits
