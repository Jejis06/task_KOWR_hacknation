// Typy lokalnej bazy wiedzy (/api/knowledge/*) – nie są częścią kontraktu bloków, właściciel: B.
import { createContext, useContext } from "react";
import type { KnowledgeStatus } from "./types";

export interface Procedure {
  id: string; title: string; organ?: string; when?: string; how_to_submit?: string;
  steps?: string[]; attachments?: string[]; notes?: string;
  fees?: Record<string, number | Record<string, number>>; fee_pln?: number;
  typical_duration?: string; typical_duration_status?: KnowledgeStatus;
  form_url?: string; form_title?: string; status: KnowledgeStatus; sources?: string[];
}
export interface FundingProgram {
  id: string; name: string; applicant?: string; scope?: string; call?: string; for_farmer?: boolean;
  status: KnowledgeStatus; open_question?: string; sources?: string[]; call_status?: KnowledgeStatus;
}
export interface LegalRule { id: string; title: string; rule: string; status: KnowledgeStatus; sources?: string[] }
export interface EuAct { id: string; short: string; act: string; celex?: string; relevance?: string; farmer_impact?: string; status: KnowledgeStatus }

export interface Knowledge {
  procedures: Record<string, Procedure>;
  funding: Record<string, FundingProgram>;
  legal: Record<string, LegalRule>;
  eu: EuAct[];
  eurlexPattern?: string;
  disclaimer?: string;
  loaded: boolean;
}

export const emptyKnowledge: Knowledge = { procedures: {}, funding: {}, legal: {}, eu: [], loaded: false };
export const KnowledgeContext = createContext<Knowledge>(emptyKnowledge);
export const useKnowledge = () => useContext(KnowledgeContext);

export function byId<T extends { id: string }>(items: T[] | undefined): Record<string, T> {
  return Object.fromEntries((items ?? []).map((i) => [i.id, i]));
}

/** Opłata dla roku daty analizy; gdy brak stawki dla tego roku – najbliższa wcześniejsza (albo pierwsza znana). */
export function feeFor(p: Procedure | undefined, year: number): { fee: number; year: number } | null {
  if (!p?.fees) return p?.fee_pln ? { fee: p.fee_pln, year } : null;
  const years = Object.keys(p.fees).filter((k) => /^\d{4}$/.test(k)).map(Number).sort();
  if (!years.length) return null;
  const y = years.includes(year) ? year : (years.filter((k) => k <= year).pop() ?? years[0]);
  return { fee: p.fees[String(y)] as number, year: y };
}
