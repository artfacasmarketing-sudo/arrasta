"""As regras que o carrossel nunca quebra.

Cada regra devolve uma lista de problemas. Lista vazia é aprovado.
O que dá para contar vira regra aqui. O que depende de gosto (se o gancho
prende de verdade, se a ordem conta uma história) fica no prompt e na sua leitura.
"""
import re
import unicodedata

from . import largura as L
from .visual import MODELOS, VISUAIS

# limites de palavras por papel
CAPA_TITULO = 12
CAPA_TEXTO = 10
MIOLO_TITULO = 8
MIOLO_TOTAL = 30
FINAL_TOTAL = 25
PEDIDO = 12
SLIDES_MIN = 5
SLIDES_MAX = 10
DESTAQUES_POR_SLIDE = 2

CAMPO = {"titulo": "o título", "texto": "o texto", "pedido": "o pedido"}
TIPOS = ("capa", "miolo", "final")
CAMPOS_SLIDE = {"tipo", "titulo", "texto", "pedido", "imagem"}
CAMPOS_TOPO = {"arroba", "visual", "cores", "tema", "slides", "imagem"}
CHAVES_COR = ("fundo", "texto", "texto2", "destaque", "sobre_destaque")

PALAVRA = re.compile(r"[0-9A-Za-zÀ-ÖØ-öø-ÿ]+(?:[-'][0-9A-Za-zÀ-ÖØ-öø-ÿ]+)*")
NUMERO = re.compile(r"\d+(?:[.,]\d+)*")
ARROBA = re.compile(r"^@[A-Za-z0-9._]{1,30}$")
COR = re.compile(r"^#[0-9a-fA-F]{6}$")

# pedido de ação fora do último slide corta a leitura
PEDIDO_FORA = re.compile(
    r"\b(comenta|comente|comentem|compartilha|compartilhe|compartilhem|clica|clique|cliquem)\b"
    r"|\b(salva|salve|salvem) (esse|este|isso|o post|pra|para)\b"
    r"|\blink na bio\b|\bme (segue|siga)\b|\bsegue a gente\b|\bmarca (um|uma|quem|alguém)\b|\bmarque (um|uma|quem|alguém)\b",
    re.IGNORECASE,
)
CLICHES = ("você sabia", "descubra", "segredo", "ninguém te conta", "muda tudo", "guia definitivo",
           "de uma vez por todas", "o que ninguém fala", "confira")
TRAVESSAO = re.compile(r"[–—]")
LINK = re.compile(r"https?://|www\.", re.IGNORECASE)
HASHTAG = re.compile(r"(^|\s)#\w")


def _sem_marcas(s):
    return s.replace("*", "")


def palavras(s):
    return len(PALAVRA.findall(_sem_marcas(s or "")))


def _tem_emoji(s):
    for ch in s:
        cat = unicodedata.category(ch)
        if cat == "So" or 0x1F000 <= ord(ch) <= 0x1FAFF or 0x2600 <= ord(ch) <= 0x27BF or ord(ch) == 0xFE0F:
            return True
    return False


def _normalizar(s):
    return unicodedata.normalize("NFC", s or "").strip()


def normalizar(dados):
    """limpa espaços, junta texto vazio a ausente. Não muda palavra nenhuma."""
    for s in dados.get("slides", []):
        if isinstance(s, dict):
            for k in ("titulo", "texto", "pedido"):
                if k in s and isinstance(s[k], str):
                    s[k] = _normalizar(s[k])
                    if not s[k]:
                        del s[k]
    return dados


