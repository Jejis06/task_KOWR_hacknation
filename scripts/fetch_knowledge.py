"""Pobiera dokumenty z data/knowledge/sources.yaml do data/knowledge/raw/ i wyciąga z nich tekst.

Uruchom:  make knowledge     (= cd backend && uv run --with pypdf --with python-docx python ../scripts/fetch_knowledge.py)
          ... --force        ponownie pobiera wszystko

Dokumenty dodane RĘCZNIE: wrzuć plik jako data/knowledge/raw/<id>.pdf (albo .docx) i dopisz wpis do
sources.yaml z `manual: true` (url opcjonalny). Skrypt nie pobiera go z sieci, tylko wyciąga tekst do <id>.txt.

Wynik: raw/<id>.pdf|.docx, raw/<id>.txt, raw/manifest.json (status, rozmiar, sha256, data).
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
EXTS = (".pdf", ".docx")


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def kind_of(content: bytes) -> str | None:
    if content[:4] == b"%PDF":
        return ".pdf"
    if content[:2] == b"PK":  # docx = zip
        return ".docx"
    return None


def extract_text(path: Path) -> str:
    try:
        if path.suffix == ".pdf":
            from pypdf import PdfReader
            return "\n".join((p.extract_text() or "") for p in PdfReader(str(path)).pages)
        if path.suffix == ".docx":
            import docx  # python-docx
            d = docx.Document(str(path))
            parts = [p.text for p in d.paragraphs]
            for t in d.tables:
                parts += [" | ".join(c.text for c in row.cells) for row in t.rows]
            return "\n".join(parts)
    except ImportError as e:
        return f"[brak biblioteki do ekstrakcji: {e}]"
    except Exception as e:  # noqa: BLE001
        return f"[błąd ekstrakcji: {e}]"
    return ""


def html_to_text(raw: bytes) -> str:
    import html as _html
    import re
    t = raw.decode("utf-8", "replace")
    t = re.sub(r"(?is)<(script|style|nav|footer|header)[^>]*>.*?</\1>", " ", t)
    t = re.sub(r"(?i)<br\s*/?>|</(p|div|tr|li|h[1-6])>", "\n", t)
    t = re.sub(r"(?i)</t[dh]>", " | ", t)
    t = _html.unescape(re.sub(r"<[^>]+>", " ", t))
    return "\n".join(ln.strip() for ln in t.splitlines() if ln.strip())


def existing_file(doc_id: str) -> Path | None:
    return next((RAW / f"{doc_id}{ext}" for ext in EXTS if (RAW / f"{doc_id}{ext}").exists()), None)


def finalize(doc: dict, path: Path, entry: dict) -> dict:
    data = path.read_bytes()
    txt = extract_text(path)
    (RAW / f"{doc['id']}.txt").write_text(txt, encoding="utf-8")
    return entry | {"ok": True, "file": path.name, "bytes": len(data),
                    "sha256": hashlib.sha256(data).hexdigest(), "text_chars": len(txt)}


def main(force: bool = False) -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    docs = yaml.safe_load((KDIR / "sources.yaml").read_text(encoding="utf-8"))["documents"]
    mpath = RAW / "manifest.json"
    manifest = json.loads(mpath.read_text()) if mpath.exists() else {}
    with httpx.Client(headers={"User-Agent": UA}, follow_redirects=True, timeout=60) as c:
        for d in docs:
            base = {"title": d["title"], "url": d.get("url"), "manual": bool(d.get("manual"))}
            have = existing_file(d["id"])
            txt_missing = not (RAW / f"{d['id']}.txt").exists()
            try:
                if d.get("html"):
                    if not txt_missing and not force:
                        print(f"skip  {d['id']}")
                        continue
                    r = c.get(d["url"])
                    if r.status_code == 200 and "html" in r.headers.get("content-type", ""):
                        txt = html_to_text(r.content)
                        (RAW / f"{d['id']}.txt").write_text(txt, encoding="utf-8")
                        manifest[d["id"]] = base | {"ok": True, "http": 200, "retrieved_at": now(), "kind": "html",
                                                    "text_chars": len(txt)}
                        print(f"ok    {d['id']}  html  {len(txt)//1024} KB tekstu")
                    else:
                        manifest[d["id"]] = base | {"ok": False, "http": r.status_code, "retrieved_at": now()}
                        print(f"FAIL  {d['id']}  {r.status_code}")
                    continue
                if have and (d.get("manual") or not force):
                    if txt_missing or force:
                        manifest[d["id"]] = finalize(d, have, base | {"retrieved_at": manifest.get(
                            d["id"], {}).get("retrieved_at", now())})
                        print(f"text  {d['id']}  ({have.name})")
                    else:
                        print(f"skip  {d['id']}")
                    continue
                if (d.get("manual") or not d.get("url")) and not txt_missing:
                    print(f"skip  {d['id']}  (tekst w repo, PDF tylko lokalnie)")
                    continue
                if d.get("manual") or not d.get("url"):
                    manifest[d["id"]] = base | {"ok": False, "retrieved_at": now(),
                                                "note": f"brak pliku – wrzuć raw/{d['id']}.pdf lub .docx"}
                    print(f"MISS  {d['id']}  (wrzuć plik ręcznie)")
                    continue
                r = c.get(d["url"])
                ext = kind_of(r.content) if r.status_code == 200 else None
                entry = base | {"http": r.status_code, "retrieved_at": now()}
                if ext:
                    out = RAW / f"{d['id']}{ext}"
                    out.write_bytes(r.content)
                    entry = finalize(d, out, entry)
                    print(f"ok    {d['id']}  {ext}  {len(r.content)//1024} KB")
                else:
                    entry |= {"ok": False, "note": f"nie PDF/DOCX (content-type {r.headers.get('content-type')})"}
                    print(f"FAIL  {d['id']}  {r.status_code}")
            except Exception as e:  # noqa: BLE001
                entry = base | {"ok": False, "error": str(e), "retrieved_at": now()}
                print(f"FAIL  {d['id']}  {e}")
            manifest[d["id"]] = entry
    ids = {d["id"] for d in docs}
    for stale in [k for k in manifest if k not in ids]:  # usunięte z sources.yaml
        manifest.pop(stale)
        for ext in (*EXTS, ".txt"):
            (RAW / f"{stale}{ext}").unlink(missing_ok=True)
    mpath.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main(force="--force" in sys.argv)
