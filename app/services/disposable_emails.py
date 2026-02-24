from typing import Set

DISPOSABLE_DOMAINS: Set[str] = {
    "temp-mail.org",
    "guerrillamail.com",
    "mailinator.com",
    "throwaway.email",
    "tempmail.com",
    "fakeinbox.com",
    "sharklasers.com",
    "guerrillamailblock.com",
    "grr.la",
    "dispostable.com",
    "yopmail.com",
    "trashmail.com",
    "trashmail.me",
    "trashmail.net",
    "maildrop.cc",
    "getairmail.com",
    "getnada.com",
    "tempr.email",
    "discard.email",
    "tmpmail.org",
    "tmpmail.net",
    "emailondeck.com",
    "33mail.com",
    "guerrillamail.info",
    "guerrillamail.net",
    "guerrillamail.de",
    "tempail.com",
    "burnermail.io",
    "inboxbear.com",
    "mailnesia.com",
}


def is_disposable_domain(email: str) -> bool:
    """Check if an email address uses a known disposable domain."""
    parts = email.lower().split("@")
    if len(parts) != 2:
        return False
    return parts[1] in DISPOSABLE_DOMAINS


def get_email_local_part(email: str) -> str:
    """Extract the local part (before @) from an email address."""
    parts = email.split("@")
    return parts[0] if parts else ""


def compute_entropy_ratio(text: str) -> float:
    """Compute ratio of unique characters to total length.
    Higher ratio = more random-looking.
    """
    if not text:
        return 0.0
    return len(set(text)) / len(text)
