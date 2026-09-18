"""Os modelos de carrossel e as paletas. Contraste pela fórmula da WCAG 2.1: texto comum 4,5:1, texto grande 3:1.

Cada modelo é uma pasta em modelos/ com o molde.html (posição e tamanho). As cores são do arrasta e ficam aqui.
A conferência de contraste que decide é a do render, letra por letra contra os pixels que ficam embaixo dela.
A conta de paleta aqui é o aviso rápido para quem troca as cores no slides.json.
"""
from pathlib import Path

MODELOS_DIR = Path(__file__).resolve().parent / "modelos"

ESCURO = {"fundo": "#0f1115", "texto": "#f4f1ea", "texto2": "#a3a9b4", "destaque": "#ffc83d", "sobre_destaque": "#0f1115"}
CLARO = {"fundo": "#f6f3ec", "texto": "#16181d", "texto2": "#5b616c", "destaque": "#c2410c", "sobre_destaque": "#ffffff"}

# imagem: foto de fundo em cima, faixa na cor de fundo embaixo com o texto
MODELOS = {
    "escuro": {"paleta": ESCURO, "imagem": False},
    "claro": {"paleta": CLARO, "imagem": False},
    "imagem": {"paleta": ESCURO, "imagem": True},
}
VISUAIS = tuple(MODELOS)
PALETAS = {k: m["paleta"] for k, m in MODELOS.items()}

# (cor do texto, cor do fundo, mínimo, onde aparece)
PARES = (
    ("texto", "fundo", 4.5, "título e texto"),
    ("texto2", "fundo", 4.5, "@, número do slide e texto de apoio"),
    ("destaque", "fundo", 3.0, "palavra em destaque (só em título, texto grande)"),
    ("sobre_destaque", "destaque", 3.0, "texto do pedido (grande e em negrito)"),
)


def molde(visual):
    return MODELOS_DIR / visual / "molde.html"


def cores(dados):
    c = dict(PALETAS[dados.get("visual", "escuro")])
    c.update(dados.get("cores", {}))
    return c


def _lum(hexcor):
    rgb = [int(hexcor[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    rgb = [v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4 for v in rgb]
    return 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]


def lum_rgb(r, g, b):
    rgb = [v / 255 for v in (r, g, b)]
    rgb = [v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4 for v in rgb]
    return 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]


def razao(la, lb):
    la, lb = max(la, lb), min(la, lb)
    return (la + 0.05) / (lb + 0.05)


def contraste(a, b):
    return razao(_lum(a), _lum(b))


def minimo_wcag(fs, peso):
    """texto grande (18pt, ou 14pt em negrito) pede 3:1; o resto, 4,5:1. 1pt = 4/3 px."""
    return 3.0 if fs >= 24 or (fs >= 18.66 and peso >= 700) else 4.5


def conferir_contraste(c):
    """devolve [(par, razão, mínimo, onde)] dos pares abaixo do mínimo."""
    ruins = []
    for frente, fundo, minimo, onde in PARES:
        r = contraste(c[frente], c[fundo])
        if r < minimo:
            ruins.append((f"{frente} sobre {fundo}", round(r, 2), minimo, onde))
    return ruins
