# Briefing para um novo treinamento em VR no mesmo estilo

Este documento descreve como o treinamento **Operação Lei Seca** foi construído, para servir de base a um novo cenário — por exemplo, **operação em cassino clandestino**.

**Como usar:** abra um novo chat com acesso a esta pasta (`C:\Users\marcus.leite\Downloads\leiseca`) e cole o texto da seção 1. O restante é referência técnica para o assistente ler.

O guia do projeto anterior (`C:\Users\marcus.leite\Downloads\DV\GUIA_PARA_NOVO_PROJETO.md`) continua valendo para a parte geral (pipeline, personagens, site, armadilhas do ambiente). Este aqui acrescenta o que mudou e o que foi aprendido na Lei Seca.

---

## 1. Texto para colar no novo chat

> Quero criar um treinamento em realidade virtual de uma **operação policial em um cassino clandestino** (jogo de azar ilegal) no Rio de Janeiro, **no mesmo estilo e com a mesma arquitetura** do projeto que está em `C:\Users\marcus.leite\Downloads\leiseca`.
>
> Antes de começar, leia `GUIA_PARA_NOVO_PROJETO.md` nessa pasta (e o guia de `C:\Users\marcus.leite\Downloads\DV`, que ele cita) e use os scripts de lá como modelo: copie e adapte, não reescreva do zero.
>
> O que eu quero:
> - Cenário 3D gerado no **Blender** por script (arquivo `.blend` como fonte), em português e com a realidade brasileira.
> - Versão **three.js/WebXR** publicada no **Vercel** via GitHub, rodando no Meta Quest.
> - Texturas realistas de uso livre (CC0), iluminação pré-calculada (bake), personagens **Rocketbox** animados com voz, boca e olhar (os arquivos já estão em `leiseca\07_Personagens\rocketbox`).
> - Mecânica de treinamento baseada na **lei e no procedimento brasileiros**, com variações sorteadas, modo treino, modo avaliação, modo história e relatório com nota e base legal.
> - Crie o projeto na pasta `C:\Users\marcus.leite\Downloads\cassino` e suba para o repositório `https://github.com/marcusforster13/cassino` (minha conta é `marcusforster13`).
>
> Antes de modelar, me faça as perguntas da seção 6 do guia e pesquise a base legal.
>
> Trabalhe como no projeto anterior: fale comigo em português simples, mostre imagens do que fez, teste antes de subir e suba para o GitHub/Vercel a cada etapa.

### O que você (usuário) precisa fazer antes

1. Criar o repositório vazio `cassino` em github.com/marcusforster13 (sem README).
2. Depois do primeiro envio do assistente: em vercel.com, **Add New → Project → Import** o repositório `cassino`. Não mude nenhuma configuração de build.
3. No projeto do Vercel: **Settings → Deployment Protection → Vercel Authentication → Disabled**, senão o site pede login e não abre no Quest.

---

## 2. O que copiar da Lei Seca

| De | Serve para |
|---|---|
| `01_Cena_Render_Cycles/blitz_lei_seca.py` | Modelo de script que **gera a cena inteira do zero** (materiais, prédios, postes, objetos `I_*` interativos, câmeras, propriedades `ls_*` da cena lidas pelo site). No projeto novo: um `cassino.py` equivalente |
| `01_Cena_Render_Cycles/aplicar_texturas_cc0.py`, `arvores.py` | Texturas Poly Haven e árvores |
| `01_Cena_Render_Cycles/modelos/` (`extrair_carros.py`, `carros/*.glb`, `CREDITOS.md`) | Carros prontos (viatura, van, SUV, sedã) com rodas separadas |
| `02_Cena_VR_Otimizada/otimizar_para_vr.py` | Otimização e colisão |
| `04_ThreeJS/pipeline_threejs.py` | Lightmaps, exportação `cena.glb` + `cena.json`, cópia de áudio e cenário |
| `04_ThreeJS/web/index.html`, `treinamento.js`, `audio.js` | Site, motor do treinamento e som |
| `05_Treinamento/cenario_ls_01.json` | Formato do cenário (fases, ações, erros, variações, diálogos, vozes) |
| `06_Audio/gerar_roteiro_vozes.py` | Folha de falas para imprimir e gravar |
| `07_Personagens/converter_personagens.py` | Conversão Rocketbox → `.glb` com animações e poses por IK |
| `atualizar_tudo.ps1`, `vercel.json`, `.gitignore`, `.gitattributes` | Raiz do projeto |

`04_ThreeJS/web/transito.js` (carros passando) só interessa se houver rua com tráfego.

## 3. O que a Lei Seca tem a mais que o projeto DV

