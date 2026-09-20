"""arrasta: escreva o tema, saia com o carrossel pronto pra postar."""
import argparse
import codecs
import json
import re
import sys
import unicodedata
from pathlib import Path

from . import __version__
from . import prompt as P
from . import ia, regras, resposta, visual

PEDIDO = "pedido.json"
# nomes que o Windows não aceita como pasta
RESERVADOS = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)), *(f"lpt{i}" for i in range(1, 10))}


class ArquivoIlegivel(Exception):
    pass


def ler_texto(arq):
    """lê o arquivo como o editor gravou: UTF-8 com ou sem BOM, ou UTF-16 (Bloco de Notas e PowerShell antigos)."""
    b = Path(arq).read_bytes()
    if b.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        return b.decode("utf-16")
    try:
        return b.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ArquivoIlegivel(f"{arq} não está em UTF-8. Abra no editor, salve de novo escolhendo a codificação UTF-8 e rode de novo")


def slug(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    if len(s) > 40:
        s = s[:41].rsplit("-", 1)[0] if "-" in s[:41] else s[:40]
    return f"{s}-carrossel" if s in RESERVADOS else s or "carrossel"


def mostrar_erros(erros):
    print(f"\nO carrossel quebrou {len(erros)} regra(s):", file=sys.stderr)
    for regra, onde, msg in erros:
        print(f"  {onde} [{regra}]: {msg}", file=sys.stderr)


def aplicar_visual(dados, a, base, pedido=None):
    """--visual e --imagem valem sobre o arquivo; caminho de foto relativo vira absoluto a partir de base."""
    pedido = pedido or {}
    v = getattr(a, "visual", None) or pedido.get("visual")
    if v:
        dados["visual"] = v
    img = getattr(a, "imagem", None)
    if img:
        dados["imagem"] = str(Path(img).expanduser().resolve())
    elif pedido.get("imagem") and "imagem" not in dados:
        dados["imagem"] = pedido["imagem"]
    for d in [dados] + [s for s in dados.get("slides", []) if isinstance(s, dict)]:
        f = d.get("imagem")
        if isinstance(f, str) and f.strip() and not Path(f).expanduser().is_absolute():
            d["imagem"] = str((Path(base) / Path(f).expanduser()).resolve())
    return dados


def gerar_pngs(dados, saida, avisos=None, recusa=None):
    """recusa: se for uma lista, recebe o que o texto pode resolver quando o render recusa (para o correcao.txt)."""
    from .render import Recusado, renderizar
    avisos = [] if avisos is None else avisos
    try:
        arquivos = renderizar(dados, saida, avisos=avisos)
    except Recusado as e:
        print(f"\nRecusado: {e}", file=sys.stderr)
        if recusa is not None:
            recusa.extend(e.para_ia)
        return 1
    print(f"\n{len(arquivos) - 1} slides prontos em {Path(saida).resolve()}")
    for a in arquivos:
        print(f"  {a.name}")
    if avisos:
        sys.stdout.flush()
        print("\nAviso (os slides saíram, mas dá para melhorar):", file=sys.stderr)
        for v in avisos:
            print(f"  {P.aviso_viuva(v)}", file=sys.stderr)
    return 0


def gravar_aviso(pasta, avisos):
    """no caminho com IA, o aviso vira o texto pronto para colar na conversa; sem aviso, some o correcao.txt velho."""
    corr = Path(pasta) / "correcao.txt"
    if avisos:
        corr.write_text(P.ajuste_linhas(avisos), encoding="utf-8")
        print(f"Para ajustar, cole o texto de {corr} na mesma conversa da IA e rode de novo.", file=sys.stderr)
    elif corr.exists():
        corr.unlink()


def validar_e_gerar(dados, saida, fonte=None, avisos=None, recusa=None):
    regras.normalizar(dados)
    erros = regras.verificar(dados, fonte_dos_numeros=fonte)
    if erros:
        mostrar_erros(erros)
        return erros
    saida = Path(saida)
    saida.mkdir(parents=True, exist_ok=True)
    (saida / "slides.json").write_text(json.dumps(dados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return gerar_pngs(dados, saida, avisos, recusa)


def cmd_render(a):
    arq = Path(a.arquivo)
    if not arq.exists():
        print(f"Arquivo não encontrado: {arq}", file=sys.stderr)
        return 2
    try:
        dados = json.loads(ler_texto(arq))
    except ArquivoIlegivel as e:
        print(e, file=sys.stderr)
        return 1
    except json.JSONDecodeError as e:
        print(f"{arq} não é um JSON válido (linha {e.lineno}, coluna {e.colno}): {e.msg}", file=sys.stderr)
        return 1
    if a.arroba:
        dados["arroba"] = a.arroba
    if isinstance(dados, dict):
        aplicar_visual(dados, a, arq.parent)
    regras.normalizar(dados)
    erros = regras.verificar(dados)
    if erros:
        mostrar_erros(erros)
        return 1
    saida = Path(a.saida or Path("saida") / arq.stem)
    r = gerar_pngs(dados, saida)
    if r == 0 and (saida / "slides.json").resolve() != arq.resolve():
        (saida / "slides.json").write_text(json.dumps(dados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return r


def cmd_prompt(a, motivo=None):
    pasta = Path(a.saida or Path("saida") / slug(a.tema))
    pasta.mkdir(parents=True, exist_ok=True)
    texto = P.montar(a.tema, a.publico, a.slides, a.visual)
    (pasta / "prompt.txt").write_text(texto, encoding="utf-8")
    img = str(Path(a.imagem).expanduser().resolve()) if a.imagem else None
    (pasta / PEDIDO).write_text(json.dumps({"tema": a.tema, "publico": a.publico, "arroba": a.arroba, "slides": a.slides,
                                            "visual": a.visual, "imagem": img},
                                           ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    resp = pasta / "resposta.txt"
    if motivo:
        print(motivo + "\n")
    print("=" * 72)
    print(texto)
    print("=" * 72)
    print(f"""
1. Copie o prompt acima (ele também está em {pasta / 'prompt.txt'}).
2. Cole numa conversa nova de qualquer IA (ChatGPT, Claude, Gemini).
3. Salve a resposta da IA inteira no arquivo {resp}
4. Rode:  arrasta montar {resp}""")
    return 0


def cmd_montar(a):
    arq = Path(a.resposta)
    if not arq.exists():
        print(f"Arquivo não encontrado: {arq}. Salve nele a resposta da IA.", file=sys.stderr)
        return 2
    pedido = {}
    if (arq.parent / PEDIDO).exists():
        pedido = json.loads((arq.parent / PEDIDO).read_text(encoding="utf-8"))
    try:
        dados = resposta.extrair(ler_texto(arq))
    except ArquivoIlegivel as e:
        print(e, file=sys.stderr)
        return 1
    except resposta.RespostaInvalida as e:
        print(f"Não deu para ler a resposta: {e}", file=sys.stderr)
        return 1
    arroba = a.arroba or pedido.get("arroba")
    if arroba:
        dados["arroba"] = arroba
    aplicar_visual(dados, a, arq.parent, pedido)
    fonte = " ".join(x for x in (pedido.get("tema"), pedido.get("publico")) if x) if pedido else None
    if fonte is None:
        print(f"(sem {PEDIDO} ao lado da resposta: a regra do número com fonte não foi conferida)")
    avisos, recusa = [], []
    r = validar_e_gerar(dados, a.saida or arq.parent, fonte, avisos, recusa)
    corr = arq.parent / "correcao.txt"
    # regra quebrada, ou slide recusado no desenho por algo que o texto resolve (não coube, textos encostados):
    # os dois viram o mesmo correcao.txt, pronto para colar na conversa da IA
    if isinstance(r, list) or recusa:
        corr.write_text(P.correcao(r if isinstance(r, list) else recusa), encoding="utf-8")
        print(f"\nCole o texto de {corr} na mesma conversa da IA, salve a nova resposta em {arq} e rode de novo.", file=sys.stderr)
        return 1
    if r == 0:
        gravar_aviso(arq.parent, avisos)
    return r


def cmd_tema(a):
    try:
        if ia.provedor(a.ia) is None:
            return cmd_prompt(a, motivo="Sem OPENAI_API_KEY nem ANTHROPIC_API_KEY no ambiente: o arrasta monta o prompt e você cola em qualquer IA.")
        pasta = Path(a.saida or Path("saida") / slug(a.tema))
        dados, *_ = ia.gerar(a.tema, a.publico, a.slides, a.modelo, a.ia, visual=a.visual)
    except ia.FalhaIA as e:
        print(f"\n{e}", file=sys.stderr)
        return 1
    if a.arroba:
        dados["arroba"] = a.arroba
    aplicar_visual(dados, a, Path.cwd())
    avisos = []
    r = validar_e_gerar(dados, pasta, " ".join(x for x in (a.tema, a.publico) if x), avisos)
    if r == 0:
        gravar_aviso(pasta, avisos)
    return 1 if isinstance(r, list) else r


def main(argv=None):
    # no Windows, com a saída indo para pipe ou arquivo (Git Bash, redirecionamento), o Python usa cp1252 e
    # quebra em qualquer caractere fora dela; o arrasta escreve sempre em UTF-8
    for s in (sys.stdout, sys.stderr):
        if (s.encoding or "").lower().replace("-", "") != "utf8" and hasattr(s, "reconfigure"):
            s.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(prog="arrasta", description="Escreva o tema, saia com o carrossel pronto pra postar.")
    ap.add_argument("--versao", action="version", version=f"arrasta {__version__}")
    sub = ap.add_subparsers(dest="cmd", metavar="comando")

    def tema_args(p):
        p.add_argument("tema", help="sobre o que é o carrossel, entre aspas")
        p.add_argument("--arroba", help="seu @, aparece no topo dos slides")
        p.add_argument("--publico", help="pra quem é o carrossel (opcional)")
        p.add_argument("--slides", type=int, default=7, choices=range(regras.SLIDES_MIN, regras.SLIDES_MAX + 1), metavar="N",
                       help=f"quantos slides, de {regras.SLIDES_MIN} a {regras.SLIDES_MAX} (padrão 7)")
        p.add_argument("--saida", help="pasta de saída (padrão: saida/<tema>)")
        visual_args(p)

    def visual_args(p):
        p.add_argument("--visual", choices=visual.VISUAIS, help="modelo dos slides: " + ", ".join(visual.VISUAIS) + " (padrão: escuro)")
        p.add_argument("--imagem", help="foto de fundo para todos os slides (visual imagem)")

    p = sub.add_parser("tema", help="gera o carrossel a partir do tema (com chave da OpenAI ou da Anthropic, num comando só)")
    tema_args(p)
    p.add_argument("--ia", choices=ia.PROVEDORES, help="qual chave usar quando as duas estão no ambiente (padrão: openai)")
    p.add_argument("--modelo", help="modelo da IA (padrão: " + ", ".join(f"{v} na {ia.NOME[k]}" for k, v in ia.MODELO_PADRAO.items()) + ")")
    p.set_defaults(f=cmd_tema)

    p = sub.add_parser("prompt", help="monta o prompt para colar em qualquer IA (sem chave)")
    tema_args(p)
    p.set_defaults(f=cmd_prompt)

    p = sub.add_parser("montar", help="lê a resposta da IA, confere as regras e gera os PNGs")
    p.add_argument("resposta", help="arquivo com a resposta da IA")
    p.add_argument("--arroba", help="seu @ (se não foi dado no prompt)")
    p.add_argument("--saida", help="pasta de saída (padrão: a pasta da resposta)")
    visual_args(p)
    p.set_defaults(f=cmd_montar)

    p = sub.add_parser("render", help="gera os PNGs de um slides.json escrito por você")
    p.add_argument("arquivo", help="o slides.json")
    p.add_argument("--arroba", help="seu @ (substitui o do arquivo)")
    p.add_argument("--saida", help="pasta de saída (padrão: saida/<nome do arquivo>)")
    visual_args(p)
    p.set_defaults(f=cmd_render)

    p = sub.add_parser("regras", help="mostra as regras que todo carrossel cumpre")
    p.set_defaults(f=lambda a: print(regras.descrever()) or 0)

    a = ap.parse_args(argv)
    if not a.cmd:
        ap.print_help()
        return 2
    # no PowerShell, @nome sem aspas some da linha de comando; quem digita sem o @ também é atendido
    if getattr(a, "arroba", None) and not a.arroba.startswith("@"):
        a.arroba = "@" + a.arroba
    return a.f(a)


if __name__ == "__main__":
    sys.exit(main())
