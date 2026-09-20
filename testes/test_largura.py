"""A conta de largura em Python tem de ser a mesma do navegador — e a tabela de estilos tem de ser a do molde.

São as duas coisas que podem apodrecer em silêncio: alguém mexe no CSS e a tabela fica velha, ou a conta
da fonte começa a divergir do Chromium. As duas quebram este arquivo antes de chegar no usuário.
"""
import pytest

from arrasta import largura as L
from arrasta import visual as V

PAPEIS = {"capa": 1, "miolo": 3, "final": 6}
PALAVRAS = ["a", "ação", "brinde", "coração", "orçamento", "qualidade", "surpreendentemente", "Wi", "ÁRVORE",
            "compartilhamento", "responsabilidade", "extraordinariamente", "mmmmm", "AVATAR", "Toca", "1.200"]

LER_ESTILO = """
(campo) => {
  const el = document.querySelector('[data-id="' + campo + '"]');
  if (!el) return null;
  const cs = getComputedStyle(el), cx = caixaDe(el), cw = el.clientWidth;
  return {fs: parseFloat(cs.fontSize), peso: parseInt(cs.fontWeight),
          espaco: cs.letterSpacing === "normal" ? 0 : parseFloat(cs.letterSpacing),
          caixaalta: cs.textTransform === "uppercase",
          caixa: cw > 0 ? cw - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight) : cx.dir - cx.esq};
}
"""

MEDIR_PALAVRAS = """
([campo, palavras]) => {
  const el = document.querySelector('[data-id="' + campo + '"]');
  const out = [];
  for (const p of palavras) {
    el.textContent = p;
    const r = document.createRange(); r.selectNodeContents(el);
    out.push(r.getBoundingClientRect().width);
  }
  return out;
}
"""


@pytest.fixture(scope="module")
def pagina():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        nav = pw.chromium.launch()
        pag = nav.new_page(viewport={"width": 1080, "height": 1350}, device_scale_factor=1)

        def montar(vis, papel, campo, cheio=True):
            """desenha o slide com o campo cheio (a pílula do pedido só chega na largura máxima assim)."""
            pag.goto((L.MODELOS_DIR / vis / "molde.html").as_uri())
            s = {"tipo": papel, "papel": papel, "titulo": "Titulo", "texto": "Texto"}
            if papel == "final":
                s["pedido"] = "Pedido"
            if cheio:
                s[campo] = " ".join(["palavra"] * 60)
            meta = {"cores": dict(V.PALETAS[vis]), "arroba": "@af", "i": PAPEIS[papel], "n": 6,
                    "imagem": (L.MODELOS_DIR.parent.parent / "exemplos/exemplo/01.png").as_uri()
                              if V.MODELOS[vis]["imagem"] else ""}
            pag.evaluate("([s, m]) => montar(s, m)", [s, meta])
            pag.evaluate("async () => await medir()")
            return pag

        yield montar
        nav.close()


@pytest.mark.parametrize("chave", sorted(L.ESTILOS))
def test_a_tabela_de_estilos_e_a_do_molde(pagina, chave):
    """a tabela é lida do navegador; se o CSS mudar e ela não, a conta de largura passa a medir outro slide."""
    vis, papel, campo = chave
    vivo = pagina(vis, papel, campo).evaluate(LER_ESTILO, campo)
    assert vivo is not None, f"{chave}: o molde não tem esse campo"
    fs, peso, espaco, alta, caixa = L.ESTILOS[chave]
    assert abs(vivo["fs"] - fs) < 0.05, f'{chave}: tamanho {vivo["fs"]} no molde, {fs} na tabela'
    assert vivo["peso"] == peso
    assert abs(vivo["espaco"] - espaco) < 0.05
    assert vivo["caixaalta"] == alta
    assert abs(vivo["caixa"] - caixa) < 0.5, f'{chave}: caixa {vivo["caixa"]} no molde, {caixa} na tabela'


