"""O caminho sem chave pela linha de comando: prompt -> resposta colada -> montar -> PNG."""
import json
from pathlib import Path

from arrasta import cli

EXEMPLO = json.loads((Path(__file__).resolve().parents[1] / "exemplos/exemplo.json").read_text(encoding="utf-8"))


def test_nome_da_pasta_corta_em_palavra_inteira():
    assert cli.slug("por que o cliente some depois do orçamento") == "por-que-o-cliente-some-depois-do"
    assert len(cli.slug("x" * 60)) == 40
    assert cli.slug("!!!") == "carrossel"


def test_sem_chave_tema_vira_prompt_e_montar_gera_png(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    pasta = tmp_path / "c"
    assert cli.main(["tema", "carrossel que prende", "--arroba", "@teste", "--saida", str(pasta)]) == 0
    assert (pasta / "prompt.txt").exists() and json.loads((pasta / "pedido.json").read_text())["arroba"] == "@teste"

    ruim = json.loads(json.dumps(EXEMPLO))
    ruim["slides"][1]["texto"] = "Quem posta 3 vezes por semana cresce."
    (pasta / "resposta.txt").write_text("Aqui está:\n```json\n" + json.dumps(ruim, ensure_ascii=False) + "\n```", encoding="utf-8")
    assert cli.main(["montar", str(pasta / "resposta.txt")]) == 1
    assert "3" in (pasta / "correcao.txt").read_text() and not list(pasta.glob("*.png"))

    (pasta / "resposta.txt").write_text(json.dumps(EXEMPLO, ensure_ascii=False), encoding="utf-8")
    assert cli.main(["montar", str(pasta / "resposta.txt")]) == 0
    assert sorted(p.name for p in pasta.glob("[0-9][0-9].png")) == [f"{i:02d}.png" for i in range(1, 7)]
    assert json.loads((pasta / "slides.json").read_text())["arroba"] == "@teste"
    assert not (pasta / "correcao.txt").exists()
