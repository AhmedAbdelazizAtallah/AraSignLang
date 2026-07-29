"""
Smart Arabic word builder.

Turns a stream of accepted letters into ranked word suggestions using prefix
search, frequency ranking, Levenshtein spell-correction and Arabic letter
normalisation.
"""
from __future__ import annotations

from functools import lru_cache
from typing import List

from backend.services.arabic_dictionary import load_dictionary

_NORMALISE = str.maketrans(
    {"أ": "ا", "إ": "ا", "آ": "ا", "ى": "ي", "ة": "ه", "ؤ": "و", "ئ": "ي"}
)


def normalise(text: str) -> str:
    return text.translate(_NORMALISE)


@lru_cache(maxsize=1)
def _dictionary():
    d = load_dictionary()
    index = [(w, normalise(w), freq) for w, freq in d.items()]
    return d, index


def _levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cost = 0 if ca == cb else 1
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost))
        prev = cur
    return prev[-1]


class WordBuilder:
    def suggest(self, prefix: str, limit: int = 6) -> List[str]:
        if not prefix:
            return []
        _, index = _dictionary()
        npref = normalise(prefix)

        prefix_hits = [(w, freq) for (w, nw, freq) in index if nw.startswith(npref)]
        prefix_hits.sort(key=lambda t: (-t[1], len(t[0])))
        results = [w for w, _ in prefix_hits]

        if len(results) < limit:
            fuzzy = []
            for (w, nw, freq) in index:
                if w in results:
                    continue
                dist = _levenshtein(npref, nw[: len(npref) + 2])
                if dist <= 2:
                    fuzzy.append((w, freq, dist))
            fuzzy.sort(key=lambda t: (t[2], -t[1]))
            results.extend(w for w, _, _ in fuzzy)

        return results[:limit]

    def best_word(self, letters: List[str]) -> str:
        prefix = "".join(letters)
        suggestions = self.suggest(prefix, limit=1)
        return suggestions[0] if suggestions else prefix


word_builder = WordBuilder()
