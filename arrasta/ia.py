"""Caminho com chave: o arrasta pede o texto direto à IA, confere e pede correção se precisar.

Funciona com a chave da OpenAI (OPENAI_API_KEY) ou da Anthropic (ANTHROPIC_API_KEY).
A chave é de quem usa e o custo da chamada sai da conta dessa pessoa.
Se as duas estiverem no ambiente, usa a da OpenAI; --ia escolhe.
"""
import json
import os

from . import prompt as P
from . import regras

PROVEDORES = ("openai", "anthropic")
CHAVES = {"openai": "OPENAI_API_KEY", "anthropic": "ANTHROPIC_API_KEY"}
MODELO_PADRAO = {"openai": "gpt-6-astra", "anthropic": "claude-opus-5"}
NOME = {"openai": "OpenAI", "anthropic": "Anthropic"}
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


def provedor(escolha=None):
    """devolve 'openai', 'anthropic' ou None (sem chave). Com as duas chaves, OpenAI; escolha força um."""
    if escolha:
        if not os.environ.get(CHAVES[escolha]):
            raise FalhaIA(f"--ia {escolha} pede a variável {CHAVES[escolha]} no ambiente")
        return escolha
    for p in PROVEDORES:
        if os.environ.get(CHAVES[p]):
            return p
    return None


def _pedir_anthropic(cliente, modelo, msgs):
    import anthropic
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
        raise FalhaIA(f"o modelo {modelo} não foi encontrado na Anthropic")
    except anthropic.RateLimitError:
        raise FalhaIA("limite de uso da sua conta na Anthropic atingido. Espere um pouco e tente de novo")
    except anthropic.BadRequestError as e:
        raise FalhaIA(f"a Anthropic recusou o pedido: {e.message}")
    except anthropic.APIStatusError as e:
        raise FalhaIA(f"erro {e.status_code} na API da Anthropic. Tente de novo em alguns minutos")
    except anthropic.APIConnectionError:
        raise FalhaIA("sem conexão com a API da Anthropic")
    if r.stop_reason == "refusal":
        raise FalhaIA("a IA se recusou a escrever sobre esse tema")
    if r.stop_reason == "max_tokens":
        raise FalhaIA("a resposta da IA foi cortada no meio")
    texto = next((b.text for b in r.content if b.type == "text"), "")
    return texto, {"role": "assistant", "content": r.content}


def _pedir_openai(cliente, modelo, msgs):
    import openai
    try:
        r = cliente.responses.create(
            model=modelo,
            input=msgs,
            max_output_tokens=16000,
            text={"format": {"type": "json_schema", "name": "carrossel", "schema": ESQUEMA, "strict": True}},
        )
    except openai.AuthenticationError:
        raise FalhaIA("a chave OPENAI_API_KEY foi recusada. Confira se copiou a chave inteira")
    except openai.PermissionDeniedError:
        raise FalhaIA("a chave não tem permissão para esse modelo")
    except openai.NotFoundError:
        raise FalhaIA(f"o modelo {modelo} não foi encontrado na OpenAI")
    except openai.RateLimitError as e:
        if getattr(e, "code", None) == "insufficient_quota":
            raise FalhaIA("sua conta da OpenAI está sem crédito. Coloque crédito em platform.openai.com e tente de novo")
        raise FalhaIA("limite de uso da sua conta na OpenAI atingido. Espere um pouco e tente de novo")
    except openai.BadRequestError as e:
        raise FalhaIA(f"a OpenAI recusou o pedido: {e.message}")
    except openai.APIStatusError as e:
        raise FalhaIA(f"erro {e.status_code} na API da OpenAI. Tente de novo em alguns minutos")
    except openai.APIConnectionError:
        raise FalhaIA("sem conexão com a API da OpenAI")
    for item in r.output or []:
        for parte in getattr(item, "content", None) or []:
            if getattr(parte, "type", None) == "refusal":
                raise FalhaIA("a IA se recusou a escrever sobre esse tema")
    if r.status == "incomplete":
        motivo = getattr(r.incomplete_details, "reason", None)
        if motivo == "content_filter":
            raise FalhaIA("a IA se recusou a escrever sobre esse tema")
        raise FalhaIA("a resposta da IA foi cortada no meio")
    if r.status != "completed":
        raise FalhaIA(f"a OpenAI devolveu a resposta com estado {r.status}")
    texto = r.output_text
    return texto, {"role": "assistant", "content": texto}


def gerar(tema, publico=None, slides=7, modelo=None, ia=None, avisar=print):
    """devolve (dados, tentativas, provedor, modelo). Levanta FalhaIA se a API recusar ou se o texto não passar nas regras."""
    p = provedor(ia)
    if p is None:
        raise FalhaIA("nenhuma chave no ambiente (OPENAI_API_KEY ou ANTHROPIC_API_KEY)")
    modelo = modelo or os.environ.get("ARRASTA_MODELO") or MODELO_PADRAO[p]
    if p == "openai":
        import openai
        cliente, pedir = openai.OpenAI(), _pedir_openai
    else:
        import anthropic
        cliente, pedir = anthropic.Anthropic(), _pedir_anthropic
    msgs = [{"role": "user", "content": P.montar(tema, publico, slides)
             + "\nCampo que não se aplica ao slide (texto da capa, pedido fora do final) vai como texto vazio \"\"."}]
    fonte = " ".join(x for x in (tema, publico) if x)
    erros = []
    for tentativa in range(1, TENTATIVAS + 1):
        avisar(f"pedindo o texto à IA ({NOME[p]}, {modelo}), tentativa {tentativa} de {TENTATIVAS}...")
        texto, turno = pedir(cliente, modelo, msgs)
        try:
            dados = json.loads(texto)
        except json.JSONDecodeError:
            raise FalhaIA("a IA devolveu um JSON quebrado")
        regras.normalizar(dados)
        erros = regras.verificar(dados, fonte_dos_numeros=fonte)
        if not erros:
            return dados, tentativa, p, modelo
        avisar(f"a resposta quebrou {len(erros)} regra(s); pedindo correção")
        msgs += [turno, {"role": "user", "content": P.correcao(erros)}]
    raise FalhaIA("depois de %d tentativas o texto ainda quebra regras:\n%s" % (
        TENTATIVAS, "\n".join(f"  {onde}: {msg}" for _, onde, msg in erros)))
