"""
Arabic dictionary + auto-complete engine.

Provides prefix-based word suggestions ranked by frequency so that as the user
signs letters (e.g. ب ا ب) the app can propose complete words (باب, بابا, ...).

The word list is a curated set of common Arabic words with rough frequency
weights (higher = more common). You can extend WORDS freely, or load an external
newline-separated list via `backend/services/data/arabic_words.txt`.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Tuple

# --------------------------------------------------------------------------- #
# Core curated word list: (word, frequency_weight)
# Grouped by first letter for readability; order does not matter.
# --------------------------------------------------------------------------- #
_BASE_WORDS: List[Tuple[str, int]] = [
    # تحيات ومجاملات
    ("السلام", 100), ("عليكم", 95), ("مرحبا", 98), ("أهلا", 96), ("شكرا", 97),
    ("عفوا", 80), ("مبروك", 70), ("تحية", 60), ("سلام", 90),
    # ضمائر وكلمات وظيفية شائعة
    ("انا", 100), ("انت", 95), ("هو", 90), ("هي", 90), ("نحن", 85), ("هم", 80),
    ("هذا", 95), ("هذه", 90), ("ذلك", 70), ("الذي", 75), ("التي", 70),
    ("في", 100), ("من", 100), ("الى", 95), ("على", 95), ("عن", 85), ("مع", 90),
    ("هل", 85), ("ما", 90), ("ماذا", 80), ("متى", 75), ("اين", 80), ("كيف", 85),
    ("لماذا", 75), ("نعم", 95), ("لا", 98), ("ربما", 60),
    # أفعال شائعة
    ("اريد", 90), ("احب", 88), ("اكل", 80), ("شرب", 75), ("ذهب", 78), ("جاء", 76),
    ("قال", 80), ("فعل", 70), ("عمل", 82), ("درس", 78), ("لعب", 74), ("كتب", 80),
    ("قرأ", 78), ("سمع", 74), ("رأى", 72), ("نام", 70), ("جلس", 70), ("وقف", 68),
    ("ساعد", 76), ("فهم", 74), ("عرف", 76), ("تكلم", 72), ("استطيع", 70),
    # أسماء ومفاهيم شائعة
    ("بيت", 90), ("باب", 85), ("بابا", 88), ("ماما", 88), ("ولد", 80), ("بنت", 80),
    ("رجل", 78), ("امرأة", 74), ("طفل", 76), ("مدرسة", 85), ("جامعة", 82),
    ("كتاب", 88), ("قلم", 80), ("ورقة", 70), ("ماء", 90), ("طعام", 82), ("خبز", 78),
    ("شاي", 74), ("قهوة", 76), ("سيارة", 82), ("طريق", 78), ("مدينة", 78),
    ("بلد", 76), ("عمل", 84), ("وظيفة", 72), ("مال", 78), ("وقت", 84), ("يوم", 88),
    ("ليل", 74), ("نهار", 72), ("صباح", 86), ("مساء", 84), ("سنة", 78), ("شهر", 74),
    ("اسبوع", 72), ("ساعة", 78), ("دقيقة", 70),
    # مشاعر وحالات
    ("سعيد", 82), ("حزين", 74), ("تعبان", 76), ("مريض", 74), ("جائع", 72),
    ("عطشان", 70), ("خائف", 68), ("غاضب", 68), ("بخير", 88), ("جيد", 86),
    ("ممتاز", 78), ("جميل", 80), ("كبير", 78), ("صغير", 78), ("جديد", 76),
    ("قديم", 72), ("سريع", 72), ("بطيء", 66),
    # كلمات دراسية/تقنية (مناسبة لمشروع تخرج)
    ("ذكاء", 78), ("اصطناعي", 74), ("تعلم", 80), ("الة", 70), ("حاسوب", 74),
    ("برنامج", 76), ("مشروع", 80), ("بحث", 74), ("علم", 82), ("لغة", 84),
    ("اشارة", 86), ("يد", 82), ("حرف", 84), ("كلمة", 84), ("جملة", 80),
    # أيام ومناسبات
    ("السبت", 70), ("الاحد", 70), ("الاثنين", 68), ("الثلاثاء", 66),
    ("الاربعاء", 66), ("الخميس", 68), ("الجمعة", 72),
    # جُمل شائعة كوحدات
    ("شكرا لك", 85), ("من فضلك", 88), ("لا بأس", 70), ("ان شاء الله", 80),
    ("الحمد لله", 82), ("كيف حالك", 84), ("صباح الخير", 82), ("مساء الخير", 80),
    ("مع السلامة", 80), ("تصبح على خير", 70), ("اسمي", 82), ("انا بخير", 80),
]

_DATA_FILE = Path(__file__).resolve().parent / "data" / "arabic_words.txt"


def _normalize(text: str) -> str:
    """Normalize Arabic text for tolerant matching (unify alef/hamza, drop tashkeel)."""
    if not text:
        return ""
    # Remove tashkeel (diacritics)
    tashkeel = "".join(chr(c) for c in range(0x064B, 0x0653))
    text = "".join(ch for ch in text if ch not in tashkeel)
    # Unify alef variants and hamza forms to a plain form for matching
    trans = {
        "أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا",
        "ى": "ي", "ئ": "ي", "ؤ": "و", "ة": "ه",
    }
    for a, b in trans.items():
        text = text.replace(a, b)
    return text.strip()


@lru_cache(maxsize=1)
def _load_words() -> List[Tuple[str, int]]:
    """Load and merge the base list with an optional external file."""
    words = dict()
    for w, freq in _BASE_WORDS:
        words[w] = max(freq, words.get(w, 0))

    if _DATA_FILE.exists():
        for line in _DATA_FILE.read_text(encoding="utf-8").splitlines():
            parts = line.strip().split("\t")
            if not parts or not parts[0]:
                continue
            w = parts[0].strip()
            freq = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 50
            words[w] = max(freq, words.get(w, 0))

    # Pre-compute normalized form for each word.
    return [(w, freq) for w, freq in words.items()]


def suggest(prefix: str, limit: int = 6) -> List[str]:
    """Return up to `limit` word suggestions for the given (letters) prefix.

    Matching is prefix-based on a normalized form, ranked by:
      1) exact-prefix match, 2) frequency, 3) shorter words first.
    If prefix is empty, returns the most common words as starters.
    """
    words = _load_words()
    npref = _normalize(prefix)

    if not npref:
        top = sorted(words, key=lambda x: -x[1])[:limit]
        return [w for w, _ in top]

    scored: List[Tuple[str, int, int]] = []  # (word, freq, rank)
    for w, freq in words:
        nw = _normalize(w)
        if nw.startswith(npref):
            scored.append((w, freq, 0))          # best: real prefix
        elif npref in nw:
            scored.append((w, freq, 1))          # contains it somewhere
    scored.sort(key=lambda x: (x[2], -x[1], len(x[0])))
    return [w for w, _, _ in scored[:limit]]


def contains_word(word: str) -> bool:
    """True if the (normalized) word exists in the dictionary."""
    nw = _normalize(word)
    return any(_normalize(w) == nw for w, _ in _load_words())
