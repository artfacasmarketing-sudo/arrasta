"""Caminho com chave: o arrasta pede o texto direto à API da Anthropic, confere e pede correção se precisar.

A chave é de quem usa (variável ANTHROPIC_API_KEY) e o custo da chamada sai da conta dessa pessoa.
"""
import json
import os

from . import prompt as P
from . import regras

MODELO_PADRAO = "claude-opus-5"
TENTATIVAS = 3

ESQUEMA = {
    "type": "object",
    "properties": {
        "slides": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "tipo": {"type": "string", "enum": ["capa", "miolo", "final"]},
                    "titulo": {"type": "string"},
                    "texto": {"type": "string"},
                    "pedido": {"type": "string"},
                },
                "required": ["tipo", "titulo", "texto", "pedido"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["slides"],
    "additionalProperties": False,
}


class FalhaIA(Exception):
    pass


def tem_chave():
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def gerar(tema, publico=None, slides=7, modelo=None, avisar=print):
    """devolve (dados, tentativas). Levanta FalhaIA se a API recusar ou se o texto não passar nas regras."""
    import anthropic

    modelo = modelo or os.environ.get("ARRASTA_MODELO") or MODELO_PADRAO
    cliente = anthropic.Anthropic()
    msgs = [{"role": "user", "content": P.montar(tema, publico, slides)
             + "\nCampo que não se aplica ao slide (texto da capa, pedido fora do final) vai como texto vazio \"\"."}]
    fonte = " ".join(x for x in (tema, publico) if x)
    erros = []
    for tentativa in range(1, TENTATIVAS + 1):
        avisar(f"pedindo o texto à IA ({modelo}), tentativa {tentativa} de {TENTATIVAS}...")
        try:
            r = cliente.beta.messages.create(
                model=modelo,
                max_tokens=16000,
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
                output_config={"format": {"type": "json_schema", "schema": ESQUEMA}},
                messages=msgs,
            )
        except anthropic.AuthenticationError:
            raise FalhaIA("a chave ANTHROPIC_API_KEY foi recusada. Confira se copiou a chave inteira")
        except anthropic.PermissionDeniedError:
            raise FalhaIA("a chave não tem permissão para esse modelo")
        except anthropic.NotFoundError:
            raise FalhaIA(f"o modelo {modelo} não foi encontrado")
        except anthropic.RateLimitError:
            raise FalhaIA("limite de uso da sua conta na Anthropic atingido. Espere um pouco e tente de novo")
        except anthropic.BadRequestError as e:
            raise FalhaIA(f"a API recusou o pedido: {e.message}")
        except anthropic.APIStatusError as e:
            raise FalhaIA(f"erro {e.status_code} na API da Anthropic. Tente de novo em alguns minutos")
        except anthropic.APIConnectionError:
            raise FalhaIA("sem conexão com a API da Anthropic")
        if r.stop_reason == "refusal":
            raise FalhaIA("a IA se recusou a escrever sobre esse tema")
        if r.stop_reason == "max_tokens":
            raise FalhaIA("a resposta da IA foi cortada no meio")
        texto = next((b.text for b in r.content if b.type == "text"), "")
        try:
            dados = json.loads(texto)
        except json.JSONDecodeError:
            raise FalhaIA("a IA devolveu um JSON quebrado")
        regras.normalizar(dados)
        erros = regras.verificar(dados, fonte_dos_numeros=fonte)
        if not erros:
            return dados, tentativa
        avisar(f"a resposta quebrou {len(erros)} regra(s); pedindo correção")
        msgs += [{"role": "assistant", "content": r.content}, {"role": "user", "content": P.correcao(erros)}]
    raise FalhaIA("depois de %d tentativas o texto ainda quebra regras:\n%s" % (
        TENTATIVAS, "\n".join(f"  {onde}: {msg}" for _, onde, msg in erros)))
