"""Caminho com chave, contra um servidor falso local (não gasta nada e não precisa de chave real).

Prova o ramo de cada provedor: o pedido sai no formato certo, a resposta que quebra regra volta para a IA com a
correção, e a segunda resposta, correta, é aceita. A chamada à API de verdade fica de fora destes testes.
"""
import copy
import json
import os
import pathlib
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from arrasta import ia

EXEMPLO = json.loads((Path(__file__).resolve().parents[1] / "exemplos/exemplo.json").read_text(encoding="utf-8"))


def slides_da_api():
    s = copy.deepcopy(EXEMPLO["slides"])
    for x in s:
        for k in ("texto", "pedido"):
            x.setdefault(k, "")
    return s


def resposta_anthropic(slides):
    return {"id": "msg_teste", "type": "message", "role": "assistant", "model": "claude-opus-5",
            "content": [{"type": "text", "text": json.dumps({"slides": slides}, ensure_ascii=False)}],
            "stop_reason": "end_turn", "stop_sequence": None, "usage": {"input_tokens": 10, "output_tokens": 10}}


def resposta_openai(slides, status="completed", recusa=False):
    parte = ({"type": "refusal", "refusal": "não posso"} if recusa else
             {"type": "output_text", "text": json.dumps({"slides": slides}, ensure_ascii=False), "annotations": []})
    return {"id": "resp_teste", "object": "response", "created_at": 0, "status": status, "model": "gpt-6-astra",
            "incomplete_details": {"reason": "max_output_tokens"} if status == "incomplete" else None,
            "output": [{"type": "message", "id": "msg_teste", "status": "completed", "role": "assistant", "content": [parte]}],
            "parallel_tool_calls": True, "tool_choice": "auto", "tools": [],
            "usage": {"input_tokens": 10, "output_tokens": 10, "total_tokens": 20,
                      "input_tokens_details": {"cached_tokens": 0}, "output_tokens_details": {"reasoning_tokens": 0}}}


@pytest.fixture
def servidor(monkeypatch):
    recebidos, fila = [], []

    class H(BaseHTTPRequestHandler):
        def do_POST(self):
            corpo = json.loads(self.rfile.read(int(self.headers["content-length"])))
            recebidos.append({"caminho": self.path, "beta": self.headers.get("anthropic-beta"), "corpo": corpo})
            proximo = fila.pop(0)
            # (status, corpo) quando o teste quer um erro; só o corpo quando é 200
            status, proximo = proximo if isinstance(proximo, tuple) else (200, proximo)
            dados = json.dumps(proximo).encode()
            self.send_response(status)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(dados)))
            self.end_headers()
            self.wfile.write(dados)

        def log_message(self, *a):
            pass

    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_port}"
    monkeypatch.setenv("ANTHROPIC_BASE_URL", base)
    monkeypatch.setenv("OPENAI_BASE_URL", base + "/v1")
    for v in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "ARRASTA_MODELO"):
        monkeypatch.delenv(v, raising=False)
    yield recebidos, fila
    srv.shutdown()


def calar(*_):
    pass


# ---------------------------------------------------------------- qual chave vale

def test_sem_chave_nenhum_provedor(monkeypatch):
    for v in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.delenv(v, raising=False)
    assert ia.provedor() is None


def test_uma_chave_escolhe_o_dono_dela(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "a")
    assert ia.provedor() == "anthropic"
    monkeypatch.delenv("ANTHROPIC_API_KEY")
    monkeypatch.setenv("OPENAI_API_KEY", "o")
    assert ia.provedor() == "openai"


def test_duas_chaves_openai_e_ia_forca(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "a")
    monkeypatch.setenv("OPENAI_API_KEY", "o")
    assert ia.provedor() == "openai"
    assert ia.provedor("anthropic") == "anthropic"


def test_ia_forcada_sem_a_chave_dela_falha(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "o")
    with pytest.raises(ia.FalhaIA, match="ANTHROPIC_API_KEY"):
        ia.provedor("anthropic")


# ---------------------------------------------------------------- Anthropic

