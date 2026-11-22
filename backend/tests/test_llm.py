"""LLM: zapas bez klucza, formalności zawsze z reguł, cytaty tylko z naszej listy źródeł (bez sieci – klient podmieniony)."""
import pytest

from app.knowledge.analysis import analyse_all
from app.llm import openai_client, service
from app.llm.grounding import Grounding, Source
from tests.test_knowledge_analysis import ctx, dry_data


def grounding() -> Grounding:
    c = ctx()
    a = analyse_all(c, dry_data(c)).model_dump(mode="json")
    return Grounding(ctx=c, analysis=a, recs=a["recommendations"],
                     sources=[Source("S1", "Staw/zbiornik na zgłoszenie – art. 394 ust. 1 pkt 9", "https://example.gov/pw")],
                     text="KONTEKST TESTOWY")


@pytest.fixture(autouse=True)
def no_cache(monkeypatch):
    monkeypatch.setattr(service, "cache_get", lambda k: None)
    monkeypatch.setattr(service, "cache_set", lambda *a, **k: None)


async def test_summary_template_without_key(monkeypatch):
    async def none(*a, **k):
        return None
    monkeypatch.setattr(openai_client, "complete_json", none)
    r = await service.summary(grounding())
    assert r.source == "template" and r.headline and 1 <= len(r.todo) <= 3
    assert r.todo[0].formality == "none"   # najpierw to, co wolno od razu


async def test_summary_formality_comes_from_rules_not_model(monkeypatch):
    g = grounding()
    pond = next(x for x in g.recs if x["measure_id"] == "oczko_zbiornik")

    async def lying(*a, **k):
        return {"headline": "H", "paragraphs": ["p"], "todo": [
            {"measure_id": "oczko_zbiornik", "text": "Kop staw, nie trzeba nic zgłaszać", "formality": "none"},
            {"measure_id": "wymyslone_dzialanie", "text": "x"}]}
    monkeypatch.setattr(openai_client, "complete_json", lying)
    r = await service.summary(g)
    assert r.source == "llm"
    assert [t.measure_id for t in r.todo] == ["oczko_zbiornik"]          # nieznane działanie odrzucone
    assert r.todo[0].formality == pond["formality"] == "notification"    # model nie zmieni kwalifikacji


async def test_chat_keeps_only_known_citations(monkeypatch):
    async def fake(*a, **k):
        return {"answer": "Wystarczy zgłoszenie [S1].", "sources": ["S1", "S99"], "suggestions": ["a", "b", "c", "d"]}
    monkeypatch.setattr(openai_client, "complete_json", fake)
    r = await service.chat(grounding(), [service.ChatMessage(role="user", content="Czy mogę kopać staw?")])
    assert r.answer == "Wystarczy zgłoszenie."
    assert [c.url for c in r.citations] == ["https://example.gov/pw"] and len(r.suggestions) == 3


async def test_chat_template_answers_pond_question(monkeypatch):
    async def none(*a, **k):
        return None
    monkeypatch.setattr(openai_client, "complete_json", none)
    r = await service.chat(grounding(), [service.ChatMessage(role="user", content="Czy mogę wykopać staw?")])
    assert r.source == "template" and "5000" in r.answer


@pytest.mark.parametrize("topic", list(service.FAQ))
async def test_faq_template_every_topic_without_llm(monkeypatch, topic):
    async def none(*a, **k):
        return None
    monkeypatch.setattr(openai_client, "complete_json", none)
    r = await service.faq(grounding(), topic)
    assert r.source == "template" and r.question and (r.paragraphs or r.bullets)


async def test_faq_costs_never_invent_amounts_in_template(monkeypatch):
    async def none(*a, **k):
        return None
    monkeypatch.setattr(openai_client, "complete_json", none)
    r = await service.faq(grounding(), "koszty")
    assert any("nie szacujemy" in p for p in r.paragraphs)
