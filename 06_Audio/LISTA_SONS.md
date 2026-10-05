# Sons do treinamento — Operação Lei Seca

Coloque os arquivos em `06_Audio\brutos\` com o nome da tabela (`.mp3`, `.ogg` ou `.wav`). O pipeline copia para o site.

Fontes com licença livre: **freesound.org** (filtro *Creative Commons 0*) e **pixabay.com/sound-effects**. Não extrair áudio de vídeos.

| Arquivo | O que é | Situação |
|---|---|---|
| `amb_rua_noite` | Ambiente de rua à noite (loop) | já temos |
| `bip_etilometro` | Bipe do etilômetro ao terminar a leitura | falta (o site gera um bipe simples) |
| `radio_chiado`, `radio_bip` | Rádio da coordenação | falta |
| `transito_passando` | Carros passando na faixa livre (loop) | falta |
| `motor_carro_chegando` | Carro chegando e parando | falta |
| `sirene_longe`, `cachorro_longe` | Sons distantes, esporádicos | falta |

Vozes: rode `gerar_roteiro_vozes.py` para gerar o roteiro de gravação. Sem gravação, o site usa a voz sintética do navegador, com legenda.
