"""
AI Arabic sentence generator.

A lightweight, dependency-free suggestion engine that proposes complete Arabic
sentences based on the words built so far, combining templates with keyword
triggers. Fully offline; swap `generate()` for an LLM call if desired.
"""
from __future__ import annotations

from typing import List

STARTERS: List[str] = [
    "السلام عليكم ورحمة الله وبركاته.",
    "أنا طالب في كلية الذكاء الاصطناعي.",
    "كيف حالك؟",
    "يمكن استخدام هذه المنصة للتواصل.",
    "أهلاً وسهلاً بك.",
    "شكراً جزيلاً لك.",
    "صباح الخير.",
    "الحمد لله، أنا بخير.",
]

_TRIGGERS = {
    "سلام": ["السلام عليكم ورحمة الله وبركاته.", "وعليكم السلام."],
    "اهلا": ["أهلاً وسهلاً بك.", "أهلاً بك في منصتنا."],
    "اهل": ["أهلاً وسهلاً بك."],
    "كيف": ["كيف حالك؟", "كيف يمكنني مساعدتك؟"],
    "شكر": ["شكراً جزيلاً لك.", "شكراً على تواصلك."],
    "انا": ["أنا طالب في كلية الذكاء الاصطناعي.", "أنا بخير، شكراً لك."],
    "طالب": ["أنا طالب في كلية الذكاء الاصطناعي."],
    "منصة": ["يمكن استخدام هذه المنصة للتواصل."],
    "صباح": ["صباح الخير.", "صباح النور."],
    "مساء": ["مساء الخير.", "مساء النور."],
}


def _normalise(text: str) -> str:
    table = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ى": "ي", "ة": "ه"})
    return text.translate(table)


class SentenceGenerator:
    def generate(self, current_text: str, limit: int = 5) -> List[str]:
        text = current_text.strip()
        if not text:
            return STARTERS[:limit]

        norm = _normalise(text)
        suggestions: List[str] = []

        for key, options in _TRIGGERS.items():
            if key in norm:
                for opt in options:
                    if opt not in suggestions:
                        suggestions.append(opt)

        for c in [f"{text} من فضلك.", f"{text}؟", f"{text} شكراً لك."]:
            if c not in suggestions:
                suggestions.append(c)

        for s in STARTERS:
            if len(suggestions) >= limit:
                break
            if s not in suggestions:
                suggestions.append(s)

        return suggestions[:limit]


sentence_generator = SentenceGenerator()
