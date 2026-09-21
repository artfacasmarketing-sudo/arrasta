---
name: carrossel
description: Gera um carrossel de Instagram com o arrasta escrevendo você mesmo o texto, sem chave de API. Use quando a pessoa pedir um carrossel, slides de Instagram ou um post em carrossel sobre um tema, dentro da pasta do arrasta.
---

# Carrossel com o arrasta

Você é a IA que escreve o texto. O arrasta monta o pedido, confere as regras e desenha os slides. O ciclo é sempre este,
na pasta do arrasta, com o `arrasta` do ambiente da pasta: `.venv/bin/arrasta` no Mac e no Linux,
`.venv\Scripts\arrasta` no Windows. Nos comandos abaixo, `arrasta` quer dizer esse.

## O pedido da pessoa

Tire do pedido: o tema (obrigatório) e, se ela disser, o @ (`--arroba "@perfil"`), para quem é (`--publico`),
quantos slides (`--slides`, de 5 a 10), o visual (`--visual escuro`, `claro` ou `imagem`), a foto do visual imagem
(`--imagem caminho/da/foto.jpg`) e a pasta de saída (`--saida`). Se faltar o tema, pergunte. O resto tem padrão.

**Antes de montar, pergunte o OBJETIVO** — é a pergunta que muda o carrossel inteiro:

> Para que serve este carrossel: **alcance** (chegar em gente nova), **salvamento** (ela guarda para usar),
> **comentário** (ela responde), **autoridade** (ela passa a te levar a sério) ou **clique** (ela vai para o link)?

O objetivo escolhe a fórmula de copy, a forma do gancho da capa e o pedido do último slide. Passe em
`--objetivo <valor>` (aceita com ou sem acento). Se a pessoa não quiser escolher ou já tiver dito o que quer
de um jeito que dá para traduzir ("quero que salvem" → salvamento), siga com o que ela disse e diga qual
objetivo você usou. Sem objetivo nenhum, o arrasta escreve como sempre escreveu.

Com **clique**, pergunte também **o que a pessoa encontra no link** antes de montar, e passe em
`--destino "<o que tem lá>"`. Sem destino o arrasta recusa: o carrossel falaria de um link que ninguém
descreveu, e você teria de inventar o que tem lá.

Para ver as cinco fórmulas com a espinha slide a slide: `arrasta objetivos`.

## O ciclo

1. Monte o pedido:
   `arrasta prompt "<tema>" --objetivo <objetivo> <opções>`
   Ele grava `prompt.txt` e `pedido.json` numa pasta e imprime o caminho do `resposta.txt`. Use essa pasta daqui em diante.
2. Leia o `prompt.txt` inteiro e siga cada regra dele. Grave em `resposta.txt` só o JSON que ele pede.
3. Rode `arrasta montar <pasta>/resposta.txt`.
4. Se o montar terminar com erro, ou deixar um `correcao.txt` na pasta, leia o `correcao.txt`, reescreva o
   `resposta.txt` mudando só o que ele pede e rode o passo 3 de novo. No máximo 3 correções.
   - Erro com `correcao.txt`: uma regra quebrou ou o texto não coube no slide. Os PNGs não saíram.
   - Sucesso com `correcao.txt`: os PNGs saíram, mas uma linha de título ou pedido ficou com uma palavra só.
   - Erro sem `correcao.txt` (foto que não abre, navegador que falta): não é coisa de texto. Pare e mostre a mensagem.
   - Se depois de 3 correções ainda houver erro, pare e mostre à pessoa o que o `correcao.txt` pede.
5. Mostre a prévia: leia `<pasta>/previa.png` (no Claude Code a imagem aparece na conversa) e diga onde estão os PNGs
   e quantas correções foram precisas.

## Nunca

- Chamar `arrasta render` para o texto que você escreveu. A regra do número com fonte só é conferida no caminho
  `arrasta prompt` → `arrasta montar`, que lê o tema do `pedido.json`.
- Mexer à mão em `pedido.json`, `prompt.txt` ou `slides.json`, nem mudar o tema para um número passar.
- Inventar número, estatística ou pesquisa. Só vale número que estiver no tema.
- Inventar cliente, depoimento, nome ou resultado. Prova social só com o que a pessoa trouxe no tema;
  sem isso, o slide vira argumento, nunca depoimento.
- Inventar o que tem do outro lado do link. Só o que a pessoa disse no `--destino`.
- Terminar slide anunciando o próximo ("mas falta", "agora vem", "tem coisa pior"). Cada slide fecha a
  própria ideia: quem puxa a pessoa para o próximo é a espinha da fórmula, não uma frase-isca.
- Usar `arrasta tema` com chave de API: aqui quem escreve é você.
