"""Language endpoints: word autocomplete + AI sentence suggestions."""
from __future__ import annotations

from fastapi import APIRouter

from backend.models.schemas import (
    SentenceRequest,
    SentenceResponse,
    SuggestRequest,
    SuggestResponse,
)
from backend.services.sentence_generator import sentence_generator
from backend.services.word_builder import word_builder

router = APIRouter(prefix="/api/language", tags=["language"])


@router.post("/suggest", response_model=SuggestResponse)
async def suggest_words(req: SuggestRequest) -> SuggestResponse:
    words = word_builder.suggest(req.prefix, req.limit)
    return SuggestResponse(prefix=req.prefix, words=words)


@router.post("/sentences", response_model=SentenceResponse)
async def suggest_sentences(req: SentenceRequest) -> SentenceResponse:
    sentences = sentence_generator.generate(req.text, req.limit)
    return SentenceResponse(sentences=sentences)
