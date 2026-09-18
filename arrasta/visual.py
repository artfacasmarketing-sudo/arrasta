"""Paletas e contraste. Contraste pela fórmula da WCAG 2.1: texto comum 4,5:1, texto grande 3:1."""

PALETAS = {
    "escuro": {"fundo": "#0f1115", "texto": "#f4f1ea", "texto2": "#a3a9b4", "destaque": "#ffc83d", "sobre_destaque": "#0f1115"},
    "claro": {"fundo": "#f6f3ec", "texto": "#16181d", "texto2": "#5b616c", "destaque": "#c2410c", "sobre_destaque": "#ffffff"},
}

# (cor do texto, cor do fundo, mínimo, onde aparece)
PARES = (
    ("texto", "fundo", 4.5, "título e texto"),
    ("texto2", "fundo", 4.5, "@, número do slide e texto de apoio"),
    ("destaque", "fundo", 3.0, "palavra em destaque (só em título, texto grande)"),
    ("sobre_destaque", "destaque", 3.0, "texto do pedido (grande e em negrito)"),
)


def cores(dados):
    c = dict(PALETAS[dados.get("visual", "escuro")])
    c.update(dados.get("cores", {}))
    return c


def _lum(hexcor):
    rgb = [int(hexcor[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    rgb = [v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4 for v in rgb]
    return 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]


def contraste(a, b):
    la, lb = sorted((_lum(a), _lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def conferir_contraste(c):
    """devolve [(par, razão, mínimo, onde)] dos pares abaixo do mínimo."""
    ruins = []
    for frente, fundo, minimo, onde in PARES:
        r = contraste(c[frente], c[fundo])
        if r < minimo:
            ruins.append((f"{frente} sobre {fundo}", round(r, 2), minimo, onde))
    return ruins
