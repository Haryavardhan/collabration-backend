import os
import re
import math
import requests
from collections import Counter

# ─────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────
STOP_WORDS = {
    "a","an","the","is","it","in","of","to","and","or","for",
    "with","on","at","by","from","this","that","are","was",
    "be","as","i","me","my","we","you","he","she","they","what",
    "how","do","does","did","can","could","will","would","should",
    "have","had","has","not","no","but","if","so","up","out","about"
}

# ─────────────────────────────────────────────
#  Load & chunk career_docs.txt at import time
# ─────────────────────────────────────────────
_DOCS_PATH = os.path.join(os.path.dirname(__file__), '..', 'career_docs.txt')
_CHUNKS: list[str] = []

def _load_chunks():
    global _CHUNKS
    try:
        with open(_DOCS_PATH, 'r', encoding='utf-8') as f:
            raw = f.read()
    except Exception:
        return

    # Split on section dividers – keeps each topic as a clean passage
    sections = re.split(r'-{10,}', raw)
    chunks = []
    for sec in sections:
        sec = sec.strip()
        if len(sec) > 60:          # skip tiny/empty fragments
            chunks.append(sec)

    # Also create smaller paragraph-level chunks for fine-grained retrieval
    for sec in sections:
        for para in sec.split('\n\n'):
            para = para.strip()
            if len(para) > 80 and para not in chunks:
                chunks.append(para)

    _CHUNKS = chunks

_load_chunks()


# ─────────────────────────────────────────────
#  TF-IDF retrieval
# ─────────────────────────────────────────────
def _tokenize(text: str) -> list[str]:
    words = re.findall(r'\b[a-z]+\b', text.lower())
    return [w for w in words if w not in STOP_WORDS and len(w) > 2]


def _tfidf_score(query_tokens: list[str], doc: str, all_docs: list[str]) -> float:
    doc_tokens = _tokenize(doc)
    if not doc_tokens:
        return 0.0
    doc_freq = Counter(doc_tokens)
    total_doc_tokens = len(doc_tokens)
    score = 0.0
    N = len(all_docs)

    for term in set(query_tokens):
        tf = doc_freq.get(term, 0) / total_doc_tokens
        # crude IDF: how many docs contain the term
        df = sum(1 for d in all_docs if term in d.lower())
        idf = math.log((N + 1) / (df + 1)) + 1
        score += tf * idf
    return score


def retrieve_relevant_chunks(question: str, top_k: int = 3) -> list[str]:
    """Return the top-k most relevant chunks from career_docs.txt."""
    if not _CHUNKS:
        return []
    q_tokens = _tokenize(question)
    if not q_tokens:
        return []

    scored = [
        (_tfidf_score(q_tokens, chunk, _CHUNKS), chunk)
        for chunk in _CHUNKS
    ]
    scored.sort(key=lambda x: x[0], reverse=True)

    # Only return chunks with a meaningful relevance score
    threshold = 0.005
    relevant = [chunk for score, chunk in scored[:top_k] if score > threshold]
    return relevant


# ─────────────────────────────────────────────
#  Groq API call  (falls back if no key)
# ─────────────────────────────────────────────
_GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
_MODEL    = "llama-3.1-8b-instant"   # free, fast Groq model

def _call_groq(messages: list[dict]) -> str:
    api_key = os.getenv("GROK_API_KEY") or os.getenv("GROQ_API_KEY")
    if not api_key:
        return "⚠️ Groq API key not configured. Please add GROK_API_KEY to your .env file."

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {"model": _MODEL, "messages": messages, "temperature": 0.7, "max_tokens": 800}

    try:
        resp = requests.post(_GROQ_URL, json=payload, headers=headers, timeout=30)
        if resp.status_code == 200:
            return resp.json()['choices'][0]['message']['content']
        else:
            return f"⚠️ Groq error ({resp.status_code}): {resp.text}"
    except requests.Timeout:
        return "⚠️ Request to Groq API timed out. Please try again."
    except Exception as e:
        return f"⚠️ Connection error: {str(e)}"


# ─────────────────────────────────────────────
#  Main RAG entry-point
# ─────────────────────────────────────────────
_SYSTEM_PROMPT = """\
You are a friendly and knowledgeable career guidance AI assistant for students \
from class 10 through degree level. Your role is to give clear, structured, \
and encouraging advice about careers, course selection, skills, and learning paths.

When relevant context from our career knowledge base is provided, \
base your answer on it and say so. If the knowledge base doesn't cover the topic, \
answer from your general knowledge but be transparent about it.

Keep answers concise, well-formatted, and student-friendly. Use bullet points \
and short paragraphs where helpful."""


def ask_career_bot(question: str, history: list[dict] | None = None) -> dict:
    """
    RAG pipeline:
      1. Retrieve top chunks from career_docs.txt
      2. If relevant chunks found → pass them as context to Groq
      3. If no relevant chunks → ask Groq directly (general knowledge fallback)

    Returns: {"answer": str, "source": "docs+ai" | "docs" | "ai"}
    """
    relevant_chunks = retrieve_relevant_chunks(question, top_k=3)
    source = "ai"

    # Build system message
    system_content = _SYSTEM_PROMPT
    if relevant_chunks:
        context_block = "\n\n---\n".join(relevant_chunks[:3])
        system_content += (
            f"\n\n=== CAREER KNOWLEDGE BASE CONTEXT ===\n{context_block}\n"
            "=== END CONTEXT ===\n\n"
            "Use the above context to answer the question where applicable."
        )
        source = "docs+ai"

    messages = [{"role": "system", "content": system_content}]

    # Include recent conversation history (max last 6 turns)
    if history:
        for turn in history[-6:]:
            messages.append({"role": turn["role"], "content": turn["content"]})

    messages.append({"role": "user", "content": question})

    answer = _call_groq(messages)
    return {"answer": answer, "source": source}
