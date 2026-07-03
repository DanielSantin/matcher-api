"""
stage1_rules.py — Tentativa de Estágio 1 (classificação + normalização) sem IA,
usando regex/heurísticas, pra comparar contra o Stage 1 do Groq (ia_parser.py).

Experimento: reproduz as regras do SYSTEM_STAGE1, mas sem entender linguagem
natural de verdade — espera-se que quebre em frases ambíguas/coloquiais que
o LLM resolve por bom senso.
"""

import re

FORA_DE_ESCOPO = (
    "cimento", "tinta", "verniz", "madeira", "elétrico", "eletrico",
    "argamassa", "massa corrida", "pvc", "areia", "tijolo",
)


def _norm_num(s: str) -> float:
    return float(s.replace(".", "").replace(",", ".")) if "," in s or "." in s else float(s)


def _extrair_quantidade(texto: str) -> tuple[float, str]:
    m = re.match(r'^([\d]+(?:[.,]\d+)?)\s*', texto.strip())
    if m:
        return float(m.group(1).replace(',', '.')), texto[m.end():].strip()
    return 1.0, texto.strip()


def _detectar_tipo(msg: str) -> str:
    low = msg.lower()
    if re.search(r'\bforro\b|teto de gesso', low):
        return "forro"
    if re.search(r'\bparede\b', low) and re.search(r'\bml\b|altura', low):
        return "parede"
    return "lista"


def _extrair_forro(msg: str) -> dict:
    low = msg.lower()
    subtipo = "aramado" if re.search(r'aramado|suspenso|arame|pendural', low) else "estruturado"

    area_m2 = None
    perimetro_ml = None

    m = re.search(r'(\d+(?:[.,]\d+)?)\s*(?:metros? quadrados?|m²|m2)\b', low)
    if m:
        area_m2 = _norm_num(m.group(1))
    m = re.search(r'(\d+(?:[.,]\d+)?)\s*metros? de forro', low)
    if m:
        area_m2 = _norm_num(m.group(1))

    m = re.search(r'(\d+(?:[.,]\d+)?)\s*metros? de tabica', low)
    if m:
        perimetro_ml = _norm_num(m.group(1))
    m = re.search(r'per[ií]metro\s*(\d+(?:[.,]\d+)?)', low)
    if m:
        perimetro_ml = _norm_num(m.group(1))

    m = re.search(r'(\d+(?:[.,]\d+)?)\s*(?:metros?\s*)?por\s*(\d+(?:[.,]\d+)?)\s*(?:metros?)?', low)
    if m and area_m2 is None:
        x, y = _norm_num(m.group(1)), _norm_num(m.group(2))
        area_m2 = x * y
        perimetro_ml = 2 * (x + y)

    alt_pend = 0.6
    m = re.search(r'(?:alt\.?\s*pendural|pendural|altura pendural)\s*(\d+(?:[.,]\d+)?)', low)
    if m:
        alt_pend = _norm_num(m.group(1))

    tabica = "natural" if "tabica natural" in low else "branca"

    pergunta = ""
    if area_m2 is None:
        pergunta = "Qual é a área do teto em m²? (ex: para um ambiente de 5×4m, são 20 m²)"
    elif perimetro_ml is None:
        pergunta = "Qual é o perímetro do ambiente em metros lineares? (ex: 5+4+5+4 = 18 ml)"

    return {
        "tipo": "forro", "subtipo": subtipo,
        "area_m2": area_m2, "perimetro_ml": perimetro_ml,
        "tabica": tabica, "alt_pend": alt_pend,
        "obs_geral": "", "pergunta": pergunta,
    }


def _extrair_parede(msg: str) -> dict:
    low = msg.lower()
    paredes = []
    for qtd_s, ml_s, alt_s in re.findall(
        r'(\d+)\s*(?:de\s*)?parede[s]?\s*(?:de\s*)?(\d+(?:[.,]\d+)?)\s*ml.*?(\d+(?:[.,]\d+)?)\s*(?:m|metros)?\s*(?:de\s*)?altura',
        low,
    ):
        for _ in range(int(qtd_s)):
            paredes.append({"ml": _norm_num(ml_s), "altura": _norm_num(alt_s)})

    altura_global = None
    m = re.search(r'(\d+(?:[.,]\d+)?)\s*(?:m|metros)?\s*de\s*altura', low)
    if m:
        altura_global = _norm_num(m.group(1))

    if not paredes and altura_global is not None:
        for qtd_s, ml_s in re.findall(r'(\d+)\s*(?:de\s*)?paredes?\s*(?:de\s*)?(\d+(?:[.,]\d+)?)\s*ml', low):
            for _ in range(int(qtd_s)):
                paredes.append({"ml": _norm_num(ml_s), "altura": altura_global})

    portas = 0
    m = re.search(r'(\d+)\s*portas?', low)
    if m:
        portas = int(m.group(1))

    return {
        "tipo": "parede", "subtipo": "stst",
        "paredes": paredes, "portas": portas,
        "obs_geral": "", "pergunta": "",
    }


