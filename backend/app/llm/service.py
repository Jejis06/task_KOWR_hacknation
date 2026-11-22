"""„Wytłumacz mi prosto” i „Zapytaj o swoją działkę” – LLM z ugruntowaniem i zapasem z szablonów."""
from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.config import settings
from app.core.cache import cache_get, cache_set, make_key
from app.llm import openai_client
from app.llm.grounding import FORMALITY_PL, Grounding

Formality = Literal["none", "notification", "permit", "depends"]
DISCLAIMER = "Informacja orientacyjna, nie porada prawna. Ostateczną decyzję podejmują Wody Polskie, starostwo i ARiMR."
EASE = {"none": 0, "notification": 1, "depends": 2, "permit": 3}
SUMMARY_TTL_S = 6 * 3600

STYLE = """Piszesz dla polskiego rolnika, często starszego (70+), bez wiedzy technicznej.
Zasady: prosty polski, krótkie zdania, zero żargonu (zamiast „KBW” pisz „bilans opadów i parowania”), liczby z jednostkami,
zwracaj się per „Ty”. Opieraj się WYŁĄCZNIE na faktach z sekcji KONTEKST. Nie zmieniaj oceny, formalności, opłat ani statusów
naborów – są wyliczone regułami. Jeśli czegoś nie ma w kontekście, powiedz wprost, że tego nie wiesz. Nie obiecuj dotacji,
gdy nabór jest zamknięty. Nie podawaj adresów www ani numerów artykułów spoza kontekstu."""


class TodoItem(BaseModel):
    text: str
    formality: Formality = "none"
    measure_id: str | None = None


class SummaryResponse(BaseModel):
    headline: str
    paragraphs: list[str] = Field(default_factory=list)
    todo: list[TodoItem] = Field(default_factory=list)
    source: Literal["llm", "template"] = "template"
    model: str | None = None
    disclaimer: str = DISCLAIMER


class Citation(BaseModel):
    title: str
    url: str | None = None


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=1000)


class ChatResponse(BaseModel):
    answer: str
    citations: list[Citation] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)
    source: Literal["llm", "template"] = "template"
    model: str | None = None


def _sorted_recs(g: Grounding) -> list[dict[str, Any]]:
    """Kolejność do „co zrobić”: najpierw to, co wolno od razu, potem wg priorytetu z reguł."""
    return sorted(g.recs, key=lambda r: (EASE.get(r.get("formality") or "none", 9), r.get("priority") or 9))


def _todo_text(r: dict[str, Any]) -> str:
    f = r.get("formality") or "none"
    t = r.get("title") or r["measure_id"]
    if f == "notification":
        return f"{t} – najpierw zgłoszenie wodnoprawne" + (f" (opłata {r['fee_pln']:.2f} zł)".replace(".", ",") if r.get("fee_pln") else "") + "."
    if f == "permit":
        return f"{t} – najpierw pozwolenie wodnoprawne (złóż przed sezonem)."
    when = f" ({r['when']})" if r.get("when") else ""
    return f"{t}{when}."


# ───────────────────────────── szablony (zapas bez LLM) ─────────────────────────────
def summary_template(g: Grounding) -> SummaryResponse:
    a = (g.analysis or {}).get("assessment")
    if not a:
        return SummaryResponse(headline="Nie mamy dość danych, żeby ocenić wodę na tym polu.",
                               paragraphs=["Spróbuj ponownie za chwilę albo wybierz inną datę. Bez oceny nie podajemy zaleceń."])
    paras = [p for p in (a.get("current_summary"), a.get("historical_summary")) if p]
    ret = next((r for r in g.recs if r.get("group") == "retencja_krajobrazowa"), None)
    if ret:
        paras.append(f"Najpierw zatrzymaj wodę: {ret.get('title', '').lower()}. {ret.get('why') or ''}".strip())
    todo = [TodoItem(text=_todo_text(r), formality=r.get("formality") or "none", measure_id=r["measure_id"])
            for r in _sorted_recs(g)[:3]]
    return SummaryResponse(headline=f"Na Twoim polu: {a.get('current_label_pl') or 'ocena niepewna'}.", paragraphs=paras, todo=todo)


TOPICS = [
    (r"staw|oczk|zbiornik|kopa", ["staw_zgloszenie", "staw_pozwolenie", "oczko_male"]),
    (r"studni|odwiert|pomp", ["studnia_do_30m", "studnia_glebinowa", "zwykle_korzystanie", "abolicja_studnie"]),
    (r"nawadn|deszczown|kropl|podlew", ["nawadnianie_pozwolenie", "pobor_z_cieku", "zwykle_korzystanie"]),
    (r"rów|row|zastaw|meliorac|spółk", ["row_zatrzymanie", "row_przebudowa", "melioracje_utrzymanie"]),
]


