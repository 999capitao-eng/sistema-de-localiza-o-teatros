import re

from unidecode import unidecode

PREFIXOS = re.compile(
    r"^(?:cine teatro|cineteatro|cine|teatro|auditorio|sala|centro cultural|"
    r"espaco cultural|casa de espetaculos)\s+"
)


def normalizar_nome(texto):
    s = unidecode(texto or "").lower()
    for variante in ("theatro", "theater", "theatre"):
        s = s.replace(variante, "teatro")
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def nome_sem_prefixo(texto):
    s = normalizar_nome(texto)
    while True:
        novo = PREFIXOS.sub("", s)
        if novo == s:
            return s
        s = novo


def parse_capacidade(valor):
    """Converte '1.200', '350 lugares' etc. em inteiro. Fora de 10..20000 vira None."""
    if valor is None:
        return None
    achados = re.findall(r"\d[\d.,]*", str(valor))
    if not achados:
        return None
    bruto = achados[0].replace(".", "").replace(",", "")
    try:
        n = int(bruto)
    except ValueError:
        return None
    return n if 10 <= n <= 20000 else None
