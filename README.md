# Operação Lei Seca — treinamento VR de fiscalização de trânsito

Cena 3D de uma blitz da Operação Lei Seca numa avenida do Rio de Janeiro, à noite, para treinar a abordagem, o teste do etilômetro e a decisão do agente em realidade virtual (Meta Quest, pelo navegador).

Mesma arquitetura do projeto "A Casa em Silêncio": o `.blend` é a única fonte e todo o resto é gerado.

## Pastas

| Pasta | Conteúdo |
|---|---|
| `01_Cena_Render_Cycles/` | **Fonte**: `blitz_lei_seca.blend`, o script que cria a cena do zero (`blitz_lei_seca.py`), texturas CC0 e `modelos/` (peças feitas à mão) |
| `02_Cena_VR_Otimizada/` | Versão para Unity/Unreal (`.blend`, `.glb`, `.fbx`) e malha de colisão |
| `04_ThreeJS/` | Pipeline three.js (texturas PBR, lightmaps) e o site WebXR em `web/` (publicado no Vercel) |
| `05_Treinamento/` | `cenario_ls_01.json` (toda a mecânica, editável) e `ROTEIRO_TREINAMENTO.md` (para instrutores) |
| `06_Audio/` | Sons e vozes (`brutos/`), lista de sons e roteiro de vozes |
| `07_Personagens/` | Conversor dos personagens (Microsoft Rocketbox, licença MIT) |

## Atualizar tudo depois de mexer na cena

```powershell
.\atualizar_tudo.ps1          # padrão (~4 min)
.\atualizar_tudo.ps1 rapido   # teste
.\atualizar_tudo.ps1 alta     # lightmaps em qualidade máxima
.\atualizar_tudo.ps1 recriar  # refaz o .blend pelo script (apaga edições feitas à mão no .blend)
```

Requer Blender 5.2. Arquivos `.blend`, `.fbx` e `.exr` usam **Git LFS**.

## Modos do treinamento

- **Exploração**: cena livre; os marcadores explicam cada parte da blitz.
- **História**: três atendimentos guiados (condutor regular, resultado de álcool, recusa).
- **Treino**: um atendimento sorteado, com objetivos e dicas na tela.
- **Avaliação**: um atendimento sorteado, sem dicas. Relatório com nota (aprovação: 70 e nenhuma falha grave) e base legal.

Variação forçada pela URL: `?v=condutor:recusa,sinais:visiveis,passageiro:nenhum,documentos:regular`.

## Base legal

CTB arts. 165, 165-A, 276, 277 e 306; Resolução Contran nº 1.031/2026 (revogou a 432/2013). O conteúdo é um **rascunho para validação** com a coordenação da operação: ver `05_Treinamento/ROTEIRO_TREINAMENTO.md`.

Sem logotipos e sem brasões oficiais: há espaços marcados `Brasao_(inserir_imagem_oficial)` para a imagem que o órgão estiver autorizado a usar. Texturas: Poly Haven (CC0). Personagens: Microsoft Rocketbox (MIT).

**Se beber, não dirija.**
