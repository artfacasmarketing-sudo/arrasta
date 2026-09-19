"""Renderiza o slides.json em PNG 1080x1350 no Chromium e confere cada slide antes de gravar.

Conferências por slide (o slide só é gravado se passar em todas):
  fonte     todo caractere existe na fonte embutida (nada cai em fonte do sistema), inclusive o que o molde escreve
  carregou  a fonte foi carregada e usada em cada texto
  cabe      o texto cabe na caixa; a letra nunca encolhe
  colisão   dois textos do slide ficam mais longe um do outro do que as linhas de cada um entre si
  imagem    a foto de fundo existe e abriu
  contraste cada letra contra os pixels que ficam embaixo dela no slide desenhado (WCAG: 4,5:1, texto grande 3:1)
  canvas    o PNG gravado tem 1080x1350
"""
import io
import math
import re
from pathlib import Path

from fontTools.ttLib import TTFont
from PIL import Image

from . import visual

MODELOS = visual.MODELOS_DIR
FONTES = sorted((MODELOS / "fontes").glob("*.woff2"))
W, H = 1080, 1350
NOME_PNG = re.compile(r"^\d{2}\.png$")
# diferença mínima (0-255, em cinza) para contar como tinta: texto legível difere do fundo muito mais que isso,
# e a foto redesenhada entre duas capturas difere muito menos
LIMIAR_TINTA = 32
COR_CSS = re.compile(r"rgba?\(([\d.]+),\s*([\d.]+),\s*([\d.]+)(?:,\s*([\d.]+))?\)")


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


def imagens_dos_slides(dados, base=None):
    """caminho absoluto da foto de cada slide (a do slide, senão a do carrossel), ou None. Relativo vale a partir de base."""
    base = Path(base or ".")
    fotos = []
    for s in dados["slides"]:
        f = s.get("imagem") or dados.get("imagem")
        if not f:
            fotos.append(None)
            continue
        p = Path(f).expanduser()
        p = (p if p.is_absolute() else base / p).resolve()
        if not p.is_file():
            raise Recusado(f"imagem não encontrada: {f} (procurei em {p})")
        try:
            with Image.open(p) as im:
                im.verify()
        except Exception:
            raise Recusado(f"{f} não é uma imagem que dê para abrir (use JPG, PNG ou WebP)")
        fotos.append(p)
    return fotos


def _cor(css):
    m = COR_CSS.match(css.strip())
    if not m or (m.group(4) is not None and float(m.group(4)) < 1):
        return None
    return tuple(round(float(m.group(k))) for k in (1, 2, 3))


def contraste_sobre_pixels(fundo, trechos):
    """para cada trecho de texto, o PIOR contraste entre a cor da letra e cada pixel do fundo sob as linhas dele."""
    lum_de = {}
    out = []
    for t in trechos:
        cor = _cor(t["cor"])
        if cor is None or not t["caixas"]:
            continue
        lt = visual.lum_rgb(*cor)
        pior = None
        for x, y, w, h in t["caixas"]:
            x0, y0 = max(0, math.floor(x)), max(0, math.floor(y))
            x1, y1 = min(fundo.width, math.ceil(x + w)), min(fundo.height, math.ceil(y + h))
            if x1 <= x0 or y1 <= y0:
                continue
            for _, px in fundo.crop((x0, y0, x1, y1)).getcolors((x1 - x0) * (y1 - y0)):
                lb = lum_de.get(px)
                if lb is None:
                    lb = lum_de[px] = visual.lum_rgb(*px[:3])
                r = visual.razao(lt, lb)
                pior = r if pior is None else min(pior, r)
        if pior is not None:
            out.append({"id": t["id"], "cor": "#%02x%02x%02x" % cor, "fs": t["fs"], "peso": t["peso"],
                        "contraste": round(pior, 2), "minimo": visual.minimo_wcag(t["fs"], t["peso"])})
    return out


