/**
 * Karta „Wytłumacz mi prosto” – nagłówek, akapity i 3 zadania z plakietką formalności.
 * Działa z LLM i z zapasem (source: "template").
 */
import { useEffect, useState } from "react";
import { Lightbulb, RefreshCw } from "lucide-react";
import { api, type LlmSummary } from "@/api/client";
import { Button } from "@/components/ui/button";
import { FormalityBadge } from "./LegalPlan";

type Props = {
  parcelId: string;
  date: string;
  crop?: string;
};

export function SimpleExplain({ parcelId, date, crop }: Props) {
  const [data, setData] = useState<LlmSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [retry, setRetry] = useState(0);

  useEffect(() => {
    const ctrl = new AbortController();
    setLoading(true);
    setError("");
    setData(null);
    api
      .summary({ id: parcelId, date, crop: crop || undefined }, ctrl.signal)
      .then((s) => {
        if (!ctrl.signal.aborted) {
          setData(s);
          setLoading(false);
        }
      })
      .catch((e: unknown) => {
        if (ctrl.signal.aborted) return;
        setError(e instanceof Error ? e.message : "Nie udało się przygotować wyjaśnienia.");
        setLoading(false);
      });
    return () => ctrl.abort();
  }, [parcelId, date, crop, retry]);

  if (loading) {
    return (
      <section className="simple-explain" aria-busy="true" aria-live="polite">
        <div className="simple-explain-head">
          <Lightbulb size={20} aria-hidden="true" />
          <h2>Wytłumacz mi prosto</h2>
        </div>
        <p className="simple-explain-loading">Przygotowuję krótkie wyjaśnienie…</p>
        <div className="skeleton" />
        <div className="skeleton" />
      </section>
    );
  }

  if (error || !data) {
    return (
      <section className="simple-explain simple-explain-error" role="alert">
        <div className="simple-explain-head">
          <Lightbulb size={20} aria-hidden="true" />
          <h2>Wytłumacz mi prosto</h2>
        </div>
        <p>{error || "Brak wyjaśnienia."}</p>
        <Button
          type="button"
          variant="outline"
          className="simple-explain-retry"
          onClick={() => setRetry((n) => n + 1)}
        >
          <RefreshCw size={16} aria-hidden="true" />
          Spróbuj ponownie
        </Button>
      </section>
    );
  }

  return (
    <section className="simple-explain" aria-labelledby="simple-explain-title">
      <div className="simple-explain-head">
        <Lightbulb size={20} aria-hidden="true" />
        <h2 id="simple-explain-title">Wytłumacz mi prosto</h2>
        <span className="llm-source" title={data.model ? `model: ${data.model}` : undefined}>
          {data.source === "llm" ? "AI" : "wersja uproszczona"}
        </span>
      </div>
      <p className="simple-explain-headline">{data.headline}</p>
      {data.paragraphs.map((p, i) => (
        <p key={i} className="simple-explain-p">
          {p}
        </p>
      ))}
      {data.todo.length > 0 && (
        <ol className="simple-explain-todo">
          {data.todo.map((item, i) => (
            <li key={i}>
              <span className="simple-explain-todo-text">{item.text}</span>
              <FormalityBadge r={{ formality: item.formality }} />
            </li>
          ))}
        </ol>
      )}
      {data.disclaimer && <p className="simple-explain-disclaimer">{data.disclaimer}</p>}
    </section>
  );
}
