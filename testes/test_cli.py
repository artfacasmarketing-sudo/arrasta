"""O caminho sem chave pela linha de comando: prompt -> resposta colada -> montar -> PNG."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from arrasta import cli

EXEMPLO = json.loads((Path(__file__).resolve().parents[1] / "exemplos/exemplo.json").read_text(encoding="utf-8"))


def test_nome_da_pasta_corta_em_palavra_inteira():
    assert cli.slug("por que o cliente some depois do orçamento") == "por-que-o-cliente-some-depois-do"
    assert len(cli.slug("x" * 60)) == 40
    assert cli.slug("!!!") == "carrossel"
    assert cli.slug("Con") == "con-carrossel" and cli.slug("LPT1") == "lpt1-carrossel"  # o Windows não cria pasta con


def test_sem_chave_tema_vira_prompt_e_montar_gera_png(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    pasta = tmp_path / "c"
    assert cli.main(["tema", "carrossel que prende", "--arroba", "@teste", "--saida", str(pasta)]) == 0
    assert (pasta / "prompt.txt").exists() and json.loads((pasta / "pedido.json").read_text(encoding="utf-8"))["arroba"] == "@teste"

    ruim = json.loads(json.dumps(EXEMPLO))
    ruim["slides"][1]["texto"] = "Quem posta 3 vezes por semana cresce."
    (pasta / "resposta.txt").write_text("Aqui está:\n```json\n" + json.dumps(ruim, ensure_ascii=False) + "\n```", encoding="utf-8")
    assert cli.main(["montar", str(pasta / "resposta.txt")]) == 1
    assert "3" in (pasta / "correcao.txt").read_text(encoding="utf-8") and not list(pasta.glob("*.png"))

    (pasta / "resposta.txt").write_text(json.dumps(EXEMPLO, ensure_ascii=False), encoding="utf-8")
    assert cli.main(["montar", str(pasta / "resposta.txt")]) == 0
    assert sorted(p.name for p in pasta.glob("[0-9][0-9].png")) == [f"{i:02d}.png" for i in range(1, 7)]
    assert json.loads((pasta / "slides.json").read_text(encoding="utf-8"))["arroba"] == "@teste"
    assert not (pasta / "correcao.txt").exists()


def test_arroba_sem_o_arroba_ganha_o_arroba(tmp_path):
    assert cli.main(["prompt", "tema", "--arroba", "seuperfil", "--saida", str(tmp_path)]) == 0
    assert json.loads((tmp_path / "pedido.json").read_text(encoding="utf-8"))["arroba"] == "@seuperfil"


def test_render_le_json_com_bom(tmp_path):
    (tmp_path / "c.json").write_text(json.dumps(EXEMPLO, ensure_ascii=False), encoding="utf-8-sig")
    assert cli.main(["render", str(tmp_path / "c.json"), "--saida", str(tmp_path / "s")]) == 0


@pytest.mark.parametrize("codificacao", ["utf-8", "utf-8-sig", "utf-16"])
def test_le_resposta_como_o_editor_gravou(tmp_path, codificacao):
    """Bloco de Notas grava UTF-8 com BOM; PowerShell 5 (Out-File, >) grava UTF-16."""
    (tmp_path / "resposta.txt").write_text(json.dumps(EXEMPLO, ensure_ascii=False), encoding=codificacao)
    assert cli.main(["montar", str(tmp_path / "resposta.txt")]) == 0
    assert json.loads((tmp_path / "slides.json").read_text(encoding="utf-8"))["slides"][1]["titulo"] == EXEMPLO["slides"][1]["titulo"]


def test_arquivo_fora_de_utf8_da_erro_claro(tmp_path, capsys):
    (tmp_path / "c.json").write_text(json.dumps(EXEMPLO, ensure_ascii=False), encoding="cp1252")
    assert cli.main(["render", str(tmp_path / "c.json")]) == 1
    assert "não está em UTF-8" in capsys.readouterr().err


def test_saida_em_pipe_cp1252_nao_quebra(tmp_path):
    """no Windows, a saída em pipe (Git Bash, redirecionamento) vem em cp1252; "→" e emoji do tema não podem derrubar."""
    env = dict(os.environ, PYTHONIOENCODING="cp1252")
    for v in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
        env.pop(v, None)
    r = subprocess.run([sys.executable, "-m", "arrasta", "prompt", "antes → depois \U0001F525", "--saida", str(tmp_path)],
                       capture_output=True, env=env)
    assert r.returncode == 0, r.stderr.decode("utf-8", "replace")
    assert "antes → depois \U0001F525".encode() in r.stdout


def test_recusa_por_nao_caber_vira_correcao_para_a_ia(tmp_path):
    """controle positivo: cada regra passa, mas o texto do slide 3 não cabe no desenho. O montar recusa e grava o
    correcao.txt no mesmo formato das regras, pronto para colar na IA."""
    d = json.loads(json.dumps(EXEMPLO))
    d["slides"][2]["titulo"] = "Curto"
    d["slides"][2]["texto"] = " ".join(["inconstitucionalmente"] * 26)
    (tmp_path / "resposta.txt").write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    assert cli.main(["montar", str(tmp_path / "resposta.txt")]) == 1
    t = (tmp_path / "correcao.txt").read_text(encoding="utf-8")
    assert t.startswith("Seu carrossel quebrou estas regras:") and "- slide 3: o texto passa" in t and "encurte o título ou o texto" in t
    assert not list(tmp_path.glob("*.png"))


def test_recusa_por_textos_encostados_vira_correcao(tmp_path, monkeypatch):
    import shutil
    from arrasta import render
    modelos = tmp_path / "modelos"
    shutil.copytree(render.MODELOS, modelos)
    html = modelos / "escuro" / "molde.html"
    html.write_text(html.read_text(encoding="utf-8").replace("margin-top: 44px; letter-spacing", "margin-top: -60px; letter-spacing"), encoding="utf-8")
    monkeypatch.setattr(render, "MODELOS", modelos)
    pasta = tmp_path / "c"
    pasta.mkdir()
    (pasta / "resposta.txt").write_text(json.dumps(EXEMPLO, ensure_ascii=False), encoding="utf-8")
    assert cli.main(["montar", str(pasta / "resposta.txt")]) == 1
    assert "- slide 2: o título e o texto ficaram colados; encurte um dos dois" in (pasta / "correcao.txt").read_text(encoding="utf-8")


def test_recusa_que_o_texto_nao_resolve_nao_vai_para_a_ia(tmp_path):
    """foto que não existe é problema de arquivo, não de texto: recusa sem correcao.txt."""
    d = json.loads(json.dumps(EXEMPLO))
    d["visual"], d["imagem"] = "imagem", str(tmp_path / "nao-existe.jpg")
    (tmp_path / "resposta.txt").write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    assert cli.main(["montar", str(tmp_path / "resposta.txt")]) == 1
    assert not (tmp_path / "correcao.txt").exists()
