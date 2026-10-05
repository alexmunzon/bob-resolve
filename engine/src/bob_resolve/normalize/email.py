"""Email cleanup: trim and lowercase, or None when it is not an address."""


def normalize_email(raw: str | None) -> str | None:
    """Trim and lowercase. Dots in the local part are kept, even for gmail.com."""
    s = (raw or "").strip().lower()
    local, at, domain = s.partition("@")
    if not at or not local or "." not in domain or "@" in domain or " " in s:
        return None
    return s
