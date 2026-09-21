"""O prompt que vai para a IA. As regras aqui são as mesmas que o regras.py confere depois."""
from . import formulas as F
from . import largura as L
from . import regras as R

CAMPOS = (("capa", "titulo", "título da capa"), ("capa", "texto", "texto de apoio da capa"),
          ("miolo", "titulo", "título do miolo"), ("miolo", "texto", "texto do miolo"),
          ("final", "titulo", "título do último slide"), ("final", "pedido", "pedido"))


def cabe_na_tela(visual):
    """o que foi MEDIDO na fonte sobre a largura do slide, em letras e em caracteres por linha.

    O limite de letras só aparece onde ele prende de verdade (onde alguma palavra do português não cabe).
    Aqui é orientação; quem recusa é o regras.py, que mede palavra por palavra."""
    limites = [f"- Nenhuma palavra do {nome} pode passar de {L.LIMITE_LETRAS[(visual, papel, campo)][0]} letras: "
               f"mais que isso não cabe na largura do slide e o carrossel é recusado."
               for papel, campo, nome in CAMPOS if (visual, papel, campo) in L.LIMITE_LETRAS]
    porlinha = ", ".join(f"{nome} {L.POR_LINHA[(visual, papel, campo)]}"
                         for papel, campo, nome in CAMPOS if (visual, papel, campo) in L.POR_LINHA)
    return "\n".join(["", "CABE NA TELA (medido na fonte do arrasta, não é estimativa)", *limites,
                       f"- Cabem por linha, mais ou menos: {porlinha} caracteres.",
                       "- Palavra que não cabe não encolhe a letra: o slide é recusado e você reescreve."])

MODELO_JSON = """{
  "slides": [
    {"tipo": "capa", "titulo": "...", "texto": "..."},
    {"tipo": "miolo", "titulo": "...", "texto": "..."},
    {"tipo": "final", "titulo": "...", "pedido": "..."}
  ]
}"""


def sem_objetivo(slides):
    """o que cada slide faz quando ninguém disse o objetivo: o comportamento de sempre, nada muda."""
    return f"""CAPA (slide 1)
- Abre uma pergunta na cabeça de quem lê e não entrega a resposta. Quem lê a capa tem de querer arrastar.
- Cita algo concreto do dia a dia desse público: um objeto, um lugar, um momento.

MIOLO (slides 2 a {slides - 1})
- Uma ideia por slide, na ordem que responde a pergunta da capa aos poucos.

FINAL (slide {slides})
- "titulo" fecha a ideia em uma frase.
- "pedido" faz UM pedido só: comentar uma palavra, salvar o post ou mandar pra alguém."""


def montar(tema, publico=None, slides=7, visual=None, objetivo=None):
    miolo = slides - 2
    visual = visual or "escuro"
    publico = publico or "quem se interessa por esse tema"
    estrutura = F.texto(objetivo, slides) if objetivo else sem_objetivo(slides)
    return f"""Você escreve carrosséis de Instagram em português do Brasil, do jeito que se fala.

TEMA: {tema}
PÚBLICO: {publico}

Escreva um carrossel de {slides} slides sobre o tema: 1 capa, {miolo} de miolo e 1 final.

{estrutura}

QUANTAS PALAVRAS CABEM
- Capa: "titulo" com até {R.CAPA_TITULO} palavras. "texto" opcional, com até {R.CAPA_TEXTO} palavras.
- Miolo: "titulo" com até {R.MIOLO_TITULO} palavras. "titulo" mais "texto" com até {R.MIOLO_TOTAL} no slide.
- Final: "pedido" com até {R.PEDIDO} palavras, e o slide inteiro com até {R.FINAL_TOTAL}.

REGRAS DE ESCRITA
- Pedido (comentar, salvar, compartilhar, seguir) só no último slide.
- Cada slide FECHA a própria ideia. A vontade de arrastar vem da ordem dos slides, não de uma frase no fim.
  PROIBIDO terminar slide anunciando o próximo: "mas falta", "agora vem", "tem coisa pior", "e tem mais",
  "só que", "o problema é outro", "no próximo slide". Se o slide só faz sentido com o seguinte, ele está
  no lugar errado.
- Não invente cliente, depoimento, nome nem resultado. Prova social só com o que estiver no TEMA acima;
  sem isso, escreva o argumento, nunca um depoimento.
- Frase curta. Sem emoji, sem travessão, sem hashtag, sem link.
- Sem clichê: {", ".join(f'"{c}"' for c in R.CLICHES)}.
- Não invente número, estatística, pesquisa ou fato. Só use número que estiver no TEMA acima.
- Para destacar em cor, marque até {R.DESTAQUES_POR_SLIDE} trechos curtos por slide com asteriscos: *assim*.
{cabe_na_tela(visual)}

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
