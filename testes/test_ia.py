"""Caminho com chave, contra um servidor falso local (não gasta nada e não precisa de chave real).

Prova o ramo de cada provedor: o pedido sai no formato certo, a resposta que quebra regra volta para a IA com a
correção, e a segunda resposta, correta, é aceita. A chamada à API de verdade fica de fora destes testes.
"""
import copy
import json
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
            dados = json.dumps(fila.pop(0)).encode()
            self.send_response(200)
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
