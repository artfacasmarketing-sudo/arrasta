"""O objetivo decide três coisas: a fórmula, o gancho da capa e o pedido do final.

O que estes testes seguram: a espinha cobre exatamente os slides pedidos, cada objetivo tem fórmula, o
prompt muda quando o objetivo vem e NÃO muda quando não vem, e a frase-isca continua proibida.
"""
import json

import pytest

from arrasta import cli, formulas as F, prompt as P, regras


def test_todo_objetivo_tem_formula_pedido_e_quando_nao_usar():
    assert set(F.OBJETIVOS) == set(F.FORMULAS) == set(F.PEDIDOS) == set(F.NOME)
    for obj in F.OBJETIVOS:
        f = F.FORMULAS[obj]
        assert f["nome"] and f["origem"] and f["capa"] and f["final"] and f["nao_usar"]
        assert sum(1 for p in f["miolo"] if len(p) == 3 and p[2] == "repete") == 1, \
            f"{obj}: a espinha precisa de um passo, e só um, que estica"


@pytest.mark.parametrize("obj", F.OBJETIVOS)
@pytest.mark.parametrize("n", range(regras.SLIDES_MIN, regras.SLIDES_MAX + 1))
def test_a_espinha_cobre_exatamente_os_slides_pedidos(obj, n):
    e = F.espinha(obj, n)
    assert len(e) == n
    assert e[0][0] == "capa" and e[-1][0] == "final"
    assert all(o_que for _, o_que in e)


def test_o_passo_que_estica_e_o_que_cresce():
    """de 5 para 10 slides, quem aparece mais vezes é o passo marcado para repetir."""
    curto = [p[0] for p in F.espinha("salvamento", 5)]
    longo = [p[0] for p in F.espinha("salvamento", 10)]
    assert longo.count("um passo") - curto.count("um passo") == 5
    assert "a promessa" in curto and "a promessa" in longo


@pytest.mark.parametrize("obj", F.OBJETIVOS)
def test_o_prompt_leva_a_espinha_o_gancho_e_o_pedido(obj):
    t = P.montar("brindes corporativos", "gestor", 7, "escuro", obj)
    assert f"OBJETIVO DESTE CARROSSEL: {F.NOME[obj]}" in t
    assert F.FORMULAS[obj]["nome"] in t
    assert "ESPINHA, slide a slide" in t and "slide 7 (final)" in t
    verbo, exemplo = F.PEDIDOS[obj]
    assert f"de {verbo}" in t and exemplo in t
    assert F.FORMULAS[obj]["nao_usar"] in t


def test_sem_objetivo_o_prompt_e_o_de_sempre():
    """quem já usa não pode ser surpreendido: sem --objetivo, a estrutura continua a antiga."""
    t = P.montar("brindes corporativos", "gestor", 7, "escuro")
    assert "OBJETIVO DESTE CARROSSEL" not in t and "ESPINHA" not in t
    assert "CAPA (slide 1)" in t and "MIOLO (slides 2 a 6)" in t and "FINAL (slide 7)" in t


@pytest.mark.parametrize("objetivo", [None, *F.OBJETIVOS])
def test_a_frase_isca_e_proibida_com_ou_sem_objetivo(objetivo):
    """53% dos carrosséis do B1 tinham pelo menos uma frase que anuncia o próximo slide. Saiu a regra que
    mandava fazer isso; entrou a proibição, nos dois caminhos."""
    t = P.montar("brindes", None, 7, "escuro", objetivo)
    assert "Cada slide termina deixando vontade de ver o próximo" not in t
    assert "PROIBIDO terminar slide anunciando o próximo" in t
    assert "mas falta" in t and "tem coisa pior" in t


@pytest.mark.parametrize("objetivo", [None, *F.OBJETIVOS])
def test_prova_social_inventada_e_proibida(objetivo):
    t = P.montar("brindes", None, 7, "escuro", objetivo)
    assert "Não invente cliente, depoimento, nome nem resultado" in t


def test_o_cli_aceita_o_objetivo_com_e_sem_acento_e_recusa_o_resto(tmp_path):
    for escrito in ("comentário", "comentario", "COMENTÁRIO"):
        assert cli.objetivo_valido(escrito) == "comentario"
    with pytest.raises(Exception):
        cli.objetivo_valido("engajamento")


def test_o_objetivo_vai_para_o_prompt_e_fica_no_pedido(tmp_path):
    pasta = tmp_path / "s"
    assert cli.main(["prompt", "brindes corporativos", "--objetivo", "salvamento", "--saida", str(pasta)]) == 0
    assert "Fórmula: POPP" in (pasta / "prompt.txt").read_text(encoding="utf-8")
    assert json.loads((pasta / "pedido.json").read_text(encoding="utf-8"))["objetivo"] == "salvamento"


def test_arrasta_objetivos_mostra_as_cinco(capsys):
    assert cli.main(["objetivos"]) == 0
    saida = capsys.readouterr().out
    for obj in F.OBJETIVOS:
        assert F.FORMULAS[obj]["nome"] in saida and F.NOME[obj] in saida
    assert "não inventa cliente" in saida
