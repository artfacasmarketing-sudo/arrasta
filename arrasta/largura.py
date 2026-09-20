"""Largura de um texto em px na fonte embutida, medida sem abrir o navegador.

Quem garante que o texto cabe é o render, que mede no Chromium que desenha o slide. Isto aqui é a mesma
conta feita ANTES, em Python puro com o fontTools que já é dependência, para duas coisas:
  1. o regras.py recusar a palavra que não cabe antes de ligar o navegador, dizendo a palavra e o número;
  2. o prompt.py dizer à IA o limite por papel em LETRAS, em vez de só contar palavras.

A conta é a mesma do navegador: avanço de cada glifo no peso pedido (hmtx + HVAR), mais o kerning do GPOS
(que na Inter varia com o peso, pelo VarStore do GDEF), mais o letter-spacing depois de cada letra.
Cada trecho é medido na mesma face que o navegador usaria, pela unicode-range declarada no comum.css:
o kerning não atravessa a fronteira entre duas faces, no navegador nem aqui.
"""
import re
from functools import lru_cache
from pathlib import Path

from fontTools.ttLib import TTFont
from fontTools.varLib.varStore import VarStoreInstancer

MODELOS_DIR = Path(__file__).resolve().parent / "modelos"
CSS = MODELOS_DIR / "comum.css"
# a face de cada letra sai da unicode-range do @font-face, não de "qual arquivo tem o glifo"
FACE = re.compile(r"@font-face\s*\{[^}]*?src:\s*url\(\"([^\"]+)\"\)[^}]*?unicode-range:\s*([^;]+);", re.S)
FAIXA = re.compile(r"U\+([0-9A-Fa-f]+)(?:-([0-9A-Fa-f]+))?")


@lru_cache(maxsize=None)
def _faces():
    """[(TTFont, faixas)] na ordem do CSS. Na dúvida vale a última declarada, como na cascata."""
    css = CSS.read_text(encoding="utf-8")
    out = []
    for arq, faixas in FACE.findall(css):
        ini_fim = [(int(a, 16), int(b or a, 16)) for a, b in FAIXA.findall(faixas)]
        out.append((TTFont(MODELOS_DIR / arq), tuple(ini_fim)))
    if not out:
        raise RuntimeError(f"nenhum @font-face com unicode-range em {CSS}")
    return tuple(out)


def _face_da_letra(ch):
    """o índice da face que o navegador usaria para esta letra: a última cuja unicode-range a contém."""
    cp = ord(ch)
    escolhida = None
    for i, (_, faixas) in enumerate(_faces()):
        if any(a <= cp <= b for a, b in faixas):
            escolhida = i
    return escolhida


@lru_cache(maxsize=None)
def _avancos(i, peso):
    """glifo -> avanço em unidades da em, no peso pedido (o HVAR faz a conta)."""
    tt = _faces()[i][0]
    gs = tt.getGlyphSet(location={"wght": peso})
    return {n: gs[n].width for n in tt.getGlyphOrder()}, gs.location


@lru_cache(maxsize=None)
def _lookups_de_kern(i):
    """as subtabelas do kern que valem para texto latino, na ordem dos lookups."""
    tt = _faces()[i][0]
    if "GPOS" not in tt:
        return ()
    g = tt["GPOS"].table
    quais = set()
    for sr in g.ScriptList.ScriptRecord:
        if sr.ScriptTag not in ("latn", "DFLT"):
            continue
        sis = [sr.Script.DefaultLangSys] if sr.Script.DefaultLangSys else []
        sis += [r.LangSys for r in sr.Script.LangSysRecord]
        for si in sis:
            quais |= set(si.FeatureIndex)
    lk = set()
    for k in quais:
        fr = g.FeatureList.FeatureRecord[k]
        if fr.FeatureTag == "kern":
            lk |= set(fr.Feature.LookupListIndex)
    fora = []
    for k in sorted(lk):
        sub = []
        for st in g.LookupList.Lookup[k].SubTable:
            sub.append(st.ExtSubTable if g.LookupList.Lookup[k].LookupType == 9 else st)
        fora.append(tuple(sub))
    return tuple(fora)


