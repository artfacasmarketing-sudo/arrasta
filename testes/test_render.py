"""Controle positivo do render: cada defeito plantado tem de ser recusado, e nada pode ser gravado quando recusa."""
import copy
import json
import re
import shutil
from pathlib import Path

import pytest
from PIL import Image

from arrasta import render

EXEMPLO = json.loads((Path(__file__).resolve().parents[1] / "exemplos/exemplo.json").read_text(encoding="utf-8"))


def ex():
    return copy.deepcopy(EXEMPLO)


def pngs(pasta):
    return sorted(p.name for p in Path(pasta).glob("[0-9][0-9].png"))


def test_exemplo_grava_um_png_por_slide(tmp_path):
    arquivos = render.renderizar(ex(), tmp_path)
    assert pngs(tmp_path) == [f"{i:02d}.png" for i in range(1, len(EXEMPLO["slides"]) + 1)]
    assert (tmp_path / "previa.png") in arquivos
    for p in pngs(tmp_path):
        with Image.open(tmp_path / p) as im:
            assert im.size == (1080, 1350)


def test_rodada_menor_nao_deixa_png_velho(tmp_path):
    render.renderizar(ex(), tmp_path)
    d = ex()
    del d["slides"][1]
    render.renderizar(d, tmp_path)
    assert pngs(tmp_path) == [f"{i:02d}.png" for i in range(1, len(d["slides"]) + 1)]


@pytest.mark.parametrize("plantar, trecho", [
    (lambda d: d["slides"][2].update(texto=" ".join(["inconstitucionalmente"] * 26)), "passa"),
    (lambda d: d["slides"][0].update(titulo="Anticonstitucionalissimamente"), r'"Anticonstitucionalissimamente" tem \d+ px'),
    (lambda d: d.update(cores={"texto": "#333333"}), "contraste"),
    (lambda d: d.update(visual="claro", cores={"destaque": "#f6e7b0"}), "contraste"),
    (lambda d: d["slides"][1].update(titulo="A capa entrega 你"), "caractere que a fonte não tem"),
])
def test_defeito_plantado_e_recusado_sem_gravar(tmp_path, plantar, trecho):
    d = ex()
    plantar(d)
    with pytest.raises(render.Recusado, match=trecho):
        render.renderizar(d, tmp_path / "saida")
    assert pngs(tmp_path / "saida") == []


def test_fonte_que_nao_carrega_e_recusada(tmp_path, monkeypatch):
    """controle do instrumento: sem os arquivos de fonte, a conferência 'carregou' tem de acusar."""
    modelos = tmp_path / "modelos"
    shutil.copytree(render.MODELOS, modelos)
    for f in (modelos / "fontes").glob("*.woff2"):
        f.unlink()
    monkeypatch.setattr(render, "MODELOS", modelos)
    with pytest.raises(render.Recusado, match="fonte não carregou"):
        render.renderizar(ex(), tmp_path / "saida")


def test_molde_com_letra_fora_da_fonte_e_recusado(tmp_path, monkeypatch):
    """a seta da capa era "→", que a Inter embutida não tem: cada sistema desenhava com a fonte dele."""
    modelos = tmp_path / "modelos"
    shutil.copytree(render.MODELOS, modelos)
    html = modelos / "escuro" / "molde.html"
    html.write_text(html.read_text(encoding="utf-8").replace(">arrasta<svg", ">arrasta →<svg"), encoding="utf-8")
    monkeypatch.setattr(render, "MODELOS", modelos)
    with pytest.raises(render.Recusado, match="U\\+2192"):
        render.renderizar(ex(), tmp_path / "saida")


def test_palavra_larga_e_recusada_com_a_palavra_e_o_numero(tmp_path):
    """o que a contagem de palavras aprova e a caixa recusa: uma palavra só, larga demais.

    Medido no Chromium com o molde escuro: "surpreendentemente" a 104px dá 1025 px no macOS, a caixa do
    título tem 888. A largura sai do navegador DESTE sistema e não é a mesma nos três (o Linux arredonda o
    avanço de cada glifo), então o teste cobra a palavra, a caixa exata e a ordem de grandeza do transbordo,
    nunca o pixel exato. A recusa tem de dizer a palavra e o número: sem isso a IA corrige no escuro."""
    d = ex()
    d["slides"][0].update(titulo="O jeito surpreendentemente simples de fazer")
    with pytest.raises(render.Recusado) as e:
        render.renderizar(d, tmp_path / "saida")
    msg = str(e.value)
    assert 'surpreendentemente' in msg and "888 px de largura" in msg
    largura, passa = (int(x) for x in re.search(r"tem (\d+) px.*passa (\d+) px", msg).groups())
    assert 1010 <= largura <= 1040 and 122 <= passa <= 152 and largura - 888 == passa
    assert pngs(tmp_path / "saida") == []
    # e o que a IA recebe nomeia a palavra
    assert any("surpreendentemente" in msg for _, _, msg in e.value.para_ia)


def test_capa_que_cabe_passa(tmp_path):
    """controle positivo do outro lado: a mesma capa sem a palavra longa tem de ser aceita."""
    d = ex()
    d["slides"][0].update(titulo="O jeito simples de fazer")
    render.renderizar(d, tmp_path / "saida")
    assert pngs(tmp_path / "saida") == [f"{i:02d}.png" for i in range(1, len(d["slides"]) + 1)]


def test_arroba_que_nao_cabe_e_recusada(tmp_path):
    """o @ fica fora de [data-caixa]: até 20/09 nenhuma conferência olhava a largura dele e o slide saía furado.

    30 letras é o que a regra ARROBA aceita; com as mais largas da fonte, o @ passa 70 px da margem do slide."""
    d = ex()
    d["arroba"] = "@" + "W" * 30
    with pytest.raises(render.Recusado, match="o @ passa"):
        render.renderizar(d, tmp_path / "saida")
    assert pngs(tmp_path / "saida") == []


def test_arroba_que_cabe_passa(tmp_path):
    """controle positivo: o mesmo @ com letras estreitas cabe e não pode ser recusado."""
    d = ex()
    d["arroba"] = "@" + "i" * 30
    render.renderizar(d, tmp_path / "saida")
    assert pngs(tmp_path / "saida") == [f"{i:02d}.png" for i in range(1, len(d["slides"]) + 1)]
