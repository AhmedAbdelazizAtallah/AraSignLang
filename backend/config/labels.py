"""
Arabic Sign Language label mapping.

✅ This file is aligned EXACTLY with your training `data.yaml`:

    nc: 28
    names:
      0: "ا"   1: "ب"   2: "ت"   3: "ث"   4: "ج"   5: "ح"   6: "خ"
      7: "د"   8: "ذ"   9: "ر"  10: "ز"  11: "س"  12: "ش"  13: "ص"
     14: "ض"  15: "ط"  16: "ظ"  17: "ع"  18: "غ"  19: "ف"  20: "ق"
     21: "ك"  22: "ل"  23: "م"  24: "ن"  25: "ه"  26: "و"  27: "ي"

The model outputs a class id (0..27); we map it straight to the Arabic glyph
below using the SAME order as your data.yaml, so predictions are correct.
"""
from __future__ import annotations

from typing import Dict, List

# Index -> Arabic glyph, IDENTICAL order to data.yaml `names:` (28 letters).
CLASS_NAMES: List[str] = [
    "ا",  # 0
    "ب",  # 1
    "ت",  # 2
    "ث",  # 3
    "ج",  # 4
    "ح",  # 5
    "خ",  # 6
    "د",  # 7
    "ذ",  # 8
    "ر",  # 9
    "ز",  # 10
    "س",  # 11
    "ش",  # 12
    "ص",  # 13
    "ض",  # 14
    "ط",  # 15
    "ظ",  # 16
    "ع",  # 17
    "غ",  # 18
    "ف",  # 19
    "ق",  # 20
    "ك",  # 21
    "ل",  # 22
    "م",  # 23
    "ن",  # 24
    "ه",  # 25
    "و",  # 26
    "ي",  # 27
]

# Here the class name IS already the Arabic glyph, so the map is identity.
ARABIC_GLYPH: Dict[str, str] = {name: name for name in CLASS_NAMES}

# No control tokens in this model (letters only).
CONTROL_TOKENS: set[str] = set()


def glyph_for(class_name: str) -> str:
    """Return the Arabic glyph for a given class name."""
    return ARABIC_GLYPH.get(class_name, class_name)


def is_control(class_name: str) -> bool:
    """Return True if the class is a control token (none in this model)."""
    return class_name in CONTROL_TOKENS