@lru_cache(maxsize=None)
def _variador(i, peso):
    tt = _faces()[i][0]
    loc = _avancos(i, peso)[1]  # a posição normalizada, com o avar já aplicado
    vs = getattr(tt["GDEF"].table, "VarStore", None) if "GDEF" in tt else None
    return VarStoreInstancer(vs, tt["fvar"].axes, loc) if vs is not None else None


def _valor(i, peso, v):
    """XAdvance de um ValueRecord, com a variação por peso resolvida (DeltaFormat 0x8000 = VariationIndex)."""
    if v is None:
        return 0
    x = getattr(v, "XAdvance", 0) or 0
    d = getattr(v, "XAdvDevice", None)
    if d is not None and getattr(d, "DeltaFormat", 0) == 0x8000:
        var = _variador(i, peso)
        if var is not None:
            x += var[(d.StartSize << 16) | d.EndSize]
    return x


@lru_cache(maxsize=None)
def _kern(i, peso, g1, g2):
    """o ajuste entre dois glifos vizinhos, somado lookup a lookup.

    Dentro de um lookup vale a primeira subtabela que CASA o par — não a primeira que cobre o primeiro
    glifo. A diferença não é detalhe: na Inter, "A" está na cobertura de uma subtabela de pares que não
    tem "V", e o valor de A/V mora na subtabela de classes seguinte. Parar na primeira cobertura zera
    o kerning de maiúscula inteiro (medido: até 28,6 px numa palavra)."""
    total = 0
    for sub in _lookups_de_kern(i):
        for st in sub:
            cob = st.Coverage.glyphs
            if g1 not in cob:
                continue
            if st.Format == 1:
                achou = False
                for pv in st.PairSet[cob.index(g1)].PairValueRecord:
                    if pv.SecondGlyph == g2:
                        total += _valor(i, peso, pv.Value1)
                        achou = True
                        break
                if not achou:
                    continue  # esta subtabela não casa o par; a próxima ainda pode casar
            else:
                c1 = st.ClassDef1.classDefs.get(g1, 0)
                c2 = st.ClassDef2.classDefs.get(g2, 0)
                if not (c1 < st.Class1Count and c2 < st.Class2Count):
                    continue
                total += _valor(i, peso, st.Class1Record[c1].Class2Record[c2].Value1)
            break  # casou: este lookup acabou aqui
    return total


def _trechos_por_face(txt):
    """quebra o texto onde o navegador trocaria de face: o kerning não atravessa essa fronteira."""
    out = []
    for ch in txt:
        i = _face_da_letra(ch)
        if out and out[-1][0] == i:
            out[-1][1].append(ch)
        else:
            out.append((i, [ch]))
    return [(i, "".join(cs)) for i, cs in out]


class SemGlifo(Exception):
    """a fonte embutida não tem esta letra; quem recusa por isso é o render, com o U+ na mensagem."""


def largura(txt, fs, peso, espaco=0.0, caixaalta=False):
    """largura do texto em px, do jeito que o navegador desenha: avanço + kerning + letter-spacing."""
    if caixaalta:
        txt = txt.upper()
    if not txt:
        return 0.0
    total_un, faces = 0.0, _faces()
    for i, pedaco in _trechos_por_face(txt):
        if i is None:
            raise SemGlifo(f"nenhuma face cobre {pedaco!r}")
        tt = faces[i][0]
        cmap = tt.getBestCmap()
        av = _avancos(i, peso)[0]
        nomes = []
        for ch in pedaco:
            n = cmap.get(ord(ch))
            if n is None:
                raise SemGlifo(f"a fonte não tem {ch!r} (U+{ord(ch):04X})")
            nomes.append(n)
        total_un += sum(av[n] for n in nomes)
        total_un += sum(_kern(i, peso, a, b) for a, b in zip(nomes, nomes[1:]))
    upem = faces[0][0]["head"].unitsPerEm
    # o letter-spacing entra depois de cada letra, inclusive a última: é assim que o Chromium mede o trecho
    return total_un / upem * fs + espaco * len(txt)


