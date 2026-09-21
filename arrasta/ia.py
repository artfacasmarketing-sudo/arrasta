"""Caminho automático: o arrasta pede o texto direto à IA, confere e pede correção se precisar.

Dois jeitos de chegar na IA:
  por chave   OPENAI_API_KEY ou ANTHROPIC_API_KEY. A chave é de quem usa e o custo sai da conta dessa pessoa.
              Se as duas estiverem no ambiente, usa a da OpenAI; --ia escolhe.
  por CLI     o `claude` ou o `codex` já instalados e logados na assinatura de quem usa, em modo sem
              interface. Sem chave, sem custo por chamada além da assinatura. Só com --ia claude_code
              ou --ia codex: sem isso, nada muda.

O CLI é usado como gerador de texto e nada mais: cada chamada roda numa pasta vazia, sem ferramenta,
sem skill, sem MCP e sem os arquivos de instrução de quem usa. O que o carrossel tem de seguir está no
prompt do arrasta; o que estiver no CLAUDE.md ou no AGENTS.md da pessoa não pode entrar no meio.
"""
import json
import os
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path

from . import prompt as P
from . import regras, resposta

PROVEDORES = ("openai", "anthropic", "claude_code", "codex")
CHAVES = {"openai": "OPENAI_API_KEY", "anthropic": "ANTHROPIC_API_KEY"}
CLIS = {"claude_code": "claude", "codex": "codex"}
MODELO_PADRAO = {"openai": "gpt-6-astra", "anthropic": "claude-opus-5"}  # o CLI usa o padrão dele
NOME = {"openai": "OpenAI", "anthropic": "Anthropic", "claude_code": "Claude Code", "codex": "Codex"}
TENTATIVAS = 3
ESPERA_CLI = 600
# o que a OpenAI manda no 429 quando a conta está zerada, no code ou no type
SEM_CREDITO = ("insufficient_quota", "credit_balance_exhausted")

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
    """devolve o provedor, ou None quando não há nenhum caminho automático.

    Sem escolha, só os de chave entram: quem não pediu nada continua recebendo o que recebia antes.
    Os CLI só entram por --ia claude_code / --ia codex."""
    if escolha in CLIS:
        if not shutil.which(CLIS[escolha]):
            raise FalhaIA(f"--ia {escolha} pede o comando {CLIS[escolha]} instalado e no PATH")
        return escolha
    if escolha:
        if not os.environ.get(CHAVES[escolha]):
            raise FalhaIA(f"--ia {escolha} pede a variável {CHAVES[escolha]} no ambiente")
        return escolha
    for p in CHAVES:
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
        # o 429 tem duas causas e dois consertos. Sem crédito, esperar não resolve nunca.
        # Medido em 20/09/2026: o SDK põe "insufficient_quota" no TYPE do corpo e "credit_balance_exhausted"
        # no code; comparar só com o code deixava a conta zerada recebendo "espere um pouco".
        corpo = getattr(e, "body", None)
        erro = corpo.get("error", corpo) if isinstance(corpo, dict) else {}
        tipo = erro.get("type") if isinstance(erro, dict) else None
        if getattr(e, "code", None) in SEM_CREDITO or tipo in SEM_CREDITO:
            raise FalhaIA("sua conta da OpenAI está sem crédito. Coloque crédito em "
                          "platform.openai.com/settings/organization/billing e rode de novo")
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


class SessaoCLI:
    """uma conversa com um CLI logado por assinatura.

    Guarda a sessão para a correção voltar na MESMA conversa (o CLI sabe o que ele mesmo respondeu), e a
    pasta vazia onde cada chamada roda. O id do modelo é o que o próprio CLI disser ter usado."""

    def __init__(self, qual):
        self.qual = qual
        self.sessao = None
        self.modelo = None
        self._tmp = tempfile.TemporaryDirectory(prefix="arrasta-cli-")
        self.pasta = Path(self._tmp.name) / "trabalho"
        self.pasta.mkdir()
        self.ambiente = _ambiente(qual, Path(self._tmp.name))