def pegada(fundo, com_texto, e):
    """onde o texto pinta: a caixa da tinta somada à caixa de fundo dele, se tiver.

    Tinta é o pixel que muda quando só esse texto aparece, procurado só perto da caixa dele (a foto de fundo pode sair
    redesenhada com diferença pequena entre duas capturas; por isso a diferença tem de passar de LIMIAR_TINTA).
    Devolve None se não achou tinta nenhuma: aí o instrumento não viu o texto e a conferência não vale."""
    from PIL import ImageChops
    x0, y0, x1, y1 = e["caixa"]
    fe, fc, fd, fb = e["folga"]  # o máximo que uma letra pinta fora da caixa do elemento, pela fonte
    area = (max(0, math.floor(x0 - fe)), max(0, math.floor(y0 - fc)),
            min(fundo.width, math.ceil(x1 + fd)), min(fundo.height, math.ceil(y1 + fb)))
    dif = ImageChops.difference(fundo.crop(area), com_texto.crop(area)).convert("L").point(lambda v: 255 if v > LIMIAR_TINTA else 0)
    caixa = dif.getbbox()
    if not caixa:
        return None
    caixa = (caixa[0] + area[0], caixa[1] + area[1], caixa[2] + area[0], caixa[3] + area[1])
    if e["fundo"]:
        caixa = (min(caixa[0], x0), min(caixa[1], y0), max(caixa[2], x1), max(caixa[3], y1))
    return caixa


def colisoes(pegadas):
    """dois textos que dividem a mesma faixa de largura têm de ficar mais longe um do outro do que as linhas de
    cada um ficam entre si; senão viram um bloco só, ou um por cima do outro."""
    out = []
    for k, (a, pa) in enumerate(pegadas):
        for b, pb in pegadas[k + 1:]:
            if not pa or not pb or min(pa[2], pb[2]) <= max(pa[0], pb[0]):
                continue
            vao = max(pb[1] - pa[3], pa[1] - pb[3])
            minimo = max(a["vao"], b["vao"])
            out.append({"a": a["id"], "b": b["id"], "vao": round(vao, 1), "minimo": round(minimo, 1)})
    return out


