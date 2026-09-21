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
    # e o cuidado nunca pode virar licença para responder em prosa: 5 de 20 quebraram assim em 21/09
    assert "A resposta continua sendo só o JSON" in t
    assert "diga isso no lugar de forçar" not in t


def test_sem_objetivo_a_estrutura_e_a_antiga_menos_o_que_puxava_o_proximo():
    """sem --objetivo continua a estrutura de antes (capa, miolo, final, sem fórmula nem espinha).

    O QUE MUDOU, de propósito: o miolo dizia "na ordem que responde a pergunta da capa aos poucos". O "aos
    poucos" virava frase que anuncia o próximo slide — 17 de 25 slides de miolo da prova, contados por
    leitura. Saiu; no lugar, cada slide fecha a própria ideia."""
    t = P.montar("brindes corporativos", "gestor", 7, "escuro")
    assert "OBJETIVO DESTE CARROSSEL" not in t and "ESPINHA" not in t
    assert "CAPA (slide 1)" in t and "MIOLO (slides 2 a 6)" in t and "FINAL (slide 7)" in t
    assert "aos poucos" not in t
    assert "Cada slide fecha a própria ideia" in t


@pytest.mark.parametrize("objetivo", [None, *F.OBJETIVOS])
def test_a_frase_isca_e_proibida_com_ou_sem_objetivo(objetivo):
    """contado por LEITURA na prova de 21/09/2026: 17 de 25 slides de miolo terminavam anunciando o próximo
    com o prompt antigo, 0 de 25 com o novo. Saiu a regra que mandava fazer isso; entrou a proibição, nos
    dois caminhos. (O "16% no B1" e o "12% -> 0%" que estavam aqui saíram de um detector de expressão
    literal, que na mesma prova achou 3 dos 17: número de detector, não do padrão.)"""
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


def test_clique_sem_destino_e_recusado_com_exemplo(tmp_path, capsys):
    """sem destino, a IA inventa o que tem no link: 4 de 4 cliques da conferência de 21/09/2026."""
    assert cli.main(["prompt", "kit de boas-vindas", "--objetivo", "clique", "--saida", str(tmp_path / "a")]) == 2
    err = capsys.readouterr().err
    assert "pede --destino" in err and F.EXEMPLO_DESTINO in err
    assert not (tmp_path / "a" / "prompt.txt").exists(), "recusou, então não pode ter gravado nada"


def test_clique_com_destino_leva_o_destino_e_a_proibicao(tmp_path):
    pasta = tmp_path / "b"
    assert cli.main(["prompt", "kit de boas-vindas", "--objetivo", "clique",
                     "--destino", "checklist do que entra no kit", "--saida", str(pasta)]) == 0
    t = (pasta / "prompt.txt").read_text(encoding="utf-8")
    assert "DESTINO (o que a pessoa encontra no link): checklist do que entra no kit" in t
    assert "não invente item, formato, preço nem prazo DO DESTINO" in t
    assert json.loads((pasta / "pedido.json").read_text(encoding="utf-8"))["destino"] == "checklist do que entra no kit"


@pytest.mark.parametrize("objetivo", [None, *F.OBJETIVOS])
def test_o_link_inventado_e_proibido_com_ou_sem_objetivo(objetivo):
    t = P.montar("brindes", None, 7, "escuro", objetivo, "um destino" if objetivo == "clique" else None)
    assert "Não invente o que existe do outro lado do link" in t


def test_salvamento_nao_pede_numero_de_ordem():
    """5 de 5 salvamentos pediram correção pelo "1, 2, 3" dos passos: o número de ordem também é número."""
    t = F.texto("salvamento", 7)
    assert "numerado" not in t and "quantos passos" not in t
    assert "SEM número de ordem" in t


def test_viral_e_ponte_fecham_a_ideia_e_nao_o_pra_quem():
    for obj in ("alcance", "clique"):
        assert "repetiria" in F.FORMULAS[obj]["final"]
        assert "para quem" not in F.FORMULAS[obj]["final"]


def test_autoridade_so_usa_primeira_pessoa_com_experiencia_no_tema():
    f = F.FORMULAS["autoridade"]
    assert "princípio" in f["final"] and "Primeira pessoa só se" in f["final"]
    assert any("SÓ se o TEMA trouxer a experiência" in passo[1] for passo in f["miolo"])


def test_comentario_pede_uma_palavra_do_tema_em_maiusculas_e_marcada():
    """no claro e no imagem o pedido já sai todo em caixa-alta: sem a marca, a palavra-chave some."""
    verbo, exemplo = F.PEDIDOS["comentario"]
    assert "MAIÚSCULAS" in verbo and "asteriscos" in verbo
    assert "*CADERNO*" in exemplo


def test_a_palavra_chave_marcada_passa_nas_regras_e_sai_destacada_nos_tres_visuais(tmp_path):
    """o render já tem ênfase no pedido: cor no claro e no imagem, sublinhado dentro da pílula no escuro
    (amarelo sobre a pílula amarela sumiria). Controle: o mesmo pedido SEM a marca não tem ênfase nenhuma.
    No escuro a ênfase é sublinhado, que não aparece como cor: ali o teste só garante que nada quebra, e a
    prova de que o sublinhado sai é o print de 21/09/2026 (pedido-com-enfase-3-visuais.png)."""
    from PIL import Image
    from arrasta import render
    foto = tmp_path / "f.jpg"
    Image.new("RGB", (1600, 1200), "#334455").save(foto)
    for vis in ("escuro", "claro", "imagem"):
        for marcado, esperado in ((True, 1), (False, 0)):
            pedido = "Acha que o caderno dá conta? Comenta " + ("*CADERNO*" if marcado else "CADERNO") + " aqui."
            d = {"visual": vis, "slides": [
                {"tipo": "capa", "titulo": "Vendedor bom anota tudo no caderno"},
                {"tipo": "miolo", "titulo": "O caderno é do vendedor"},
                {"tipo": "miolo", "titulo": "Anotado não é controlado"},
                {"tipo": "miolo", "titulo": "A conversa mora no celular"},
                {"tipo": "final", "titulo": "Quem guarda a conversa é o dono.", "pedido": pedido}]}
            if vis == "imagem":
                d["imagem"] = str(foto)
            assert regras.verificar(d) == [], vis
            medidas = []
            render.renderizar(d, tmp_path / f"{vis}-{marcado}", previa=False, medidas=medidas)
            # o trecho marcado vira um texto próprio dentro do pedido, com a cor e o contraste medidos
            trechos_do_pedido = [m for m in medidas if m["slide"] == 5 and m["id"] == "pedido"]
            cores = {m["cor"] for m in trechos_do_pedido}
            assert len(cores) == (2 if marcado and vis != "escuro" else 1), (vis, marcado, cores)


def test_clique_separa_o_destino_das_dicas():
    """o que existe do outro lado sai do destino; a dica é conteúdo do carrossel, sobre o tema."""
    t = F.texto("clique", 7, "checklist do que entra no kit")
    assert "não invente item, formato, preço nem prazo DO DESTINO" in t
    assert "Nunca diga que uma dica está no link" in t
    assert "tirada do DESTINO" not in t
    passos = [p for p, _ in F.espinha("clique", 7)]
    assert passos.count("uma dica") == 3 and "uma amostra" not in passos
