"""
Compact built-in Arabic dictionary + frequency weights.

Ships a curated, high-frequency Arabic wordlist so autocomplete works out of the
box with zero external dependencies. To scale up, drop a UTF-8 wordlist (one
`word<TAB>frequency` per line) at `backend/services/data/words.txt`.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict

_DATA_FILE = Path(__file__).resolve().parent / "data" / "words.txt"

BUILTIN_WORDS: Dict[str, int] = {
    "السلام": 100, "عليكم": 98, "ورحمة": 60, "الله": 95, "وبركاته": 55,
    "أهلا": 90, "وسهلا": 70, "مرحبا": 88, "كيف": 85, "حالك": 80,
    "أنا": 92, "أنت": 84, "نحن": 70, "هم": 60, "هو": 65, "هي": 64,
    "طالب": 78, "طالبة": 60, "في": 99, "كلية": 62, "الذكاء": 58,
    "الاصطناعي": 57, "جامعة": 66, "مدرسة": 55, "معلم": 52, "دكتور": 54,
    "شكرا": 90, "عفوا": 70, "من": 97, "فضلك": 68, "نعم": 88, "لا": 89,
    "اسم": 75, "اسمي": 74, "ما": 91, "هذا": 86, "هذه": 84, "ذلك": 70,
    "اسلام": 72, "اسلوب": 60, "اسلك": 40, "اسلوبي": 35, "استاذ": 66,
    "استطيع": 58, "استخدام": 62, "المنصة": 55, "للتواصل": 50, "تواصل": 52,
    "يمكن": 80, "يجب": 76, "أريد": 78, "أحب": 74, "أعمل": 68, "أدرس": 66,
    "بيت": 70, "باب": 64, "كتاب": 74, "قلم": 66, "ماء": 72, "خبز": 62,
    "صباح": 80, "الخير": 78, "مساء": 76, "النور": 60, "ليلة": 55, "سعيدة": 58,
    "تشرفنا": 55, "معك": 60, "معي": 58, "اليوم": 82, "غدا": 64, "أمس": 60,
    "جيد": 78, "ممتاز": 70, "بخير": 76, "الحمد": 82, "لله": 80,
    "عربي": 60, "لغة": 66, "الإشارة": 58, "حرف": 70, "كلمة": 72, "جملة": 68,
    "مشروع": 64, "تخرج": 60, "ذكاء": 58, "تعلم": 66, "آلة": 50, "بيانات": 55,
}


def _load_external() -> Dict[str, int]:
    words: Dict[str, int] = {}
    if _DATA_FILE.exists():
        for line in _DATA_FILE.read_text(encoding="utf-8").splitlines():
            parts = line.strip().split("\t")
            if not parts or not parts[0]:
                continue
            word = parts[0]
            freq = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 1
            words[word] = max(words.get(word, 0), freq)
    return words


def load_dictionary() -> Dict[str, int]:
    merged = dict(BUILTIN_WORDS)
    merged.update(_load_external())
    return merged
