"""Renderiza o slides.json em PNG 1080x1350 no Chromium e confere cada slide antes de gravar.

Conferências por slide (o slide só é gravado se passar em todas):
  fonte     todo caractere existe na fonte embutida (nada cai em fonte do sistema)
  carregou  a fonte foi carregada e usada em cada texto
  cabe      o texto cabe na caixa; a letra nunca encolhe
  contraste cores dentro do mínimo da WCAG (conferido antes, no carrossel inteiro)
  canvas    o PNG gravado tem 1080x1350
"""
import re
from pathlib import Path

from fontTools.ttLib import TTFont
from PIL import Image

from . import visual

MODELO = Path(__file__).resolve().parent / "modelo"
FONTES = sorted((MODELO / "fontes").glob("*.woff2"))
W, H = 1080, 1350
NOME_PNG = re.compile(r"^\d{2}\.png$")


class Recusado(Exception):
    """o carrossel não passou numa conferência; a mensagem diz qual e onde."""


def _mapa_de_caracteres():
    cps = set()
    for f in FONTES:
        cps |= set(TTFont(f).getBestCmap())
    return cps


def _papel(i, n):
    return "capa" if i == 1 else "final" if i == n else "miolo"


def conferir_caracteres(dados):
    cmap = _mapa_de_caracteres()
    faltam = []
    for i, s in enumerate(dados["slides"], 1):
        for k in ("titulo", "texto", "pedido"):
            for ch in s.get(k, "").replace("*", ""):
                if not ch.isspace() and ord(ch) not in cmap:
                    faltam.append(f"slide {i}, {k}: \"{ch}\" (U+{ord(ch):04X})")
    return faltam


def renderizar(dados, saida, previa=True):
    """grava saida/01.png ... NN.png (e previa.png). Devolve a lista de arquivos gravados."""
    from playwright.sync_api import sync_playwright

    saida = Path(saida)
    slides = dados["slides"]
    n = len(slides)
    cores = visual.cores(dados)
    ruins = visual.conferir_contraste(cores)
    if ruins:
        raise Recusado("contraste abaixo do mínimo: " + "; ".join(f"{p} {r}:1 (mínimo {m}:1, usado em {o})" for p, r, m, o in ruins))
    faltam = conferir_caracteres(dados)
    if faltam:
        raise Recusado("caractere que a fonte não tem: " + "; ".join(faltam))

    imagens = []
    with sync_playwright() as pw:
        try:
            nav = pw.chromium.launch()
        except Exception as e:
            if "Executable doesn't exist" in str(e):
                raise Recusado("o navegador que desenha os slides não está instalado. Rode: playwright install --only-shell chromium")
            raise
        try:
            pag = nav.new_page(viewport={"width": W, "height": H}, device_scale_factor=1)
            pag.goto((MODELO / "slide.html").as_uri())
            for i, s in enumerate(slides, 1):
                meta = {"cores": cores, "arroba": dados.get("arroba", ""), "i": i, "n": n}
                pag.evaluate("([s, m]) => montar(s, m)", [dict(s, papel=_papel(i, n)), meta])
                m = pag.evaluate("async () => await medir()")
                problemas = []
                for f in m["fontes"]:
                    if f["faces"] == 0 or f["carregadas"] < f["faces"] or not f["familia"]:
                        problemas.append(f"fonte não carregou em {f['id']}")
                z = m["zona"]
                if m["filhos"]:
                    topo = min(c["top"] for c in m["filhos"])
                    fundo = max(c["bottom"] for c in m["filhos"])
                    if topo < z["top"] - 0.5 or fundo > z["bottom"] + 0.5:
                        excesso = round(max(z["top"] - topo, 0) + max(fundo - z["bottom"], 0))
                        problemas.append(f"o texto passa {excesso} px da caixa; encurte o slide")
                for c in m["filhos"]:
                    if c["sw"] > c["cw"] + 1:
                        problemas.append(f"uma palavra do {c['id']} é mais larga que a caixa; troque por uma mais curta")
                if m["canvas"] != [W, H]:
                    problemas.append(f"canvas {m['canvas']}, esperado {W}x{H}")
                if problemas:
                    raise Recusado(f"slide {i}: " + "; ".join(problemas))
                imagens.append(pag.screenshot(clip={"x": 0, "y": 0, "width": W, "height": H}, type="png"))
        finally:
            nav.close()

    # só depois de todos passarem: limpa os PNG de uma rodada anterior e grava os novos
    saida.mkdir(parents=True, exist_ok=True)
    for velho in saida.iterdir():
        if NOME_PNG.match(velho.name) or velho.name == "previa.png":
            velho.unlink()
    gravados = []
    for i, png in enumerate(imagens, 1):
        p = saida / f"{i:02d}.png"
        p.write_bytes(png)
        with Image.open(p) as im:
            if im.size != (W, H):
                raise Recusado(f"{p.name} saiu com {im.size}, esperado {W}x{H}")
        gravados.append(p)
    no_disco = sorted(x for x in saida.iterdir() if NOME_PNG.match(x.name))
    if len(no_disco) != n:
        raise Recusado(f"{n} slides no arquivo, {len(no_disco)} PNG na pasta")
    if previa:
        gravados.append(folha(gravados, saida / "previa.png"))
    return gravados


def folha(pngs, destino):
    """uma imagem com todos os slides lado a lado, para ver o carrossel inteiro de uma vez."""
    lado, gap = 360, 24
    alto = round(lado * H / W)
    cols = len(pngs) if len(pngs) <= 5 else -(-len(pngs) // 2)
    linhas = -(-len(pngs) // cols)
    f = Image.new("RGB", (cols * lado + (cols + 1) * gap, linhas * alto + (linhas + 1) * gap), "#d9d6cf")
    for k, p in enumerate(pngs):
        with Image.open(p) as im:
            f.paste(im.convert("RGB").resize((lado, alto), Image.LANCZOS), (gap + (k % cols) * (lado + gap), gap + (k // cols) * (alto + gap)))
    f.save(destino)
    return destino
