"""Controle positivo do render: cada defeito plantado tem de ser recusado, e nada pode ser gravado quando recusa."""
import copy
import json
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
    (lambda d: d["slides"][0].update(titulo="Anticonstitucionalissimamente"), "mais larga que a caixa"),
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
    modelo = tmp_path / "modelo"
    shutil.copytree(render.MODELO, modelo)
    for f in (modelo / "fontes").glob("*.woff2"):
        f.unlink()
    monkeypatch.setattr(render, "MODELO", modelo)
    with pytest.raises(render.Recusado, match="fonte não carregou"):
        render.renderizar(ex(), tmp_path / "saida")


def test_molde_com_letra_fora_da_fonte_e_recusado(tmp_path, monkeypatch):
    """a seta da capa era "→", que a Inter embutida não tem: cada sistema desenhava com a fonte dele."""
    modelo = tmp_path / "modelo"
    shutil.copytree(render.MODELO, modelo)
    html = modelo / "slide.html"
    html.write_text(html.read_text(encoding="utf-8").replace(">arrasta<svg", ">arrasta →<svg"), encoding="utf-8")
    monkeypatch.setattr(render, "MODELO", modelo)
    with pytest.raises(render.Recusado, match="U\\+2192"):
        render.renderizar(ex(), tmp_path / "saida")