def _ambiente(qual, base):
    """o ambiente do CLI, sem o que é de quem usa.

    O `claude` se isola por bandeira (--safe-mode desliga CLAUDE.md, skill, plugin, hook e MCP).
    O `codex` não: medido em 20/09/2026, ele carrega o AGENTS.md de $CODEX_HOME e as skills de
    ~/.claude/skills mesmo com --ignore-user-config. O jeito que funciona é dar a ele um CODEX_HOME só
    com o arquivo de login e um HOME vazio — provado por sonda, que passou a voltar sem nenhuma skill
    e sem nenhum AGENTS.md."""
    if qual != "codex":
        return dict(os.environ)
    casa = base / "casa"
    casa.mkdir(exist_ok=True)
    lar = base / "codex"
    lar.mkdir(exist_ok=True)
    login = Path(os.environ.get("CODEX_HOME") or (Path.home() / ".codex")) / "auth.json"
    if not login.is_file():
        raise FalhaIA("o codex não está logado (não achei o auth.json). Rode: codex login")
    alvo = lar / "auth.json"
    if not alvo.exists():
        # o login é apontado, nunca copiado nem lido. O Windows só faz symlink com privilégio;
        # lá vale o hardlink, que é o mesmo arquivo com outro nome.
        try:
            alvo.symlink_to(login)
        except OSError:
            try:
                os.link(login, alvo)
            except OSError as e:
                raise FalhaIA(f"não deu para apontar o login do codex em {lar}: {e}")
    env = dict(os.environ)
    env.update(HOME=str(casa), CODEX_HOME=str(lar))
    return env


def _rodar_cli(args, entrada, sessao):
    # o caminho inteiro, resolvido pelo PATH: no Windows o subprocess não procura .bat/.cmd sozinho,
    # e o comando some com "arquivo não encontrado" mesmo estando instalado
    exe = shutil.which(args[0])
    if not exe:
        raise FalhaIA(f"o comando {args[0]} não está instalado")
    args = [exe, *args[1:]]
    try:
        r = subprocess.run(args, input=entrada, capture_output=True, text=True,
                           cwd=str(sessao.pasta), env=sessao.ambiente, timeout=ESPERA_CLI)
    except subprocess.TimeoutExpired:
        raise FalhaIA(f"o {CLIS[sessao.qual]} passou de {ESPERA_CLI}s sem responder")
    except FileNotFoundError:
        raise FalhaIA(f"o comando {CLIS[sessao.qual]} não está instalado")
    if r.returncode != 0:
        fim = (r.stderr or r.stdout or "").strip().splitlines()
        raise FalhaIA(f"o {CLIS[sessao.qual]} saiu com erro {r.returncode}: " + (fim[-1] if fim else "sem mensagem"))
    return r


def _pedir_claude_code(sessao, modelo, msgs):
    """--safe-mode desliga CLAUDE.md, skills, plugins, hooks e MCP; --tools "" tira toda ferramenta."""
    args = ["claude", "-p", "--safe-mode", "--tools", "", "--strict-mcp-config", "--output-format", "json"]
    if sessao.sessao is None:
        sessao.sessao = str(uuid.uuid4())
        args += ["--session-id", sessao.sessao]
    else:
        args += ["--resume", sessao.sessao]
    if modelo:
        args += ["--model", modelo]
    r = _rodar_cli(args, msgs[-1]["content"], sessao)
    try:
        d = json.loads(r.stdout)
    except json.JSONDecodeError:
        raise FalhaIA("o claude devolveu uma saída que não é JSON")
    if d.get("is_error"):
        raise FalhaIA(f"o claude recusou: {str(d.get('result'))[:200]}")
    sessao.modelo = next(iter(d.get("modelUsage") or {}), None) or sessao.modelo
    texto = d.get("result") or ""
    return texto, {"role": "assistant", "content": texto}


