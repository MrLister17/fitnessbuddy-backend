import requests
import pandas as pd

# Load NCD database locally for RAG
try:
    df = pd.read_csv("ncd_database.csv")
except Exception:
    df = pd.DataFrame()

# ==========================================
# GOLD STANDARD DATASET (loaded once)
# ==========================================
GOLD_STANDARD_URL = "https://raw.githubusercontent.com/MrLister17/FitnessBuddyAPI/main/gold_standard_dataset.json"
gold_standard: list = []

try:
    _gs_resp = requests.get(GOLD_STANDARD_URL, timeout=10)
    _gs_resp.raise_for_status()
    gold_standard = _gs_resp.json()
    print(f"[RAG] Gold standard dataset loaded: {len(gold_standard)} entries")
except Exception as _e:
    print(f"[RAG] WARNING: Could not load gold standard dataset: {_e}")


def search_gold_standard(query: str, k: int = 2) -> str:
    """Search gold standard dataset by keyword overlap."""
    if not gold_standard:
        return ""
    query_words = set(query.lower().split())
    scored = []
    for entry in gold_standard:
        haystack = f"{entry.get('prompt', '')} {entry.get('gold_reference', '')}".lower()
        score = sum(1 for w in query_words if w in haystack)
        if score > 0:
            scored.append((score, entry))
    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:k]
    if not top:
        return ""
    parts = []
    for _, entry in top:
        source = entry.get("source", "Expert Source")
        expert = entry.get("expert", "")
        ref    = entry.get("gold_reference", "")
        parts.append(f"[{source} — {expert}]: {ref}")
    return "\n".join(parts)


def simple_keyword_search(query: str, k: int = 2) -> str:
    """CSV fallback search."""
    query_lower = query.lower()
    if df.empty:
        return ""
    matches = df[df['Context_Chunk'].str.contains(query_lower.split()[0], case=False, na=False)]
    if matches.empty:
        return "\n".join(df['Context_Chunk'].head(k).tolist())
    return "\n".join(matches['Context_Chunk'].head(k).tolist())


def retrieve_facts(query: str, k: int = 2) -> tuple:
    gold_result = search_gold_standard(query, k=k)
    if gold_result:
        return gold_result, "GOLD STANDARD REFERENCES (Expert-Verified)"
    csv_result = simple_keyword_search(query, k=k)
    return csv_result, "DATABASE FACTS (FROM CSV)"
