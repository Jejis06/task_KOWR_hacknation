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
gdy nabór jest zamknięty. Nie podawaj adresów www ani numerów artykułów spoza kontekstu.
NIE licz samodzielnie nowych kwot, sum ani iloczynów (np. stawka × hektary) – podawaj liczby dokładnie tak, jak są
w kontekście (np. „437,60 zł za hektar”); rachunki zostaw rolnikowi lub doradcy."""


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
                   model=settings.openai_model, v=3)
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


# ───────────────────── FAQ: rozwijane pytania nad raportem ─────────────────────
FaqTopic = Literal["sytuacja", "zatrzymac", "koszty", "zysk", "dotacje", "formalnosci", "kiedy"]
FAQ: dict[str, tuple[str, str]] = {
    "sytuacja": ("Co się dzieje z wodą na moim polu?",
                 "Streść ocenę: jak jest teraz, jak bywało w 10 latach, kiedy najgorzej i dlaczego."),
    "zatrzymac": ("Jak mogę zatrzymać wodę na moim polu?",
                  "Wymień działania z listy DZIAŁANIA w kolejności: retencja (miejsca na działce), potem gleba. Przy każdym: "
                  "gdzie, jak, kiedy. Nawadnianie tylko na końcu, jeśli jest w kontekście."),
    "koszty": ("Ile to będzie kosztować?",
               "Podaj tylko koszty z kontekstu: opłaty urzędowe, widełki kosztu oczka. Dla działań bez kwoty w kontekście napisz, "
               "od czego zależy koszt (nasiona, praca, sprzęt), ale NIE wymyślaj kwot."),
    "zysk": ("Co na tym zyskam?",
             "Opisz korzyści z kontekstu: ile wody zatrzyma oczko (m³) i jaki to procent niedoboru, ograniczenie strat plonu "
             "(jeśli jest szacunek spadku plonu), płatności ekoschematów (stawki z kontekstu). Nie wyceniaj plonu w złotych, "
             "jeśli kontekst tego nie podaje – powiedz to wprost."),
    "dotacje": ("Jakie dofinansowania mogę dostać?",
                "Wymień programy z sekcji DZIAŁANIA (pieniądze) i DOTACJE, które są dla rolnika. Przy każdym: na co, ile (jeśli "
                "jest w kontekście) i STATUS NABORU. Programy z zamkniętym naborem opisz jako „czekaj na nabór”."),
    "formalnosci": ("Jakie formalności muszę załatwić?",
                    "Pogrupuj działania: bez formalności / zgłoszenie wodnoprawne / pozwolenie. Podaj urząd, opłatę, czas i że "
                    "zgłoszenie składa się przed rozpoczęciem prac. Formalności bierz wyłącznie z kontekstu."),
    "kiedy": ("Co zrobić w najbliższych tygodniach?",
              "Na podstawie daty analizy, fazy uprawy, prognozy i terminów działań: co zrobić teraz, co przed wiosną, co w "
              "sezonie. Konkretne miesiące."),
}


class FaqResponse(BaseModel):
    topic: str
    question: str
    paragraphs: list[str] = Field(default_factory=list)
    bullets: list[str] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    source: Literal["llm", "template"] = "template"
    model: str | None = None
    disclaimer: str = DISCLAIMER


FAQ_SYS = STYLE + """
Odpowiadasz na JEDNO pytanie rolnika o jego działkę. Krótko: 1–2 akapity po 1–3 zdania i do 6 punktów (każdy 1 zdanie).
Zwróć JSON: {"paragraphs": ["…"], "bullets": ["…"], "sources": ["S3", "S7"]}. W tekście nie wstawiaj numerów źródeł."""


def _zl(v: float | None, dec: int = 0) -> str:
    return "—" if v is None else f"{v:,.{dec}f} zł".replace(",", " ").replace(".", ",")


def faq_template(g: Grounding, topic: str) -> FaqResponse:
    """Odpowiedzi z reguł – bez LLM. Tylko fakty z analizy; brak danych mówimy wprost."""
    q = FAQ[topic][0]
    a = g.analysis or {}
    wb = a.get("water_balance") or {}
    pond = wb.get("pond") or {}
    recs = _sorted_recs(g)
    paras: list[str] = []
    bullets: list[str] = []
    if not a.get("assessment"):
        return FaqResponse(topic=topic, question=q, paragraphs=["Nie mamy dość danych, żeby odpowiedzieć dla tej działki i daty."])
    if topic == "sytuacja":
        s = summary_template(g)
        paras, bullets = [s.headline, *s.paragraphs[:2]], []
    elif topic == "zatrzymac":
        paras = ["Najpierw zatrzymaj wodę na polu, potem popraw glebę – nawadnianie na końcu."]
        bullets = [f"{r['title']}: {r.get('why') or ''}".strip() for r in g.recs][:6]
    elif topic == "koszty":
        if pond:
            bullets.append(f"Oczko (ok. {pond.get('volume_m3')} m³): wykop {_zl(pond.get('cost_pln_min'))} – {_zl(pond.get('cost_pln_max'))} "
                           "(szacunek, bez uszczelnienia i przelewu).")
        for r in recs:
            if r.get("fee_pln"):
                bullets.append(f"{r['title']}: opłata urzędowa {_zl(r['fee_pln'], 2)} ({FORMALITY_PL.get(r.get('formality') or 'none')}).")
        paras = ["Koszt międzyplonu, mulczu czy uprawy uproszczonej zależy od nasion, sprzętu i pracy – tego nie szacujemy."]
    elif topic == "zysk":
        if pond:
            bullets.append(f"Oczko zatrzyma do ok. {pond.get('stored_per_year_m3')} m³ wody w roku"
                           + (f" – ok. {pond['covers_season_pct']}% sezonowego niedoboru." if pond.get("covers_season_pct") else "."))
        irr = a.get("irrigation") or {}
        if irr.get("yield_loss_pct"):
            bullets.append(f"Bez wody spadek plonu w tym sezonie szacujemy na ok. {irr['yield_loss_pct']:.0f}% (FAO-56).")
        for f in {f["name"]: f for r in recs for f in r.get("funding") or []}.values():
            if f.get("call_kind") == "annual" and f.get("scope"):
                bullets.append(f"{f['name']}: {f['scope']}")
        paras = ["Plonu nie wyceniamy w złotych – zależy od ceny skupu i pogody."]
    elif topic == "dotacje":
        seen = {}
        for r in recs:
            for f in r.get("funding") or []:
                seen.setdefault(f["name"], f)
        bullets = [f"{f['name']} – {f.get('call_label')}" for f in seen.values()] or ["Dla działań z raportu nie ma przypisanego programu."]
        paras = ["Większość dotacji inwestycyjnych to zwrot kosztów po realizacji. Ekoschematy składasz co roku we wniosku obszarowym."]
    elif topic == "formalnosci":
        for r in recs:
            f = r.get("formality") or "none"
            extra = f" – {r['office']}, opłata {_zl(r.get('fee_pln'), 2)}, {r.get('wait')}" if f in ("notification", "permit") else ""
            bullets.append(f"{r['title']}: {FORMALITY_PL.get(f)}{extra}.")
        paras = ["Zgłoszenie lub pozwolenie składasz przed rozpoczęciem prac."]
    elif topic == "kiedy":
        bullets = [f"{r['title']}: {r['when']}" for r in g.recs if r.get("when")][:6]
        crit = (a.get("assessment") or {}).get("critical_months") or []
        if crit:
            paras = ["Najwięcej wody brakuje w miesiącach: " + ", ".join(str(m) for m in crit) + " – zatrzymaj wodę wcześniej."]
    return FaqResponse(topic=topic, question=q, paragraphs=paras, bullets=bullets)


async def faq(g: Grounding, topic: str) -> FaqResponse:
    key = make_key("llm_faq", id=g.ctx.parcel.id, date=g.ctx.as_of.isoformat(), crop=g.ctx.crop, topic=topic,
                   model=settings.openai_model, v=2)
    if (hit := cache_get(key)) is not None:
        return FaqResponse.model_validate(hit)
    tpl = faq_template(g, topic)
    if not (g.analysis or {}).get("assessment"):
        return tpl
    question, instr = FAQ[topic]
    out = await openai_client.complete_json(FAQ_SYS, [_ctx_message(g), {"role": "user", "content": f"PYTANIE: {question}\nWSKAZÓWKI: {instr}"}],
                                            max_tokens=900)
    if not out or not (out.get("paragraphs") or out.get("bullets")):
        return tpl
    cites, seen = [], set()
    for sid in out.get("sources") or []:
        s = g.source(str(sid).strip("[] "))
        if s and s.sid not in seen:
            seen.add(s.sid)
            cites.append(Citation(title=s.title, url=s.url))
    clean = lambda t: re.sub(r"\s*\[S\d+\]", "", str(t)).strip()
    res = FaqResponse(topic=topic, question=question, paragraphs=[clean(p) for p in out.get("paragraphs") or []][:3],
                      bullets=[clean(b) for b in out.get("bullets") or []][:6], citations=cites[:5], source="llm",
                      model=settings.openai_model)
    cache_set(key, res.model_dump(mode="json"), SUMMARY_TTL_S)
    return res
