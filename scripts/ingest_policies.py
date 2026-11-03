"""Convert data/políticas_da_loja.pdf into data/policies_chunks.json.

Run manually whenever the PDF changes:

    python scripts/ingest_policies.py

The chat runtime never reads the PDF directly -- only the JSON this
produces, which is committed to the repo. Requires the `pdftotext` CLI
(poppler-utils) to be installed.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from emporio_agent import config  # noqa: E402

PDF_PATH = config.DATA_DIR / "políticas_da_loja.pdf"
OUT_PATH = config.DATA_DIR / "policies_chunks.json"

_HEADER_RE = re.compile(r"^Emp[oó]rio da M[uú]sica Manual de Pol[ií]ticas e Procedimentos$")
_FOOTER_RE = re.compile(r"^P[aá]gina \d+$")
_SECTION_RE = re.compile(r"^(\d{1,2}(?:\.\d{1,2})?)\.?\s+([A-ZÀ-Ü].{0,90})$")
_SKIP_PREFIXES = (
    "EMPÓRIO DA MÚSICA",
    "Sua música começa aqui",
    "Versão 2.1",
    "Última atualização",
    "Documento interno",
)

# Editorial notes attached to chunks the manual states ambiguously or
# contradictorily. Surfaced by policies.py alongside the matching chunk so
# the agent (and the README's "Assumptions" section) stay consistent.
NOTES: dict[str, str] = {
    "1.2": (
        "Nota editorial: a capa e esta seção trazem o telefone/WhatsApp "
        "(67) 3341-4444, mas a seção 7 cita (67) 3321-4500 como canal de "
        "WhatsApp. Tratamos (67) 3341-4444 (repetido 2x, incluindo a capa) "
        "como o número correto. O e-mail aqui aparece como "
        "'contato@empóriodamusica.com.br' (com acento no 'ó'), o que é um "
        "erro de digitação -- o domínio correto, usado na capa, é "
        "'contato@emporiodamusica.com.br' (sem acento)."
    ),
    "3": (
        "Nota editorial: esta seção resume o parcelamento como 'até 12x, "
        "parcela mínima de R$100,00'. A seção 3.1 detalha faixas "
        "diferentes por quantidade de parcelas. Tratamos 3.1 como a regra "
        "vigente e esta tabela como apenas a faixa mais alta (7-12x)."
    ),
    "4.2": (
        "Nota editorial: esta seção dá 30 dias corridos (da compra) para "
        "troca por defeito de fabricação, mas a seção 8.1 garante 90 dias "
        "(do recebimento) de garantia legal. Entre 30 e 90 dias contados "
        "do recebimento, a loja encaminha a decisão para a equipe humana "
        "em vez de negar ou aceitar automaticamente."
    ),
    "5.1": (
        "Nota editorial: 'frete grátis para pedidos acima de R$500,00' é "
        "interpretado como estritamente maior que R$500 -- um pedido de "
        "exatos R$500,00 paga a taxa fixa de R$35. A 'região metropolitana' "
        "de Campo Grande não é definida no manual; tratamos apenas a "
        "cidade de Campo Grande como entrega local, e qualquer outra "
        "cidade como 'outras cidades' (seção 5.2)."
    ),
    "4.1": (
        "Nota editorial: o direito de arrependimento vale para compras "
        "online e é contado a partir do recebimento do produto. O dataset "
        "de pedidos não registra o canal da compra nem a data real de "
        "recebimento (só uma previsão de entrega), então o agente deve "
        "perguntar essas informações ao cliente antes de dar uma resposta "
        "definitiva em casos de fronteira."
    ),
}


def _run_pdftotext(pdf_path: Path) -> str:
    result = subprocess.run(
        ["pdftotext", "-layout", str(pdf_path), "-"],
        capture_output=True,
        check=True,
        text=True,
    )
    return result.stdout


def _clean_lines(raw_text: str) -> list[str]:
    lines = []
    for line in raw_text.splitlines():
        line = line.strip()
        if not line:
            continue
        if _HEADER_RE.match(line) or _FOOTER_RE.match(line):
            continue
        if any(line.startswith(prefix) for prefix in _SKIP_PREFIXES):
            continue
        lines.append(line)
    return lines


def _parse_sections(lines: list[str]) -> list[dict]:
    sections: list[dict] = []
    current: dict | None = None
    for line in lines:
        match = _SECTION_RE.match(line)
        if match:
            number, title = match.group(1), match.group(2).strip()
            current = {"number": number, "title": title, "lines": [title]}
            sections.append(current)
            continue
        if current is not None:
            current["lines"].append(line)
    return sections


def build_chunks() -> list[dict]:
    raw_text = _run_pdftotext(PDF_PATH)
    lines = _clean_lines(raw_text)
    sections = _parse_sections(lines)
    chunks = []
    for section in sections:
        number = section["number"]
        chunk = {
            "section": number,
            "title": section["title"],
            "text": "\n".join(section["lines"]),
        }
        if number in NOTES:
            chunk["note"] = NOTES[number]
        chunks.append(chunk)
    return chunks


def main() -> None:
    chunks = build_chunks()
    OUT_PATH.write_text(
        json.dumps(chunks, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Wrote {len(chunks)} chunks to {OUT_PATH}")


if __name__ == "__main__":
    main()
