"""O prompt que vai para a IA. As regras aqui são as mesmas que o regras.py confere depois."""
from . import regras as R

MODELO_JSON = """{
  "slides": [
    {"tipo": "capa", "titulo": "...", "texto": "..."},
    {"tipo": "miolo", "titulo": "...", "texto": "..."},
    {"tipo": "final", "titulo": "...", "pedido": "..."}
  ]
}"""


def montar(tema, publico=None, slides=7):
    miolo = slides - 2
    publico = publico or "quem se interessa por esse tema"
    return f"""Você escreve carrosséis de Instagram em português do Brasil, do jeito que se fala.

TEMA: {tema}
PÚBLICO: {publico}

Escreva um carrossel de {slides} slides sobre o tema: 1 capa, {miolo} de miolo e 1 final.

CAPA (slide 1)
- Abre uma pergunta na cabeça de quem lê e não entrega a resposta. Quem lê a capa tem de querer arrastar.
- Cita algo concreto do dia a dia desse público: um objeto, um lugar, um momento.
- "titulo" com até {R.CAPA_TITULO} palavras. "texto" opcional, com até {R.CAPA_TEXTO} palavras.

MIOLO (slides 2 a {slides - 1})
- Uma ideia por slide, na ordem que responde a pergunta da capa aos poucos.
- Cada slide termina deixando vontade de ver o próximo.
- "titulo" com até {R.MIOLO_TITULO} palavras. "titulo" mais "texto" com até {R.MIOLO_TOTAL} palavras no slide.

FINAL (slide {slides})
- "titulo" fecha a ideia em uma frase.
- "pedido" faz UM pedido só, com até {R.PEDIDO} palavras: comentar uma palavra, salvar o post ou mandar pra alguém.
- O slide inteiro com até {R.FINAL_TOTAL} palavras.

REGRAS DE ESCRITA
- Pedido (comentar, salvar, compartilhar, seguir) só no último slide.
- Frase curta. Sem emoji, sem travessão, sem hashtag, sem link.
- Sem clichê: {", ".join(f'"{c}"' for c in R.CLICHES)}.
- Não invente número, estatística, pesquisa ou fato. Só use número que estiver no TEMA acima.
- Para destacar em cor, marque até {R.DESTAQUES_POR_SLIDE} trechos curtos por slide com asteriscos: *assim*.

Antes de responder, conte as palavras de cada campo e confira cada regra. Reescreva o que passar do limite.

Responda só com o JSON, sem nenhum texto antes ou depois, neste formato:
{MODELO_JSON}
"""


def correcao(erros):
    linhas = "\n".join(f"- {onde}: {msg}" for _, onde, msg in erros)
    return f"""Seu carrossel quebrou estas regras:
{linhas}

Reescreva o JSON inteiro corrigindo só isso. Mantenha o resto. Responda só com o JSON, sem texto antes ou depois."""


def aviso_viuva(v):
    campo = {"titulo": "do título", "pedido": "do pedido"}[v["id"]]
    qual = "a última linha" if v["ultima"] else "uma linha"
    return f"slide {v['slide']}: {qual} {campo} ficou com uma palavra só (\"{v['palavra']}\"): troque a palavra ou encurte"


def ajuste_linhas(avisos):
    linhas = "\n".join(f"- {aviso_viuva(v)}" for v in avisos)
    return f"""Seu carrossel foi gerado, mas estas linhas ficaram com uma palavra só:
{linhas}

Reescreva o JSON inteiro mudando só esses campos, com o mesmo sentido e sem passar dos limites de palavras. Mantenha o resto. Responda só com o JSON, sem texto antes ou depois."""
