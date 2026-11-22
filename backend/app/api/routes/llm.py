"""Endpointy LLM – kontrakt w docs/llm_contract.md. Błąd LLM nigdy nie jest błędem HTTP (200 + source="template")."""
from __future__ import annotations

import datetime as dt

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.api.routes.parcel import _resolve, _validate_date
from app.contracts.models import AnalysisContext
from app.llm import grounding, service
from app.llm.service import FAQ, ChatMessage, ChatResponse, FaqResponse, FaqTopic, SummaryResponse

router = APIRouter(prefix="/api/llm", tags=["llm"])


class ParcelQuery(BaseModel):
    id: str | None = None
    lon: float | None = None
    lat: float | None = None
    date: dt.date | None = None
    crop: str | None = None


class ChatRequest(ParcelQuery):
    messages: list[ChatMessage] = Field(default_factory=list, max_length=40)


async def _grounding(q: ParcelQuery) -> grounding.Grounding:
    as_of = _validate_date(q.date)
    ctx = AnalysisContext(parcel=await _resolve(q.id, q.lon, q.lat), as_of=as_of, crop=q.crop or None)
    return await grounding.build(ctx)


@router.post("/summary", response_model=SummaryResponse)
async def summary(q: ParcelQuery) -> SummaryResponse:
    """„Wytłumacz mi prosto” – streszczenie raportu i 3 zadania (formalność z reguł)."""
    return await service.summary(await _grounding(q))


@router.post("/chat", response_model=ChatResponse)
async def chat(q: ChatRequest) -> ChatResponse:
    """„Zapytaj o swoją działkę” – odpowiedź z cytatami wyłącznie ze źródeł z naszej bazy."""
    return await service.chat(await _grounding(q), q.messages)


class FaqRequest(ParcelQuery):
    topic: FaqTopic


@router.get("/faq/topics")
async def faq_topics() -> list[dict[str, str]]:
    """Stała lista pytań (frontend pokazuje je od razu, odpowiedź liczy się dopiero po rozwinięciu)."""
    return [{"topic": k, "question": v[0]} for k, v in FAQ.items()]


@router.post("/faq", response_model=FaqResponse)
async def faq(q: FaqRequest) -> FaqResponse:
    """Odpowiedź na jedno z pytań – LLM z ugruntowaniem, a bez klucza / przy błędzie – z reguł (source="template")."""
    return await service.faq(await _grounding(q), q.topic)
