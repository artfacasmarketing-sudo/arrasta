"""As fórmulas de copy do carrossel: o objetivo escolhe a espinha, o gancho da capa e o pedido do final.

De onde vem cada uma:
  Viral, False Statement e POPP são os três moldes de copy do João, os mesmos que ele usa em todo negócio.
  A False Statement foi a copy vencedora no carrossel do Laços de 06/09/2026.
  Prova em primeira pessoa e Ponte são adaptações declaradas, feitas porque faltava fórmula para dois dos
  cinco objetivos: a primeira é o POPP com a prova no lugar da promessa, a segunda é o Viral com o CTA
  virando a ponte para o destino.

O que o corpus mediu e entra aqui como apoio, não como fórmula: pedido único no último slide, "comente"
em 79% dos pedidos, e capa com número e capa contrária como as duas formas de gancho com mais sinal.

Regra dura da prova social: a IA não inventa cliente, depoimento, nome nem resultado. Prova social só com
o que a pessoa trouxer no TEMA. Sem prova no tema, o slide vira argumento, não depoimento.
Pela mesma regra, a IA não inventa o que existe do outro lado do link: o clique só roda com --destino, e o
carrossel fala do destino só com o que está escrito nele.
"""

OBJETIVOS = ("alcance", "salvamento", "comentario", "autoridade", "clique")
NOME = {"alcance": "alcance", "salvamento": "salvamento", "comentario": "comentário",
        "autoridade": "autoridade", "clique": "clique"}