def _pedir_codex(sessao, modelo, msgs):
    comum = ["--ignore-rules", "--skip-git-repo-check", "-c", "project_doc_max_bytes=0"]
    saida = sessao.pasta.parent / "resposta.txt"
    if sessao.sessao is None:
        args = ["codex", "exec", *comum, "--sandbox", "read-only", "-C", str(sessao.pasta)]
    else:
        args = ["codex", "exec", "resume", *comum]
    if modelo:
        args += ["-m", modelo]
    args += ["-o", str(saida)]
    if sessao.sessao is not None:
        args.append(sessao.sessao)
    args.append("-")
    r = _rodar_cli(args, msgs[-1]["content"], sessao)
    # o cabeçalho com a sessão e o modelo sai no stderr; a resposta vai para o arquivo do -o
    for linha in ((r.stderr or "") + "\n" + (r.stdout or "")).splitlines():
        if linha.startswith("session id:") and sessao.sessao is None:
            sessao.sessao = linha.split(":", 1)[1].strip()
        elif linha.startswith("model:"):
            sessao.modelo = linha.split(":", 1)[1].strip() or sessao.modelo
    if sessao.sessao is None:
        raise FalhaIA("o codex não disse o id da sessão; sem ele a correção não volta na mesma conversa")
    if not saida.is_file():
        raise FalhaIA("o codex não gravou a resposta")
    texto = saida.read_text(encoding="utf-8")
    saida.unlink()
    return texto, {"role": "assistant", "content": texto}


def gerar(tema, publico=None, slides=7, modelo=None, ia=None, avisar=print, contexto=None, objetivo=None):
    """devolve (dados, tentativas, provedor, modelo). Levanta FalhaIA se a API recusar ou se o texto não passar nas regras.

    contexto: o que não vem da IA e muda o que é aprovado — visual e foto, já resolvidos. Entra no dados ANTES de
    conferir: a largura que cabe muda de um molde para o outro, e o visual imagem só é válido com a foto junto."""
    p = provedor(ia)
    if p is None:
        raise FalhaIA("nenhuma chave no ambiente (OPENAI_API_KEY ou ANTHROPIC_API_KEY)")
    # nos CLI o modelo padrão é o do próprio CLI: é o que a pessoa recebe quando abre ele na mão
    modelo = modelo or os.environ.get("ARRASTA_MODELO") or MODELO_PADRAO.get(p)
    if p in CLIS:
        cliente = SessaoCLI(p)
        pedir = _pedir_claude_code if p == "claude_code" else _pedir_codex
    elif p == "openai":
        import openai
        cliente, pedir = openai.OpenAI(), _pedir_openai
    else:
        import anthropic
        cliente, pedir = anthropic.Anthropic(), _pedir_anthropic
    contexto = {k: v for k, v in (contexto or {}).items() if v}
    msgs = [{"role": "user", "content": P.montar(tema, publico, slides, contexto.get("visual"), objetivo)
             + "\nCampo que não se aplica ao slide (texto da capa, pedido fora do final) vai como texto vazio \"\"."}]
    fonte = " ".join(x for x in (tema, publico) if x)
    erros = []
    for tentativa in range(1, TENTATIVAS + 1):
        avisar(f"pedindo o texto à IA ({NOME[p]}, {modelo or 'modelo padrão do CLI'}), tentativa {tentativa} de {TENTATIVAS}...")
        texto, turno = pedir(cliente, modelo, msgs)
        try:
            dados = json.loads(texto) if p not in CLIS else resposta.extrair(texto)
        except (json.JSONDecodeError, resposta.RespostaInvalida):
            raise FalhaIA("a IA devolveu um JSON quebrado")
        dados.update(contexto)
        regras.normalizar(dados)
        erros = regras.verificar(dados, fonte_dos_numeros=fonte)
        if not erros:
            return dados, tentativa, p, getattr(cliente, "modelo", None) or modelo
        avisar(f"a resposta quebrou {len(erros)} regra(s); pedindo correção")
        msgs += [turno, {"role": "user", "content": P.correcao(erros)}]
    raise FalhaIA("depois de %d tentativas o texto ainda quebra regras:\n%s" % (
        TENTATIVAS, "\n".join(f"  {onde}: {msg}" for _, onde, msg in erros)))
