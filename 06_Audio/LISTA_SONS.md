# Sons do treinamento — Operação Lei Seca

Os arquivos ficam em `06_Audio\brutos\` (`.mp3`, `.ogg` ou `.wav`). O pipeline copia para o site.

Fonte: **freesound.org**, só sons com licença **Creative Commons 0** (uso livre, sem crédito obrigatório). Foi baixada a versão MP3 de cada som. Não extrair áudio de vídeos.

## Já temos

| Arquivo | O que é | Origem (Freesound, CC0) |
|---|---|---|
| `amb_transito_noite` | Trânsito noturno a média distância: carros, motos e ônibus passando (loop) | "Medium Night City Traffic 2", brunoboselli, som 871592 |
| `motor_carro_chegando` | Carro se aproximando e parando (o site toca só o trecho de 16,5 s a 26 s) | "Pulls up and Parks Car", benwer, som 260828 |
| `bip_etilometro` | Bipe curto do aparelho (o site toca duas vezes) | "Medium Electronic Beep", wubitog, som 188383 |
| `radio_bip` | Bipe de rádio antes das falas da coordenação | "Walkie Talkie - Roger Beep", bruce965, som 321906 |
| `radio_chiado` | Chiado de rádio (baixado, ainda não usado) | "Walkie_Talkie_Static", crcavol, som 154654 |
| `porta_carro` | Porta do carro abrindo e depois fechando (o site toca cada trecho na hora certa) | "Car Door (Open and Close)", Yin_Yang_Jake007, som 416963 |

## Falta

| Arquivo | O que é |
|---|---|
| `sirene_longe`, `cachorro_longe` | Sons distantes, esporádicos (o site já sabe tocar se os arquivos existirem) |

Vozes: rode `gerar_roteiro_vozes.py` para gerar o roteiro de gravação. Sem gravação, o site usa a voz sintética do navegador, com legenda.
