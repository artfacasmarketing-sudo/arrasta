"""Caminho com chave, contra um servidor falso local (não gasta nada e não precisa de chave real).

Prova o ramo: o pedido sai no formato certo, a resposta que quebra regra volta para a IA com a correção,
e a segunda resposta, correta, é aceita. A chamada à API de verdade fica de fora deste teste.
"""
import copy
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from arrasta import ia

EXEMPLO = json.loads((Path(__file__).resolve().parents[1] / "exemplos/exemplo.json").read_text(encoding="utf-8"))


def resposta_da_api(slides):
    return {"id": "msg_teste", "type": "message", "role": "assistant", "model": "claude-opus-5",
            "content": [{"type": "text", "text": json.dumps({"slides": slides}, ensure_ascii=False)}],
            "stop_reason": "end_turn", "stop_sequence": None, "usage": {"input_tokens": 10, "output_tokens": 10}}


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
    monkeypatch.setenv("ANTHROPIC_BASE_URL", f"http://127.0.0.1:{srv.server_port}")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "chave-de-teste")
    monkeypatch.delenv("ARRASTA_MODELO", raising=False)
    yield recebidos, fila
    srv.shutdown()


def slides_da_api():
    s = copy.deepcopy(EXEMPLO["slides"])
    for x in s:
        for k in ("texto", "pedido"):
            x.setdefault(k, "")
    return s


def test_resposta_que_quebra_regra_volta_com_correcao(servidor):
    recebidos, fila = servidor
    ruim = slides_da_api()
    ruim[0]["titulo"] = " ".join(["palavra"] * 15)
    fila += [resposta_da_api(ruim), resposta_da_api(slides_da_api())]

    dados, tentativas = ia.gerar("por que o carrossel não prende", avisar=lambda *_: None)

    assert tentativas == 2 and len(recebidos) == 2
    assert dados["slides"][0]["titulo"] == EXEMPLO["slides"][0]["titulo"]
    primeiro, segundo = recebidos
    assert primeiro["caminho"].startswith("/v1/messages")
    assert primeiro["corpo"]["model"] == ia.MODELO_PADRAO
    assert primeiro["corpo"]["fallbacks"] == "default"
    assert "server-side-fallback-2026-07-01" in primeiro["beta"]
    assert primeiro["corpo"]["output_config"]["format"]["type"] == "json_schema"
    assert "por que o carrossel não prende" in primeiro["corpo"]["messages"][0]["content"]
    ultima = segundo["corpo"]["messages"][-1]["content"]
    assert "slide 1" in ultima and "15 palavras" in ultima


def test_tres_respostas_ruins_param_com_erro(servidor):
    recebidos, fila = servidor
    ruim = slides_da_api()
    ruim[2]["texto"] = "Comenta aqui embaixo."
    fila += [resposta_da_api(ruim)] * ia.TENTATIVAS
    with pytest.raises(ia.FalhaIA, match="ainda quebra regras"):
        ia.gerar("tema qualquer", avisar=lambda *_: None)
    assert len(recebidos) == ia.TENTATIVAS
