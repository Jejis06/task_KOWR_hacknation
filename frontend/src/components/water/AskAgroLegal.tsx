/**
 * „Zapytaj AgroLegal” – rozwijane pytania nad raportem (dodatek AI; raport poniżej jest liczony regułami, bez AI).
 * - Każde pytanie to natywne <details> (klawiatura, czytnik ekranu); otwarte jest tylko jedno naraz (name="faq").
 * - Odpowiedź liczy się dopiero po rozwinięciu i zostaje w pamięci strony – rolnik nie czeka na rzeczy, których nie czyta.
 * - W odpowiedzi: krótkie akapity, punkty, a „Źródła” i informacja o pochodzeniu odpowiedzi – jeszcze jeden poziom niżej.
 */
import { useRef, useState } from "react";
import { BookOpen, ChevronDown, Coins, FileText, HandCoins, Lightbulb, MessageCircle, PiggyBank, CalendarClock, Droplets, Sprout } from "lucide-react";
import { api, type FaqTopic, type LlmFaq } from "@/api/client";

const QUESTIONS: { topic: FaqTopic; q: string; Icon: typeof Droplets }[] = [
  { topic: "sytuacja", q: "Co się dzieje z wodą na moim polu?", Icon: Droplets },
  { topic: "zatrzymac", q: "Jak mogę zatrzymać wodę na moim polu?", Icon: Sprout },
  { topic: "koszty", q: "Ile to będzie kosztować?", Icon: Coins },
  { topic: "zysk", q: "Co na tym zyskam?", Icon: PiggyBank },
  { topic: "dotacje", q: "Jakie dofinansowania mogę dostać?", Icon: HandCoins },
  { topic: "formalnosci", q: "Jakie formalności muszę załatwić?", Icon: FileText },
  { topic: "kiedy", q: "Co zrobić w najbliższych tygodniach?", Icon: CalendarClock },
];

type State = { status: "loading" } | { status: "ok"; data: LlmFaq } | { status: "error"; message: string };

export function AskAgroLegal({ parcelId, date, crop, onOpenChat }: {
  parcelId: string; date: string; crop?: string; onOpenChat?: () => void;
}) {
  const [answers, setAnswers] = useState<Partial<Record<FaqTopic, State>>>({});
  const key = `${parcelId}|${date}|${crop ?? ""}`;
  const lastKey = useRef(key);
  if (lastKey.current !== key) {          // inna działka / data / uprawa → stare odpowiedzi nieważne
    lastKey.current = key;
    if (Object.keys(answers).length) setAnswers({});
  }

  async function load(topic: FaqTopic) {
    setAnswers((a) => ({ ...a, [topic]: { status: "loading" } }));
    try {
      const data = await api.faq({ id: parcelId, date, crop, topic });
      setAnswers((a) => ({ ...a, [topic]: { status: "ok", data } }));
    } catch (e) {
      setAnswers((a) => ({ ...a, [topic]: { status: "error", message: e instanceof Error ? e.message : "Nie udało się." } }));
    }
  }

  return (
    <section className="ask-agrolegal" aria-labelledby="ask-title">
      <div className="ask-head">
        <Lightbulb size={20} aria-hidden="true" />
        <div>
          <h2 id="ask-title">Podpowiedzi dla Twojego pola</h2>
          <p>Kliknij pytanie, żeby zobaczyć odpowiedź. Odpowiedzi pisze asystent AI na podstawie raportu poniżej.</p>
        </div>
      </div>
      <div className="faq-list">
        {QUESTIONS.map(({ topic, q, Icon }) => {
          const st = answers[topic];
          return (
            <details key={topic} className="faq-item" {...{ name: "faq" }}
              onToggle={(e) => { if ((e.currentTarget as HTMLDetailsElement).open && (!st || st.status === "error")) void load(topic); }}>
              <summary className="faq-summary">
                <Icon size={20} aria-hidden="true" className="faq-icon" />
                <span className="faq-q">{q}</span>
                <ChevronDown size={20} aria-hidden="true" className="acc-chevron" />
              </summary>
              <div className="faq-body" aria-live="polite" aria-busy={st?.status === "loading"}>
                {(!st || st.status === "loading") && (
                  <>
                    <p className="faq-loading">Przygotowuję odpowiedź dla Twojej działki… (kilka sekund)</p>
                    <div className="skeleton" />
                  </>
                )}
                {st?.status === "error" && (
                  <div role="alert" className="faq-error">
                    <p>Nie udało się przygotować odpowiedzi. {st.message}</p>
                    <button type="button" className="faq-retry" onClick={() => void load(topic)}>Spróbuj ponownie</button>
                  </div>
                )}
                {st?.status === "ok" && (
                  <>
                    {st.data.paragraphs.map((p, i) => <p key={i} className="faq-p">{p}</p>)}
                    {st.data.bullets.length > 0 && (
                      <ul className="faq-bullets">{st.data.bullets.map((b, i) => <li key={i}>{b}</li>)}</ul>
                    )}
                    <details className="faq-more">
                      <summary><BookOpen size={15} aria-hidden="true" /> Skąd ta odpowiedź?</summary>
                      <div className="faq-more-body">
                        <p>
                          {st.data.source === "llm"
                            ? "Odpowiedź napisał asystent AI wyłącznie na podstawie danych z raportu i przepisów z naszej bazy. Formalności, opłaty i terminy naborów pochodzą z reguł, nie z AI."
                            : "Asystent AI jest niedostępny – to odpowiedź złożona z wyników raportu (bez AI)."}
                        </p>
                        {st.data.citations.length > 0 && (
                          <ul className="faq-cites">
                            {st.data.citations.map((c) => (
                              <li key={c.title}>{c.url ? <a href={c.url} target="_blank" rel="noreferrer">{c.title}<span className="sr-only"> (otwiera się w nowej karcie)</span></a> : c.title}</li>
                            ))}
                          </ul>
                        )}
                        <p className="faq-disclaimer">{st.data.disclaimer}</p>
                      </div>
                    </details>
                  </>
                )}
              </div>
            </details>
          );
        })}
      </div>
      {onOpenChat && (
        <button type="button" className="ask-own" onClick={onOpenChat}>
          <MessageCircle size={18} aria-hidden="true" /> Masz inne pytanie? Zapytaj o swoją działkę
        </button>
      )}
    </section>
  );
}