# ---------------------------------------------------------------------------------------------------
# A geometria de cada campo que a IA escreve, LIDA do navegador (getComputedStyle + a caixa do molde com
# o campo cheio, para a pílula do pedido chegar na largura máxima dela). Não é cópia do CSS na mão:
# testes/test_largura.py relê tudo do molde e falha se alguém mexer no CSS sem mexer aqui.
#   (visual, papel, campo): (tamanho px, peso, letter-spacing px, caixa-alta, largura da caixa px)
ESTILOS = {
    ("escuro", "capa", "titulo"): (104, 800, -3.64, False, 888),
    ("escuro", "capa", "texto"): (42, 500, -0.63, False, 888),
    ("escuro", "miolo", "titulo"): (80, 800, -2.8, False, 888),
    ("escuro", "miolo", "texto"): (48, 450, -0.576, False, 888),
    ("escuro", "final", "titulo"): (84, 800, -2.94, False, 888),
    ("escuro", "final", "texto"): (48, 450, -0.576, False, 888),
    ("escuro", "final", "pedido"): (50, 750, -1, False, 800),
    ("claro", "capa", "titulo"): (123.5, 800, -2.47, False, 938),
    ("claro", "capa", "texto"): (58.1, 400, -0.6972, False, 938),
    ("claro", "miolo", "titulo"): (99.43, 800, -1.9886, False, 939),
    ("claro", "miolo", "texto"): (32.15, 450, 0, False, 939),
    ("claro", "final", "titulo"): (42.67, 500, -0.4267, False, 733.6),
    ("claro", "final", "texto"): (32.15, 450, 0, False, 930),
    ("claro", "final", "pedido"): (99.43, 800, -1.9886, True, 930),
    ("imagem", "capa", "titulo"): (61.11, 800, -0.6111, True, 896),
    ("imagem", "capa", "texto"): (34.69, 500, 0, False, 896),
    ("imagem", "miolo", "titulo"): (61.11, 800, -0.6111, True, 1001),
    ("imagem", "miolo", "texto"): (34.69, 450, 0, False, 1001),
    ("imagem", "final", "titulo"): (53.35, 800, 0, True, 933),
    ("imagem", "final", "texto"): (34.69, 450, 0, False, 933),
    ("imagem", "final", "pedido"): (86.26, 800, 0, True, 933),
}

# Quanto esta conta pode errar contra o navegador que vai desenhar o slide. MEDIDO em 20/09/2026 nos três
# sistemas, no mesmo Chromium 153.0.8010.12, 420 palavras por sistema (20 palavras nos 21 campos):
#   macOS    0,094 px no pior caso   0,0156 px por letra
#   Windows  0,266 px                0,0252 px por letra
#   Linux    4,524 px                0,5152 px por letra
# O Linux é o único que ARREDONDA o avanço de cada glifo (FreeType), e por isso o erro dele cresce com o
# tamanho da palavra — daí a folga ser POR LETRA, e não um número fixo.
# A direção do erro decide o tamanho da folga: quem manda no slide é o render, que mede no navegador do
# usuário. Deixar passar é aceitável (o render remede e recusa); recusar o que aquele navegador aceitaria
# não é. Por isso a folga cobre o PIOR sistema com margem, e não a média dos três.
FOLGA_BASE = 1.0
FOLGA_POR_LETRA = 0.6


def folga(n):
    """a folga em px para um trecho de n letras."""
    return FOLGA_BASE + FOLGA_POR_LETRA * n

