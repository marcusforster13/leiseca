# Roteiro do treinamento — Operação Lei Seca (cenário ls_01)

**Situação:** rascunho para validação com a coordenação da operação. Tudo o que está aqui fica em `cenario_ls_01.json` e pode ser editado sem mexer no código.

## 1. Objetivo

Treinar o agente em um atendimento completo: receber o veículo, comunicar-se com o condutor, conferir documentos, verificar o consumo de álcool, enquadrar corretamente e decidir o destino do veículo.

## 2. Papel do jogador

Agente da operação, no ponto de abordagem. Os policiais militares dão segurança e fazem a condução à delegacia quando há crime.

## 3. Etapas, pontos e base legal

| Fase | O que se espera | Pontos | Base |
|---|---|---|---|
| Recepção e segurança | Sinalizar a parada; abordar pelo lado do motorista, dentro da área protegida | 7 | procedimento (validar) |
| Comunicação inicial | Cumprimentar, identificar-se e explicar; pedir para desligar o motor; pedir habilitação e documento do veículo | 10 | CTB arts. 133 e 159 |
| Documentos | Conferir a validade da CNH e o licenciamento, enquadrando certo | 7 | CTB art. 162, V e art. 230, V |
| Verificação de álcool | Observar sinais; convidar ao teste sem coagir; bocal novo aberto na frente do condutor; orientar o sopro; mostrar o resultado; descartar o bocal. Na recusa: informar o art. 165-A | 12 a 17 | CTB arts. 165-A e 277; Res. 1.031/2026, arts. 5º, 7º e 8º |
| Enquadramento e registro | Enquadrar certo; lavrar o auto completo; não recolher a CNH; acionar os policiais se houver crime | 10 a 20 | CTB arts. 165, 165-A e 306; Res. 1.031/2026, arts. 8º a 12 |
| Veículo e encerramento | Liberar, entregar a condutor apto (fiscalizado antes) ou remover; explicar a defesa; cordialidade | 8 a 15 | CTB art. 270; Res. 1.031/2026, art. 11 |

**Aprovação:** nota 70 ou mais e nenhuma falha grave.

## 4. Falhas graves

- Coagir ou ameaçar o condutor para fazer o teste.
- Reutilizar o bocal de outro condutor.
- Liberar condutor alcoolizado, ou que recusou o teste, para seguir dirigindo.
- Dar voz de prisão apenas pela recusa.
- Entregar o veículo a outra pessoa sem fiscalizá-la, ou a quem também bebeu.

## 5. Enquadramento usado no treinamento

| Situação | Enquadramento |
|---|---|
| Medição abaixo de 0,05 mg/L e sem sinais | sem infração por álcool |
| Medição de 0,05 a 0,33 mg/L | infração do art. 165 |
| Medição de 0,34 mg/L ou mais | art. 165 + crime do art. 306: Polícia Judiciária |
| Recusa, sem sinais | infração do art. 165-A |
| Recusa, com dois sinais ou mais | art. 165 pelos sinais, com a recusa registrada |

## 6. Variações sorteadas

- **Condutor:** sóbrio · álcool (infração) · álcool (crime) · recusa.
- **Sinais:** nenhum · visíveis (olhos vermelhos, odor de álcool, fala arrastada).
- **Documentos:** regular · CNH vencida há mais de 30 dias · licenciamento em atraso.
- **Passageiro:** nenhum · habilitada e sóbria · habilitada que também bebeu.
- **Comportamento:** colaborativo · nervoso · hostil.

Para forçar pela URL: `?v=condutor:alcool_crime,passageiro:nenhum`.

## 7. Modos

- **História:** três atendimentos fixos (regular; álcool com passageira apta; recusa sem passageiro).
- **Treino:** um atendimento sorteado, com objetivos e dicas.
- **Avaliação:** um atendimento sorteado, sem dicas.

## 8. Pontos para validar com a coordenação

1. Ordem real das etapas e quem faz cada uma (agente, policial, coordenador).
2. Pedido para desligar o motor e acender a luz interna: é padrão?
3. Posição do agente em relação ao veículo e ao trânsito.
4. Triagem com etilômetro passivo: entra no treinamento? Hoje não entra; pela Res. 1.031/2026, art. 4º, é opcional e só indicativa.
5. Reteste por álcool residual na boca: tempo de espera e como registrar (art. 5º, § 2º).
6. Valor considerado: conferir os exemplos com a tabela do Anexo I.
7. Recolhimento da CNH (art. 12) e formulários ou aplicativo usados para o auto.
8. Tempo de espera por condutor habilitado antes de acionar o guincho.
9. Pesos da pontuação e nota de aprovação.