def test_anthropic_resposta_que_quebra_regra_volta_com_correcao(servidor, monkeypatch):
    recebidos, fila = servidor
    monkeypatch.setenv("ANTHROPIC_API_KEY", "chave-de-teste")
    ruim = slides_da_api()
    ruim[0]["titulo"] = " ".join(["palavra"] * 15)
    fila += [resposta_anthropic(ruim), resposta_anthropic(slides_da_api())]

    dados, tentativas, p, modelo = ia.gerar("por que o carrossel não prende", avisar=calar)

    assert (p, modelo, tentativas, len(recebidos)) == ("anthropic", "claude-opus-5", 2, 2)
    assert dados["slides"][0]["titulo"] == EXEMPLO["slides"][0]["titulo"]
    primeiro, segundo = recebidos
    assert primeiro["caminho"].startswith("/v1/messages")
    assert primeiro["corpo"]["model"] == "claude-opus-5"
    assert primeiro["corpo"]["fallbacks"] == "default"
    assert "server-side-fallback-2026-07-01" in primeiro["beta"]
    assert primeiro["corpo"]["output_config"]["format"]["type"] == "json_schema"
    assert "por que o carrossel não prende" in primeiro["corpo"]["messages"][0]["content"]
    ultima = segundo["corpo"]["messages"][-1]["content"]
    assert "slide 1" in ultima and "15 palavras" in ultima


def test_anthropic_tres_respostas_ruins_param_com_erro(servidor, monkeypatch):
    recebidos, fila = servidor
    monkeypatch.setenv("ANTHROPIC_API_KEY", "chave-de-teste")
    ruim = slides_da_api()
    ruim[2]["texto"] = "Comenta aqui embaixo."
    fila += [resposta_anthropic(ruim)] * ia.TENTATIVAS
    with pytest.raises(ia.FalhaIA, match="ainda quebra regras"):
        ia.gerar("tema qualquer", avisar=calar)
    assert len(recebidos) == ia.TENTATIVAS


# ---------------------------------------------------------------- OpenAI

def test_openai_resposta_que_quebra_regra_volta_com_correcao(servidor, monkeypatch):
    recebidos, fila = servidor
    monkeypatch.setenv("OPENAI_API_KEY", "chave-de-teste")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "chave-de-teste")  # com as duas, vale a OpenAI
    ruim = slides_da_api()
    ruim[1]["texto"] = "Quem posta 3 vezes por semana cresce mais."
    fila += [resposta_openai(ruim), resposta_openai(slides_da_api())]

    dados, tentativas, p, modelo = ia.gerar("carrossel que prende", avisar=calar)

    assert (p, modelo, tentativas, len(recebidos)) == ("openai", "gpt-6-astra", 2, 2)
    primeiro, segundo = recebidos
    assert primeiro["caminho"] == "/v1/responses"
    assert primeiro["corpo"]["model"] == "gpt-6-astra"
    fmt = primeiro["corpo"]["text"]["format"]
    assert fmt["type"] == "json_schema" and fmt["strict"] is True and fmt["schema"] == ia.ESQUEMA
    assert "carrossel que prende" in primeiro["corpo"]["input"][0]["content"]
    entrada = segundo["corpo"]["input"]
    assert [m["role"] for m in entrada] == ["user", "assistant", "user"]
    assert "3" in entrada[-1]["content"] and "não está no tema" in entrada[-1]["content"]


@pytest.mark.parametrize("resp, trecho", [
    (lambda: resposta_openai([], recusa=True), "se recusou"),
    (lambda: resposta_openai(slides_da_api(), status="incomplete"), "cortada"),
])
def test_openai_recusa_e_corte_viram_erro_claro(servidor, monkeypatch, resp, trecho):
    recebidos, fila = servidor
    monkeypatch.setenv("OPENAI_API_KEY", "chave-de-teste")
    fila.append(resp())
    with pytest.raises(ia.FalhaIA, match=trecho):
        ia.gerar("tema qualquer", avisar=calar)


def test_visual_imagem_nao_trava_o_laco_da_ia(servidor, monkeypatch, tmp_path):
    """controle positivo da regressão: o visual imagem exige foto, e a foto não vem da IA.

    Se o visual entrar no dados sem a foto junto, toda resposta quebra a regra "pede uma foto", a IA não tem
    como corrigir e as 3 tentativas queimam. O contexto (visual + foto) entra nas duas pontas ou em nenhuma."""
    from PIL import Image
    recebidos, fila = servidor
    monkeypatch.setenv("OPENAI_API_KEY", "chave-de-teste")
    foto = tmp_path / "f.jpg"
    Image.new("RGB", (800, 600), "#123456").save(foto)
    fila.append(resposta_openai(slides_da_api()))

    dados, tentativas, _, _ = ia.gerar("brindes", contexto={"visual": "imagem", "imagem": str(foto)}, avisar=calar)

    assert tentativas == 1, "a resposta boa foi recusada por uma regra que a IA não escreve"
    assert dados["visual"] == "imagem" and dados["imagem"] == str(foto)
    # e o prompt que foi para a IA é o do visual pedido
    assert "CABE NA TELA" in recebidos[0]["corpo"]["input"][0]["content"]


