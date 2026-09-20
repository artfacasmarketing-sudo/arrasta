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
def test_a_conta_da_fonte_bate_com_o_navegador(pagina, chave):
    """padrão-ouro: o Chromium que desenha o slide. Medido em 20/09/2026 em 2.898 palavras: erro máximo 0,12 px."""
    vis, papel, campo = chave
    fs, peso, espaco, alta, _ = L.ESTILOS[chave]
    no_navegador = pagina(vis, papel, campo, cheio=False).evaluate(MEDIR_PALAVRAS, [campo, PALAVRAS])
    pior = max(abs(L.largura(p, fs, peso, espaco, alta) - cr) for p, cr in zip(PALAVRAS, no_navegador))
    assert pior < 0.5, f"{chave}: a conta da fonte erra {pior:.3f} px contra o navegador"


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
    assert len(cabe) == n and len(nao) == n + 1
    assert not L.nao_cabe(cabe, *chave), f"{chave}: \"{cabe}\" deveria caber"
    assert L.nao_cabe(nao, *chave), f"{chave}: \"{nao}\" deveria não caber"


def test_palavra_com_hifen_nao_e_medida_inteira():
    """o navegador quebra depois do hífen; medir o trecho inteiro recusaria o que cabe."""
    assert L.pedacos("responsabilidade-socioambiental e/ou") == ["responsabilidade-", "socioambiental", "e/", "ou"]
    assert not L.nao_cabe("responsabilidade-socioambiental", "escuro", "capa", "titulo")
