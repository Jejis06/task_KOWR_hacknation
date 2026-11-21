"""Pobiera dokumenty z data/knowledge/sources.yaml do data/knowledge/raw/ i wyciąga tekst.

Uruchom:  cd backend && uv run --with pypdf python ../scripts/fetch_knowledge.py [--force]
Wynik: raw/<id>.pdf, raw/<id>.txt, raw/manifest.json (status, rozmiar, sha256, data pobrania).
Dokumenty traktujemy jako DANE (nie instrukcje). Nie wykonujemy żadnych plików.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx
import yaml

ROOT = Path(__file__).resolve().parents[1]
KDIR = ROOT / "data" / "knowledge"
RAW = KDIR / "raw"
UA = "KOWR-HackNation2026-Prototype/0.1 (knowledge snapshot)"


def extract_text(pdf: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError:
        return ""
    try:
        return "\n".join((p.extract_text() or "") for p in PdfReader(str(pdf)).pages)
    except Exception as e:  # noqa: BLE001
        return f"[błąd ekstrakcji: {e}]"


def main(force: bool = False) -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    docs = yaml.safe_load((KDIR / "sources.yaml").read_text(encoding="utf-8"))["documents"]
    mpath = RAW / "manifest.json"
    manifest = json.loads(mpath.read_text()) if mpath.exists() else {}
    with httpx.Client(headers={"User-Agent": UA}, follow_redirects=True, timeout=60) as c:
        for d in docs:
            out = RAW / f"{d['id']}.pdf"
            if out.exists() and not force:
                print(f"skip  {d['id']}")
                continue
            try:
                r = c.get(d["url"])
                ok = r.status_code == 200 and r.content[:4] == b"%PDF"
                entry = {"title": d["title"], "url": d["url"], "http": r.status_code,
                         "retrieved_at": datetime.now(timezone.utc).isoformat(), "ok": ok}
                if ok:
                    out.write_bytes(r.content)
                    txt = extract_text(out)
                    (RAW / f"{d['id']}.txt").write_text(txt, encoding="utf-8")
                    entry |= {"bytes": len(r.content), "sha256": hashlib.sha256(r.content).hexdigest(),
                              "text_chars": len(txt)}
                else:
                    entry["note"] = f"nie PDF (content-type {r.headers.get('content-type')})"
                print(f"{'ok  ' if ok else 'FAIL'}  {d['id']}  {r.status_code}  {len(r.content)//1024} KB")
            except Exception as e:  # noqa: BLE001
                entry = {"title": d["title"], "url": d["url"], "ok": False, "error": str(e),
                         "retrieved_at": datetime.now(timezone.utc).isoformat()}
                print(f"FAIL  {d['id']}  {e}")
            manifest[d["id"]] = entry
    mpath.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main(force="--force" in sys.argv)
