"""
matcher.py — Fuzzy matching de itens normalizados contra catálogo de produtos.
"""

import re
from rapidfuzz import process, fuzz


def _normalizar(texto: str) -> str:
    texto = texto.lower()
    texto = re.sub(r'[^\w\s\d,.]', ' ', texto)
    texto = re.sub(r'\s+', ' ', texto)
    return texto.strip()


def _extrair_quantidade(texto: str) -> tuple[float, str]:
    """Extrai quantidade do início do texto. Retorna (qtd, resto)."""
    m = re.match(r'^([\d]+(?:[.,]\d+)?)\s*', texto.strip())
    if m:
        qtd = float(m.group(1).replace(',', '.'))
        resto = texto[m.end():].strip()
        return qtd, resto
    return 1.0, texto.strip()


def match_item(texto: str, catalogo: list[dict], threshold: int = 60) -> dict | None:
    """
    Tenta casar um texto normalizado com o melhor produto do catálogo.
    Retorna o produto com score, ou None se abaixo do threshold.
    """
    nomes = [_normalizar(p["nome"]) for p in catalogo]
    texto_norm = _normalizar(texto)

    resultado = process.extractOne(
        texto_norm,
        nomes,
        scorer=fuzz.WRatio,
        score_cutoff=threshold,
    )
    if resultado is None:
        return None

    _, score, idx = resultado
    produto = catalogo[idx]
    return {**produto, "score": round(score, 1)}


def match_lista(itens_texto: list[str], catalogo: list[dict], threshold: int = 60) -> list[dict]:
    """
    Processa uma lista de linhas normalizadas (ex: ["5 placa st 240", "1 cx ta25"]).
    Retorna lista de itens com código, nome, quantidade e score.
    """
    resultados = []
    for linha in itens_texto:
        linha = linha.strip()
        if not linha:
            continue

        qtd, texto = _extrair_quantidade(linha)
        produto = match_item(texto, catalogo, threshold)

        if produto:
            resultados.append({
                "codigo":    produto["codigo"],
                "nome":      produto["nome"],
                "unidade":   produto.get("unidade", "UN"),
                "quantidade": qtd,
                "score":     produto["score"],
            })
        else:
            resultados.append({
                "codigo":    None,
                "nome":      texto,
                "unidade":   "UN",
                "quantidade": qtd,
                "score":     0,
            })

    return resultados