# ---------------------------------------------------------------------------------------------------
# Caminho por CLI de assinatura: o claude e o codex como geradores de texto, sem chave.
# Aqui eles são falsos — o CI não tem login. O que estes testes cobram é o CONTRATO: as bandeiras de
# isolamento saem na linha de comando, a correção volta na mesma conversa, e o id do modelo é o que o
# CLI disse. Que o isolamento funciona de verdade, quem prova é a sonda (b1/sondas no laboratório).

CARROSSEL_RUIM = {"slides": [dict(s) for s in slides_da_api()]}
CARROSSEL_BOM = {"slides": [dict(s) for s in slides_da_api()]}
CARROSSEL_RUIM["slides"][1]["texto"] = "Quem posta 3 vezes por semana cresce mais."


def _falso(pasta, nome, corpo):
    """um CLI falso no PATH. No Windows, quem é achado é o .bat; ele chama o .py ao lado."""
    py = pasta / f"{nome}.py"
    py.write_text("import sys, os, json, pathlib\n" + corpo, encoding="utf-8")
    if os.name == "nt":
        (pasta / f"{nome}.bat").write_text(f'@"{sys.executable}" "%~dp0{nome}.py" %*\n', encoding="utf-8")
        return py
    p = pasta / nome
    p.write_text(f"#!{sys.executable}\n" + py.read_text(encoding="utf-8"), encoding="utf-8")
    p.chmod(0o755)
    return p


@pytest.fixture
def cli_falso(tmp_path, monkeypatch):
    """põe um claude e um codex falsos no PATH; cada chamada grava argv e ambiente num JSONL."""
    binario = tmp_path / "bin"
    binario.mkdir()
    diario = tmp_path / "chamadas.jsonl"
    comum = f"""
diario = pathlib.Path({str(diario)!r})
entrada = sys.stdin.read()
with diario.open("a", encoding="utf-8") as f:
    lar = os.environ.get("CODEX_HOME") or ""
    f.write(json.dumps({{"argv": sys.argv, "entrada": entrada, "cwd": os.getcwd(),
                         "cwd_vazio": not os.listdir(os.getcwd()),
                         "HOME": os.environ.get("HOME"), "CODEX_HOME": lar,
                         "itens_do_lar": sorted(os.listdir(lar)) if os.path.isdir(lar) else [],
                         "login_e_link": (os.path.islink(os.path.join(lar, "auth.json"))
                                          or os.stat(os.path.join(lar, "auth.json")).st_nlink > 1)}}) + "\\n")
n = sum(1 for _ in diario.open(encoding="utf-8"))
carrossel = {json.dumps(CARROSSEL_RUIM)!r} if n == 1 else {json.dumps(CARROSSEL_BOM)!r}
"""
    _falso(binario, "claude", comum + """
print(json.dumps({"type": "result", "is_error": False, "result": carrossel,
                  "modelUsage": {"claude-opus-5[1m]": {"inputTokens": 1, "outputTokens": 2}}}))
""")
    # o codex de verdade manda o cabeçalho (sessão e modelo) no STDERR e só a resposta no stdout.
    # O falso fazia pelo stdout e por isso não pegou o defeito: o provedor lia o stream errado.
    _falso(binario, "codex", comum + """
print("session id: 01a0-falsa", file=sys.stderr)
print("model: gpt-5.6-sol", file=sys.stderr)
alvo = sys.argv[sys.argv.index("-o") + 1]
pathlib.Path(alvo).write_text("Segue o JSON:\\n" + carrossel, encoding="utf-8")
""")
    monkeypatch.setenv("PATH", str(binario) + os.pathsep + os.environ["PATH"])
    lar = tmp_path / "codexhome"
    lar.mkdir()
    (lar / "auth.json").write_text("{}", encoding="utf-8")
    monkeypatch.setenv("CODEX_HOME", str(lar))
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    return diario


def chamadas(diario):
    return [json.loads(l) for l in diario.read_text(encoding="utf-8").splitlines()]


