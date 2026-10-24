import re
from decimal import Decimal

_AMOUNT = re.compile(r"\$\s*([\d,]+)")


class SourceError(Exception):
    pass


def parse_amount_range(text):
    """'$1,001 - $15,000' → (1001, 15000), 'Over $50,000,000' → (50000000, None)."""
    nums = [Decimal(n.replace(",", "")) for n in _AMOUNT.findall(text or "")]
    if not nums:
        return None, None
    if "over" in text.lower():
        return nums[0], None
    return nums[0], (nums[1] if len(nums) > 1 else nums[0])


OWNER_LABELS = {
    "SP": "배우자",
    "SPOUSE": "배우자",
    "JT": "공동",
    "JOINT": "공동",
    "DC": "자녀",
    "CHILD": "자녀",
    "DEPENDENT CHILD": "자녀",
    "SELF": "본인",
    "": "본인",
}


def owner_label(code):
    return OWNER_LABELS.get((code or "").strip().upper(), code or "본인")


def strip_ns(tag):
    return tag.rsplit("}", 1)[-1]