# Regras de normalização (ordem importa — primeira que casar, vence).
# Cada entrada: (regex, função(match, texto) -> str | list[str] | None)
def _r_chapa(texto: str) -> str | None:
    if not re.search(r'\bchapa|placa\b', texto):
        return None
    if re.search(r'grande|2,40|2\.40|\b240\b', texto) or re.search(r'1,20|1\.20', texto) and re.search(r'2,40|2\.40', texto):
        return "chapa gesso ST 1,20x2,40m"
    if re.search(r'm[ée]dia|1,80|1\.80|\b180\b', texto):
        return "chapa gesso ST 1,20x1,80m"
    if re.search(r'pequena|\b60\b|0,60', texto):
        return "chapa gesso ST 0,60x2,00m"
    return "chapa gesso ST"


def _r_montante(texto: str) -> str | None:
    m = re.search(r'montante\s*(\d+)', texto)
    return f"montante {m.group(1)}" if m else None


def _r_guia(texto: str) -> str | None:
    m = re.search(r'guias?\s*(\d+)', texto)
    return f"guia {m.group(1)}" if m else None


def _r_parafuso(texto: str) -> str | list[str] | None:
    tem_embalagem = re.search(r'\bcx\b|caixa|pacote|\bpct\b', texto)
    tem_parafuso = re.search(r'parafuso|\bta25\b|\btn25\b', texto)
    tem_6mm_bucha = re.search(r'6\s*mm|bucha', texto)
    if tem_embalagem and tem_parafuso:
        return "caixa parafuso TA25 1000un"
    if tem_parafuso and tem_6mm_bucha:
        return ["parafuso 6mm 4,5x45mm", "bucha 6mm"]
    if tem_parafuso:
        return "parafuso TA25 unitário"
    if re.search(r'\bbucha\b', texto) and "6" in texto:
        return "bucha 6mm"
    return None


def _r_massa(texto: str) -> str | None:
    if re.search(r'\bmassa\b', texto) and "cimentícia" not in texto and "corrida" not in texto:
        return "massa 25kg multiperfil"
    return None


def _r_gesso(texto: str) -> str | None:
    if re.search(r'\bgesso\b', texto) and "cimentícia" not in texto:
        return "gesso revestimento 40kg"
    return None


def _r_tabica(texto: str) -> str | None:
    if "tabica" not in texto:
        return None
    if re.search(r'tabica\s*(branca|\bb\b)', texto):
        return "tabica branca"
    if re.search(r'tabica\s*(natural|\bn\b)', texto):
        return "tabica natural"
    return "tabica"  # sem cor → vai gerar pergunta


def _r_fita_tela(texto: str) -> str | None:
    if re.search(r'\bfita\b|\btela\b', texto):
        if re.search(r'azul|verde|amarel|\d+\s*m\b', texto) and "fita" in texto:
            return None  # tem detalhe específico — não sabemos generalizar, deixa passthrough
        return "fita telada 48mm 90m"
    return None


def _r_f530(texto: str) -> str | None:
    tem_f530 = re.search(r'\bf\s*530\b|\befe\s*530\b|\bf-530\b|\bf\s*47\b|\befe\s*47\b', texto)
    if not tem_f530:
        return None
    if re.search(r'conector', texto):
        return "conector perfil F530"
    if re.search(r'suporte|nivelador', texto):
        return "suporte nivelador F530"
    return "perfil F530 3,00m"


_REGRAS = [_r_f530, _r_tabica, _r_fita_tela, _r_gesso, _r_massa, _r_parafuso, _r_montante, _r_guia, _r_chapa]


def _normalizar_item(texto: str) -> str | list[str]:
    low = texto.lower()
    for regra in _REGRAS:
        resultado = regra(low)
        if resultado is not None:
            return resultado
    return texto  # passthrough — sem regra, deixa como veio


def _extrair_lista(msg: str) -> dict:
    linhas = re.split(r'[\n,]|(?:\s+e\s+)', msg)
    itens: list[str] = []
    obs: list[str] = []
    pergunta = ""

    for linha in linhas:
        linha = linha.strip()
        if not linha:
            continue
        qtd, resto = _extrair_quantidade(linha)
        low = resto.lower()

        if any(fe in low for fe in FORA_DE_ESCOPO):
            obs.append(linha)
            continue

        normalizado = _normalizar_item(resto)
        qtd_str = str(int(qtd)) if qtd == int(qtd) else str(qtd)

        if isinstance(normalizado, list):
            for n in normalizado:
                itens.append(f"{qtd_str} {n}")
        else:
            if normalizado == "tabica":
                pergunta = "A tabica pode ser Branca ou Natural — qual você prefere?"
                continue
            itens.append(f"{qtd_str} {normalizado}")

    obs_geral = "Alguns itens fora do nosso catálogo não foram incluídos: " + "; ".join(obs) if obs else ""

    return {
        "tipo": "lista", "itens": itens,
        "obs_geral": obs_geral, "pergunta": pergunta,
    }


def classificar(mensagem: str) -> dict:
    tipo = _detectar_tipo(mensagem)
    if tipo == "forro":
        return _extrair_forro(mensagem)
    if tipo == "parede":
        return _extrair_parede(mensagem)
    return _extrair_lista(mensagem)