def test_cli_so_entra_quando_e_pedido(cli_falso, monkeypatch, tmp_path):
    """sem --ia, nada muda: quem não tem chave continua caindo no caminho sem chave."""
    assert ia.provedor() is None
    assert ia.provedor("claude_code") == "claude_code"
    assert ia.provedor("codex") == "codex"
    monkeypatch.setenv("PATH", str(tmp_path / "nao-existe"))
    with pytest.raises(ia.FalhaIA, match="comando claude"):
        ia.provedor("claude_code")


@pytest.mark.parametrize("qual, bandeiras", [
    ("claude_code", ["--safe-mode", "--strict-mcp-config", "--tools"]),
    ("codex", ["--ignore-rules", "--skip-git-repo-check", "project_doc_max_bytes=0"]),
])
def test_cli_gera_isolado_e_corrige_na_mesma_conversa(cli_falso, qual, bandeiras):
    dados, tentativas, p, modelo = ia.gerar("carrossel que prende", ia=qual, avisar=calar)

    assert (p, tentativas) == (qual, 2), "a resposta ruim tinha de voltar para o mesmo CLI"
    assert modelo == ("claude-opus-5[1m]" if qual == "claude_code" else "gpt-5.6-sol")
    c = chamadas(cli_falso)
    assert len(c) == 2
    for b in bandeiras:
        assert b in c[0]["argv"], f"faltou {b} na linha de comando"
    # a segunda chamada continua a MESMA conversa, e manda só a correção
    segunda = " ".join(c[1]["argv"])
    assert ("--resume" in segunda) or (" resume " in segunda)
    assert "Seu carrossel quebrou estas regras" in c[1]["entrada"]
    assert "3" in c[1]["entrada"] and "não está no tema" in c[1]["entrada"]
    # a primeira mandou o prompt do arrasta inteiro
    assert "carrossel que prende" in c[0]["entrada"] and "REGRAS DE ESCRITA" in c[0]["entrada"]
    # e rodou numa pasta vazia
    assert c[0]["cwd_vazio"]


def test_codex_roda_com_home_proprio_e_so_o_login(cli_falso, tmp_path):
    """medido em 20/09: o codex lê o AGENTS.md de $CODEX_HOME e as skills de ~/.claude/skills mesmo com
    --ignore-user-config. O isolamento que funciona é HOME e CODEX_HOME próprios, com só o login dentro."""
    ia.gerar("brindes", ia="codex", avisar=calar)
    c = chamadas(cli_falso)[0]
    assert c["HOME"] != os.path.expanduser("~")
    assert c["itens_do_lar"] == ["auth.json"]
    assert c["login_e_link"], "o login é apontado, nunca copiado"


def test_claude_code_nao_mexe_no_home(cli_falso):
    """o claude se isola por bandeira; mexer no HOME dele tiraria o login da assinatura."""
    ia.gerar("brindes", ia="claude_code", avisar=calar)
    # comparado com o que ESTE processo tem, não com expanduser: no Windows não existe HOME no ambiente
    assert chamadas(cli_falso)[0]["HOME"] == os.environ.get("HOME")


@pytest.mark.parametrize("corpo, trecho, nao_pode", [
    # o que a OpenAI manda de verdade quando a conta zera (medido em 20/09/2026):
    ({"error": {"message": "You have no credits remaining.", "type": "insufficient_quota",
                "param": None, "code": "credit_balance_exhausted"}}, "sem crédito", "Espere"),
    # e o 429 de limite por minuto, que continua sendo "espere"
    ({"error": {"message": "Rate limit reached for gpt-6-astra", "type": "requests",
                "param": None, "code": "rate_limit_exceeded"}}, "Espere um pouco", "sem crédito"),
])
def test_os_dois_429_da_openai_dizem_coisas_diferentes(servidor, monkeypatch, corpo, trecho, nao_pode):
    """conta sem crédito e limite por minuto chegam os dois como 429. Mandar esperar quem está sem crédito
    é mandar a pessoa esperar para sempre: o conserto é outro, e a mensagem tem de dizer qual."""
    recebidos, fila = servidor
    monkeypatch.setenv("OPENAI_API_KEY", "chave-de-teste")
    fila.extend([(429, corpo)] * 6)
    with pytest.raises(ia.FalhaIA) as e:
        ia.gerar("tema qualquer", avisar=calar)
    assert trecho in str(e.value) and nao_pode not in str(e.value)
