/**
 * Czat „Zapytaj o swoją działkę” – wysuwany panel, duża czcionka, podpowiedzi jako przyciski,
 * cytaty jako linki. Działa bez LLM (source: "template").
 */
import { useEffect, useRef, useState } from "react";
import { MessageCircle, Send, X } from "lucide-react";
import { api, type ChatMessage, type LlmChat } from "@/api/client";
import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { useIsMobile } from "@/hooks/use-mobile";

type Props = {
  parcelId: string;
  date: string;
  crop?: string;
  /** Pokazuj przycisk tylko gdy raport jest widoczny */
  visible?: boolean;
};

type Turn = { role: "user" | "assistant"; content: string; meta?: LlmChat };

const STARTERS = [
  "Czy mogę wykopać staw bez pozwolenia?",
  "Ile kosztuje zgłoszenie?",
  "Jakie dotacje na oczko?",
  "Kiedy siać międzyplon?",
];

export function ParcelChat({ parcelId, date, crop, visible = true }: Props) {
  const [open, setOpen] = useState(false);
  useEffect(() => {
    const h = () => setOpen(true);
    window.addEventListener("agrolegal:open-chat", h);
    return () => window.removeEventListener("agrolegal:open-chat", h);
  }, []);
  const [input, setInput] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [suggestions, setSuggestions] = useState<string[]>(STARTERS);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const listRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const mobile = useIsMobile();

  useEffect(() => {
    if (!open) return;
    const t = setTimeout(() => inputRef.current?.focus(), 200);
    return () => clearTimeout(t);
  }, [open]);

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: "smooth" });
  }, [turns, loading]);

  // Nowa działka / data → czysta rozmowa
  useEffect(() => {
    setTurns([]);
    setSuggestions(STARTERS);
    setError("");
    setInput("");
  }, [parcelId, date, crop]);

  async function ask(text: string) {
    const content = text.trim().slice(0, 1000);
    if (!content || loading) return;
    setError("");
    setInput("");
    const nextUser: Turn = { role: "user", content };
    const history: ChatMessage[] = [...turns, nextUser].map((t) => ({
      role: t.role,
      content: t.content,
    }));
    setTurns((prev) => [...prev, nextUser]);
    setLoading(true);
    try {
      const res = await api.chat({
        id: parcelId,
        date,
        crop: crop || undefined,
        messages: history,
      });
      setTurns((prev) => [...prev, { role: "assistant", content: res.answer, meta: res }]);
      if (res.suggestions?.length) setSuggestions(res.suggestions);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Nie udało się uzyskać odpowiedzi.");
      setTurns((prev) => prev.slice(0, -1));
      setInput(content);
    } finally {
      setLoading(false);
    }
  }

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    void ask(input);
  }

  const body = (
    <div className="parcel-chat-body">
      <div className="parcel-chat-messages" ref={listRef} role="log" aria-live="polite">
        {turns.length === 0 && !loading && (
          <p className="parcel-chat-welcome">
            Zapytaj o wodę, glebę, uprawę, prawo wodne albo dotacje dla tej działki. Wybierz pytanie
            albo napisz własne.
          </p>
        )}
        {turns.map((t, i) => (
          <div key={i} className={`parcel-chat-bubble ${t.role}`}>
            <p>{t.content}</p>
            {t.role === "assistant" && t.meta && (
              <div className="parcel-chat-meta">
                {t.meta.citations?.length > 0 && (
                  <ul className="parcel-chat-citations">
                    {t.meta.citations.map((c) => (
                      <li key={c.title}>
                        {c.url ? (
                          <a href={c.url} target="_blank" rel="noreferrer">
                            {c.title}
                          </a>
                        ) : (
                          c.title
                        )}
                      </li>
                    ))}
                  </ul>
                )}
                <span className="llm-source">
                  {t.meta.source === "llm" ? "AI" : "wersja uproszczona"}
                </span>
              </div>
            )}
          </div>
        ))}
        {loading && (
          <div className="parcel-chat-bubble assistant loading" aria-busy="true">
            Myślę…
          </div>
        )}
        {error && (
          <p className="parcel-chat-error" role="alert">
            {error}
          </p>
        )}
      </div>

      {suggestions.length > 0 && (
        <div className="parcel-chat-suggestions" aria-label="Propozycje pytań">
          {suggestions.map((s) => (
            <button
              key={s}
              type="button"
              className="parcel-chat-chip"
              disabled={loading}
              onClick={() => void ask(s)}
            >
              {s}
            </button>
          ))}
        </div>
      )}

      <form className="parcel-chat-form" onSubmit={onSubmit}>
        <label className="sr-only" htmlFor="parcel-chat-input">
          Twoje pytanie
        </label>
        <textarea
          id="parcel-chat-input"
          ref={inputRef}
          rows={2}
          maxLength={1000}
          value={input}
          disabled={loading}
          placeholder="Napisz pytanie…"
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              void ask(input);
            }
          }}
        />
        <Button type="submit" size="lg" disabled={loading || !input.trim()} aria-label="Wyślij pytanie">
          <Send size={20} aria-hidden="true" />
          Wyślij
        </Button>
      </form>
    </div>
  );

  if (!visible) return null;

  return (
    <>
      <button
        type="button"
        className="parcel-chat-fab"
        onClick={() => setOpen(true)}
        aria-haspopup="dialog"
        aria-expanded={open}
      >
        <MessageCircle size={22} aria-hidden="true" />
        Zapytaj o swoją działkę
      </button>

        <Sheet open={open} onOpenChange={setOpen}>
          {/* telefon: panel od dołu (zamiast vaul/Drawer usuniętego przy sprzątaniu zależności) */}
          <SheetContent side={mobile ? "bottom" : "right"}
            className={`parcel-chat-panel ${mobile ? "parcel-chat-drawer" : "parcel-chat-sheet"}`}>
            <SheetHeader className="parcel-chat-header">
              <SheetTitle>Zapytaj o swoją działkę</SheetTitle>
              <SheetDescription>
                Proste odpowiedzi o wodzie, prawie i dotacjach dla Twojego pola.
              </SheetDescription>
            </SheetHeader>
            {body}
            <button
              type="button"
              className="parcel-chat-close-mobile sr-only"
              onClick={() => setOpen(false)}
            >
              <X size={18} /> Zamknij
            </button>
          </SheetContent>
        </Sheet>
    </>
  );
}
