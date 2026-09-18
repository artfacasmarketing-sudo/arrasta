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
