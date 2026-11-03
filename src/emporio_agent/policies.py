"""BM25 retrieval over the store's policy manual.

The manual is ~4k tokens across 28 sections -- far too small to justify an
embeddings/vector-store pipeline (and its added latency, cost, and
dependency surface). A hand-rolled BM25 with light stemming, stopwords,
and a domain synonym map is a few dozen lines, has zero external
dependencies, and is trivially debuggable. See README "Technical
decisions" for the fuller rationale.
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

from . import config
from .data import fold

_TOKEN_RE = re.compile(r"[a-z0-9]+")

_STOPWORDS = {
    fold(w)
    for w in (
        "a as o os de da do das dos e em um uma uns umas para por com no na "
        "nos nas que se ao aos à às é são ser foi como mais menos sem sob "
        "sobre ou isso esse essa isto este esta aquele aquela também já "
        "muito pode podem deve devem"
    ).split()
}

# Maps a query word to related words that appear in the manual but not in
# the customer's own phrasing (e.g. a customer says "devolver", the manual
# says "arrependimento"). Expansion is query-side only; the index itself is
# built straight from the manual's own words.
_SYNONYMS: dict[str, list[str]] = {
    "devolver": ["arrependimento", "devolucao", "reembolso"],
    "devolucao": ["arrependimento", "reembolso", "devolver"],
    "arrepender": ["arrependimento"],
    "cancelar": ["arrependimento", "devolucao"],
    "trocar": ["troca", "trocas"],
    "defeito": ["garantia", "defeito"],
    "quebrado": ["defeito", "garantia"],
    "parcelar": ["parcelamento", "parcelas", "credito"],
    "parcela": ["parcelamento", "parcelas"],
    "parcelas": ["parcelamento"],
    "boleto": ["pagamento"],
    "pix": ["pagamento", "desconto"],
    "cartao": ["pagamento", "credito", "debito"],
    "entrega": ["frete", "envio", "entregas"],
    "frete": ["entrega", "envio"],
    "envio": ["frete", "entrega"],
    "prazo": ["entrega", "frete", "garantia"],
    "rastreio": ["rastreamento"],
    "rastrear": ["rastreamento"],
    "horario": ["funcionamento"],
    "hora": ["horario", "funcionamento"],
    "abre": ["funcionamento", "horario"],
    "abrem": ["funcionamento", "horario"],
    "abrir": ["funcionamento", "horario"],
    "fecha": ["funcionamento", "horario"],
    "fecham": ["funcionamento", "horario"],
    "fechar": ["funcionamento", "horario"],
    "aberto": ["funcionamento"],
    "fechado": ["funcionamento"],
    "feriado": ["funcionamento"],
    "endereco": ["dados", "empresa"],
    "telefone": ["dados", "empresa", "whatsapp"],
    "whatsapp": ["atendimento"],
    "promocao": ["promocoes", "desconto"],
    "desconto": ["promocao", "promocoes"],
    "garantia": ["defeito"],
}


def _stem(token: str) -> str:
    """Strip a trailing plural -s; good enough for a small PT manual."""
    if len(token) > 3 and token.endswith("s") and not token.endswith("ss"):
        return token[:-1]
    return token


def _tokenize(text: str, expand_synonyms: bool = False) -> list[str]:
    tokens = [_stem(t) for t in _TOKEN_RE.findall(fold(text))]
    tokens = [t for t in tokens if t not in _STOPWORDS]
    if expand_synonyms:
        expanded = list(tokens)
        for t in tokens:
            expanded.extend(_stem(s) for s in _SYNONYMS.get(t, []))
        return expanded
    return tokens


class PolicyIndex:
    K1 = 1.5
    B = 0.75

    def __init__(self, chunks_path: Path | None = None):
        path = Path(chunks_path or (config.DATA_DIR / "policies_chunks.json"))
        self.chunks: list[dict] = json.loads(path.read_text(encoding="utf-8"))

        self._doc_tokens: list[list[str]] = []
        doc_freq: dict[str, int] = {}
        for chunk in self.chunks:
            tokens = _tokenize(f"{chunk['title']} {chunk['text']}")
            self._doc_tokens.append(tokens)
            for term in set(tokens):
                doc_freq[term] = doc_freq.get(term, 0) + 1

        n_docs = len(self.chunks)
        self._avg_len = (sum(len(t) for t in self._doc_tokens) / n_docs) if n_docs else 0
        self._idf = {
            term: math.log((n_docs - df + 0.5) / (df + 0.5) + 1) for term, df in doc_freq.items()
        }

    def search(self, query: str, top_k: int = 3, min_score: float = 0.1) -> list[dict]:
        query_tokens = _tokenize(query, expand_synonyms=True)
        if not query_tokens:
            return []

        scores = []
        for i, doc_tokens in enumerate(self._doc_tokens):
            if not doc_tokens:
                scores.append(0.0)
                continue
            doc_len = len(doc_tokens)
            term_freq: dict[str, int] = {}
            for t in doc_tokens:
                term_freq[t] = term_freq.get(t, 0) + 1

            score = 0.0
            for term in query_tokens:
                idf = self._idf.get(term)
                if idf is None:
                    continue
                f = term_freq.get(term, 0)
                if f == 0:
                    continue
                denom = f + self.K1 * (1 - self.B + self.B * doc_len / self._avg_len)
                score += idf * (f * (self.K1 + 1)) / denom
            scores.append(score)

        ranked = sorted(range(len(self.chunks)), key=lambda i: scores[i], reverse=True)
        results = []
        for i in ranked[:top_k]:
            if scores[i] < min_score:
                continue
            chunk = self.chunks[i]
            result = {"section": chunk["section"], "title": chunk["title"], "text": chunk["text"]}
            if "note" in chunk:
                result["note"] = chunk["note"]
            results.append(result)
        return results
