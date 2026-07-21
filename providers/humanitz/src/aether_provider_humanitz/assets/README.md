# Imagens do jogo (capa e logo)

Deixe aqui as imagens que o painel deve usar para este jogo, com estes nomes
exatos:

- `banner.<ext>` — a capa larga (topo da página do jogo e cartão do catálogo)
- `logo.<ext>` — o logotipo (sobreposto ao banner)

`<ext>` pode ser `png`, `jpg`, `jpeg`, `webp`, `svg` ou `gif`.

Quando existem, **estas imagens têm prioridade** sobre qualquer imagem da
internet (Steam/Wikimedia) — e o painel nunca vai à rede buscar a capa deste
jogo. Se você não deixar nada aqui, o Core cai para a imagem da loja, como antes.

O Core copia o arquivo para a pasta de mídia (`<AETHER_DATA_DIR>/catalog/media/`)
e o serve de lá; trocar o arquivo aqui troca a imagem no painel na hora.