# cada fórmula: nome, de onde veio, a espinha (capa, miolo, final), quando não usar.
# No miolo, o passo marcado com "repete" é o que estica quando o carrossel tem mais slides, e os marcados
# com "opcional" são os primeiros a sair quando tem menos.
FORMULAS = {
    "alcance": {
        "nome": "Viral",
        "origem": "molde do João: gancho negativo, alternativa, promessa, soluções, CTA",
        "capa": "o gancho negativo: diga o que NÃO funciona, contra o que esse público faz sem pensar",
        "miolo": [
            ("a alternativa", "o que fazer em vez daquilo, dito em uma frase"),
            ("a promessa", "o que muda no dia a dia de quem troca", "opcional"),
            ("uma solução", "uma coisa concreta de fazer, com o objeto ou o momento do dia dela", "repete"),
        ],
        "final": "o título fecha a ideia numa frase que a pessoa repetiria. O \"pra quem\" fica só no pedido",
        "nao_usar": "quando o tema não tem um erro comum de verdade para contrariar: gancho negativo sem "
                    "alvo vira reclamação genérica",
    },
    "comentario": {
        "nome": "False Statement",
        "origem": "molde do João, a copy vencedora do carrossel do Laços de 06/09/2026: afirmação falsa, "
                  "virada, prova, desmentido, mais prova, CTA",
        "capa": "a afirmação falsa, dita como se fosse verdade aceita, no lugar-comum que esse público repete",
        "miolo": [
            ("a virada", "por que aquilo não se sustenta, em uma frase"),
            ("a prova", "o caso, o número ou o que a pessoa trouxe no TEMA. Sem prova no tema, escreva o "
                        "argumento, nunca um depoimento inventado"),
            ("o desmentido", "o que é verdade no lugar da afirmação da capa"),
            ("mais prova", "outro caso ou outro argumento, do mesmo jeito", "repete"),
        ],
        "final": "fecha com a frase que a pessoa vai querer repetir ou discordar",
        "nao_usar": "quando o assunto é delicado ou o erro custa caro para quem lê: afirmação falsa em "
                    "tema de saúde, dinheiro alheio ou segurança confunde em vez de provocar",
    },
    "salvamento": {
        "nome": "POPP",
        "origem": "molde do João: problema, oportunidade, passos práticos, promessa, CTA",
        # sem "quantos passos" e sem passo numerado: o número de ordem também é número, e o portão recusa
        # número que não está no tema. Conferência de 21/09/2026: 5 de 5 salvamentos pediram 1 correção,
        # todas pelo "1, 2, 3" dos passos (e pelo "3" da capa, no d02).
        "capa": "o problema, dito no momento em que ele acontece. Número só se estiver escrito no TEMA",
        "miolo": [
            ("a oportunidade", "o que dá para fazer a respeito, em uma frase"),
            ("um passo", "um passo prático que a pessoa consegue executar sozinha, dito pela ação e SEM "
                         "número de ordem na frente (1, 2, 3 também é número, e só vale número do TEMA)", "repete"),
            ("a promessa", "o que ela tem nas mãos depois de fazer os passos"),
        ],
        "final": "fecha dizendo quando ela vai precisar disso de novo",
        "nao_usar": "quando o tema não vira passo: assunto de opinião ou de posicionamento não se salva "
                    "para usar depois",
    },
    "autoridade": {
        "nome": "Prova em primeira pessoa",
        "origem": "adaptação do POPP: a prova entra no lugar da promessa, e quem fala é quem fez",
        "capa": "o que todo mundo vê por fora, ou o número do caso quando ele está no TEMA",
        # primeira pessoa só com experiência escrita no tema: sem ela, a fórmula fala do caso na terceira
        # pessoa. O d19 inventou "nenhuma campanha começa aqui sem essas respostas" num tema sem caso.
        "miolo": [
            ("o que se via", "a situação como ela era antes, sem enfeite. Em primeira pessoa (eu, faço, "
                             "fazemos, aqui) SÓ se o TEMA trouxer a experiência de quem fala"),
            ("o que foi feito diferente", "a decisão concreta, não o conselho genérico"),
            ("o que saiu disso", "o resultado, SÓ com o que está no TEMA. Sem dado no tema, escreva o que "
                                 "mudou na prática, sem número"),
            ("o que isso ensina", "o que quem lê tira disso para o caso dela", "repete"),
        ],
        "final": "fecha com o princípio que fica, dito como regra, não como relato. Primeira pessoa só se "
                 "o TEMA trouxer a experiência",
        "nao_usar": "quando não há caso, número nem experiência própria no TEMA: sem isso a fórmula vira "
                    "depoimento inventado, que é exatamente o que não pode",
    },
    "clique": {
        "nome": "Ponte",
        "origem": "adaptação do Viral: o CTA deixa de ser pedido e vira a ponte para o destino",
        "capa": "a promessa concreta do que existe do outro lado, deixando a lacuna aberta",
        "miolo": [
            ("por que o jeito comum não chega lá", "o caminho que a pessoa tentaria sozinha e onde ele para"),
            ("o que existe do outro lado", "o que ela vai encontrar, SÓ com o que está no DESTINO, dito pelo "
                                           "que resolve"),
            # a amostra é conteúdo do CARROSSEL, sobre o tema: tirar a amostra do destino virou logística
            # ("use o e-mail que você lê todo dia") no lugar de dica ("nome maior que o logo") — 21/09/2026
            ("uma dica", "uma dica concreta sobre o TEMA, que já serve sem clicar. É conteúdo deste carrossel, "
                         "não do destino: nunca diga que a dica está no link", "repete"),
        ],
        "final": "o título fecha a ideia numa frase que a pessoa repetiria. O \"pra quem\" fica só no pedido",
        "nao_usar": "quando não existe destino de verdade: sem página, material ou link, a ponte não leva a "
                    "lugar nenhum e o carrossel promete o que não entrega",
    },
}

# o pedido do último slide: verbo e texto, um por objetivo. Pedido único, sempre no último slide.
PEDIDOS = {
    "alcance": ("mandar pra alguém", "Manda pra quem precisa ler isso"),
    "salvamento": ("salvar", "Salva pra usar na hora de fazer"),
    # a palavra-chave vai em MAIÚSCULAS e marcada com *asteriscos*: no claro e no imagem o pedido já sai todo
    # em caixa-alta, e só a cor separa a palavra; no escuro a marca vira sublinhado dentro da pílula
    "comentario": ("comentar uma palavra do tema, escrita em MAIÚSCULAS e marcada com asteriscos (ela conta "
                   "como um dos 2 destaques do slide)", "Discorda? Comenta *CADERNO* aqui embaixo"),
    "autoridade": ("seguir", "Me segue pra ver o resto do método"),
    "clique": ("clicar", "O link está na bio"),
}


