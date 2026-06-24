"""
matcher.py — Fuzzy matching de itens normalizados contra catálogo de produtos.
"""

import re
from rapidfuzz import process, fuzz


def _normalizar(texto: str) -> str:
    texto = texto.lower()
    # Expande "x" entre números (dimensões) para espaço: "1,20x2,40m" → "1,20 2,40m"
    texto = re.sub(r'(?<=[\d,])x(?=[\d,])', ' ', texto)
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


def _extrair_numeros(texto: str) -> set:
    """Extrai números decimais do texto (ex: '2,40', '1,80', '25')."""
    return set(re.findall(r'\d+[,.]\d+|\d{2,}', texto))


def match_item(texto: str, catalogo: list[dict], threshold: int = 60) -> dict | None:
    """
    Tenta casar um texto normalizado com o melhor produto do catálogo.

    O WRatio sozinho favorece strings mais curtas via partial_ratio.
    Por isso o ranking final usa, em ordem de prioridade:
      1. Cobertura de tokens da query no produto (mais tokens = mais específico)
      2. Números em comum (para desempatar dimensões como 1,80m vs 2,40m)
      3. Score WRatio como critério final
    """
    nomes = [_normalizar(p["nome"]) for p in catalogo]
    texto_norm = _normalizar(texto)
    query_tokens = set(texto_norm.split())
    numeros_query = _extrair_numeros(texto_norm)

    # Top-10 candidatos para re-rankeamento
    candidatos = process.extract(
        texto_norm,
        nomes,
        scorer=fuzz.WRatio,
        score_cutoff=threshold,
        limit=10,
    )
    if not candidatos:
        return None

    def rankear(item):
        _, score, idx = item
        cat_tokens = set(nomes[idx].split())
        # 1. Fração dos tokens da query presentes no produto
        cobertura = sum(1 for t in query_tokens if t in cat_tokens) / max(len(query_tokens), 1)
        # 2. Números exatos em comum
        nums_comuns = len(numeros_query & _extrair_numeros(nomes[idx]))
        return (cobertura, nums_comuns, score)

    melhor = max(candidatos, key=rankear)
    _, score, idx = melhor
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