def renderizar(dados, saida, previa=True, base=None, medidas=None, vaos=None, avisos=None):
    """grava saida/01.png ... NN.png (e previa.png). Devolve a lista de arquivos gravados.

    base: pasta a partir da qual caminho relativo de imagem é lido. medidas: se for uma lista, recebe o contraste
    medido de cada texto de cada slide. avisos: se for uma lista, recebe as linhas de título e pedido que ficaram com
    uma palavra só (não recusa: a letra não encolhe, quem resolve é o texto)."""
    from playwright.sync_api import sync_playwright

    saida = Path(saida)
    slides = dados["slides"]
    n = len(slides)
    nome_visual = dados.get("visual", "escuro")
    molde = MODELOS / nome_visual / "molde.html"
    cores = visual.cores(dados)
    ruins = visual.conferir_contraste(cores)
    if ruins:
        raise Recusado("contraste abaixo do mínimo: " + "; ".join(f"{p} {r}:1 (mínimo {m}:1, usado em {o})" for p, r, m, o in ruins))
    faltam = conferir_caracteres(dados)
    if faltam:
        raise Recusado("caractere que a fonte não tem: " + "; ".join(faltam))
    fotos = imagens_dos_slides(dados, base)
    if visual.MODELOS[nome_visual]["imagem"] and None in fotos:
        raise Recusado(f"o visual imagem pede uma foto no slide {fotos.index(None) + 1}")

    cmap = _mapa_de_caracteres()
    imagens = []
    with sync_playwright() as pw:
        try:
            nav = pw.chromium.launch()
        except Exception as e:
            if "Executable doesn't exist" in str(e):
                raise Recusado("o navegador que desenha os slides não está instalado. Rode: playwright install --only-shell chromium")
            if "shared libraries" in str(e) or "missing dependencies" in str(e):
                raise Recusado("faltam no Linux as bibliotecas que o navegador usa. Rode: "
                               "playwright install --with-deps --only-shell chromium (vai pedir a senha de administrador)")
            raise
        try:
            pag = nav.new_page(viewport={"width": W, "height": H}, device_scale_factor=1)
            pag.goto(molde.as_uri())
            for i, s in enumerate(slides, 1):
                meta = {"cores": cores, "arroba": dados.get("arroba", ""), "i": i, "n": n,
                        "imagem": fotos[i - 1].as_uri() if fotos[i - 1] else ""}
                pag.evaluate("([s, m]) => montar(s, m)", [dict(s, papel=_papel(i, n)), meta])
                m = pag.evaluate("async () => await medir()")
                problemas = []
                for f in m["fontes"]:
                    if f["faces"] == 0 or f["carregadas"] < f["faces"] or not f["familia"]:
                        problemas.append(f"fonte não carregou em {f['id']}")
                for im in m["imagens"]:
                    if not im["ok"]:
                        problemas.append("a imagem de fundo não abriu no navegador")
                for z in m["caixas"]:
                    if not z["filhos"]:
                        continue
                    topo = min(c["top"] for c in z["filhos"])
                    fundo = max(c["bottom"] for c in z["filhos"])
                    if topo < z["top"] - 0.5 or fundo > z["bottom"] + 0.5:
                        excesso = round(max(z["top"] - topo, 0) + max(fundo - z["bottom"], 0))
                        problemas.append(f"o texto passa {excesso} px da caixa; encurte o slide")
                    for c in z["filhos"]:
                        if c["sw"] > c["cw"] + 1 or c["left"] < z["left"] - 0.5 or c["right"] > z["right"] + 0.5:
                            problemas.append(f"uma palavra do {c['id']} é mais larga que a caixa; troque por uma mais curta")
                fora = sorted({ch for ch in m["texto"] if not ch.isspace() and ord(ch) not in cmap})
                if fora:
                    problemas.append("o molde escreve letra que a fonte embutida não tem: " + " ".join(f"U+{ord(ch):04X}" for ch in fora))
                if m["canvas"] != [W, H]:
                    problemas.append(f"canvas {m['canvas']}, esperado {W}x{H}")
                if problemas:
                    raise Recusado(f"slide {i}: " + "; ".join(problemas))
                png = pag.screenshot(clip={"x": 0, "y": 0, "width": W, "height": H}, type="png")
                foto = lambda: Image.open(io.BytesIO(pag.screenshot(clip={"x": 0, "y": 0, "width": W, "height": H}, type="png"))).convert("RGB")
                pag.evaluate("async () => await esconderTexto()")
                sem = foto()
                # autoconferência: sem as letras, a tela tem de mudar; igual à de antes quer dizer foto velha
                com = Image.open(io.BytesIO(png)).convert("RGB")
                from PIL import ImageChops
                for _ in range(3):
                    if ImageChops.difference(com, sem).getbbox():
                        break
                    sem = foto()
                else:
                    raise RuntimeError(f"slide {i}: a foto da tela sem as letras saiu igual à com letras; a conferência não mediu nada")
                medido = contraste_sobre_pixels(sem, m["trechos"])
                baixos = [c for c in medido if c["contraste"] < c["minimo"]]
                if baixos:
                    raise Recusado(f"slide {i}: contraste abaixo do mínimo sobre o fundo desenhado: " + "; ".join(
                        f"{c['id']} {c['contraste']}:1 (mínimo {c['minimo']}:1)" for c in baixos))
                pegadas = []
                for e in m["elementos"]:
                    pag.evaluate("async i => await soOTexto(i)", e["i"])
                    pe = pegada(sem, foto(), e)
                    for _ in range(3):
                        if pe is not None:
                            break
                        pe = pegada(sem, foto(), e)
                    if pe is None:
                        raise RuntimeError(f"slide {i}: a conferência de colisão não achou a tinta de {e['id']}; ela não mediu nada")
                    pegadas.append((e, pe))
                perto = [c for c in colisoes(pegadas) if c["vao"] < c["minimo"]]
                if perto:
                    raise Recusado(f"slide {i}: textos encostados: " + "; ".join(
                        f"{c['a']} e {c['b']} a {c['vao']} px (mínimo {c['minimo']} px, o vão entre as linhas deles)" for c in perto))
                if medidas is not None:
                    medidas.extend(dict(c, slide=i) for c in medido)
                if vaos is not None:
                    vaos.extend(dict(c, slide=i) for c in colisoes(pegadas))
                if avisos is not None:
                    avisos.extend(dict(v, slide=i) for v in m["viuvas"])
                imagens.append(png)
        finally:
            nav.close()

    # só depois de todos passarem: limpa os PNG de uma rodada anterior e grava os novos
    saida.mkdir(parents=True, exist_ok=True)
    try:
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
    except PermissionError as e:
        # no Windows, PNG aberto em outro programa fica travado
        raise Recusado(f"sem permissão para gravar {e.filename}. Se ele estiver aberto em outro programa, feche e rode de novo")
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