def espinha(objetivo, slides):
    """a espinha inteira para N slides: [(nome do passo, o que o slide faz)], capa e final incluídos."""
    f = FORMULAS[objetivo]
    fixos = [p for p in f["miolo"] if len(p) == 2]
    opcionais = [p for p in f["miolo"] if len(p) == 3 and p[2] == "opcional"]
    repete = next(p for p in f["miolo"] if len(p) == 3 and p[2] == "repete")
    miolo = slides - 2
    # a ordem original, sem o que repete; o que sobrar de slide vira repetição do passo que estica
    base = [p[:2] for p in f["miolo"] if p is not repete]
    while len(base) > miolo and opcionais:
        fora = opcionais.pop()
        base = [p for p in base if p[0] != fora[0]]
    base = base[:miolo]
    faltam = miolo - len(base)
    onde = [p[0] for p in f["miolo"]].index(repete[0])
    corpo = base[:onde] + [repete[:2]] * max(faltam, 0) + base[onde:]
    return [("capa", f["capa"])] + corpo[:miolo] + [("final", f["final"])]


# o clique precisa saber o que tem do outro lado: sem isso a IA inventa ("os kits prontos estão no link da
# bio"), que é a mesma mentira do depoimento inventado. Conferência de 21/09/2026: 4 de 4 cliques sem destino.
PEDE_DESTINO = ("clique",)
EXEMPLO_DESTINO = "checklist do que entra no kit de boas-vindas, com os itens e o prazo de cada um"


def texto(objetivo, slides, destino=None):
    """o pedaço do prompt que a fórmula manda. Sem objetivo, o prompt não muda."""
    f = FORMULAS[objetivo]
    verbo, exemplo = PEDIDOS[objetivo]
    linhas = [f"OBJETIVO DESTE CARROSSEL: {NOME[objetivo]}",
              f'Fórmula: {f["nome"]} ({f["origem"]}).',
              ""]
    if destino:
        linhas += [f"DESTINO (o que a pessoa encontra no link): {destino}",
                   "Quando falar do que existe do outro lado do link, use SÓ o que está escrito na linha acima: "
                   "não invente item, formato, preço nem prazo DO DESTINO.",
                   "As dicas do miolo são outra coisa: conteúdo do carrossel, sobre o tema, que servem sem clicar. "
                   "Nunca diga que uma dica está no link.",
                   ""]
    linhas += [
              "ESPINHA, slide a slide. Cada slide cumpre o papel dele e fecha a própria ideia:"]
    for i, (papel, o_que) in enumerate(espinha(objetivo, slides), 1):
        nome = {"capa": "capa", "final": "final"}.get(papel, papel)
        linhas.append(f"  slide {i} ({nome}): {o_que}")
    linhas += [
        "",
        f"GANCHO DA CAPA: {f['capa']}.",
        f"PEDIDO DO ÚLTIMO SLIDE: um só, de {verbo}. Escreva com as suas palavras, no espírito de "
        f'"{exemplo}".',
        # o "quando não usar" é para quem ESCOLHE o objetivo, e mora no `arrasta objetivos`. Aqui ele entra
        # só como cuidado: mandar a IA "dizer que não serve" faz ela responder em prosa e quebrar o JSON —
        # aconteceu em 5 de 20 temas na conferência de 21/09/2026, 4 deles em autoridade.
        f"CUIDADO COM ESTA FÓRMULA: {f['nao_usar']}. Se for o caso deste tema, escreva com o que o tema dá "
        f"e não invente o que falta. A resposta continua sendo só o JSON.",
    ]
    return "\n".join(linhas)


def descrever():
    """as cinco fórmulas com a espinha de cada uma, para ler na tela."""
    fora = [__doc__.strip(), ""]
    for obj in OBJETIVOS:
        f = FORMULAS[obj]
        verbo, exemplo = PEDIDOS[obj]
        fora += [f"## {NOME[obj]} — {f['nome']}", f"origem: {f['origem']}", ""]
        for i, (papel, o_que) in enumerate(espinha(obj, 7), 1):
            fora.append(f"  {i}. [{papel}] {o_que}")
        fora += ["", f"  pedido: {verbo} — \"{exemplo}\"", f"  não usar: {f['nao_usar']}", ""]
    return "\n".join(fora)
