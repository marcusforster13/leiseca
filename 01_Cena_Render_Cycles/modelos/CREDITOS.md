# Créditos dos modelos 3D

Os veículos da cena vêm de dois pacotes do Sketchfab, com licença **CC-BY 4.0** (uso comercial permitido, com crédito ao autor). Foram modificados: separados em um arquivo por veículo, repintados, com adesivos e interior acrescentados.

- This work is based on "Generic passenger car pack" (https://sketchfab.com/3d-models/generic-passenger-car-pack-20f9af9b8a404d5cb022ac6fe87f21f5) by Comrade1280 (https://sketchfab.com/comrade1280) licensed under CC-BY-4.0 (http://creativecommons.org/licenses/by/4.0/)
- This work is based on "Generic civil service vehicles pack" (https://sketchfab.com/3d-models/generic-civil-service-vehicles-pack-8ff2a13f30914932a70c7950cfa58465) by Comrade1280 (https://sketchfab.com/comrade1280) licensed under CC-BY-4.0 (http://creativecommons.org/licenses/by/4.0/)

## Como refazer

1. Baixe os dois pacotes em formato glTF e descompacte em `_fontes/passageiros/` e `_fontes/servicos/` (ficam fora do Git).
2. Rode `blender -b --factory-startup --python extrair_carros.py` para gerar `carros/<nome>.glb`.
3. `ver_carros.py` renderiza uma folha de conferência.

| Arquivo | Uso na cena |
|---|---|
| `hatch.glb` | carro abordado (prata, janela do motorista aberta, interior) |
| `seda.glb` | carro na área de regularização (branco) |
| `perua.glb` | viatura da PM (branca, faixa azul, giroflex) |
| `van.glb` | van de apoio (branca, LEI SECA) |
| `guincho.glb` | guincho plataforma |
| `suv.glb` | carro estacionado |
| `compacto`, `minivan`, `taxi`, `onibus` | reserva (trânsito na faixa livre, outros condutores) |