def verificar(dados, fonte_dos_numeros=None, miolo_sem_imagem=None):
    """devolve [(regra, onde, problema)]. fonte_dos_numeros: texto onde todo número dos slides tem de aparecer.
    miolo_sem_imagem (opcional): teto de palavras do slide do miolo que NÃO tem imagem (nem no slide, nem no topo).
    Sem ele, vale MIOLO_TOTAL em todo slide, como sempre; slide com imagem fica sempre em MIOLO_TOTAL. O título do
    miolo continua em MIOLO_TITULO. Quem integra passa um teto maior só onde o molde tem espaço para texto."""
    erros = []
    add = lambda regra, onde, msg: erros.append((regra, onde, msg))

    if not isinstance(dados, dict):
        return [("formato", "arquivo", "o arquivo tem de ser um objeto JSON com a lista \"slides\"")]
    for k in dados:
        if k not in CAMPOS_TOPO:
            add("formato", "arquivo", f"campo desconhecido \"{k}\" (os aceitos: {', '.join(sorted(CAMPOS_TOPO))})")
    if "arroba" in dados and not (isinstance(dados["arroba"], str) and ARROBA.match(dados["arroba"])):
        add("formato", "arroba", "use o formato @seuperfil (letras, números, ponto e _)")
    if "visual" in dados and dados["visual"] not in VISUAIS:
        add("formato", "visual", "use " + ", ".join(f"\"{v}\"" for v in VISUAIS))
    if "imagem" in dados and not (isinstance(dados["imagem"], str) and dados["imagem"].strip()):
        add("formato", "imagem", "imagem é o caminho do arquivo da foto, entre aspas")
    if "cores" in dados:
        c = dados["cores"]
        if not isinstance(c, dict):
            add("formato", "cores", "cores tem de ser um objeto, ex.: {\"destaque\": \"#ffcc00\"}")
        else:
            for k, v in c.items():
                if k not in CHAVES_COR:
                    add("formato", "cores", f"cor desconhecida \"{k}\" (as aceitas: {', '.join(CHAVES_COR)})")
                elif not (isinstance(v, str) and COR.match(v)):
                    add("formato", "cores", f"{k}: use cor no formato #rrggbb")

    slides = dados.get("slides")
    if not isinstance(slides, list) or not slides:
        add("formato", "slides", "falta a lista \"slides\"")
        return erros

    # estrutura: capa, miolo, final
    n = len(slides)
    if not SLIDES_MIN <= n <= SLIDES_MAX:
        add("estrutura", "carrossel", f"{n} slides; o carrossel tem de ter de {SLIDES_MIN} a {SLIDES_MAX}")
    for i, s in enumerate(slides, 1):
        onde = f"slide {i}"
        if not isinstance(s, dict):
            add("formato", onde, "cada slide é um objeto com tipo e titulo")
            continue
        for k in s:
            if k not in CAMPOS_SLIDE:
                add("formato", onde, f"campo desconhecido \"{k}\" (os aceitos: tipo, titulo, texto, pedido, imagem)")
        for k in ("titulo", "texto", "pedido", "imagem"):
            if k in s and not isinstance(s[k], str):
                add("formato", onde, f"{k} tem de ser texto")
        tipo = s.get("tipo")
        esperado = "capa" if i == 1 else "final" if i == n else "miolo"
        if tipo not in TIPOS:
            add("formato", onde, f"tipo \"{tipo}\" não existe (use capa, miolo ou final)")
        elif tipo != esperado:
            add("estrutura", onde, f"é \"{tipo}\", mas aqui vai \"{esperado}\" (capa primeiro, final por último, miolo no meio)")
        if not isinstance(s.get("titulo"), str) or not s.get("titulo"):
            add("formato", onde, "falta o titulo")
    if any(not isinstance(s, dict) or not isinstance(s.get("titulo", ""), str) for s in slides):
        return erros
    if MODELOS.get(dados.get("visual", "escuro"), {}).get("imagem"):
        sem = [str(i) for i, s in enumerate(slides, 1) if not (s.get("imagem") or dados.get("imagem"))]
        if sem:
            add("formato", "imagem", f"o visual imagem pede uma foto: \"imagem\" no topo (uma para todos) ou em cada slide (falta no slide {', '.join(sem)})")

    vis = dados.get("visual", "escuro")
    for i, s in enumerate(slides, 1):
        onde = f"slide {i}"
        tit, txt, ped = s.get("titulo", ""), s.get("texto", ""), s.get("pedido", "")
        papel = "capa" if i == 1 else "final" if i == n else "miolo"

        if papel == "capa":
            if palavras(tit) > CAPA_TITULO:
                add("gancho na capa", onde, f"titulo com {palavras(tit)} palavras; a capa aceita até {CAPA_TITULO}")
            if palavras(txt) > CAPA_TEXTO:
                add("gancho na capa", onde, f"texto com {palavras(txt)} palavras; na capa até {CAPA_TEXTO}")
        elif papel == "miolo":
            if palavras(tit) > MIOLO_TITULO:
                add("pouco texto por slide", onde, f"titulo com {palavras(tit)} palavras; até {MIOLO_TITULO}")
            total = palavras(tit) + palavras(txt)
            teto = MIOLO_TOTAL
            if miolo_sem_imagem is not None and not (s.get("imagem") or dados.get("imagem")):
                teto = miolo_sem_imagem
            if total > teto:
                add("pouco texto por slide", onde, f"{total} palavras no slide; até {teto}")
        else:
            if not ped:
                add("pedido no lugar certo", onde, "o último slide tem de ter o pedido (comentar, salvar ou mandar pra alguém)")
            elif palavras(ped) > PEDIDO:
                add("pedido no lugar certo", onde, f"pedido com {palavras(ped)} palavras; até {PEDIDO}")
            total = palavras(tit) + palavras(txt) + palavras(ped)
            if total > FINAL_TOTAL:
                add("pedido no lugar certo", onde, f"{total} palavras no último slide; até {FINAL_TOTAL}, para o pedido não se perder")

        if papel != "final":
            if ped:
                add("pedido no lugar certo", onde, "pedido só no último slide")
            m = PEDIDO_FORA.search(_sem_marcas(tit + " " + txt))
            if m:
                add("pedido no lugar certo", onde, f"\"{m.group(0)}\" é pedido; pedido só no último slide")

        # cabe na largura: uma palavra longa do português não cabe sozinha e nenhuma contagem de palavras
        # pega isso. Medida aqui na fonte embutida, antes de ligar o navegador; o render remede no Chromium.
        for campo in ("titulo", "texto", "pedido"):
            for pedaco, w, caixa in L.nao_cabe(_sem_marcas(s.get(campo, "")), vis, papel, campo):
                add("cabe na caixa", onde, f"a palavra \"{pedaco}\" tem {round(w)} px e {CAMPO[campo]} só tem "
                                           f"{round(caixa)} px de largura; passa {round(w - caixa)} px")

        tudo = " ".join(x for x in (tit, txt, ped) if x)
        if _tem_emoji(tudo):
            add("escrita", onde, "sem emoji")
        if TRAVESSAO.search(tudo):
            add("escrita", onde, "sem travessão; use vírgula ou ponto")
        if LINK.search(tudo):
            add("escrita", onde, "sem link no slide")
        if HASHTAG.search(tudo):
            add("escrita", onde, "sem hashtag no slide")
        baixo = _sem_marcas(tudo).lower()
        for c in CLICHES:
            if c in baixo:
                add("escrita", onde, f"clichê \"{c}\"; diga a coisa concreta")
        for k in ("titulo", "texto", "pedido"):
            v = s.get(k, "")
            if v.count("*") % 2:
                add("formato", onde, f"{k}: destaque aberto sem fechar (use *palavra*)")
        if sum(s.get(k, "").count("*") // 2 for k in ("titulo", "texto", "pedido")) > DESTAQUES_POR_SLIDE:
            add("formato", onde, f"no máximo {DESTAQUES_POR_SLIDE} destaques por slide")

        if fonte_dos_numeros is not None:
            base = {x.replace(",", ".") for x in NUMERO.findall(fonte_dos_numeros)}
            for num in NUMERO.findall(tudo):
                if num.replace(",", ".") not in base:
                    add("número com fonte", onde, f"o número {num} não está no tema; a IA não inventa número")
    return erros


def descrever():
    return f"""As regras que o arrasta confere em todo carrossel:

1. Estrutura: de {SLIDES_MIN} a {SLIDES_MAX} slides. Capa primeiro, miolo no meio, final por último.
2. Gancho na capa: título com até {CAPA_TITULO} palavras e texto de apoio com até {CAPA_TEXTO}.
3. Pouco texto por slide: no miolo, título com até {MIOLO_TITULO} palavras e até {MIOLO_TOTAL} palavras no slide.
4. Pedido no lugar certo: o pedido (comentar, salvar, mandar pra alguém) só no último slide,
   com até {PEDIDO} palavras, e o último slide com até {FINAL_TOTAL} palavras no total.
5. Escrita: sem emoji, sem travessão, sem hashtag, sem link e sem clichê de guru.
6. Número com fonte: quando o texto vem da IA, todo número nos slides tem de estar no tema que você escreveu.
7. Cabe na caixa: a letra nunca encolhe. Palavra mais larga que o slide é recusada aqui, medida na fonte,
   antes de abrir o navegador; o resto (quantas linhas o texto dá) é remedido no slide desenhado.
   Se o texto não cabe, o slide é recusado e você encurta. Dois textos não encostam.
8. Dá para ler: o contraste de cada letra é medido no slide desenhado, contra o que fica embaixo dela, inclusive a foto.

O que a máquina não mede (se o gancho prende, se a ordem conta uma história) vai como orientação no prompt."""
