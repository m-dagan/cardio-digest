#!/usr/bin/env python3
"""Weekly cardiopulmonary literature digest.

Queries PubMed (NCBI E-utilities) for articles entered in the past week in the
configured journals that match one or more configured topics, and writes:

    docs/data/latest.json            the current digest (read by docs/index.html)
    docs/data/archive/<date>.json    a dated copy
    docs/data/index.json             list of archived digests
    docs/data/seen.json              PMIDs already shown (prevents repeats)

Environment variables (all optional):
    NCBI_API_KEY       raises the E-utilities rate limit from 3 to 10 requests/s
    NCBI_EMAIL         contact address NCBI asks automated tools to supply
    ANTHROPIC_API_KEY  enables one- to two-sentence AI summaries via Claude
    LOOKBACK_DAYS      overrides settings.lookback_days for a manual run
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import requests
import yaml

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "docs" / "data"
EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
TOOL = "cardio-literature-digest"

API_KEY = os.environ.get("NCBI_API_KEY", "").strip()
EMAIL = os.environ.get("NCBI_EMAIL", "").strip()
PAUSE = 0.12 if API_KEY else 0.38

session = requests.Session()
session.headers["User-Agent"] = f"{TOOL}/1.0 (+https://github.com)"


# --------------------------------------------------------------------------- HTTP
def eutil(endpoint: str, params: dict, retries: int = 4) -> requests.Response:
    """POST to an E-utility with polite pacing and retry on rate-limit/5xx."""
    data = {"tool": TOOL, **params}
    if API_KEY:
        data["api_key"] = API_KEY
    if EMAIL:
        data["email"] = EMAIL
    for attempt in range(retries):
        time.sleep(PAUSE)
        try:
            r = session.post(f"{EUTILS}/{endpoint}", data=data, timeout=60)
        except requests.RequestException as exc:
            err = exc
        else:
            if r.status_code == 200:
                return r
            err = RuntimeError(f"{endpoint} HTTP {r.status_code}: {r.text[:200]}")
        time.sleep(2 ** attempt)
    raise RuntimeError(f"E-utilities request failed after {retries} attempts: {err}")


def esearch(term: str, mindate: str | None = None, maxdate: str | None = None,
            reldate: int | None = None, retmax: int = 2000) -> tuple[int, list[str]]:
    params = {"db": "pubmed", "term": term, "retmode": "json", "retmax": retmax,
              "datetype": "edat"}
    if reldate is not None:
        params["reldate"] = reldate
    else:
        params["mindate"], params["maxdate"] = mindate, maxdate
    js = eutil("esearch.fcgi", params).json()["esearchresult"]
    if "ERROR" in js:
        raise RuntimeError(f"PubMed query error: {js['ERROR']}")
    return int(js.get("count", 0)), js.get("idlist", [])


def efetch(pmids: list[str]) -> list[ET.Element]:
    articles = []
    for i in range(0, len(pmids), 150):
        batch = pmids[i:i + 150]
        r = eutil("efetch.fcgi", {"db": "pubmed", "id": ",".join(batch),
                                  "retmode": "xml"})
        root = ET.fromstring(r.content)
        articles.extend(root.findall("PubmedArticle"))
    return articles


# ------------------------------------------------------------------------ parsing
def text(el: ET.Element | None) -> str:
    if el is None:
        return ""
    return re.sub(r"\s+", " ", "".join(el.itertext())).strip()


MONTHS = {m: i for i, m in enumerate(
    "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split(), 1)}


def parse_date(el: ET.Element | None) -> str:
    if el is None:
        return ""
    y = el.findtext("Year")
    if not y:
        md = el.findtext("MedlineDate") or ""
        m = re.search(r"\d{4}", md)
        return m.group(0) if m else ""
    mo = el.findtext("Month") or ""
    mo = MONTHS.get(mo[:3], int(mo) if mo.isdigit() else 0)
    d = el.findtext("Day")
    if mo and d and d.isdigit():
        return f"{y}-{mo:02d}-{int(d):02d}"
    return f"{y}-{mo:02d}" if mo else y


CONCLUSION_LABELS = ("CONCLUSION", "CONCLUSIONS", "INTERPRETATION",
                     "CONCLUSIONS AND RELEVANCE", "CONCLUSION AND RELEVANCE")


def parse_article(pa: ET.Element) -> dict:
    mc = pa.find("MedlineCitation")
    art = mc.find("Article")
    pmid = mc.findtext("PMID")
    journal = art.find("Journal")

    authors = []
    for a in art.findall("AuthorList/Author"):
        if a.find("CollectiveName") is not None:
            authors.append(text(a.find("CollectiveName")))
        else:
            last, ini = a.findtext("LastName") or "", a.findtext("Initials") or ""
            if last:
                authors.append(f"{last} {ini}".strip())

    sections = []
    for ab in art.findall("Abstract/AbstractText"):
        sections.append({"label": (ab.get("Label") or "").strip(), "text": text(ab)})
    conclusion = next((s["text"] for s in sections
                       if s["label"].upper() in CONCLUSION_LABELS), "")

    doi = ""
    for e in art.findall("ELocationID"):
        if e.get("EIdType") == "doi":
            doi = (e.text or "").strip()
    if not doi:
        for e in pa.findall("PubmedData/ArticleIdList/ArticleId"):
            if e.get("IdType") == "doi":
                doi = (e.text or "").strip()
    pmc = next((e.text for e in pa.findall("PubmedData/ArticleIdList/ArticleId")
                if e.get("IdType") == "pmc"), "")

    epub = art.find("ArticleDate")
    date = parse_date(epub) if epub is not None else parse_date(
        journal.find("JournalIssue/PubDate"))

    return {
        "pmid": pmid,
        "title": text(art.find("ArticleTitle")).rstrip("."),
        "authors": authors,
        "journal": journal.findtext("Title") or "",
        "journal_abbrev": journal.findtext("ISOAbbreviation")
                          or mc.findtext("MedlineJournalInfo/MedlineTA") or "",
        "ta": mc.findtext("MedlineJournalInfo/MedlineTA") or "",
        "date": date,
        "pub_types": [text(p) for p in art.findall("PublicationTypeList/PublicationType")],
        "abstract": sections,
        "conclusion": conclusion,
        "doi": doi,
        "pmc": pmc,
        "pubmed_url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
        "url": f"https://doi.org/{doi}" if doi else f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
    }


# ------------------------------------------------------------------------ ranking
TYPE_WEIGHT = {
    "Randomized Controlled Trial": 6, "Meta-Analysis": 5, "Systematic Review": 4,
    "Practice Guideline": 5, "Guideline": 5, "Consensus Development Conference": 4,
    "Clinical Trial, Phase III": 4, "Multicenter Study": 2, "Review": 1,
    "Editorial": -2, "Comment": -2, "Letter": -3, "Case Reports": -3,
}
DISPLAY_TYPES = ["Randomized Controlled Trial", "Meta-Analysis", "Systematic Review",
                 "Practice Guideline", "Guideline", "Review", "Editorial", "Letter",
                 "Case Reports", "Comment"]


def score(a: dict) -> float:
    s = 10 * len(a["topics"])
    s += max([TYPE_WEIGHT.get(t, 0) for t in a["pub_types"]] or [0])
    s += 1 if a["abstract"] else -1
    return s


def article_kind(pub_types: list[str]) -> str:
    for t in DISPLAY_TYPES:
        if t in pub_types:
            return {"Randomized Controlled Trial": "RCT", "Practice Guideline": "Guideline",
                    "Case Reports": "Case report", "Comment": "Commentary"}.get(t, t)
    return "Original research" if "Journal Article" in pub_types else (pub_types or [""])[0]


# -------------------------------------------------------------------- AI summary
def ai_summaries(articles: list[dict], cfg: dict) -> None:
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    setting = str(cfg.get("enabled", "auto")).lower()
    if setting in ("false", "no", "off") or not key:
        return
    model = cfg.get("model", "claude-haiku-5-5")
    done = 0
    for a in articles[: int(cfg.get("max_articles", 120))]:
        abstract = " ".join(f"{s['label']}: {s['text']}" if s["label"] else s["text"]
                            for s in a["abstract"])
        if len(abstract) < 200:
            continue
        prompt = (
            "Summarise this article for a cardiologist specialising in pulmonary "
            "hypertension and heart failure, in at most two sentences (≤60 words). "
            "State design, population and size, and the principal quantitative finding "
            "(effect estimate with CI or p-value where reported). Use only information "
            "in the abstract; no preamble.\n\n"
            f"Title: {a['title']}\nJournal: {a['journal']}\nAbstract: {abstract}")
        try:
            r = session.post(
                "https://api.anthropic.com/v1/messages",
                headers={"x-api-key": key, "anthropic-version": "2023-06-01",
                         "content-type": "application/json"},
                json={"model": model, "max_tokens": 200,
                      "messages": [{"role": "user", "content": prompt}]},
                timeout=60)
            r.raise_for_status()
            a["ai_summary"] = "".join(b.get("text", "") for b in r.json()["content"]).strip()
            done += 1
        except Exception as exc:  # summaries are a convenience; never fail the run
            print(f"  AI summary skipped for {a['pmid']}: {exc}", file=sys.stderr)
    print(f"AI summaries generated: {done}")


# --------------------------------------------------------------------------- main
def load_json(path: Path, default):
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def main() -> int:
    cfg = yaml.safe_load((ROOT / "config.yaml").read_text())
    st = cfg.get("settings", {})
    lookback = int(os.environ.get("LOOKBACK_DAYS") or st.get("lookback_days", 8))

    today = dt.datetime.now(dt.timezone.utc).date()
    start = today - dt.timedelta(days=lookback)
    mindate, maxdate = start.strftime("%Y/%m/%d"), today.strftime("%Y/%m/%d")

    journals = [t for fam in cfg["journals"] if fam.get("enabled", True)
                for t in fam["titles"]]
    family_of = {t.lower(): fam["family"] for fam in cfg["journals"] for t in fam["titles"]}
    journal_clause = "(" + " OR ".join(f'"{j}"[ta]' for j in journals) + ")"
    excl = st.get("exclude_publication_types") or []
    excl_clause = (" NOT (" + " OR ".join(f'"{p}"[pt]' for p in excl) + ")") if excl else ""

    print(f"Window {mindate}–{maxdate}; {len(journals)} journals; "
          f"{len(cfg['topics'])} topics")

    topic_hits: dict[str, list[str]] = {}
    for tp in cfg["topics"]:
        q = " ".join(tp["query"].split())
        term = f"({q}) AND {journal_clause}{excl_clause}"
        count, ids = esearch(term, mindate, maxdate)
        print(f"  {tp['label']}: {count}")
        for pmid in ids:
            topic_hits.setdefault(pmid, []).append(tp["id"])

    seen = load_json(DATA / "seen.json", {})
    cutoff = (today - dt.timedelta(weeks=int(st.get("seen_memory_weeks", 12)))).isoformat()
    seen = {k: v for k, v in seen.items() if v >= cutoff}
    # Only suppress articles shown in a digest at least 4 days old, so a manual
    # re-run during the week reproduces (rather than empties) the current digest.
    recent = (today - dt.timedelta(days=4)).isoformat()
    new_ids = [p for p in topic_hits if not (p in seen and seen[p] <= recent)]
    print(f"Unique matches {len(topic_hits)}; new this week {len(new_ids)}")

    articles = []
    for pa in efetch(new_ids):
        a = parse_article(pa)
        a["topics"] = topic_hits.get(a["pmid"], [])
        a["kind"] = article_kind(a["pub_types"])
        a["family"] = (family_of.get(a["ta"].lower())
                       or family_of.get(a["journal_abbrev"].lower().replace(".", "")) or "")
        articles.append(a)
    articles.sort(key=lambda a: a["date"], reverse=True)   # newest first within ties
    articles.sort(key=score, reverse=True)                 # stable: most relevant first
    articles = articles[: int(st.get("max_articles", 250))]

    ai_summaries(articles, st.get("ai_summary", {}))

    warnings = []
    if st.get("health_check", True):
        for j in journals:
            try:
                n, _ = esearch(f'"{j}"[ta]', reldate=120, retmax=0)
            except RuntimeError as exc:
                warnings.append(f"{j}: query failed ({exc})")
                continue
            if n == 0:
                warnings.append(f"{j}: no PubMed records in the last 120 days — "
                                "check the NLM abbreviation in config.yaml")
        print(f"Journal health check: {len(warnings)} warning(s)")

    digest = {
        "generated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "window": {"from": start.isoformat(), "to": today.isoformat()},
        "topics": [{k: tp[k] for k in ("id", "label", "colour")} for tp in cfg["topics"]],
        "journal_count": len(journals),
        "articles": articles,
        "warnings": warnings,
    }

    (DATA / "archive").mkdir(parents=True, exist_ok=True)
    payload = json.dumps(digest, ensure_ascii=False, indent=1)
    (DATA / "latest.json").write_text(payload)
    (DATA / "archive" / f"{today.isoformat()}.json").write_text(payload)

    for a in articles:
        seen.setdefault(a["pmid"], today.isoformat())
    (DATA / "seen.json").write_text(json.dumps(seen, indent=0, sort_keys=True))

    index = sorted({p.stem for p in (DATA / "archive").glob("*.json")}, reverse=True)
    (DATA / "index.json").write_text(json.dumps(index))
    print(f"Wrote digest with {len(articles)} articles")
    return 0


if __name__ == "__main__":
    sys.exit(main())
