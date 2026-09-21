"""Controle positivo das regras: cada defeito plantado tem de reprovar na regra certa, e o exemplo tem de passar."""
import copy
import json
from pathlib import Path

import pytest

from arrasta import regras, resposta

EXEMPLO = json.loads((Path(__file__).resolve().parents[1] / "exemplos/exemplo.json").read_text(encoding="utf-8"))


def ex():
    return copy.deepcopy(EXEMPLO)


def regras_quebradas(dados, fonte=None):
    regras.normalizar(dados)
    return {r for r, _, _ in regras.verificar(dados, fonte_dos_numeros=fonte)}


def frase(n):
    return " ".join(["palavra"] * n)


def test_exemplo_passa():
    assert regras.verificar(ex()) == []


def test_limite_exato_passa_e_um_a_mais_reprova():
    d = ex()
    d["slides"][0]["titulo"] = frase(regras.CAPA_TITULO)
    assert regras_quebradas(d) == set()
    d["slides"][0]["titulo"] = frase(regras.CAPA_TITULO + 1)
    assert regras_quebradas(d) == {"gancho na capa"}


def test_teto_do_miolo_sem_imagem_e_opcional():
    # sem o parâmetro: o teto de sempre, com ou sem imagem
    d = ex()
    d["slides"][1]["titulo"] = frase(5)
    d["slides"][1]["texto"] = frase(regras.MIOLO_TOTAL - 5)
    assert regras_quebradas(d) == set()
    d["slides"][1]["texto"] = frase(regras.MIOLO_TOTAL - 4)
    assert regras_quebradas(d) == {"pouco texto por slide"}
    # com o parâmetro: o slide sem imagem vai até o teto novo, e um a mais reprova
    d["slides"][1]["texto"] = frase(50 - 5)
    assert {r for r, _, _ in regras.verificar(d, miolo_sem_imagem=50)} == set()
    d["slides"][1]["texto"] = frase(50 - 4)
    erros = regras.verificar(d, miolo_sem_imagem=50)
    assert [(r, m) for r, _, m in erros] == [("pouco texto por slide", "51 palavras no slide; até 50")]
    # o título do miolo não muda de teto
    d["slides"][1].update(titulo=frase(regras.MIOLO_TITULO + 1), texto=frase(10))
    assert {r for r, _, _ in regras.verificar(d, miolo_sem_imagem=50)} == {"pouco texto por slide"}


def test_slide_com_imagem_fica_no_teto_de_sempre():
    d = ex()
    d["slides"][1].update(titulo=frase(5), texto=frase(regras.MIOLO_TOTAL - 4), imagem="foto.jpg")
    erros = regras.verificar(d, miolo_sem_imagem=50)
    assert [(o, m) for r, o, m in erros if r == "pouco texto por slide"] == [("slide 2", f"{regras.MIOLO_TOTAL + 1} palavras no slide; até {regras.MIOLO_TOTAL}")]
    # imagem no topo vale para todos os slides
    d = ex()
    d["imagem"] = "foto.jpg"
    d["slides"][1].update(titulo=frase(5), texto=frase(regras.MIOLO_TOTAL - 4))
    assert "pouco texto por slide" in {r for r, _, _ in regras.verificar(d, miolo_sem_imagem=50)}


@pytest.mark.parametrize("plantar, regra", [
    (lambda d: d["slides"].pop(1) and d["slides"].pop(1), "estrutura"),
    (lambda d: d["slides"].extend(copy.deepcopy(d["slides"][1:3]) * 3), "estrutura"),
    (lambda d: d["slides"].insert(2, d["slides"].pop(0)), "estrutura"),
    (lambda d: d["slides"][0].update(texto=frase(regras.CAPA_TEXTO + 1)), "gancho na capa"),
    (lambda d: d["slides"][1].update(titulo=frase(regras.MIOLO_TITULO + 1)), "pouco texto por slide"),
    (lambda d: d["slides"][1].update(texto=frase(regras.MIOLO_TOTAL)), "pouco texto por slide"),
    (lambda d: d["slides"][-1].pop("pedido"), "pedido no lugar certo"),
    (lambda d: d["slides"][-1].update(pedido=frase(regras.PEDIDO + 1)), "pedido no lugar certo"),
    (lambda d: d["slides"][-1].update(texto=frase(regras.FINAL_TOTAL)), "pedido no lugar certo"),
    (lambda d: d["slides"][2].update(pedido="Comenta EU"), "pedido no lugar certo"),
    (lambda d: d["slides"][2].update(texto="Comenta aqui embaixo o que achou."), "pedido no lugar certo"),
    (lambda d: d["slides"][0].update(texto="salva esse post"), "pedido no lugar certo"),
    (lambda d: d["slides"][3].update(titulo="Cada slide puxa o próximo \U0001F525"), "escrita"),
    (lambda d: d["slides"][3].update(texto="Termine com algo em aberto — quem lê arrasta."), "escrita"),
    (lambda d: d["slides"][3].update(texto="Veja mais em https://exemplo.com"), "escrita"),
    (lambda d: d["slides"][3].update(texto="Frase curta #marketing"), "escrita"),
    (lambda d: d["slides"][3].update(titulo="O segredo do carrossel"), "escrita"),
    (lambda d: d["slides"][1].update(titulo="A capa *entrega tudo"), "formato"),
    (lambda d: d["slides"][1].update(titulo="*A* *capa* *entrega*"), "formato"),
    (lambda d: d["slides"][1].update(subtitulo="x"), "formato"),
    (lambda d: d.update(arroba="seuperfil"), "formato"),
    (lambda d: d.update(visual="neon"), "formato"),
    (lambda d: d.update(cores={"fundo": "preto"}), "formato"),
])
def test_defeito_plantado_reprova_na_regra_certa(plantar, regra):
    d = ex()
    plantar(d)
    assert regra in regras_quebradas(d)