@pytest.mark.parametrize("chave", sorted(L.ESTILOS))
def test_a_conta_da_fonte_cabe_na_folga_declarada(pagina, chave):
    """padrão-ouro: o Chromium que desenha o slide, NESTE sistema.

    O erro não é o mesmo nos três: medido em 20/09/2026 no mesmo Chromium 153.0.8010.12, 420 palavras por
    sistema, deu 0,094 px no macOS, 0,266 px no Windows e 4,524 px no Linux, que arredonda o avanço de cada
    glifo e por isso erra proporcional ao tamanho da palavra. O que o teste cobra não é um número fixo: é
    que o erro real caiba na folga que o regras.py usa para não recusar o que este navegador aceitaria."""
    vis, papel, campo = chave
    fs, peso, espaco, alta, _ = L.ESTILOS[chave]
    no_navegador = pagina(vis, papel, campo, cheio=False).evaluate(MEDIR_PALAVRAS, [campo, PALAVRAS])
    for p, cr in zip(PALAVRAS, no_navegador):
        n = len(p.upper() if alta else p)
        erro = L.largura(p, fs, peso, espaco, alta) - cr
        assert abs(erro) <= L.folga(n), (f"{chave} {p!r}: a conta erra {erro:+.3f} px e a folga para {n} "
                                         f"letras é {L.folga(n):.2f} px")


def test_a_folga_cobre_o_pior_sistema_medido():
    """a folga não pode encolher abaixo do que foi medido: no Linux o erro chegou a 0,5152 px por letra e a
    4,524 px numa palavra de 18 letras (CI de 20/09/2026, run 35545244660, os 3 sistemas na mesma rodada)."""
    assert L.FOLGA_POR_LETRA >= 0.5152
    assert L.folga(18) >= 4.524
    assert L.folga(1) >= 0.5152


def test_o_kerning_entra_na_conta():
    """controle: sem kerning a conta erra até 28,6 px em palavra de caixa-alta. Um par conhecido tem de kernar."""
    assert L._kern(0, 800, "A", "V") < -100
    fs, peso, espaco, alta, _ = L.ESTILOS[("claro", "final", "pedido")]
    com = L.largura("avaliação", fs, peso, espaco, alta)
    sem = sum(L._avancos(0, peso)[0][L._faces()[0][0].getBestCmap()[ord(c)]] for c in "AVALIAÇÃO")
    sem = sem / L._faces()[0][0]["head"].unitsPerEm * fs + espaco * len("avaliação")
    assert sem - com > 20, "o kerning não está mudando a conta"


@pytest.mark.parametrize("chave, n, cabe, nao", [(k, *v) for k, v in L.LIMITE_LETRAS.items()])
def test_o_limite_de_letras_tem_as_duas_palavras_que_o_justificam(chave, n, cabe, nao):
    """o limite não é arredondamento: a palavra mais larga do léxico com N letras cabe, e a de N+1 não."""
    fs, peso, espaco, alta, caixa = L.ESTILOS[chave]
    assert len(cabe) == n and len(nao) == n + 1
    # aqui é a largura crua contra a caixa, sem a folga do pré-filtro: o limite é sobre o que CABE no slide,
    # não sobre o que o regras.py consegue barrar antes do navegador
    assert L.largura(cabe, fs, peso, espaco, alta) <= caixa, f"{chave}: \"{cabe}\" deveria caber"
    assert L.largura(nao, fs, peso, espaco, alta) > caixa, f"{chave}: \"{nao}\" deveria não caber"


def test_palavra_com_hifen_nao_e_medida_inteira():
    """o navegador quebra depois do hífen; medir o trecho inteiro recusaria o que cabe."""
    assert L.pedacos("responsabilidade-socioambiental e/ou") == ["responsabilidade-", "socioambiental", "e/", "ou"]
    assert not L.nao_cabe("responsabilidade-socioambiental", "escuro", "capa", "titulo")
