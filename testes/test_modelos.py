"""Os três modelos: cada um gera o exemplo, mede o contraste de cada texto sobre o slide desenhado, e o modelo
com imagem aguenta foto clara e foto escura. Controle positivo: texto em cima de faixa clara da foto tem de reprovar,
mesmo quando a MÉDIA da foto é escura."""
import copy
import json
import shutil
from pathlib import Path

import pytest
from PIL import Image, ImageDraw, ImageStat

from arrasta import cli, regras, render, visual

EXEMPLO = json.loads((Path(__file__).resolve().parents[1] / "exemplos/exemplo.json").read_text(encoding="utf-8"))


def ex(v, imagem=None):
    d = copy.deepcopy(EXEMPLO)
    d["visual"] = v
    if imagem:
        d["imagem"] = str(imagem)
    return regras.normalizar(d)


def foto(pasta, nome, fundo, listra=None):
    """foto sintética 1600x1200: cor de fundo com ruído leve; listra = (y0, y1, cor) em fração da altura."""
    im = Image.effect_noise((1600, 1200), 40).convert("RGB")
    im = Image.blend(Image.new("RGB", im.size, fundo), im, 0.15)
    if listra:
        ImageDraw.Draw(im).rectangle((0, int(listra[0] * 1200), 1600, int(listra[1] * 1200)), fill=listra[2])
    p = pasta / nome
    im.save(p, quality=90)
    return p


@pytest.mark.parametrize("v", visual.VISUAIS)
def test_cada_modelo_gera_o_exemplo_com_contraste_medido(tmp_path, v):
    img = foto(tmp_path, "clara.jpg", "#f4f4f4") if v == "imagem" else None
    medidas = []
    render.renderizar(ex(v, img), tmp_path / "s", medidas=medidas)
    pngs = sorted((tmp_path / "s").glob("[0-9][0-9].png"))
    assert len(pngs) == len(EXEMPLO["slides"])
    assert all(Image.open(p).size == (1080, 1350) for p in pngs)
    # todo slide teve texto medido, e todo texto passou do mínimo
    assert {m["slide"] for m in medidas} == set(range(1, len(EXEMPLO["slides"]) + 1))
    assert all(m["contraste"] >= m["minimo"] for m in medidas)


@pytest.mark.parametrize("fundo", ["#f7f7f5", "#0a0a0c"])
def test_imagem_foto_clara_e_escura_ficam_legiveis(tmp_path, fundo):
    medidas = []
    render.renderizar(ex("imagem", foto(tmp_path, "f.jpg", fundo)), tmp_path / "s", medidas=medidas)
    pior = min(m["contraste"] / m["minimo"] for m in medidas)
    assert pior >= 1


def test_contraste_medido_na_area_do_texto_e_nao_na_media(tmp_path, monkeypatch):
    """planta o defeito: a foto passa a cobrir o slide inteiro, sem a faixa. A foto é quase toda preta (média escura),
    com uma listra branca só onde o título da capa cai. Pela média passaria; pela área real tem de reprovar."""
    modelos = tmp_path / "modelos"
    shutil.copytree(render.MODELOS, modelos)
    html = modelos / "imagem" / "molde.html"
    t = html.read_text(encoding="utf-8")
    t = t.replace('style.height = Math.max(0, capaTopo - FOTO_ACIMA * capDe(titulo)) + "px"', 'style.height = "1350px"')
    t = t.replace("--escurecer: 193.9px;", "--escurecer: 0px;")
    html.write_text(t, encoding="utf-8")
    monkeypatch.setattr(render, "MODELOS", modelos)
    img = foto(tmp_path, "listra.jpg", "#050505", listra=(0.80, 0.92, "#ffffff"))
    with Image.open(img) as im:
        media = tuple(round(c) for c in ImageStat.Stat(im.convert("RGB")).mean)
    assert visual.razao(visual.lum_rgb(0xf4, 0xf1, 0xea), visual.lum_rgb(*media)) >= 4.5  # a média aprovaria
    with pytest.raises(render.Recusado, match="contraste abaixo do mínimo sobre o fundo desenhado"):
        render.renderizar(ex("imagem", img), tmp_path / "s")


def test_imagem_por_slide_vale_sobre_a_do_carrossel(tmp_path):
    d = ex("imagem", foto(tmp_path, "todas.jpg", "#202020"))
    d["slides"][1]["imagem"] = str(foto(tmp_path, "so_a_2.jpg", "#e0e0e0"))
    fotos = render.imagens_dos_slides(d)
    assert fotos[1].name == "so_a_2.jpg" and {f.name for i, f in enumerate(fotos) if i != 1} == {"todas.jpg"}


def test_visual_imagem_sem_foto_reprova(tmp_path):
    d = ex("imagem")
    assert "formato" in {r for r, _, _ in regras.verificar(d)}
    with pytest.raises(render.Recusado, match="imagem"):
        render.renderizar(d, tmp_path / "s")


def test_foto_que_nao_existe_reprova_com_o_caminho(tmp_path):
    with pytest.raises(render.Recusado, match="imagem não encontrada"):
        render.renderizar(ex("imagem", tmp_path / "nao-existe.jpg"), tmp_path / "s")