- **Cena 100% por script** (`blitz_lei_seca.py`): `atualizar_tudo.ps1 recriar` refaz tudo em ~5 min. Não há modelagem manual a preservar.
- **Modelos prontos importados** (`carro_modelo()`): materiais com prefixo `Modelo_` mantêm a UV original no otimizador; texturas dos modelos viram JPG ≤ 1024 px no pipeline.
- **Objetos dinâmicos** (carro, porta, itens na mão) não têm lightmap: são iluminados por `iluminar(m)` com um lightmap branco 1×1 e `luz_dinamica` do `cena.json`.
- **Personagem sentado em veículo**: poses `sentado*` por IK no conversor, `seguirCarro()`, plano de corte no assoalho, olhar com limites próprios (as clavículas são filhas do pescoço: é preciso restaurar a rotação delas ao girar o pescoço).
- **Entrega de objeto na mão** (documento): pose em duas etapas, objeto preso entre dois ossos dos dedos, vista de frente ao clicar.
- **Equipamento levado ao rosto do personagem** (etilômetro), visor desenhado em canvas.
- **Vozes**:
  - a gravação é achada pelo **texto exato** da fala; a versão feminina usa o mesmo nome de arquivo com `_f`;
  - `audio.js` corta sozinho o silêncio das pontas das falas (`silencio()`), nivela o volume e aceita `trecho = { ini, dur, ritmo, vol }` em `tocar()`;
  - personagem alterado usa a mesma gravação com `ritmo: .84`;
  - rádio: `radio(texto)` toca bip, fala e bip curto.
- **API de teste** em `window.__trein._t` (ver o `return` no fim de `treinamento.js`) e `window.__casa.ver(x, z, yaw, pitch)`.

## 4. Lições (não repetir os erros)

- **Unidades do Rocketbox:** o esqueleto está em centímetros. Deslocamentos em poses de IK devem ser **frações do comprimento do braço**, não metros.
- **Personagem × cenário:** depois de posicionar alguém sentado ou encostado, medir por script (topo da malha × teto, mão × peitoril). Olhar a imagem não basta.
- **Raycast em teste com o painel escondido:** chamar `updateMatrixWorld(true)` no objeto antes, senão o raio não acerta nada.
- **Nome da camada de UV** dos objetos com textura própria tem de ser `UVMap`, senão a textura some no site.
- **Lightmap:** limitar o valor máximo (3.0) para as lâmpadas não escurecerem o resto.
- **`const` usada dentro de `.then()`** precisa estar declarada antes do `await` que dispara o carregamento; o `.catch` genérico esconde o erro.
- **Resolução dos personagens:** o usuário não quer baixar. Para ganhar desempenho, **tirar** figurantes e veículos desnecessários.
- **Interior de veículo/cômodo visto por fora:** conferir de vários ângulos se nada atravessa a carroceria.
- **Vercel:** conferir a publicação pelo navegador ou pela API de *deployments* do GitHub (o `curl` repetido é bloqueado); se um push não publicar, um commit vazio resolve.
- **Edição de código pelo shell:** *heredocs* longos falham; gravar um script de patch em arquivo e executar. Arquivos podem estar com CRLF.
- **Servidor de teste:** entrada em `.claude/launch.json` (porta própria, `Cache-Control: no-store`); ele cai entre sessões.

## 5. Regras que seguimos

- Logotipo oficial só quando o usuário fornece a imagem e diz que pode usar. Sem marcas comerciais.
- Texturas, modelos e sons só de fontes livres (Poly Haven CC0, Rocketbox MIT, sons CC0), com `CREDITOS.md`.
- Toda regra do treinamento tem **base legal** citada; pontos incertos ficam marcados para **validação com instrutores**.
- Conteúdo sensível (armas, uso da força, prisão) com aviso antes de começar.
- Subir para o GitHub/Vercel a cada etapa, depois de testar, e dizer com clareza o que **não** foi verificado (som de ouvido, Quest).

## 6. O que definir para o cassino clandestino

O novo chat deve levantar e confirmar com o usuário, antes de modelar:

- **Órgão e papel do jogador:** policial civil cumprindo mandado? policial militar atendendo denúncia? fiscalização conjunta? Isso muda o que ele pode fazer (entrar, revistar, apreender, prender).
- **Momento da operação:** só a entrada e a contenção, ou também a identificação das pessoas, a arrecadação do material e a condução à delegacia.
- **Local:** fachada (galpão, loja, sobrado, fundos de bar), salão de jogos, caixa/escritório, depósito, saída dos fundos. Dia ou noite.
- **Personagens (Rocketbox):** responsável pelo local, funcionários (caixa, crupiê, segurança), apostadores, equipe policial, eventualmente idoso ou adolescente no local.
- **Objetos interativos:** máquinas caça-níqueis, mesas e fichas, dinheiro, cadernos de anotação, celulares e computadores, câmeras do local, documentos, mandado, lacres e sacos de apreensão, rádio, lanterna.
- **Variações:** com ou sem mandado; porta franqueada ou trancada; apostadores colaborativos ou tentando sair; responsável presente ou ausente; funcionário que se diz apenas empregado; dinheiro escondido; pessoa armada; menor de idade no local; tentativa de suborno.
- **Base legal a pesquisar e citar** (confirmar a redação vigente): Lei das Contravenções Penais (Decreto-Lei 3.688/1941, art. 50 e seguintes, sobre jogo de azar), regras de entrada em domicílio e busca e apreensão (Constituição, art. 5º, XI; Código de Processo Penal), cadeia de custódia (CPP, arts. 158-A a 158-F), termo circunstanciado (Lei 9.099/1995), uso de algemas (Súmula Vinculante 11), crimes que podem aparecer junto (corrupção ativa, lavagem de dinheiro, organização criminosa, corrupção de menores) e a legislação atual sobre apostas autorizadas, para separar o que é legal do que não é.
- **Pontos para validar com a instituição:** fluxo real da operação, quem faz cada etapa, formulários usados, o que se apreende e como se lacra, critérios de pontuação.