def test_numero_sem_fonte_reprova_e_com_fonte_passa():
    d = ex()
    d["slides"][1]["texto"] = "Quem posta 3 vezes por semana cresce mais."
    assert "número com fonte" in regras_quebradas(copy.deepcopy(d), fonte="carrossel que prende")
    assert "número com fonte" not in regras_quebradas(copy.deepcopy(d), fonte="postar 3 vezes por semana")
    assert "número com fonte" not in regras_quebradas(copy.deepcopy(d), fonte=None)


def test_salva_fora_de_pedido_nao_e_pedido():
    d = ex()
    d["slides"][2]["texto"] = "Uma resposta rápida salva a venda."
    assert regras_quebradas(d) == set()


def test_texto_vazio_vira_ausente():
    d = ex()
    d["slides"][0]["texto"] = "   "
    d["slides"][1]["pedido"] = ""
    assert regras_quebradas(d) == set()
    assert "texto" not in d["slides"][0] and "pedido" not in d["slides"][1]


@pytest.mark.parametrize("colado", [
    "```json\n%s\n```",
    "Claro! Aqui está o carrossel:\n\n%s\n\nSe quiser, ajusto o tom.",
    "%s",
])
def test_extrai_json_da_resposta_colada(colado):
    texto = colado % json.dumps(EXEMPLO, ensure_ascii=False, indent=2)
    assert resposta.extrair(texto) == EXEMPLO


@pytest.mark.parametrize("colado", ["", "não sei", '{"titulo": "sem slides"}'])
def test_resposta_sem_carrossel_e_recusada(colado):
    with pytest.raises(resposta.RespostaInvalida):
        resposta.extrair(colado)


def test_palavra_larga_reprova_antes_do_navegador_com_o_numero():
    """o que a contagem de palavras aprova: uma palavra só, larga demais. Medida na fonte, sem abrir o Chromium."""
    d = ex()
    d["slides"][0]["titulo"] = "O jeito surpreendentemente simples"
    erros = [e for e in regras.verificar(d) if e[0] == "cabe na caixa"]
    assert len(erros) == 1
    assert "surpreendentemente" in erros[0][2] and "1025 px" in erros[0][2] and "passa 137 px" in erros[0][2]
    d["slides"][0]["titulo"] = "O jeito simples de fazer"
    assert regras.verificar(d) == []


def test_o_limite_de_largura_muda_com_o_visual():
    """a mesma palavra cabe no escuro e não cabe no claro: a caixa e a letra são outras."""
    d = ex()
    d["slides"][0]["titulo"] = "O dimensionamento certo"
    assert [e for e in regras.verificar(d) if e[0] == "cabe na caixa"] == []
    d["visual"] = "claro"
    assert [e for e in regras.verificar(d) if e[0] == "cabe na caixa"] != []


def test_palavra_com_hifen_nao_reprova():
    """o navegador quebra a linha depois do hífen; medido inteiro o composto dá 1.621 px e seria recusado,
    mas cada pedaço cabe nos 888 px do título (878,5 e 742,5)."""
    d = ex()
    d["slides"][0]["titulo"] = "A palavra responsabilidade-socioambiental"
    assert [e for e in regras.verificar(d) if e[0] == "cabe na caixa"] == []


def test_destaque_nao_entra_na_conta_da_largura():
    """os asteriscos do *destaque* não são letra; e a palavra partida por eles continua sendo uma palavra."""
    d = ex()
    d["slides"][0]["titulo"] = "O jeito *simples* de fazer"
    assert regras.verificar(d) == []
    d["slides"][0]["titulo"] = "O jeito surpreen*dentemente* simples"
    assert [e for e in regras.verificar(d) if e[0] == "cabe na caixa"] != []
