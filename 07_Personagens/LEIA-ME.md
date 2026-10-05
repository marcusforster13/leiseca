# 07 · Personagens (Microsoft Rocketbox, licença MIT)

Três condutores, sorteados a cada atendimento (a `condutor_b` também faz a passageira):

| Papel | Modelo | Animações |
|---|---|---|
| `condutor_a` | Male_Adult_01 | parada, falando, nervoso, irritado, andando, sentado, sentado_falando, sentado_nervoso, soprando |
| `condutor_b` | Female_Adult_08 | parada, falando, nervoso, sentado, sentado_falando, sentado_nervoso, soprando |
| `condutor_c` | Male_Adult_14 | as mesmas do condutor_a |

As poses **sentado** (ao volante) e **soprando** não existem na biblioteca: o conversor cria por cima de uma animação base (pernas dobradas, mãos no volante).

Os arquivos originais (FBX e texturas, ~290 MB) ficam fora do Git. O conversor procura em `07_Personagens\rocketbox\` e, se não achar, usa a pasta do projeto anterior (`..\DV\07_Personagens\rocketbox`). Fonte: <https://github.com/microsoft/Microsoft-Rocketbox>.

**Falta para as próximas etapas:** agentes com colete e policiais militares (a biblioteca tem avatares de profissões; precisa baixar).

Converter de novo, forçando todos:

    blender -b --factory-startup --python converter_personagens.py -- --forcar