def chat_template(g: Grounding, question: str) -> ChatResponse:
    from app.knowledge import loader

    q = question.lower()
    if re.search(r"dotac|pieni|dofinans|ekoschemat|arimr|dopł", q):
        lines = [f"• {f['name']} – {f.get('call_label')}" for r in g.recs for f in r.get("funding") or []]
        uniq = list(dict.fromkeys(lines))
        ans = ("Dla działań z Twojego raportu pasują: \n" + "\n".join(uniq)) if uniq else "W raporcie nie ma programu dla tych działań."
        return ChatResponse(answer=ans + "\n\nAsystent AI jest chwilowo niedostępny – to odpowiedź z katalogu dotacji.",
                            suggestions=["Czy mogę wykopać staw?", "Kiedy siać międzyplon?"])
    for pat, ids in TOPICS:
        if re.search(pat, q):
            items = [loader.get_item("legal_pl", i) for i in ids]
            items = [i for i in items if i]
            ans = "\n".join(f"• {i['title']}: {i['rule']}" for i in items)
            cites = [Citation(title=s.title, url=s.url) for s in g.sources if any(s.title.startswith(i["title"]) for i in items)]
            return ChatResponse(answer=ans + "\n\nAsystent AI jest chwilowo niedostępny – to fragmenty przepisów z naszej bazy.",
                                citations=cites[:4], suggestions=["Ile kosztuje zgłoszenie?", "Jakie dotacje mi przysługują?"])
    return ChatResponse(answer="Asystent AI jest chwilowo niedostępny. Odpowiedź na większość pytań znajdziesz w raporcie: "
                               "ocena wody, przyczyny, co zrobić i czy potrzebne są formalności.",
                        suggestions=["Czy mogę wykopać staw?", "Jakie dotacje mi przysługują?", "Czy mogę nawadniać ze studni?"])


# ───────────────────────────── LLM ─────────────────────────────
SUMMARY_SYS = STYLE + """
Zadanie: streść raport tej działki dla rolnika. Zwróć JSON:
{"headline": "1 zdanie, najważniejsza informacja",
 "paragraphs": ["2–3 akapity po 1–3 zdania: jak jest z wodą teraz i w 10 latach, dlaczego, co najpierw zrobić"],
 "todo": [{"measure_id": "id z listy DZIAŁANIA", "text": "1 zdanie: co i kiedy zrobić, z formalnością i pieniędzmi jeśli są"}]}
todo: dokładnie 3 pozycje (lub mniej, jeśli działań jest mniej), wyłącznie measure_id z listy DZIAŁANIA, najpierw to, co wolno
zrobić od razu. Gdy brak oceny – headline mówi to wprost, todo puste."""

CHAT_SYS = STYLE + """
Zadanie: odpowiadasz na pytania rolnika o JEGO działkę: woda, susza, gleba, uprawa, zatrzymywanie wody, prawo wodne,
formalności, dotacje. Pytania spoza tego zakresu grzecznie odrzuć jednym zdaniem. Odpowiedź max ~120 słów, konkretnie,
z liczbami z kontekstu. Przy przepisach i dotacjach podaj numery źródeł z kontekstu. Zwróć JSON:
{"answer": "tekst", "sources": ["S3", "S7"], "suggestions": ["2–3 krótkie pytania, które rolnik może zadać dalej"]}"""


def _ctx_message(g: Grounding) -> dict[str, str]:
    return {"role": "user", "content": "KONTEKST:\n" + g.text}


async def summary(g: Grounding) -> SummaryResponse:
    key = make_key("llm_summary", id=g.ctx.parcel.id, date=g.ctx.as_of.isoformat(), crop=g.ctx.crop,
                   model=settings.openai_model, v=2)
    if (hit := cache_get(key)) is not None:
        return SummaryResponse.model_validate(hit)
    tpl = summary_template(g)
    if not (g.analysis or {}).get("assessment"):
        return tpl
    out = await openai_client.complete_json(SUMMARY_SYS, [_ctx_message(g)])
    if not out or not out.get("headline"):
        return tpl
    todo: list[TodoItem] = []
    for t in out.get("todo") or []:
        r = g.rec(str(t.get("measure_id") or ""))
        if r and len(todo) < 3 and not any(x.measure_id == r["measure_id"] for x in todo):
            # formalność ZAWSZE z reguł, nigdy z modelu
            todo.append(TodoItem(text=str(t.get("text") or _todo_text(r)), formality=r.get("formality") or "none",
                                 measure_id=r["measure_id"]))
    res = SummaryResponse(headline=str(out["headline"]), paragraphs=[str(p) for p in out.get("paragraphs") or []][:4],
                          todo=todo or tpl.todo, source="llm", model=settings.openai_model)
    cache_set(key, res.model_dump(mode="json"), SUMMARY_TTL_S)
    return res


async def chat(g: Grounding, messages: list[ChatMessage]) -> ChatResponse:
    msgs = messages[-12:]
    question = next((m.content for m in reversed(msgs) if m.role == "user"), "")
    if not question.strip():
        return ChatResponse(answer="Zadaj pytanie o swoje pole, np. „Czy mogę wykopać staw?”.",
                            suggestions=["Czy mogę wykopać staw?", "Jakie dotacje mi przysługują?"])
    out = await openai_client.complete_json(CHAT_SYS, [_ctx_message(g), *({"role": m.role, "content": m.content} for m in msgs)],
                                            max_tokens=900)
    if not out or not out.get("answer"):
        return chat_template(g, question)
    cites, seen = [], set()
    for sid in out.get("sources") or []:
        s = g.source(str(sid).strip("[] "))
        if s and s.sid not in seen:   # tylko źródła z naszej listy – nieznane numery odrzucamy
            seen.add(s.sid)
            cites.append(Citation(title=s.title, url=s.url))
    answer = re.sub(r"\s*\[S\d+\]", "", str(out["answer"])).strip()   # numery źródeł pokazujemy jako linki, nie w tekście
    return ChatResponse(answer=answer, citations=cites[:5], suggestions=[str(x) for x in out.get("suggestions") or []][:3],
                        source="llm", model=settings.openai_model)


__all__ = ["FORMALITY_PL", "ChatMessage", "ChatResponse", "SummaryResponse", "chat", "summary"]