def test_cli_visual_e_imagem_relativa_ao_json(tmp_path, monkeypatch):
    """--visual escolhe o modelo; foto relativa no slides.json é lida da pasta do arquivo, e o slides.json de saída
    guarda o caminho absoluto para gerar de novo de qualquer lugar."""
    pasta = tmp_path / "meu"
    pasta.mkdir()
    foto(pasta, "fundo.jpg", "#303030")
    d = copy.deepcopy(EXEMPLO)
    d["imagem"] = "fundo.jpg"
    (pasta / "c.json").write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert cli.main(["render", str(pasta / "c.json"), "--visual", "imagem", "--saida", str(tmp_path / "s")]) == 0
    salvo = json.loads((tmp_path / "s" / "slides.json").read_text(encoding="utf-8"))
    assert salvo["visual"] == "imagem" and Path(salvo["imagem"]) == (pasta / "fundo.jpg").resolve()


def test_textos_encostados_sao_recusados(tmp_path, monkeypatch):
    """controle positivo da colisão: cada texto cabe na caixa sozinho, mas o texto do miolo sobe por cima do título."""
    modelos = tmp_path / "modelos"
    shutil.copytree(render.MODELOS, modelos)
    html = modelos / "escuro" / "molde.html"
    t = html.read_text(encoding="utf-8").replace("margin-top: 44px; letter-spacing", "margin-top: -60px; letter-spacing")
    assert "margin-top: -60px" in t
    html.write_text(t, encoding="utf-8")
    monkeypatch.setattr(render, "MODELOS", modelos)
    with pytest.raises(render.Recusado, match="textos encostados: titulo e texto"):
        render.renderizar(ex("escuro"), tmp_path / "s")


ESTRESSE = {"arroba": "@perfil.com.nome_longo_ate30", "slides": [
    {"tipo": "capa", "titulo": "Por que o atendimento demorado derruba a conversão do orçamento *inteiro*",
     "texto": "e como a planilha de acompanhamento resolve isso sem contratação"},
    {"tipo": "miolo", "titulo": "Responder rápido transforma interesse em *compromisso* real",
     "texto": "Quem pede orçamento compara fornecedores ao mesmo tempo e escolhe quem demonstra organização primeiro, antes de qualquer negociação de valores ou prazos"},
    {"tipo": "miolo", "titulo": "Acompanhamento", "texto": "Retome"},
    {"tipo": "miolo", "titulo": "Documentação organizada evita retrabalho desnecessário na equipe comercial",
     "texto": "Registrar cada conversa permite continuidade quando outra pessoa assume o atendimento, sem perguntar novamente informações já fornecidas"},
    {"tipo": "final", "titulo": "Organização comercial transforma orçamento esquecido em venda fechada.",
     "texto": "Comece pela próxima conversa.",
     "pedido": "Compartilha com aquele colega que sempre esquece de responder orçamento importante"}]}


@pytest.mark.parametrize("v", visual.VISUAIS)
def test_texto_longo_perto_do_limite_passa_em_todos_os_modelos(tmp_path, v):
    """mesma quantidade de palavras em todos: texto perto do limite, com palavra longa, não pode ser recusado
    num modelo e aceito em outro."""
    d = copy.deepcopy(ESTRESSE)
    d["visual"] = v
    if v == "imagem":
        d["imagem"] = str(foto(tmp_path, "f.jpg", "#f4f4f4"))
    regras.normalizar(d)
    assert regras.verificar(d) == []
    vaos = []
    render.renderizar(d, tmp_path / "s", vaos=vaos)
    assert vaos and all(c["vao"] >= c["minimo"] for c in vaos)


@pytest.mark.parametrize("v, razao", [("claro", "3.385"), ("imagem", "3.094")])
def test_ultimo_slide_com_titulo_colado_no_pedido_e_recusado(tmp_path, monkeypatch, v, razao):
    """o defeito das primeiras prévias: título e pedido do último slide colados. Planta de novo (vão entre blocos
    encolhido para 0,5) e a conferência de colisão tem de recusar exatamente esse par."""
    modelos = tmp_path / "modelos"
    shutil.copytree(render.MODELOS, modelos)
    html = modelos / v / "molde.html"
    t = html.read_text(encoding="utf-8")
    assert f"const VAO_BLOCO = {razao};" in t
    html.write_text(t.replace(f"const VAO_BLOCO = {razao};", "const VAO_BLOCO = 0.5;"), encoding="utf-8")
    monkeypatch.setattr(render, "MODELOS", modelos)
    d = ex(v, foto(tmp_path, "f.jpg", "#303030") if v == "imagem" else None)
    for s in d["slides"][:-1]:
        s.pop("texto", None)  # só o último slide usa o vão entre blocos
    with pytest.raises(render.Recusado, match="slide 6: textos encostados: titulo e pedido"):
        render.renderizar(d, tmp_path / "s")


def test_viuva_vira_aviso_no_correcao_e_nao_recusa(tmp_path):
    """controle positivo: no claro, o pedido do exemplo quebra com "PRÓXIMO" e "CARROSSEL" sozinhos na linha.
    Os slides saem (não recusa) e o correcao.txt diz o que trocar. No escuro o mesmo texto não tem viúva: sem aviso."""
    for v, espera in (("claro", True), ("escuro", False)):
        pasta = tmp_path / v
        pasta.mkdir()
        d = copy.deepcopy(EXEMPLO)
        d["visual"] = v
        (pasta / "resposta.txt").write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
        assert cli.main(["montar", str(pasta / "resposta.txt")]) == 0
        assert len(list(pasta.glob("[0-9][0-9].png"))) == len(EXEMPLO["slides"])
        corr = pasta / "correcao.txt"
        assert corr.exists() == espera
        if espera:
            t = corr.read_text(encoding="utf-8")
            assert "slide 6: " in t and "do pedido ficou com uma palavra só" in t and "troque a palavra ou encurte" in t
            assert "texto" not in {l.split(",")[0] for l in t.splitlines()}  # texto corrido fica de fora