# Onde uma palavra longa do português realmente não cabe, e a partir de quantas letras. MEDIDO em 20/09/2026
# sobre um léxico de 4.175 palavras em português tiradas dos nossos próprios arquivos (os 5 documentos do
# arrasta-lab, o README e os textos em português do pacote): o número é o maior tamanho em que TODAS as
# palavras do léxico cabem, e ao lado vai a palavra de N+1 letras que não coube.
# Os campos que não estão aqui não têm limite útil: nenhuma palavra do léxico estourou.
# Isto é orientação para o prompt (lei 17). A garantia é a medida palavra a palavra em regras.verificar().
# Ao lado do número vão as duas palavras que o justificam: a mais larga do léxico COM N letras (cabe) e a
# de N+1 que não cabe. Elas são o que testes/test_largura.py confere — limite sem testemunha é arredondamento.
LIMITE_LETRAS = {
    ("escuro", "capa", "titulo"): (15, "dimensionamento", "compartilhamento"),   # 875 / 888 px · 893 px
    ("claro", "capa", "titulo"): (12, "documentação", "comportamento"),          # 889 / 938 px · 952 px
    ("claro", "miolo", "titulo"): (16, "compartilhamento", "metodologicamente"), # 877 / 939 px · 954 px
    ("claro", "final", "pedido"): (12, "documentação", "comportamento"),         # 852 / 930 px · 932 px
    ("imagem", "final", "pedido"): (15, "dimensionamento", "autopromocionais"),  # 890 / 933 px · 947 px
}

# caracteres por linha: a caixa dividida pela letra média do mesmo léxico, no estilo de cada campo
POR_LINHA = {
    ("escuro", "capa", "titulo"): 16, ("escuro", "capa", "texto"): 41,
    ("escuro", "miolo", "titulo"): 21, ("escuro", "miolo", "texto"): 36,
    ("escuro", "final", "titulo"): 20, ("escuro", "final", "texto"): 36,
    ("escuro", "final", "pedido"): 30,
    ("claro", "capa", "titulo"): 14, ("claro", "capa", "texto"): 32,
    ("claro", "miolo", "titulo"): 17, ("claro", "miolo", "texto"): 56,
    ("claro", "final", "titulo"): 33, ("claro", "final", "texto"): 55,
    ("claro", "final", "pedido"): 14,
    ("imagem", "capa", "titulo"): 22, ("imagem", "capa", "texto"): 49,
    ("imagem", "miolo", "titulo"): 24, ("imagem", "miolo", "texto"): 55,
    ("imagem", "final", "titulo"): 25, ("imagem", "final", "texto"): 51,
    ("imagem", "final", "pedido"): 15,
}

# onde o navegador pode quebrar dentro de um trecho sem espaço: depois do hífen e da barra.
# Medir o trecho inteiro recusaria "responsabilidade-socioambiental", que o Chromium quebra em duas linhas.
QUEBRA = re.compile(r"(?<=[-/])")


def pedacos(txt):
    """o texto partido onde o navegador pode quebrar a linha: espaço, e depois de hífen ou barra."""
    return [p for bruto in (txt or "").split() for p in QUEBRA.split(bruto) if p]


def nao_cabe(txt, visual, papel, campo):
    """[(pedaço, largura, caixa)] do que não cabe na largura do campo. Lista vazia é aprovado.

    Devolve vazio quando o campo não existe no molde (nada a conferir) ou quando alguma letra não está na
    fonte: quem recusa por letra faltando é o render, com o U+ na mensagem."""
    e = ESTILOS.get((visual, papel, campo))
    if e is None:
        return []
    fs, peso, espaco, alta, caixa = e
    fora = []
    for p in pedacos(txt):
        try:
            w = largura(p, fs, peso, espaco, alta)
        except SemGlifo:
            continue
        if w > caixa + folga(len(p)):
            fora.append((p, w, caixa))
    return fora
