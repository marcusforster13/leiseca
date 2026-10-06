/*
  Operacao Lei Seca - motor do treinamento
  Le treinamento/cenario_ls_01.json (fases, acoes, pontos, falhas graves, variacoes, dialogos, historia).

  Controles
    Computador: clique = sinalizar / falar / usar equipamento / botoes   T = menu   K = checklist
    Quest:      gatilho = sinalizar / falar / usar / botoes / teleporte
                grip (qualquer mao) = lanterna   botao Y ou B = menu do treinamento
  Variacoes forcadas pela URL (para o instrutor):  ?v=condutor:recusa,sinais:visiveis,passageiro:nenhum
*/
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import * as SkeletonUtils from 'three/addons/utils/SkeletonUtils.js';

export async function iniciar(ctx) {
  const { scene, camera, rig, renderer, CFG } = ctx;
  const CEN = await fetch('treinamento/cenario_ls_01.json').then(r => r.json());
  const V = new THREE.Vector3(), V2 = new THREE.Vector3(), UP = new THREE.Vector3(0, 1, 0);

  /* ================= estado ================= */
  const S = { ativo: false, inicio: 0, fim: 0, variacao: {}, feitos: new Map(), erros: [], graves: [], log: [],
    modo: 'avaliacao', historia: false, fila: [], naMao: false };
  let A = null;                 // atendimento em curso
  const HIST = [];              // atendimentos concluidos (para o relatorio)
  const npcs = {};
  const acoes = {};
  CEN.fases.forEach(f => {
    (f.acoes || []).forEach(a => acoes[a.id] = { ...a, fase: f.id, tipo: 'acao' });
    (f.erros || []).forEach(a => acoes[a.id] = { ...a, fase: f.id, tipo: 'erro' });
    (f.falhas_graves || []).forEach(a => acoes[a.id] = { ...a, fase: f.id, tipo: 'grave' });
  });
  const cond1 = c => {
    const m = c.match(/variacao\.(\w+)\s*(==|!=)\s*'([^']*)'/);
    if (!m) return true;
    return m[2] === '==' ? S.variacao[m[1]] === m[3] : S.variacao[m[1]] !== m[3];
  };
  // "a == 'x' && b != 'y' || c == 'z'"  (&& tem precedencia sobre ||)
  const cond = c => !c || c.split('||').some(ou => ou.split('&&').every(cond1));
  const tempo = () => ((S.fim || performance.now()) - S.inicio) / 1000;
  const fmt = s => `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(Math.floor(s % 60)).padStart(2, '0')}`;
  const nAt = () => (A ? A.n : HIST.length);

  function registrar(id, extra = '') {
    const a = acoes[id]; if (!a || !S.ativo) return;
    if (a.tipo === 'acao') {
      if (S.feitos.has(id) || !cond(a.condicao)) return;
      S.feitos.set(id, tempo());
    } else if (a.tipo === 'erro') {
      S.erros.push({ id, texto: a.texto, pontos: a.pontos, t: tempo(), extra, atendimento: nAt() });
    } else {
      S.graves.push({ id, texto: a.texto, pontos: a.pontos, base: a.base, t: tempo(), extra, atendimento: nAt() });
      legenda('Instrutor', 'Falha grave registrada: ' + a.texto, 4);
    }
    S.log.push({ t: +tempo().toFixed(1), atendimento: nAt(), id, extra });
    status();
  }
  function penalidade(pontos, texto, feedback) {
    S.erros.push({ id: 'conduta', texto, pontos, feedback, t: tempo(), atendimento: nAt() });
    S.log.push({ t: +tempo().toFixed(1), atendimento: nAt(), id: 'conduta', extra: texto }); status();
  }
  const npcPorNome = quem => /^Condutor/.test(quem) ? npcs.condutor : /^Passageir/.test(quem) ? npcs.passageiro : null;

  /* ================= paineis 3D (funcionam no computador e no Quest) ================= */
  const paineis = [];
  class Painel {
    constructor(largura = 1.1) {
      this.largura = largura; this.botoes = [];
      this.mesh = new THREE.Mesh(new THREE.PlaneGeometry(1, 1),
        new THREE.MeshBasicMaterial({ transparent: true, depthTest: false, toneMapped: false, fog: false }));
      this.mesh.renderOrder = 1000; this.mesh.visible = false; scene.add(this.mesh); paineis.push(this);
      // realce do botao apontado pelo controle (no VR a linha do controle some atras do painel)
      this.realce = new THREE.Mesh(new THREE.PlaneGeometry(1, 1), new THREE.MeshBasicMaterial({ color: 0xf0a340, transparent: true, opacity: .32, depthTest: false, toneMapped: false, fog: false }));
      this.realce.renderOrder = 1001; this.realce.visible = false; this.mesh.add(this.realce);
    }
    apontar(ray) {                                   // devolve o ponto atingido e realca o botao embaixo do raio
      if (!this.mesh.visible) return null;
      const h = ray.intersectObject(this.mesh, false)[0]; if (!h) return null;
      const py = (1 - h.uv.y) * this.H, b = this.botoes.find(b => py >= b.y0 && py <= b.y1);
      if (b) { this.realce.position.set(0, .5 - (b.y0 + b.y1) / 2 / this.H, .001); this.realce.scale.set(1 - 2 * 56 / 1024, (b.y1 - b.y0) / this.H, 1); this.realce.visible = true; }
      return h;
    }
    mostrar({ tag = '', titulo = '', texto = '', botoes = [], longe = 1.15 }) {
      const W = 1024, P = 56, cv = document.createElement('canvas'), g = cv.getContext('2d');
      cv.width = W; cv.height = 2400;
      const linhas = (txt, fonte, maxW) => { g.font = fonte; const out = []; for (const par of String(txt).split('\n')) { let l = ''; for (const w of par.split(' ')) { const t = l ? l + ' ' + w : w; if (g.measureText(t).width > maxW && l) { out.push(l); l = w; } else l = t; } out.push(l); } return out; };
      const lt = titulo ? linhas(titulo, '700 46px Segoe UI, sans-serif', W - 2 * P) : [];
      const lx = texto ? linhas(texto, '400 32px Segoe UI, sans-serif', W - 2 * P) : [];
      const lb = botoes.map(b => linhas(b.label, '600 30px Segoe UI, sans-serif', W - 2 * P - 40));     // rotulos longos quebram em linhas
      let y = P; const H0 = P + (tag ? 40 : 0) + lt.length * 56 + (lx.length ? 16 + lx.length * 44 : 0) + lb.reduce((s, l) => s + 54 + l.length * 38, 0) + P + 10;
      cv.height = Math.min(2400, H0);
      g.fillStyle = 'rgba(11,14,22,.95)'; g.beginPath(); g.roundRect(0, 0, W, cv.height, 22); g.fill();
      g.strokeStyle = 'rgba(240,163,64,.5)'; g.lineWidth = 3; g.stroke();
      if (tag) { g.fillStyle = '#f0a340'; g.font = '500 24px Consolas, monospace'; g.fillText(tag.toUpperCase(), P, y + 22); y += 40; }
      g.fillStyle = '#efe9df'; g.font = '700 46px Segoe UI, sans-serif'; lt.forEach(l => { g.fillText(l, P, y + 44); y += 56; });
      if (lx.length) { y += 16; g.fillStyle = 'rgba(239,233,223,.86)'; g.font = '400 32px Segoe UI, sans-serif'; lx.forEach(l => { g.fillText(l, P, y + 32); y += 44; }); }
      y += 10; this.botoes = [];
      for (const [bi, b] of botoes.entries()) {
        y += 12; const h = 34 + lb[bi].length * 38;
        g.fillStyle = b.cor || 'rgba(240,163,64,.14)'; g.beginPath(); g.roundRect(P, y, W - 2 * P, h, 12); g.fill();
        g.strokeStyle = 'rgba(240,163,64,.55)'; g.lineWidth = 2; g.stroke();
        g.fillStyle = '#efe9df'; g.font = '600 30px Segoe UI, sans-serif';
        lb[bi].forEach((l, li) => g.fillText(l, P + 20, y + 46 + li * 38));
        this.botoes.push({ ...b, y0: y, y1: y + h }); y += h + 8;
      }
      const tex = new THREE.CanvasTexture(cv); tex.colorSpace = THREE.SRGBColorSpace;
      this.mesh.material.map?.dispose(); this.mesh.material.map = tex; this.mesh.material.needsUpdate = true;
      this.H = cv.height; this.mesh.scale.set(this.largura, this.largura * cv.height / W, 1);
      camera.getWorldPosition(V); camera.getWorldDirection(V2); V2.y = 0; V2.normalize();
      this.mesh.position.copy(V).addScaledVector(V2, longe); this.mesh.position.y = V.y - .08;
      this.mesh.lookAt(V.x, this.mesh.position.y, V.z); this.mesh.visible = true;
      return this;
    }
    esconder() { this.mesh.visible = false; this.realce.visible = false; }
    clique(ray) {
      if (!this.mesh.visible) return false;
      const h = ray.intersectObject(this.mesh, false)[0]; if (!h) return false;
      const py = (1 - h.uv.y) * this.H, b = this.botoes.find(b => py >= b.y0 && py <= b.y1);
      if (b && b.acao) b.acao();
      return true;
    }
  }
  const menu = new Painel(1.1), dialogo = new Painel(1.15);
  const cursorVR = new THREE.Mesh(new THREE.CircleGeometry(.012, 20), new THREE.MeshBasicMaterial({ color: 0xffffff, depthTest: false, toneMapped: false, fog: false }));
  cursorVR.renderOrder = 1003; cursorVR.visible = false; scene.add(cursorVR);
  // chamado a cada quadro pelo index.html com o raio de cada controle; devolve o acerto de cada raio (ou null)
  function apontar(raios) {
    for (const p of paineis) p.realce.visible = false;
    let ultimo = null;
    const hs = raios.map(r => { let h = null; for (const p of paineis) h = p.apontar(r) || h; if (h) ultimo = h; return h; });
    cursorVR.visible = !!ultimo;
    if (ultimo) { cursorVR.position.copy(ultimo.point); cursorVR.quaternion.copy(ultimo.object.quaternion); cursorVR.translateZ(.002); }
    return hs;
  }
  const fecharPaineis = () => paineis.forEach(p => p.esconder());

  /* legenda presa a camera */
  const lcv = document.createElement('canvas'); lcv.width = 1400; lcv.height = 200;
  const ltex = new THREE.CanvasTexture(lcv); ltex.colorSpace = THREE.SRGBColorSpace;
  const leg = new THREE.Mesh(new THREE.PlaneGeometry(1.0, 1.0 * 200 / 1400), new THREE.MeshBasicMaterial({ map: ltex, transparent: true, depthTest: false, toneMapped: false, fog: false }));
  leg.position.set(0, -.3, -.95); leg.renderOrder = 1001; leg.visible = false; camera.add(leg);
  let legAte = 0;
  function legenda(quem, texto, seg = 4) {
    const g = lcv.getContext('2d'); g.clearRect(0, 0, 1400, 200);
    g.fillStyle = 'rgba(5,7,12,.82)'; g.beginPath(); g.roundRect(0, 0, 1400, 200, 18); g.fill();
    g.fillStyle = '#f0a340'; g.font = '600 34px Segoe UI, sans-serif'; g.fillText(quem, 36, 54);
    g.fillStyle = '#efe9df'; g.font = '400 38px Segoe UI, sans-serif';
    let l = '', y = 108; for (const w of texto.split(' ')) { const t = l ? l + ' ' + w : w; if (g.measureText(t).width > 1330 && l) { g.fillText(l, 36, y); y += 46; l = w; } else l = t; } g.fillText(l, 36, y);
    ltex.needsUpdate = true; legAte = performance.now() + seg * 1000;
    const vr = renderer.xr.isPresenting; leg.visible = vr;          // no VR: legenda no espaco; no computador: faixa HTML
    const hl = document.getElementById('legendaHTML'); if (hl && !vr) { hl.innerHTML = `<b>${quem}:</b> ${texto}`; hl.hidden = false; }
  }
  // catalogo de vozes gravadas (cenario -> vozes.falas): o texto falado encontra o arquivo
  const VOZ = new Map((CEN.vozes?.falas || []).filter(f => !/_f$/.test(f.arquivo)).map(f => [f.texto, f.arquivo]));
  // arquivo gravado para um texto, na voz certa: a condutora usa <arquivo>_f; se so houver a gravacao masculina, ela
  // fica com a voz sintetica (nao fala com voz de homem)
  function vozGravada(texto, voz = 'm') {
    const a = VOZ.get(texto) || VOZ.get(texto.replace(/\bObrigada\b/g, 'Obrigado')); if (!a) return null;
    if (/^f/.test(voz)) return window.__som?.tem(a + '_f') ? a + '_f' : (/^fala_condutor_/.test(a) ? null : (window.__som?.tem(a) ? a : null));
    return window.__som?.tem(a) ? a : null;
  }
  const gravacao = texto => { const a = VOZ.get(texto); return a && window.__som?.tem(a) ? a : null; };
  const duracaoFala = texto => { const a = gravacao(texto); return a ? window.__som.duracao(a) : Math.max(2.6, texto.length / 14); };
  const espera = ms => new Promise(r => setTimeout(r, ms));
  function falar(quem, texto, voz = 'f') {
    const npc = npcPorNome(quem), arq = gravacao(texto);
    if (arq) {                                            // voz gravada: sai da personagem (ou do radio/telefone)
      const seg = window.__som.duracao(arq);
      legenda(quem, texto, seg + .6);
      const med = window.__som.tocar(arq, npc ? npc.position.clone().setY(1.55) : null, !!npc);
      if (npc) npc.userData.fala = { medidor: typeof med === 'function' ? med : null, sintetica: typeof med !== 'function', ate: performance.now() + seg * 1000 };
      return espera(seg * 1000);
    }
    const seg = Math.max(3, texto.length / 14);
    legenda(quem, texto, seg);
    const p = vozSintetica(texto, voz);
    if (npc) { const f = { sintetica: true, ate: performance.now() + (p ? seg + 6 : seg * .8) * 1000 }; npc.userData.fala = f; p?.then(() => { if (npc.userData.fala === f) npc.userData.fala = null; }); }
    return p;
  }
  // chamada da coordenacao pelo radio: bip, a fala e um bip curto no fim
  const BIP = () => Math.min(.8, window.__som?.duracao('radio_bip') || .4) + .15;
  async function radio(texto) {
    window.__som?.tocar('radio_bip'); await espera(BIP() * 1000);
    await falar('Rádio · Coordenação', texto, 'm');
    window.__som?.tocar('radio_bip', null, false, { vol: .35 });
  }
  // voz do navegador (pt-BR). Retorna uma promessa que termina quando a fala acaba (ou null sem voz)
  function vozSintetica(texto, voz = 'f') {
    const lento = /_lento$/.test(voz); voz = voz.replace('_lento', '');      // fala arrastada (condutor com sinais de embriaguez)
    if (S.voz === false || !('speechSynthesis' in window)) return null;
    const vs = speechSynthesis.getVoices().filter(v => v.lang && v.lang.replace('_', '-').startsWith('pt'));
    if (!vs.length) { if (!S.avisoVoz) { S.avisoVoz = true; console.warn('Sem voz sintética em português neste navegador: só legendas.'); } return null; }
    try {
      const u = new SpeechSynthesisUtterance(texto); u.lang = 'pt-BR';
      const br = vs.filter(v => /BR/i.test(v.lang)), lista = br.length ? br : vs;
      const fem = lista.filter(v => /francisca|thalita|maria|luciana|feminin|female|google/i.test(v.name));
      const mas = lista.filter(v => /antonio|daniel|ricardo|masculin|male/i.test(v.name) && !/female/i.test(v.name));
      u.voice = (voz === 'm' ? mas[0] : fem[0]) || lista[(voz === 'm' ? 1 : 0) % lista.length];
      u.pitch = voz === 'c' ? 1.6 : voz === 'm' ? .85 : 1.05; u.rate = voz === 'm' ? 1 : .95;
      if (lento) { u.rate = .66; u.pitch *= .9; }
      return new Promise(r => { u.onend = u.onerror = () => r(); speechSynthesis.speak(u); });
    } catch (e) { return null; }
  }
  if ('speechSynthesis' in window) speechSynthesis.getVoices();      // o Chrome carrega a lista de vozes na primeira chamada

  /* fala com audio gravado (06_Audio/brutos/<audio>.mp3) ou voz sintetica, legenda e gesto; termina quando a fala acaba */
  async function dizer(npc, quem, linha, voz = 'f') {
    const { texto, gesto } = linha, audio = linha.audio || vozGravada(texto, voz);
    const som = window.__som, gravado = audio && som?.tem(audio);
    const ritmo = /_lento$/.test(voz) ? .84 : 1;            // condutor com sinais de embriaguez: a mesma gravacao, mais devagar
    const seg = gravado ? som.duracao(audio) / ritmo : Math.max(2.5, texto.length / 13);
    legenda(quem, texto, seg + .6);
    if (npc && gesto) animar(npc, gesto, seg + 1.5);
    if (gravado) {
      const med = som.tocar(audio, npc ? npc.position.clone().setY(1.55) : null, true, ritmo !== 1 ? { ritmo } : null);
      const f = npc && { medidor: typeof med === 'function' ? med : null, sintetica: typeof med !== 'function', ate: performance.now() + seg * 1000 };
      if (npc) npc.userData.fala = f;
      await espera(seg * 1000 + 350); if (npc?.userData.fala === f) npc.userData.fala = null; return;
    }
    const p = vozSintetica(texto, voz);
    const f = npc && { sintetica: true, ate: performance.now() + (p ? seg + 6 : seg) * 1000 };
    if (npc) npc.userData.fala = f;
    await (p ? Promise.race([p, espera(seg * 1000 + 6000)]) : espera(seg * 1000));
    if (npc?.userData.fala === f) npc.userData.fala = null;
    await espera(350);
  }
  /* ================= personagens provisorios (fase 3 troca por modelos reais) ================= */
  function boneco(nome, corRoupa, altura = 1.7, corCalca = 0x2b2f3a) {
    const g = new THREE.Group(), s = altura / 1.7; g.name = 'NPC_' + nome;
    const pele = new THREE.MeshStandardMaterial({ color: 0xb98a68, roughness: .7 });
    const roupa = new THREE.MeshStandardMaterial({ color: corRoupa, roughness: .85 });
    const calca = new THREE.MeshStandardMaterial({ color: corCalca, roughness: .85 });
    const cap = (r, l, m, x, y, z, rz = 0) => { const k = new THREE.Mesh(new THREE.CapsuleGeometry(r * s, l * s, 4, 12), m); k.position.set(x * s, y * s, z * s); k.rotation.z = rz; g.add(k); return k; };
    cap(.075, .7, calca, -.1, .44, 0); cap(.075, .7, calca, .1, .44, 0);
    cap(.17, .4, roupa, 0, 1.14, 0);
    cap(.055, .52, roupa, -.25, 1.1, 0, .1); const bracoD = cap(.055, .52, roupa, .25, 1.1, 0, -.1);
    cap(.05, .05, pele, 0, 1.47, 0);
    const cab = new THREE.Mesh(new THREE.SphereGeometry(.115 * s, 24, 16), pele); cab.position.set(0, 1.62 * s, 0); g.add(cab);
    const hit = new THREE.Mesh(new THREE.CylinderGeometry(.38 * s, .38 * s, altura, 8), new THREE.MeshBasicMaterial({ visible: false }));
    hit.position.y = altura / 2; hit.userData.npc = nome; g.add(hit);
    const ecv = document.createElement('canvas'); ecv.width = 256; ecv.height = 64; const eg = ecv.getContext('2d');
    eg.fillStyle = 'rgba(5,7,12,.7)'; eg.beginPath(); eg.roundRect(0, 0, 256, 64, 14); eg.fill();
    eg.fillStyle = '#efe9df'; eg.font = '600 32px Segoe UI, sans-serif'; eg.textAlign = 'center'; eg.fillText(nome, 128, 44);
    const et = new THREE.CanvasTexture(ecv); et.colorSpace = THREE.SRGBColorSpace;
    const rotulo = new THREE.Sprite(new THREE.SpriteMaterial({ map: et, depthTest: true, transparent: true, fog: false }));
    rotulo.scale.set(.5, .125, 1); rotulo.position.y = altura + .25; rotulo.renderOrder = 999; rotulo.visible = false; g.add(rotulo);   // nomes ocultos
    g.userData = { hit, bracoD, rotulo, nome };
    return g;
  }
  /* personagens reais (Rocketbox, licenca MIT) convertidos para personagens/*.glb; se faltar, usa o boneco */
  const modelos = {};
  const modelosProntos = fetch('personagens/manifest.json').then(r => r.ok ? r.json() : {}).then(man => {
    const gl = new GLTFLoader();
    return Promise.all(Object.entries(man).map(([papel, info]) => gl.loadAsync(info.arquivo).then(g => { modelos[papel] = g; }).catch(() => { })));
  }).catch(() => { });
  function personagem(papel, nome, cor, altura, calca) {
    const base = modelos[papel];
    if (!base) return boneco(nome, cor, altura, calca);
    const g = new THREE.Group(); g.name = 'NPC_' + nome;
    const m = SkeletonUtils.clone(base.scene);
    m.traverse(o => { if (o.isMesh) o.frustumCulled = false; });
    g.add(m);
    const mixer = new THREE.AnimationMixer(m), acoes = {};
    for (const clip of base.animations) acoes[clip.name.replace(/\.\d+$/, '')] = mixer.clipAction(clip);
    const parada = acoes.parada || Object.values(acoes)[0];
    if (parada) { parada.play(); parada.time = Math.random() * parada.getClip().duration; }
    // area de clique: cilindro do chao ao topo da cabeca (a altura acompanha a pose a cada quadro: em pe, agachado, escalando)
    const alt = altura;
    const hit = new THREE.Mesh(new THREE.CylinderGeometry(.42, .42, 1, 10), new THREE.MeshBasicMaterial({ visible: false }));
    hit.scale.y = alt; hit.position.y = alt / 2; hit.userData.npc = nome; g.add(hit);
    const ecv = document.createElement('canvas'); ecv.width = 256; ecv.height = 64; const eg = ecv.getContext('2d');
    eg.fillStyle = 'rgba(5,7,12,.7)'; eg.beginPath(); eg.roundRect(0, 0, 256, 64, 14); eg.fill();
    eg.fillStyle = '#efe9df'; eg.font = '600 32px Segoe UI, sans-serif'; eg.textAlign = 'center'; eg.fillText(nome, 128, 44);
    const et = new THREE.CanvasTexture(ecv); et.colorSpace = THREE.SRGBColorSpace;
    const rotulo = new THREE.Sprite(new THREE.SpriteMaterial({ map: et, depthTest: true, transparent: true, fog: false }));
    rotulo.scale.set(.5, .125, 1); rotulo.position.y = alt + .25; rotulo.visible = false; g.add(rotulo);   // nomes ocultos
    const mao = m.getObjectByName('Bip01_R_Hand') || m.getObjectByName('Bip01 R Hand');
    g.userData = { hit, rotulo, nome, mixer, acoes, atual: parada, modelo: m, bracoD: mao || g, real: true, rosto: montarRosto(m), olhar: montarOlhar(m) };
    return g;
  }
  /* rosto: boca acompanha o volume da fala e as palpebras piscam (ossos faciais do esqueleto adulto) */
  function montarRosto(m) {
    const jaw = m.getObjectByName('Bip01_MJaw');
    if (!jaw) return null;                                   // crianca (Bip02) tem eixos diferentes: fica sem
    const palp = [['Bip01_REyeBlinkTop', -1.25], ['Bip01_LEyeBlinkTop', -1.25], ['Bip01_REyeBlinkBottom', .35], ['Bip01_LEyeBlinkBottom', .35]]
      .map(([n, k]) => { const b = m.getObjectByName(n); return b && { b, base: b.position.clone(), k }; }).filter(Boolean);
    return { jaw, jawBase: jaw.quaternion.clone(), escrito: null, boca: 0, palp, piscaIni: 0, proxPisca: performance.now() + 1000 + Math.random() * 3000 };
  }
  const QZ = new THREE.Quaternion(), EIXO_Z = new THREE.Vector3(0, 0, 1);
  /* olhar: pescoco e cabeca acompanham o policial quando ele chega perto. A frente do rosto e medida na pose de
     repouso (modelo olhando para +Z) e guardada no espaco do osso da cabeca: funciona em qualquer esqueleto */
  function montarOlhar(m) {
    let cabeca, pescoco, olhoE, olhoD;
    m.traverse(o => { if (!o.isBone) return;
      if (/_Head$/.test(o.name)) cabeca = o; else if (/_Neck$/.test(o.name)) pescoco = o;
      else if (/_LEye$/.test(o.name)) olhoE = o; else if (/_REye$/.test(o.name)) olhoD = o; });
    if (!(cabeca && olhoE && olhoD)) return null;
    // base de cada osso: se a animacao nao mexe nele (trilha constante removida na exportacao), o giro nao pode acumular
    const clavs = pescoco ? pescoco.children.filter(b => /Clavicle$/.test(b.name)) : [];
    const ossos = [pescoco, cabeca, ...clavs].filter(Boolean).map(b => ({ b, base: b.quaternion.clone(), escrito: null }));
    m.updateMatrixWorld(true);
    const frenteLocal = new THREE.Vector3(0, 0, 1).applyQuaternion(cabeca.getWorldQuaternion(new THREE.Quaternion()).invert());
    return { cabeca, pescoco, olhoE, olhoD, ossos, clavs, frenteLocal, peso: 0 };
  }
  const OV1 = new THREE.Vector3(), OV2 = new THREE.Vector3(), OV3 = new THREE.Vector3(), OQ1 = new THREE.Quaternion(), OQ2 = new THREE.Quaternion(), OQ3 = new THREE.Quaternion(), OQ0 = new THREE.Quaternion();
  const AH = new THREE.Vector3();
  function ajustarAreaClique(n) {
    const u = n.userData, cab = u.olhar?.cabeca; if (!cab || !u.hit) return;
    cab.getWorldPosition(AH);
    const h = Math.max(.6, AH.y - n.position.y + .2);    // ate o topo da cabeca
    u.hit.scale.y = h; u.hit.position.y = h / 2;
  }
  function girarNoMundo(osso, q, fracao, maxAng) {       // aplica parte de uma rotacao do mundo ao osso, com limite
    OQ3.copy(OQ0).slerp(q, fracao);
    const ang = 2 * Math.acos(Math.min(1, Math.abs(OQ3.w)));
    if (ang > maxAng) { const parcial = OQ3.clone(); OQ3.copy(OQ0).slerp(parcial, maxAng / ang); }   // para no limite
    osso.parent.getWorldQuaternion(OQ1); osso.getWorldQuaternion(OQ2);
    osso.quaternion.copy(OQ1.invert().multiply(OQ3.multiply(OQ2)));
    osso.updateMatrixWorld(true);
  }
  function frenteCabeca(o) {
    o.olhoE.getWorldPosition(OV1); o.olhoD.getWorldPosition(OV2); OV1.add(OV2).multiplyScalar(.5);   // OV1 = ponto entre os olhos
    return OV3.copy(o.frenteLocal).applyQuaternion(o.cabeca.getWorldQuaternion(OQ2)).normalize();
  }
  function olhar(n, dt, posPolicial) {
    const o = n.userData.olhar; if (!o) return;
    const perto = n.visible && !n.userData.destino && n.position.distanceTo(OV1.copy(posPolicial).setY(n.position.y)) < (n.userData.assento ? 6.5 : 4.5);
    o.peso += ((perto ? 1 : 0) - o.peso) * Math.min(1, dt * 2.5);
    for (const x of o.ossos) {                            // parte da pose da animacao deste quadro (ou da base)
      if (x.escrito && x.b.quaternion.equals(x.escrito)) x.b.quaternion.copy(x.base); else x.base.copy(x.b.quaternion);
      x.escrito = null;
    }
    if (o.peso < .01) return;
    n.updateMatrixWorld(true);
    const ombros = o.clavs.map(b => b.getWorldQuaternion(new THREE.Quaternion()));     // orientacao dos ombros antes de girar o pescoco
    // sentado no carro, o agente fica de lado: pescoco e cabeca giram bem mais para encarar quem aborda
    const limites = n.userData.assento ? [[o.pescoco, .5, .85], [o.cabeca, 1, 1.15]] : [[o.pescoco, .4, .55], [o.cabeca, 1, .75]];
    for (const [osso, fr, max] of limites) {
      if (!osso) continue;
      const frente = frenteCabeca(o).clone(), alvo = OV2.copy(posPolicial).sub(OV1).normalize();
      girarNoMundo(osso, OQ0.clone().setFromUnitVectors(frente, alvo), fr * o.peso, max);
    }
    if (o.pescoco) o.clavs.forEach((b, i) => { o.pescoco.getWorldQuaternion(OQ1); b.quaternion.copy(OQ1.invert().multiply(ombros[i])); b.updateMatrixWorld(true); });   // ombros e bracos ficam onde estavam
    for (const x of o.ossos) x.escrito = x.b.quaternion.clone();
  }
  function animarRosto(n, dt, agora) {
    const r = n.userData.rosto; if (!r) return;
    let alvo = 0; const f = n.userData.fala;
    if (f) {
      if (agora > f.ate) n.userData.fala = null;
      else if (f.medidor) alvo = Math.pow(Math.min(1, Math.max(0, f.medidor() - .06) / .75), .8);   // silencio ~0,04; fala 0,3 a 0,8
      else if (f.sintetica) alvo = Math.max(0, .3 + .45 * Math.sin(agora * .019) * Math.sin(agora * .0063 + 1.7));   // ritmo de silabas
    }
    if (n.userData.soprando) alvo = 1.3 + .08 * Math.sin(agora * .012);      // soprando no etilometro: boca aberta em volta do bocal
    r.boca += (alvo - r.boca) * Math.min(1, dt * (alvo > r.boca ? 28 : 14));
    const q = r.jaw.quaternion;
    if (r.escrito && q.equals(r.escrito)) q.copy(r.jawBase);   // a animacao nao mexeu na mandibula neste quadro
    q.multiply(QZ.setFromAxisAngle(EIXO_Z, r.boca * .17)); r.escrito = q.clone();     // ate ~10 graus de abertura
    // piscar: ~150 ms fechando e abrindo, a cada 2,5 a 6,5 s
    if (agora > r.proxPisca) { r.piscaIni = agora; r.proxPisca = agora + 2500 + Math.random() * 4000; }
    const t = (agora - r.piscaIni) / 75, k = t < 1 ? t : t < 2 ? 2 - t : 0;
    for (const p of r.palp) { p.b.position.copy(p.base); p.b.position.x += p.k * k; }
  }
  const AGACHADO = new Set(['escondido', 'rendido', 'algemado_agachado']);
  function animar(npc, nome, segundos = 6, fade = .5) {
    const u = npc?.userData; if (!u?.real) return;
    if (u.algemado && !nome.startsWith('algemado'))       // algemado: maos sempre nas costas
      nome = nome === 'andando' || nome === 'correndo' ? 'algemado_andando'
        : AGACHADO.has(nome) || (AGACHADO.has(u.pose) && nome !== 'parada') ? 'algemado_agachado' : 'algemado';
    if (!u.acoes[nome]) return;
    u.pose = nome;
    const nova = u.acoes[nome];
    if (u.atual !== nova) { nova.reset().play(); u.atual?.crossFadeTo(nova, fade, false); u.atual = nova; }
    clearTimeout(u.volta);
    if (nome !== (u.base || 'parada')) u.volta = setTimeout(() => animar(npc, u.base || 'parada'), segundos * 1000);
  }
  function moverNPC(n, dt) {
    const u = n.userData;
    if (!u.destino && u.rota?.length) u.destino = u.rota.shift();
    if (!u.destino) return;
    V2.copy(u.destino).sub(n.position); V2.y = 0;
    const L = V2.length();
    if (L < .12) { u.destino = null; if (!u.rota?.length) { const cb = u.aoChegar; u.aoChegar = null; cb?.(); } return; }
    n.position.addScaledVector(V2.normalize(), Math.min(L, (u.vel || 1.4) * dt));
    const alvo = Math.atan2(V2.x, V2.z); let d = alvo - n.rotation.y; d = Math.atan2(Math.sin(d), Math.cos(d));
    n.rotation.y += d * Math.min(1, dt * 8);
    camera.getWorldDirection(V2);                         // V2 volta a ser a direcao do olhar (usada no quadro)
  }
  const ocv = document.createElement('canvas'); ocv.width = 640; ocv.height = 300;
  const otex = new THREE.CanvasTexture(ocv); otex.colorSpace = THREE.SRGBColorSpace;
  const objVR = new THREE.Mesh(new THREE.PlaneGeometry(.42, .42 * 300 / 640), new THREE.MeshBasicMaterial({ map: otex, transparent: true, depthTest: false, toneMapped: false, fog: false }));
  objVR.position.set(-.32, .2, -.9); objVR.renderOrder = 1002; objVR.visible = false; camera.add(objVR);
  const objHTML = document.createElement('div'); objHTML.id = 'objetivosHTML'; objHTML.hidden = true;
  Object.assign(objHTML.style, { position: 'fixed', right: '16px', top: '16px', maxWidth: 'min(340px, calc(100vw - 32px))', zIndex: 6,
    background: 'rgba(11,14,22,.88)', color: '#efe9df', border: '1px solid rgba(240,163,64,.5)', borderRadius: '6px', padding: '10px 14px',
    font: '13px/1.45 "Segoe UI", system-ui, sans-serif', pointerEvents: 'none' });
  document.body.appendChild(objHTML);
  let ultimoObj = '';
  function mostrarObjetivos() {
    const on = S.ativo && S.modo === 'treino', L = on ? objetivos() : [], chave = on + L.join('|') + renderer.xr.isPresenting;
    if (chave === ultimoObj) return; ultimoObj = chave;
    objHTML.hidden = !on || renderer.xr.isPresenting; objVR.visible = on && renderer.xr.isPresenting;
    if (!on) return;
    objHTML.innerHTML = '<b style="color:#f0a340;font:600 11px Consolas,monospace;letter-spacing:.08em">OBJETIVOS</b><br>' + L.map(t => '▸ ' + t).join('<br>');
    const g = ocv.getContext('2d'); g.clearRect(0, 0, 640, 300);
    g.fillStyle = 'rgba(11,14,22,.85)'; g.beginPath(); g.roundRect(0, 0, 640, 300, 16); g.fill();
    g.fillStyle = '#f0a340'; g.font = '600 22px Consolas, monospace'; g.fillText('OBJETIVOS', 22, 38);
    g.fillStyle = '#efe9df'; g.font = '400 25px Segoe UI, sans-serif';
    let y = 80; for (const t of L) { let l = '▸ ', first = true; for (const w of t.split(' ')) { const tt = l + w + ' '; if (g.measureText(tt).width > 600 && l.trim()) { g.fillText(l, 22, y); y += 30; l = '  '; first = false; } else l = tt; } g.fillText(l, 22, y); y += 38; if (y > 290) break; }
    otex.needsUpdate = true;
  }

  /* ================= carro abordado: chega, para no ponto de abordagem e sai ================= */
  const carro = ctx.cena.getObjectByName('Carro_Abordado');
  const PARADA = carro.position.clone(), ENTRADA = PARADA.clone(); ENTRADA.x -= 22;
  const SAIDA = [[PARADA.x + 5, PARADA.z + .2], [PARADA.x + 11.5, 1.2], [PARADA.x + 18, 1.75], [46, 1.75]];   // sai pela faixa livre
  const C = { rota: [], vel: 0, vmax: 5, frear: false, aoChegar: null };
  const SOM_PORTA = { abrir: { ini: .5, dur: 2.0 }, fechar: { ini: 2.6 } };      // trechos do arquivo porta_carro (abre e depois fecha)
  const rodas = []; carro.traverse(o => { if (/_Roda_[DT][ED]$/.test(o.name)) rodas.push(o); });       // rodas soltas: giram conforme o carro anda
  function moverCarro(dt) {
    if (!C.rota.length) return;
    const alvo = C.rota[0]; V.set(alvo[0] - carro.position.x, 0, alvo[1] - carro.position.z);
    const L = V.length(), ultimo = C.rota.length === 1;
    const vAlvo = C.frear && ultimo ? Math.max(.5, Math.min(C.vmax, L * 1.1)) : C.vmax;
    C.vel += (vAlvo - C.vel) * Math.min(1, dt * 2);
    const passo = C.vel * dt;
    if (L <= passo + .03) {
      carro.position.x = alvo[0]; carro.position.z = alvo[1]; C.rota.shift();
      if (!C.rota.length) { C.vel = 0; const cb = C.aoChegar; C.aoChegar = null; cb?.(); }
      return;
    }
    V.multiplyScalar(1 / L); carro.position.addScaledVector(V, passo);
    for (const r of rodas) r.rotation.z -= passo / .325;
    let d = Math.atan2(-V.z, V.x) - carro.rotation.y; d = Math.atan2(Math.sin(d), Math.cos(d));
    carro.rotation.y += d * Math.min(1, dt * 3);
  }
  // bancos: CFG.banco = [x, y, z] no espaco do carro no Blender (frente +X, esquerda +Y) -> lado = 1 motorista, -1 passageiro
  const BANCO = CFG.banco || [.2, .36, .5];
  const VB = new THREE.Vector3();                         // proprio: o V do quadro guarda a posicao do agente
  function seguirCarro(n) {
    const u = n.userData; if (!u.assento) return;
    VB.set(BANCO[0] + .08, 0, -BANCO[1] * u.assento).applyAxisAngle(UP, carro.rotation.y);      // um pouco a frente no banco: o braco sai pelo meio da janela
    n.position.set(carro.position.x + VB.x, BANCO[2] - .11 - .925 * (u.altura / 1.78), carro.position.z + VB.z);
    n.rotation.y = carro.rotation.y + Math.PI / 2; n.visible = carro.visible;
  }
  // porta do motorista (peca separada no modelo, com a origem na dobradica)
  const porta = carro.getObjectByName('Carro_Abordado_Porta');
  const PORTA_ABERTA = -1.12;
  const suave = (seg, passo) => new Promise(fim => {       // interpola de 0 a 1 em 'seg' segundos (setTimeout: funciona com a aba oculta)
    const t0 = performance.now();
    const tic = () => { const k = Math.min(1, (performance.now() - t0) / (seg * 1000)); passo(k * k * (3 - 2 * k)); k < 1 ? setTimeout(tic, 16) : fim(); };
    tic();
  });
  function moverPorta(alvo, seg = .7) {
    if (!porta) return Promise.resolve();
    const a0 = porta.rotation.y;
    return suave(seg, e => { porta.rotation.y = a0 + (alvo - a0) * e; });
  }
  const somPorta = trecho => window.__som?.tocar('porta_carro', carro.position.clone().setY(.9), false, trecho);
  /* o condutor sai do carro: a porta abre, ele se levanta para fora, da dois passos e a porta fecha.
     comPorta = false (passageira, do outro lado): aparece em pe ao lado do carro */
  async function desembarcar(n, dx = 0, comPorta = false) {
    const u = n.userData;
    const soltar = () => { u.assento = 0; (u.mats || []).forEach(m => { m.clippingPlanes = null; m.needsUpdate = true; }); u.base = 'parada'; };
    if (!comPorta || !porta) {
      soltar(); u.semVirar = false;
      n.position.set(carro.position.x + BANCO[0] + dx, 0, carro.position.z - 1.45); animar(n, 'parada', 1e6, .1);
      return;
    }
    somPorta(SOM_PORTA.abrir); await moverPorta(PORTA_ABERTA, .8);
    const ini = n.position.clone(), r0 = n.rotation.y;
    const fora = new THREE.Vector3(carro.position.x + BANCO[0] - .12, 0, carro.position.z - 1.02);
    soltar(); u.semVirar = true; animar(n, 'parada', 1e6, .6);
    await suave(.9, e => { n.position.lerpVectors(ini, fora, e); n.rotation.y = r0 + (Math.PI - r0) * e; });      // levanta virando para a calcada
    await new Promise(fim => {                              // dois passos para longe do carro
      u.vel = u.embriagado ? .55 : 1.0; u.rota = [new THREE.Vector3(fora.x - .55, 0, fora.z - 1.0)];
      if (u.acoes?.andando) animar(n, 'andando', 1e6, .25);
      u.aoChegar = () => { animar(n, 'parada', 1e6, .3); u.semVirar = false; fim(); };
      setTimeout(fim, 5000);                                // garantia, caso o quadro esteja pausado
    });
    somPorta(SOM_PORTA.fechar); await moverPorta(0, .6);
  }

  /* ================= equipamentos da mesa ================= */
  const itens = {};
  for (const [k, nome] of Object.entries({ etilometro: 'I_Etilometro', bocais: 'I_Caixa_Bocais', tablet: 'I_Tablet', maleta: 'I_Maleta_Etilometro', lixeira: 'I_Lixeira_Bocais' })) {
    const o = ctx.cena.getObjectByName(nome); if (!o) continue;
    const h = new THREE.Mesh(new THREE.SphereGeometry(k === 'lixeira' ? .3 : k === 'maleta' ? .22 : .14, 10, 8), new THREE.MeshBasicMaterial({ visible: false }));
    o.getWorldPosition(h.position); h.position.y += k === 'lixeira' ? .2 : .05; h.userData.item = k; scene.add(h); itens[k] = { o, h };
  }
  // etilometro na mao do agente: visor com a leitura e bocal descartavel encaixado na ponta
  let naMaoObj = null, bocalObj = null;
  const vcv = document.createElement('canvas'); vcv.width = 160; vcv.height = 120;
  const vtex = new THREE.CanvasTexture(vcv); vtex.colorSpace = THREE.SRGBColorSpace;
  function visorTexto(valor = 'PRONTO', unidade = '') {
    const g = vcv.getContext('2d'); g.fillStyle = '#0c1a12'; g.fillRect(0, 0, 160, 120);
    g.fillStyle = '#8dffb0'; g.textAlign = 'center';
    g.font = `700 ${valor.length > 5 ? 34 : 58}px Consolas, monospace`; g.fillText(valor, 80, unidade ? 66 : 76);
    if (unidade) { g.font = '600 26px Consolas, monospace'; g.fillText(unidade, 80, 104); }
    vtex.needsUpdate = true;
  }
  visorTexto();
  const MAO_POS = new THREE.Vector3(.17, -.17, -.42), MAO_ROT = new THREE.Quaternion().setFromEuler(new THREE.Euler(1.15, .25, 0));
  function pegarEtilometro(pegar) {
    const it = itens.etilometro; if (!it) { S.naMao = pegar; return; }
    S.naMao = pegar; it.o.visible = !pegar;
    if (pegar && !naMaoObj) {
      naMaoObj = it.o.clone(); naMaoObj.visible = true;
      // visor (no modelo: em cima do corpo, do lado do bocal) e bocal (na ponta: -Z do aparelho)
      const visor = new THREE.Mesh(new THREE.PlaneGeometry(.052, .04), new THREE.MeshBasicMaterial({ map: vtex, toneMapped: false, fog: false }));
      visor.rotation.x = -Math.PI / 2; visor.position.set(0, .0445, -.03); naMaoObj.add(visor);
      bocalObj = new THREE.Mesh(new THREE.CylinderGeometry(.0075, .0095, .085, 12), new THREE.MeshStandardMaterial({ color: 0xf2f4f6, roughness: .35 }));
      ctx.iluminar(bocalObj.material); bocalObj.rotation.x = Math.PI / 2; bocalObj.position.set(0, .022, -.145); bocalObj.visible = false; naMaoObj.add(bocalObj);
    }
    if (naMaoObj) {
      naMaoObj.userData.naBoca = 0; camera.add(naMaoObj); naMaoObj.position.copy(MAO_POS); naMaoObj.quaternion.copy(MAO_ROT);
      naMaoObj.visible = pegar;
      if (!pegar) { bocalObj.visible = false; visorTexto(); }
    }
  }
  // posicao e orientacao do aparelho diante da boca do condutor (bocal apontado para a boca, visor para cima)
  const EB = new THREE.Vector3(), EX = new THREE.Vector3(), EYv = new THREE.Vector3(), EZ = new THREE.Vector3(), EM = new THREE.Matrix4();
  function alvoBoca(pos, quat) {
    const o = npcs.condutor?.userData.olhar; if (!o) return false;
    EZ.copy(frenteCabeca(o));                               // frente do rosto; OV1 fica entre os olhos
    EB.copy(OV1); EB.y -= .092; EB.addScaledVector(EZ, .032);          // boca
    // o aparelho vem do lado do agente (pela janela): fica entre a boca e quem segura, puxando um pouco para a frente do rosto
    camera.getWorldPosition(EX); EX.sub(EB); EX.y *= .25; EX.normalize(); EZ.multiplyScalar(.45).add(EX).normalize();
    pos.copy(EB).addScaledVector(EZ, .178);              // a ponta do bocal (a 18,7 cm do centro do aparelho) entra um pouco na boca
    EYv.set(0, 1, 0).addScaledVector(EZ, -EZ.y).normalize(); EX.crossVectors(EYv, EZ);
    quat.setFromRotationMatrix(EM.makeBasis(EX, EYv, EZ));
    return true;
  }
  async function levarABoca() {
    if (!naMaoObj) return;
    const p1 = new THREE.Vector3(), q1 = new THREE.Quaternion(); if (!alvoBoca(p1, q1)) return;
    scene.attach(naMaoObj); naMaoObj.userData.naBoca = 1;
    const p0 = naMaoObj.position.clone(), q0 = naMaoObj.quaternion.clone();
    await suave(.7, e => { if (!alvoBoca(p1, q1)) return; naMaoObj.position.lerpVectors(p0, p1, e); naMaoObj.quaternion.slerpQuaternions(q0, q1, e); });
    if (naMaoObj.userData.naBoca === 1) naMaoObj.userData.naBoca = 2;      // dai em diante acompanha a cabeca
  }
  async function trazerDaBoca() {
    if (!naMaoObj || !naMaoObj.userData.naBoca) return;
    naMaoObj.userData.naBoca = 0; camera.attach(naMaoObj);
    const p0 = naMaoObj.position.clone(), q0 = naMaoObj.quaternion.clone();
    await suave(.7, e => { naMaoObj.position.lerpVectors(p0, MAO_POS, e); naMaoObj.quaternion.slerpQuaternions(q0, MAO_ROT, e); });
  }
  function bip() {
    if (window.__som?.tocar('bip_etilometro')) { setTimeout(() => window.__som.tocar('bip_etilometro'), 220); return; }   // bipe duplo
    try {
      const ac = bip.ac = bip.ac || new AudioContext(), o = ac.createOscillator(), g = ac.createGain();
      o.frequency.value = 1750; g.gain.setValueAtTime(.12, ac.currentTime); g.gain.setValueAtTime(0, ac.currentTime + .35);
      o.connect(g).connect(ac.destination); o.start(); o.stop(ac.currentTime + .4);
    } catch (e) { }
  }

  /* ================= variacoes ================= */
  function derivar(v) {
    v.alcool = v.condutor === 'sobrio' ? 'nao' : 'sim';
    v.autua = (v.alcool === 'sim' || v.documentos !== 'regular') ? 'sim' : 'nao';
    v.retem = (v.alcool === 'sim' || v.documentos === 'cnh_vencida') ? 'sim' : 'nao';
    v.veiculo = v.documentos === 'licenciamento_atrasado' ? 'remover' : v.retem === 'nao' ? 'liberar' : v.passageiro === 'habilitado_sobrio' ? 'entregar' : 'remover';
    v.decisao = v.condutor === 'sobrio' ? 'liberar' : v.condutor === 'alcool_infracao' ? 'art165' : v.condutor === 'alcool_crime' ? 'art165_crime'
      : v.sinais === 'visiveis' ? 'art165_sinais' : 'art165A';
    return v;
  }
  function sortear() {
    const forc = Object.fromEntries((new URLSearchParams(location.search).get('v') || '').split(',').filter(Boolean).map(p => p.split(':')));
    const v = {};
    for (const [k, ops] of Object.entries(CEN.variacoes)) v[k] = forc[k] && ops.includes(forc[k]) ? forc[k] : ops[Math.floor(Math.random() * ops.length)];
    if (!forc.sinais) { if (v.condutor === 'sobrio') v.sinais = 'nenhum'; if (v.condutor === 'alcool_crime') v.sinais = 'visiveis'; }
    return derivar(v);
  }

  /* ================= personagens ================= */
  // sentado no carro, o que fica abaixo do assoalho (canelas e pes) nao aparece por baixo da carroceria
  const PLANO_ASSOALHO = new THREE.Plane(new THREE.Vector3(0, 1, 0), -.24); renderer.localClippingEnabled = true;
  function limparNPCs() { Object.values(npcs).forEach(n => scene.remove(n)); for (const k in npcs) delete npcs[k]; }
  function novoNPC(papel, nome, lado) {
    const alt = papel === 'condutor_b' ? 1.66 : 1.78;
    const n = personagem(papel, nome, 0x3d4045, alt); n.userData.altura = alt;
    const mats = []; const prep = m => { const c = ctx.iluminar(m.clone()); c.clippingPlanes = [PLANO_ASSOALHO]; mats.push(c); return c; };
    n.userData.modelo?.traverse(o => { if (o.isMesh) o.material = Array.isArray(o.material) ? o.material.map(prep) : prep(o.material); });
    n.userData.mats = mats;
    n.userData.assento = lado; n.userData.semVirar = true; n.userData.base = 'sentado';
    animar(n, 'sentado', 1e6, 0); seguirCarro(n); scene.add(n);
    return n;
  }
  // "sentado" = dirigindo, maos no volante; com o carro parado o condutor solta o volante e descansa as maos no colo
  function poseSentado(n, dirigindo) {
    const u = n?.userData; if (!u?.assento) return;
    const parado = u.nervoso && u.acoes?.sentado_nervoso ? 'sentado_nervoso' : u.acoes?.sentado_parado ? 'sentado_parado' : 'sentado';
    u.base = dirigindo ? 'sentado' : parado; animar(n, u.base, 1e6, .6);
  }
  function criarNPCs(v) {
    limparNPCs();
    if (v.passageiro !== 'nenhum' && v.modelo === 'condutor_b') v.modelo = 'condutor_a';     // a passageira e sempre a condutor_b
    npcs.condutor = novoNPC(v.modelo, 'Condutor', 1);
    npcs.condutor.userData.embriagado = v.sinais === 'visiveis';
    npcs.condutor.userData.nervoso = v.comportamento === 'nervoso';
    if (v.passageiro !== 'nenhum') npcs.passageiro = novoNPC('condutor_b', 'Passageira', -1);
    if (npcs.passageiro) poseSentado(npcs.passageiro, false);
  }
  const feminino = () => S.variacao.modelo === 'condutor_b';
  const embriagado = () => S.variacao.sinais === 'visiveis';
  const vozC = () => (feminino() ? 'f' : 'm') + (embriagado() ? '_lento' : '');
  // falas do agente e do condutor no genero certo
  const T = t => !feminino() ? t : t.replace(/\bo senhor\b/g, 'a senhora').replace(/\bO senhor\b/g, 'A senhora').replace(/\bpreso\b/g, 'presa');
  const TC = t => feminino() ? t.replace(/\bObrigado\b/g, 'Obrigada') : t;      // falas do proprio condutor
  function condFala(texto) {
    const c = npcs.condutor; if (!c) return Promise.resolve();
    return dizer(c, embriagado() ? 'Condutor (fala arrastada)' : 'Condutor', { texto: TC(texto), gesto: c.userData.assento ? 'sentado_falando' : 'falando' }, vozC());
  }

  /* ================= equipe da operacao (figurantes): agentes de colete e policiais ================= */
  const figurantes = {};
  const FIGURANTES = [   // papel, nome, x, z (cena web), giro, fala ao clicar
    ['agente_a', 'Agente', -19.4, -3.25, -Math.PI / 2, 'Eu seleciono os veículos e mando para a faixa de abordagem. Daqui para a frente é com você.', 'm'],
    ['agente_b', 'Agente', -9.2, -4.55, .3, 'Aqui na tenda a gente consulta os documentos e imprime os autos. Precisando, é só chamar.', 'f'],
    ['agente_c', 'Agente', 9.5, -3.75, 1.9, 'Esta é a área de regularização: o veículo fica aqui até aparecer um condutor habilitado e em condições.', 'm'],
    ['pm_b', 'Policial', 12.0, -3.85, -.1, 'Estou na segurança da operação. Havendo crime de trânsito, a condução à delegacia é comigo.', 'm'],
  ];
  function criarFigurantes() {
    for (const [papel, nome, x, z, giro, fala, voz] of FIGURANTES) {
      if (figurantes[papel] || !modelos[papel]) continue;
      const n = personagem(papel, nome, 0x3d4045, papel === 'agente_b' ? 1.68 : 1.8);
      n.userData.modelo?.traverse(o => { if (o.isMesh) o.material = Array.isArray(o.material) ? o.material.map(m => ctx.iluminar(m.clone())) : ctx.iluminar(o.material.clone()); });
      Object.assign(n.userData, { fig: papel, falaFig: fala, vozFig: voz, giroBase: giro });
      n.position.set(x, 0, z); n.rotation.y = giro; scene.add(n); figurantes[papel] = n;
    }
  }
  function cliqueFigurante(ray) {
    const h = ray.intersectObjects(Object.values(figurantes).map(n => n.userData.hit), false)[0];
    if (!h || h.distance > 5) return false;
    const n = Object.values(figurantes).find(f => f.userData.hit === h.object); if (!n) return false;
    dizer(n, n.userData.nome, { texto: n.userData.falaFig, gesto: 'falando' }, n.userData.vozFig);
    return true;
  }

  /* ================= paineis de opcoes ================= */
  const fechar = () => dialogo.esconder();
  function dica(texto) { if (S.modo !== 'avaliacao' && S.ativo) legenda('Dica do instrutor', texto, 6); }
  function painelOpc(tag, titulo, lista, aoEscolher, texto = '') {
    fecharPaineis();
    dialogo.mostrar({ tag, titulo, texto, botoes: [...lista.map(op => ({ label: T(op.fala), acao: () => {
      fechar();
      if (op.acao) registrar(op.acao);
      if (op.tambem) registrar(op.tambem);
      if (op.erro) registrar(op.erro);
      if (op.falha) registrar(op.falha);
      if (op.feedback && S.modo === 'treino') setTimeout(() => legenda('Instrutor', op.feedback, 7), 2600);
      aoEscolher?.(op);
    } })), { label: 'Voltar', acao: fechar }] });
  }

  /* ================= documentos: o condutor estende a mao pela janela e o agente pega ================= */
  // dados ficticios, coerentes com a variacao sorteada (os mesmos que o tablet mostra)
  function dadosDocs() {
    const v = S.variacao, hoje = new Date(), val = new Date(hoje), emi = new Date(hoje);
    val.setMonth(val.getMonth() + (v.documentos === 'cnh_vencida' ? -4 : 26)); emi.setFullYear(val.getFullYear() - 10);
    const ano = hoje.getFullYear(), atras = v.documentos === 'licenciamento_atrasado';
    return { nome: CEN.documentos.nomes[v.modelo], hoje, val, emi, exercicio: atras ? ano - 2 : ano, atras };
  }
  const dcv = document.createElement('canvas'); dcv.width = 860; dcv.height = 540;
  const dtex = new THREE.CanvasTexture(dcv); dtex.colorSpace = THREE.SRGBColorSpace;
  function desenharDoc(tipo) {
    const g = dcv.getContext('2d'), d = dadosDocs(), W = 860, H = 540, cnh = tipo === 'cnh';
    g.fillStyle = cnh ? '#e9efe6' : '#eef0f4'; g.beginPath(); g.roundRect(0, 0, W, H, 28); g.fill();
    g.fillStyle = cnh ? '#2f6b4a' : '#27457a'; g.beginPath(); g.roundRect(0, 0, W, 96, [28, 28, 0, 0]); g.fill();
    g.fillStyle = '#fff'; g.font = '700 38px Segoe UI, sans-serif'; g.fillText(cnh ? 'CARTEIRA NACIONAL DE HABILITAÇÃO' : 'DOCUMENTO DO VEÍCULO · CRLV-e', 30, 50);
    g.font = '500 20px Segoe UI, sans-serif'; g.fillText('MODELO DE TREINAMENTO · sem valor legal', 30, 80);
    const campo = (rot, val, x, y, larg = 0) => { g.fillStyle = '#5b6470'; g.font = '500 19px Segoe UI, sans-serif'; g.fillText(rot, x, y);
      g.fillStyle = '#12161c'; g.font = '700 34px Segoe UI, sans-serif'; g.fillText(val, x, y + 38, larg || undefined); };
    if (cnh) {
      g.fillStyle = '#c9d2c6'; g.beginPath(); g.roundRect(30, 124, 200, 250, 10); g.fill();          // lugar da foto
      g.fillStyle = '#8d9a8b'; g.beginPath(); g.arc(130, 215, 52, 0, 7); g.fill(); g.beginPath(); g.ellipse(130, 345, 86, 70, 0, Math.PI, 0); g.fill();
      campo('NOME', d.nome, 260, 150, 570); campo('CATEGORIA', 'B', 260, 250); campo('1ª HABILITAÇÃO', dataBR(d.emi), 430, 250);
      campo('VALIDADE', dataBR(d.val), 260, 350); campo('REGISTRO', '0' + (41700000000 + d.nome.length * 7919), 30, 430);
    } else {
      campo('PLACA', 'KXR3B47', 30, 150); campo('MARCA / MODELO', 'HATCH 1.0', 300, 150); campo('COR', 'PRATA', 620, 150);
      campo('PROPRIETÁRIO', d.nome, 30, 250, 800); campo('EXERCÍCIO DO LICENCIAMENTO', String(d.exercicio), 30, 350); campo('RESTRIÇÕES', 'NENHUMA', 480, 350);
    }
    g.fillStyle = '#5b6470'; g.font = '500 19px Segoe UI, sans-serif'; g.fillText('DATA DE HOJE: ' + dataBR(d.hoje), 30, 510);
    dtex.needsUpdate = true;
  }
  const matDoc = new THREE.MeshBasicMaterial({ map: dtex, side: THREE.DoubleSide, toneMapped: false, fog: false });
  // cartao na mao do condutor (pequeno, com area de clique maior) e o mesmo cartao na mao do agente (grande, para ler)
  const docMao = new THREE.Mesh(new THREE.PlaneGeometry(.125, .078), matDoc); docMao.visible = false; scene.add(docMao);
  const docHit = new THREE.Mesh(new THREE.SphereGeometry(.2, 10, 8), new THREE.MeshBasicMaterial({ visible: false })); docMao.add(docHit);
  const docCam = new THREE.Mesh(new THREE.PlaneGeometry(.27, .17), matDoc.clone()); docCam.material.depthTest = false; docCam.material.transparent = true; docCam.renderOrder = 998;
  docCam.position.set(-.36, -.07, -.55); docCam.rotation.set(-.12, .5, 0);      // a esquerda do painel de opcoes docCam.visible = false; camera.add(docCam);
  const DM = new THREE.Vector3(), DA = new THREE.Vector3();
  const docVista = new THREE.Mesh(new THREE.PlaneGeometry(.7, .44), new THREE.MeshBasicMaterial({ map: dtex, toneMapped: false, fog: false, depthTest: false, transparent: true }));     // transparent: desenha depois dos vidros
  docVista.renderOrder = 1000; docVista.visible = false; scene.add(docVista);
  let aposVista = null;
  function mostrarVista(tipo, depois) {                     // documento de frente, no meio da visao
    fecharPaineis(); desenharDoc(tipo); docCam.visible = false;
    camera.getWorldPosition(V); camera.getWorldDirection(V2);          // bem no centro do olhar, mesmo olhando para baixo
    docVista.position.copy(V).addScaledVector(V2, .85); docVista.lookAt(V);
    docVista.visible = true; aposVista = depois;
    legenda('Documento', 'Leia os dados com calma. Gatilho ou clique para continuar.', 8);
  }
  function fecharVista() {
    if (!docVista.visible) return false;
    docVista.visible = false; const f = aposVista; aposVista = null; f?.();
    return true;
  }
  function oferecerDocumentos() {
    if (!A || A.docsPegos) return;
    const c = npcs.condutor, u = c.userData;
    // em dois tempos: primeiro ergue a mao dentro do carro (acima do peitoril), depois estende pela janela;
    // direto do colo para fora, o braco atravessava a lataria da porta
    if (u.acoes?.sentado_entregando) {
      u.baseAntes = u.base; u.base = 'sentado_entregando';
      if (u.acoes.sentado_entregando_meio) { animar(c, 'sentado_entregando_meio', 1e6, .4); setTimeout(() => { if (u.base === 'sentado_entregando') animar(c, 'sentado_entregando', 1e6, .45); }, 430); }
      else animar(c, 'sentado_entregando', 1e6, .45);
    }
    desenharDoc('cnh'); A.docsOferecidos = true; status();
    setTimeout(() => { if (A?.docsOferecidos && !A.docsPegos) docMao.visible = true; }, 480);        // o cartao aparece quando a mao ja saiu
    dica('O condutor estendeu os documentos: aponte para o cartão na mão dele e aperte o gatilho (ou clique) para pegar.');
  }
  function pegarDocumentos() {
    if (!A || A.docsPegos) return;
    const c = npcs.condutor, u = c.userData;
    A.docsPegos = true; docMao.visible = false;
    if (u.baseAntes) {                                    // recolhe o braco pelo mesmo caminho: para dentro e so depois para o colo
      const volta = u.baseAntes; u.base = volta; u.baseAntes = null;
      if (u.acoes?.sentado_entregando_meio) { animar(c, 'sentado_entregando_meio', 1e6, .4); setTimeout(() => { if (u.base === volta) animar(c, volta, 1e6, .45); }, 430); }
      else animar(c, volta, 1e6, .5);
    }
    mostrarVista('cnh', conferirCNH);
  }
  const DC = new THREE.Vector3(), DN = new THREE.Vector3(), DY = new THREE.Vector3(), DMAT = new THREE.Matrix4();
  function curvarDedos(n, on) {                             // dedos da mao esquerda fecham sobre o cartao
    const u = n?.userData, m = u?.modelo; if (!m) return;
    if (!u.dedos) { u.dedos = []; m.traverse(o => { if (o.isBone && /Bip01_L_Finger\d+$/.test(o.name)) u.dedos.push({ b: o, base: o.quaternion.clone() }); }); }
    for (const d of u.dedos) { d.b.quaternion.copy(d.base); if (on) d.b.quaternion.multiply(QZ.setFromAxisAngle(EIXO_Z, /Finger0\d?$/.test(d.b.name) ? .3 : -.5)); }
  }
  function seguirDocumento() {                              // o documento fica em pinca, entre o polegar e o indicador da mao esquerda
    if (!docMao.visible) return;
    const m = npcs.condutor?.userData.modelo, mao = m?.getObjectByName('Bip01_L_Hand');
    const ind = m?.getObjectByName('Bip01_L_Finger12') || m?.getObjectByName('Bip01_L_Finger11'), pol = m?.getObjectByName('Bip01_L_Finger02') || m?.getObjectByName('Bip01_L_Finger01');
    if (!mao || !ind || !pol) { docMao.position.set(carro.position.x + BANCO[0] + .35, 1.1, carro.position.z - 1.0); camera.getWorldPosition(DA); docMao.lookAt(DA); return; }
    mao.getWorldPosition(DM); ind.getWorldPosition(DA); pol.getWorldPosition(DC);
    const dir = DY.copy(DA).add(DC).multiplyScalar(.5).sub(DM).normalize().clone();       // do punho para a pinca
    DN.subVectors(DA, DC); DN.addScaledVector(dir, -DN.dot(dir));                            // do polegar para o indicador: normal do cartao
    if (DN.lengthSq() < 1e-6) DN.set(0, 1, 0); DN.normalize();
    const meioPinca = DA.add(DC).multiplyScalar(.5);
    DY.crossVectors(DN, dir);
    docMao.quaternion.setFromRotationMatrix(DMAT.makeBasis(dir, DY, DN));
    docMao.position.copy(meioPinca).addScaledVector(dir, .05);                              // preso por uma ponta, o resto para a frente
  }

  /* ================= fluxo do atendimento ================= */
  function novoAtendimento(v, cap) {
    S.variacao = v; S.feitos = new Map();
    A = { n: HIST.length + 1, fase: 'chegando', titulo: cap?.titulo || `Atendimento ${HIST.length + 1}` };
    criarNPCs(v);
    window.__transito?.segurar(false);
    if (porta) porta.rotation.y = 0;
    docVista.visible = false; aposVista = null;
    docMao.visible = false; docCam.visible = false;
    C.rota = []; C.vel = 0; carro.position.copy(ENTRADA); carro.rotation.y = 0; carro.visible = true;
    pegarEtilometro(false);
    const abrir = () => {
      radio(CEN.radio.inicio);
      setTimeout(() => dica('Aponte para o carro que chega e aperte o gatilho (ou clique) para sinalizar a parada.'), 3500);
      A.tAuto = setTimeout(() => { if (A && A.fase === 'chegando' && !C.rota.length) entrar(false); }, 16000);
    };
    if (cap) { fecharPaineis(); menu.mostrar({ tag: 'Modo história', titulo: cap.titulo, texto: cap.texto, longe: 1.3, botoes: [{ label: 'Começar', acao: () => { menu.esconder(); abrir(); } }] }); }
    else abrir();
    status();
  }
  function entrar(sinalizou) {
    if (!A || A.fase !== 'chegando' || C.rota.length) return;
    clearTimeout(A.tAuto);
    window.__som?.tocar('motor_carro_chegando', carro.position.clone().setY(.6));
    if (sinalizou) { registrar('sinalizar_parada'); legenda('Agente', 'Sinal de parada: braço estendido, indicando o ponto de abordagem.', 3); }
    C.vmax = 5; C.frear = true; C.rota = [[PARADA.x, PARADA.z]];
    C.aoChegar = () => { A.fase = 'parado'; carro.rotation.y = 0; poseSentado(npcs.condutor, false); dica('Veículo parado. Aproxime-se pelo lado do motorista (área protegida) e fale com o condutor.'); status(); };
  }
  function menuCondutor() {
    if (!A || A.fase !== 'parado') return;
    const D = CEN.dialogos, v = S.variacao;
    if (!A.contato) {
      A.contato = true; camera.getWorldPosition(V);
      if (V.z > -.3) registrar('na_faixa_livre'); else if (V.z < carro.position.z - .8) registrar('posicao_segura');
    }
    if (!A.abriu) return painelOpc('Condutor', 'Primeiro contato', D.abertura, () => { A.abriu = true; condFala(D.resposta_abertura[v.comportamento]); });
    const ops = [];
    if (!A.motor) ops.push({ label: D.motor.fala, acao: () => { A.motor = true; registrar('pedir_desligar'); fechar(); condFala(D.motor.resposta); } });
    if (!A.docs) ops.push({ label: D.documentos.fala, acao: () => { A.docs = true; registrar('pedir_documentos'); fechar(); condFala(D.documentos.resposta).then(oferecerDocumentos); } });
    if (A.docs && !A.cnhOk) ops.push(A.docsPegos ? { label: 'Conferir a habilitação', acao: conferirCNH } : { label: 'Pegar os documentos e conferir a habilitação', acao: () => { fechar(); pegarDocumentos(); } });
    if (A.docs && A.cnhOk && !A.crlvOk) ops.push({ label: 'Conferir o documento do veículo no tablet', acao: conferirCRLV });
    if (!A.sinais) ops.push({ label: 'Observar o condutor: fala, olhos, hálito, movimentos', acao: observar });
    if (!A.convite) ops.push({ label: 'Oferecer o teste do etilômetro', acao: convidar });
    if (A.recusou && !A.infRecusa) ops.push({ label: 'Responder à recusa', acao: responderRecusa });
    if (A.aceitou && !A.testado) ops.push({ label: 'Fazer o teste do etilômetro', acao: teste });
    if (A.testado && !A.mostrou) ops.push({ label: 'Mostrar o visor e informar o resultado', acao: mostrarResultado });
    if ((A.testado || A.infRecusa) && !A.decidiu) ops.push({ label: 'Decidir o enquadramento', acao: decidir });
    if (A.decidiu && !A.veiculoOk) ops.push({ label: 'Continuar: registro e destino do veículo', acao: aposDecisao });
    if (A.veiculoOk) ops.push({ label: 'Encerrar o atendimento', acao: encerramento });
    fecharPaineis();
    dialogo.mostrar({ tag: 'Condutor', titulo: A.veiculoOk ? 'Encerramento' : A.decidiu ? 'Providências' : 'Atendimento', botoes: [...ops.map(o => ({ ...o, label: T(o.label) })), { label: 'Encerrar conversa', acao: fechar }] });
  }
  const dataBR = d => d.toLocaleDateString('pt-BR');
  function conferirCNH() {
    A.docsPegos = true; docMao.visible = false; desenharDoc('cnh'); docCam.visible = true;
    const v = S.variacao, hoje = new Date(), val = new Date(hoje);
    val.setMonth(val.getMonth() + (v.documentos === 'cnh_vencida' ? -4 : 26));
    const certo = v.documentos === 'cnh_vencida' ? 'vencida_30' : 'regular';
    painelOpc('Tablet · habilitação', 'Carteira Nacional de Habilitação', CEN.documentos.cnh, op => {
      A.cnhOk = true;
      if (op.id === certo) registrar('conferir_cnh'); else { registrar('consulta_errada', 'CNH: ' + op.id); if (S.modo === 'treino') legenda('Instrutor', 'Confira a validade: ' + CEN.documentos.cnh.find(o => o.id === certo).fala + '.', 6); }
      setTimeout(() => mostrarVista('crlv', conferirCRLV), S.modo === 'treino' && op.id !== certo ? 3000 : 300);
    }, `Nome: ${CEN.documentos.nomes[v.modelo]}\nCategoria: B\nValidade: ${dataBR(val)}\nData de hoje: ${dataBR(hoje)}`);
  }
  function conferirCRLV() {
    desenharDoc('crlv'); docCam.visible = true;
    const v = S.variacao, ano = new Date().getFullYear(), atras = v.documentos === 'licenciamento_atrasado', certo = atras ? 'atrasado' : 'regular';
    painelOpc('Tablet · veículo', 'Documento do veículo (CRLV-e)', CEN.documentos.crlv, op => {
      A.crlvOk = true;
      docCam.visible = false; setTimeout(() => dica('Documentos devolvidos ao condutor.'), 600);
      if (op.id === certo) registrar('conferir_crlv'); else { registrar('consulta_errada', 'CRLV: ' + op.id); if (S.modo === 'treino') legenda('Instrutor', 'Confira o exercício do licenciamento: ' + CEN.documentos.crlv.find(o => o.id === certo).fala + '.', 6); }
    }, `Placa: KXR3B47 · hatch cinza\nÚltimo licenciamento: exercício ${atras ? ano - 2 : ano}\nRestrições: nenhuma`);
  }
  function observar() {
    A.sinais = true; registrar('observar_sinais'); fecharPaineis();
    dialogo.mostrar({ tag: 'Observação', titulo: 'Sinais do condutor', texto: CEN.sinais[S.variacao.sinais], botoes: [{ label: 'Anotar e continuar', acao: fechar }] });
  }
  function convidar() {
    const D = CEN.dialogos, v = S.variacao;
    painelOpc('Condutor', 'Teste do etilômetro', D.convite, () => {
      A.convite = true;
      if (v.condutor === 'recusa') { A.recusou = true; condFala(D.resposta_convite.recusa); }
      else { A.aceitou = true; condFala(v.condutor === 'sobrio' ? D.resposta_convite.aceita : D.resposta_convite.aceita_nervoso).then(() => { if (!S.naMao) dica('Pegue o etilômetro na mesa de equipamentos (toalha azul) e volte ao condutor.'); }); }
    });
  }
  function responderRecusa() {
    painelOpc('Condutor', 'O condutor recusou o teste', CEN.dialogos.recusa, () => { A.infRecusa = true; condFala(CEN.dialogos.resposta_recusa); });
  }
  function teste() {
    if (!S.naMao) { fechar(); return legenda('Equipamento', 'O etilômetro está na mesa de equipamentos (toalha azul), ao lado. Pegue o aparelho e volte.', 5); }
    painelOpc('Etilômetro', 'Bocal', CEN.dialogos.bocal, () => { if (bocalObj) bocalObj.visible = true; painelOpc('Etilômetro', 'Orientação ao condutor', CEN.dialogos.sopro, soprar); });
  }
  function soprar() {
    const v = S.variacao, r = CEN.etilometro[v.condutor];
    legenda('Etilômetro', 'Soprando… aguarde a leitura.', 3.6);
    { const c = npcs.condutor; if (c) c.userData.soprando = true; if (c?.userData.assento) animar(c, c.userData.acoes?.sentado_parado ? 'sentado_parado' : 'sentado', 5.5, .3); }      // para de olhar em volta: fica de frente para o aparelho
    visorTexto('SOPRE'); levarABoca();
    for (const [ms, trecho] of [[750, { ini: .15, dur: 1.9 }], [2150, { ini: .15 }]])       // som do sopro, em dois trechos emendados (~3 s)
      setTimeout(() => { const c = npcs.condutor; if (c?.userData.soprando) window.__som?.tocar('sopro', c.position.clone().setY(1.2), false, trecho); }, ms);
    setTimeout(() => {
      if (!A) return;
      bip(); A.testado = true; A.resultado = r; A.bocalUsado = true; fecharPaineis();
      visorTexto(r.medido, 'mg/L'); trazerDaBoca(); if (npcs.condutor) npcs.condutor.userData.soprando = false;
      dialogo.mostrar({ tag: 'Etilômetro · leitura', titulo: `${r.medido} mg/L`, texto: `Valor considerado: ${r.considerado} mg/L\n${CEN.etilometro.aparelho}`,
        botoes: [{ label: 'Mostrar o visor e informar o resultado ao condutor', acao: mostrarResultado }, { label: 'Guardar o aparelho sem mostrar', acao: fechar }] });
      status();
    }, 3700);
  }
  function mostrarResultado() {
    fechar(); A.mostrou = true; registrar('mostrar_resultado');
    condFala(CEN.dialogos.resposta_resultado[S.variacao.condutor]).then(() => dica('Descarte o bocal na lixeira e decida o enquadramento (fale com o condutor).'));
  }
  function decidir() {
    const D = CEN.dialogos, v = S.variacao;
    const r = A.resultado ? `Etilômetro: ${A.resultado.medido} mg/L (considerado ${A.resultado.considerado}).` : 'Teste recusado.';
    painelOpc('Decisão', 'Enquadramento', D.decisao, op => {
      A.decidiu = true;
      const certo = op.id === v.decisao;
      if (certo) registrar('enquadramento_correto');
      else if (op.id === 'prisao_recusa') registrar('prisao_por_recusa');
      else if (op.id === 'liberar') registrar('liberar_alcoolizado');
      else registrar('enquadramento_errado', op.id);
      if (S.modo === 'treino') legenda('Instrutor', (certo ? 'Correto. ' : 'O correto aqui: ') + D.decisao_explicacao[v.decisao], 8);
      setTimeout(aposDecisao, S.modo === 'treino' ? 4200 : 400);
    }, r + (A.sinais ? '\nSinais: ' + (v.sinais === 'visiveis' ? 'três sinais anotados.' : 'nenhum.') : '\nSinais: não observados.'));
  }
  function aposDecisao() {
    if (!A || !A.decidiu) return;
    const D = CEN.dialogos, v = S.variacao;
    if (v.autua === 'sim' && !A.auto) return painelOpc('Tablet · registro', 'Auto de infração', D.auto, () => { A.auto = true; aposDecisao(); });
    if (v.alcool === 'sim' && !A.cnh) return painelOpc('Providências', 'Habilitação do condutor', D.cnh, () => { A.cnh = true; aposDecisao(); });
    if (v.condutor === 'alcool_crime' && !A.pm) return painelOpc('Providências', 'Crime de trânsito (art. 306)', [
      { fala: 'Acionar os policiais: condução à delegacia com o auto, o resultado impresso e as testemunhas', acao: 'acionar_pm_crime', radio: true },
      { fala: 'Deixar o condutor aguardando na tenda e seguir a operação' }], op => { A.pm = true; if (op.radio) { radio(CEN.radio.crime); } setTimeout(aposDecisao, op.radio ? (BIP() + duracaoFala(CEN.radio.crime)) * 1000 + 600 : 300); });
    if (!A.veiculoOk) return destinoVeiculo();
  }
  function destinoVeiculo() {
    const D = CEN.dialogos, v = S.variacao, tem = v.passageiro !== 'nenhum';
    const fim = d => { A.destino = d; A.veiculoOk = true; status(); dica('Fale com o condutor para encerrar o atendimento.'); if (d === 'remover') { radio(CEN.radio.guincho); } };
    const remover = () => {
      if (v.veiculo === 'remover') registrar('veiculo_correto');
      else penalidade(v.veiculo === 'liberar' ? -6 : -3, 'Remoção do veículo sem necessidade', v.veiculo === 'liberar' ? 'Sem irregularidade, o veículo segue com o condutor.' : 'Havia condutor habilitado e apto para assumir o veículo (Res. 1.031/2026, art. 11).');
      fim('remover');
    };
    const lista = D.veiculo.filter(o => tem || (o.id !== 'fiscalizar_passageiro' && o.id !== 'entregar_direto'));
    painelOpc('Providências', 'Destino do veículo', lista, op => {
      if (op.id === 'liberar') {
        if (v.veiculo === 'liberar') registrar('veiculo_correto');
        else if (v.alcool === 'sim') registrar('liberar_alcoolizado');
        else penalidade(-6, 'Liberar veículo que deveria ficar retido ou ser removido', v.documentos === 'cnh_vencida' ? 'Com a habilitação vencida há mais de 30 dias, o condutor não pode seguir dirigindo (CTB art. 162, V).' : 'Veículo não licenciado é removido (CTB art. 230, V).');
        return fim('liberar');
      }
      if (op.id === 'entregar_direto') { registrar('entregar_sem_fiscalizar'); return fim('entregar'); }
      if (op.id === 'remover') return remover();
      registrar('fiscalizar_passageiro');
      painelOpc('Passageira', 'Resultado da fiscalização', D.passageiro_decisao, o2 => {
        if (o2.id === 'remover') return remover();
        if (v.passageiro === 'habilitado_alcoolizado') registrar('entregar_a_alcoolizado');
        else if (v.veiculo === 'entregar') registrar('veiculo_correto');
        else penalidade(-6, 'Entregar veículo que deveria ser removido', 'Veículo não licenciado é removido (CTB art. 230, V).');
        fim('entregar');
      }, D.passageiro_resultado[v.passageiro]);
    }, tem ? 'Há uma passageira no veículo.' : 'O condutor está sozinho.');
  }
  function encerramento() {
    const D = CEN.dialogos, v = S.variacao;
    painelOpc('Condutor', 'Encerramento', D.encerramento, () => {
      const r = D.resposta_encerramento;
      condFala(v.autua !== 'sim' ? r.liberado : v.comportamento === 'hostil' ? r.hostil : r.autuado).then(finalizar);
    });
  }
  function finalizar() {
    if (!A || A.fase === 'fim') return;
    A.fase = 'fim'; pegarEtilometro(false);
    const v = S.variacao, levado = v.condutor === 'alcool_crime' && A.pm;
    if (A.destino === 'remover') {
      desembarcar(npcs.condutor, 0, true); if (npcs.passageiro) desembarcar(npcs.passageiro, -1.6);
      legenda('Operação', levado ? 'Condutor encaminhado à delegacia. Veículo aguardando o guincho.' : 'Veículo retido, aguardando o guincho. O condutor aguarda fora do carro.', 5);
      setTimeout(concluir, 7500);
    } else {
      if (A.destino === 'entregar') legenda('Operação', 'A passageira assume o volante.', 4);
      const tr = window.__transito, t0 = performance.now(); tr?.segurar(true);
      const sair = () => {
        if (tr && !tr.livre() && performance.now() - t0 < 12000) return setTimeout(sair, 300);
        poseSentado(npcs.condutor, true);
        C.vmax = 6; C.frear = false; C.rota = SAIDA.map(p => [...p]);
        C.aoChegar = () => { carro.visible = false; Object.values(npcs).forEach(n => n.visible = false); tr?.segurar(false); };
      };
      sair();
      setTimeout(concluir, 4500);
    }
    status();
  }
  function resumo() {                                       // pontos do atendimento atual, por fase
    const fases = [];
    for (const f of CEN.fases) {
      let fp = 0, fo = 0; const itens = [];
      for (const a of f.acoes || []) {
        if (!cond(a.condicao)) continue;
        fp += a.pontos; const ok = S.feitos.has(a.id); if (ok) fo += a.pontos;
        itens.push({ texto: a.texto, ok, pontos: ok ? a.pontos : 0, base: a.base, atendimento: A.n });
      }
      fases.push({ nome: f.nome, obtidos: fo, possiveis: fp, itens });
    }
    return { n: A.n, titulo: A.titulo, variacao: { ...S.variacao }, fases };
  }
  function concluir() {
    if (!A) return;
    HIST.push(resumo()); A = null;
    if (!S.ativo) return;
    if (S.fila.length) {
      const prox = S.fila.shift();
      setTimeout(() => { limparNPCs(); novoAtendimento(derivar({ ...prox.variacao }), S.historia ? prox : null); }, 1500);
    } else encerrar();
  }

  /* ================= inicio, menu e relatorio ================= */
  function aviso() {
    fecharPaineis();
    menu.mostrar({
      tag: 'Treinamento', titulo: 'Operação Lei Seca',
      texto: 'Você é agente da operação: receba o veículo, converse com o condutor, confira os documentos, faça o teste do etilômetro e decida.\n\n' +
        'Computador: clique para sinalizar, falar e usar os equipamentos · T menu · K checklist.\n' +
        'Quest: gatilho usa/clica · botão Y ou B abre o menu · grip liga a lanterna.',
      botoes: [
        { label: 'Modo história (3 atendimentos guiados)', acao: () => comecar('historia') },
        { label: 'Modo treino (objetivos e dicas na tela)', acao: () => comecar('treino') },
        { label: 'Modo avaliação (sem dicas)', acao: () => comecar('avaliacao') },
        { label: S.voz === false ? 'Voz sintética: desligada (só legendas)' : 'Voz sintética: ligada', acao: () => { S.voz = S.voz === false; aviso(); } },
        { label: 'Cancelar', acao: () => menu.esconder() }
      ]
    });
  }
  async function comecar(modo) {
    fecharPaineis();
    let carregou = false; modelosProntos.then(() => { carregou = true; });
    await new Promise(r => setTimeout(r, 0));
    if (!carregou) {
      menu.mostrar({ tag: 'Treinamento', titulo: 'Carregando personagens…', texto: 'Aguarde alguns segundos.', botoes: [] });
      await Promise.race([modelosProntos, new Promise(r => setTimeout(r, 30000))]);
      menu.esconder();
    }
    HIST.length = 0;
    Object.assign(S, { ativo: true, inicio: performance.now(), fim: 0, erros: [], graves: [], log: [], historia: modo === 'historia', modo: modo === 'avaliacao' ? 'avaliacao' : 'treino' });
    S.fila = S.historia ? CEN.historia.slice(1) : [];
    if (ctx.hotspots) ctx.hotspots.visible = false;
    document.getElementById('relatorioHTML')?.setAttribute('hidden', '');
    rig.position.set(PARADA.x + 2.6, 0, PARADA.z - 1.9); ctx.setYaw(Math.PI / 2);      // na area protegida, olhando para o carro que chega
    novoAtendimento(S.historia ? derivar({ ...CEN.historia[0].variacao }) : sortear(), S.historia ? CEN.historia[0] : null);
  }
  function abrirMenu() {
    if (!S.ativo) return aviso();
    fecharPaineis();
    menu.mostrar({ tag: 'Menu', titulo: 'Operação Lei Seca', texto: `Tempo: ${fmt(tempo())} · ${A ? A.titulo : 'aguardando'}`,
      botoes: [
        { label: 'Checklist deste atendimento', acao: abrirChecklist },
        { label: S.naMao ? 'Guardar o etilômetro na mesa' : 'Pegar o etilômetro', acao: () => { pegarEtilometro(!S.naMao); menu.esconder(); status(); } },
        { label: 'Lanterna (liga/desliga)', acao: () => { ctx.setLanterna(!ctx.lanternaLigada(), camera); menu.esconder(); } },
        { label: 'Encerrar e ver o relatório', cor: 'rgba(240,80,64,.22)', acao: encerrar },
        { label: 'Fechar', acao: () => menu.esconder() }
      ] });
  }
  function abrirChecklist() {
    fecharPaineis();
    const linhas = CEN.fases.map(f => `${f.nome}: ` + (f.acoes || []).filter(a => cond(a.condicao)).map(a => (S.feitos.has(a.id) ? '✓ ' : '· ') + a.texto).join(' | ')).join('\n');
    menu.mostrar({ tag: 'Tablet', titulo: 'Checklist do atendimento', texto: (S.modo === 'avaliacao' ? 'No modo avaliação o checklist só aparece no relatório.' : linhas) + `\n\nTempo: ${fmt(tempo())}`, botoes: [{ label: 'Fechar', acao: () => menu.esconder() }], longe: 1.3 });
  }
  function encerrar() {
    if (!S.ativo) return;
    docMao.visible = false; docCam.visible = false;
    if (A) {                                                // atendimento interrompido: conta o que foi feito
      if (A.fase === 'parado' && S.variacao.alcool === 'sim' && A.decidiu && !A.veiculoOk) penalidade(-6, 'Atendimento encerrado sem definir o destino do veículo', 'Com infração por álcool ou recusa, o veículo fica retido até a apresentação de condutor habilitado.');
      clearTimeout(A.tAuto); HIST.push(resumo()); A = null;
    }
    S.fila = []; S.fim = performance.now(); S.ativo = false; fecharPaineis(); pegarEtilometro(false); status();
    mostrarRelatorio(relatorio());
  }
  function relatorio() {
    let possiveis = 0, obtidos = 0; const fases = [];
    CEN.fases.forEach((f, i) => {
      const fr = { nome: f.nome, obtidos: 0, possiveis: 0, itens: [] };
      for (const h of HIST) { const x = h.fases[i]; fr.obtidos += x.obtidos; fr.possiveis += x.possiveis; fr.itens.push(...x.itens); }
      possiveis += fr.possiveis; obtidos += fr.obtidos; fases.push(fr);
    });
    const desc = S.erros.reduce((s, e) => s + e.pontos, 0) + S.graves.reduce((s, e) => s + e.pontos, 0);
    const nota = possiveis ? Math.max(0, Math.round((obtidos + desc) / possiveis * 100)) : 0;
    const aprovado = nota >= CEN.aprovacao.pontos_minimos && !(CEN.aprovacao.sem_falha_grave && S.graves.length);
    return { cenario: CEN.id, data: new Date().toISOString(), tempo: fmt(tempo()), modo: S.historia ? 'historia' : S.modo, nota, aprovado, obtidos, descontos: desc, possiveis,
      atendimentos: HIST.map(h => ({ n: h.n, titulo: h.titulo, variacao: h.variacao })), fases, erros: S.erros, falhas_graves: S.graves, linha_do_tempo: S.log };
  }
  function mostrarRelatorio(r) {
    const varios = r.atendimentos.length > 1, at = e => varios ? ` [atend. ${e.atendimento}]` : '';
    const txtFases = r.fases.map(f => `${f.nome}: ${f.obtidos}/${f.possiveis}`).join('\n');
    const txtErros = [...r.falhas_graves.map(g => '⚠ FALHA GRAVE: ' + g.texto + (g.base ? ` (${g.base})` : '') + at(g)), ...r.erros.map(e => `• ${e.texto} (${e.pontos})${e.feedback ? ' — ' + e.feedback : ''}` + at(e))].join('\n') || 'Nenhum erro registrado.';
    menu.mostrar({
      tag: 'Relatório', titulo: `Nota ${r.nota}/100 · ${r.aprovado ? 'APROVADO' : 'NÃO APROVADO'}`,
      texto: `Tempo: ${r.tempo} · Atendimentos: ${r.atendimentos.length}\n\n${txtFases}\n\n${txtErros}`,
      botoes: [{ label: 'Novo treinamento (outras variações)', acao: () => { fecharPaineis(); aviso(); } }, { label: 'Fechar', acao: () => menu.esconder() }], longe: 1.4
    });
    const el = document.getElementById('relatorioHTML');
    if (el) {
      const nomeVar = v => `condutor: ${v.condutor} · sinais: ${v.sinais} · documentos: ${v.documentos} · passageiro: ${v.passageiro}`;
      el.innerHTML = `<h2>Nota ${r.nota}/100 — ${r.aprovado ? 'aprovado' : 'não aprovado'}</h2>
        <p>Tempo ${r.tempo} · modo ${r.modo}</p>
        <ul>${r.atendimentos.map(a => `<li>${a.titulo} — <em>${nomeVar(a.variacao)}</em></li>`).join('')}</ul>
        ${r.fases.map(f => `<h3>${f.nome} <small>${f.obtidos}/${f.possiveis}</small></h3><ul>${f.itens.map(i => `<li class="${i.ok ? 'ok' : 'nao'}">${i.ok ? '✓' : '✗'} ${i.texto}${varios ? ` [atend. ${i.atendimento}]` : ''}${i.base ? ` <em>(${i.base})</em>` : ''}</li>`).join('')}</ul>`).join('')}
        <h3>Erros e falhas graves</h3><ul>${txtErros.split('\n').map(l => `<li>${l}</li>`).join('')}</ul>
        <p><em>Rascunho para validação com a coordenação da operação. Base: CTB arts. 165, 165-A, 277 e 306; Resolução Contran 1.031/2026.</em></p>
        <p><button type="button" id="baixarRel">Baixar relatório (JSON)</button> <button type="button" id="fecharRel">Fechar</button></p>`;
      el.hidden = false;
      document.getElementById('baixarRel').onclick = () => { const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([JSON.stringify(r, null, 2)], { type: 'application/json' })); a.download = `relatorio_${r.cenario}_${Date.now()}.json`; a.click(); };
      document.getElementById('fecharRel').onclick = () => el.hidden = true;
    }
  }

  /* ================= modo exploracao (antes de iniciar): carro parado, condutor responde ================= */
  const INFO_ITEM = {
    etilometro: 'Etilômetro (bafômetro): mede o álcool no ar expirado, em mg/L. Com 0,05 mg/L ou mais há infração; com 0,34 mg/L ou mais, também crime.',
    bocais: 'Bocais descartáveis, embalados um a um. Cada teste usa um bocal novo, aberto na frente do condutor.',
    tablet: 'Tablet: consulta da habilitação e do veículo e registro do auto de infração.',
    maleta: 'Maleta do etilômetro, com a impressora que emite o comprovante do teste.',
    lixeira: 'Lixeira para os bocais usados.'
  };
  function cenaExploracao() {
    S.variacao = derivar({ ...CEN.historia[0].variacao });
    carro.position.copy(PARADA); carro.rotation.y = 0; carro.visible = true; criarNPCs(S.variacao); poseSentado(npcs.condutor, false);
  }
  function explorar(ray) {
    const hi = ray.intersectObjects(Object.values(itens).map(i => i.h), false)[0];
    if (hi && hi.distance < 4) { legenda('Equipamento', INFO_ITEM[hi.object.userData.item], 6); return true; }
    const hn = ray.intersectObjects(Object.values(npcs).map(n => n.userData.hit), false)[0];
    if (hn && hn.distance < 6) { condFala('Boa noite. É a Lei Seca? Pode fiscalizar, tá tudo certo.'); return true; }
    if (cliqueFigurante(ray)) return true;
    return false;
  }

  /* ================= clique / gatilho ================= */
  function usar(ray) {
    if (fecharVista()) return true;                         // documento em vista frontal: qualquer clique continua
    for (const p of paineis) if (p.clique(ray)) return true;
    if (!S.ativo) return explorar(ray);
    const hn = ray.intersectObjects(Object.values(npcs).filter(n => n.visible).map(n => n.userData.hit), false)[0];
    const hi = ray.intersectObjects(Object.values(itens).map(i => i.h), false)[0];
    const hc = carro.visible ? ray.intersectObject(carro, true)[0] : null;
    if (hi && hi.distance < 3.5 && (!hn || hi.distance < hn.distance)) { usarItem(hi.object.userData.item); return true; }
    if (A?.fase === 'chegando' && hc && hc.distance < 60) { entrar(true); return true; }
    if (docMao.visible) { const hd = ray.intersectObject(docHit, false)[0]; if (hd && hd.distance < 4) { pegarDocumentos(); return true; } }
    if (hn && hn.distance < 4.5) {
      if (hn.object.userData.npc === 'Condutor') menuCondutor(); else dizer(npcs.passageiro, 'Passageira', { texto: 'Boa noite.' }, 'f');
      return true;
    }
    if (hc && hc.distance < 4.5 && A?.fase === 'parado') { menuCondutor(); return true; }
    if (cliqueFigurante(ray)) return true;
    return false;
  }
  function usarItem(k) {
    if (k === 'etilometro') { pegarEtilometro(true); legenda('Equipamento', 'Etilômetro na mão. ' + CEN.etilometro.aparelho + '.', 4); status(); }
    else if (k === 'tablet') abrirChecklist();
    else if (k === 'lixeira' && A?.bocalUsado) { A.bocalUsado = false; registrar('descartar_bocal'); if (bocalObj) bocalObj.visible = false; legenda('Equipamento', 'Bocal usado descartado.', 2.5); }
    else legenda('Equipamento', INFO_ITEM[k], 5);
  }

  /* ================= objetivos (modo treino) e status ================= */
  function objetivos() {
    const L = [];
    if (!A) return ['Aguarde o próximo veículo'];
    if (A.fase === 'chegando') L.push('Sinalize a parada: aponte para o carro que chega');
    else if (A.fase === 'fim') L.push('Atendimento concluído');
    else if (!A.abriu) L.push('Vá até o lado do motorista e cumprimente o condutor');
    else {
      if (!A.motor) L.push('Peça para desligar o motor');
      if (!A.docs) L.push('Peça a habilitação e o documento do veículo'); else if (!A.docsPegos) L.push('Pegue os documentos da mão do condutor'); else if (!A.crlvOk) L.push('Confira a habilitação e o documento do veículo');
      if (!A.sinais) L.push('Observe os sinais do condutor');
      if (!A.convite) L.push('Ofereça o teste do etilômetro');
      else if (A.recusou && !A.infRecusa) L.push('Informe a consequência da recusa (art. 165-A)');
      else if (A.aceitou && !A.testado) L.push(S.naMao ? 'Faça o teste: bocal novo e sopro contínuo' : 'Pegue o etilômetro na mesa de equipamentos');
      else if (A.testado && !A.mostrou) L.push('Mostre o resultado ao condutor');
      if (A.bocalUsado) L.push('Descarte o bocal usado na lixeira');
      if ((A.testado || A.infRecusa) && !A.decidiu) L.push('Decida o enquadramento');
      if (A.decidiu && !A.veiculoOk) L.push('Registre e defina o destino do veículo');
      if (A.veiculoOk) L.push('Encerre o atendimento com o condutor');
    }
    return L.slice(0, 4);
  }
  function status() {
    const el = document.getElementById('statusTrein'); if (!el) return;
    el.hidden = !S.ativo || S.modo === 'treino';           // no modo treino o quadro de objetivos ocupa o canto
    el.innerHTML = `<b>${A ? A.titulo : 'Operação Lei Seca'}</b> · ${fmt(tempo())}<br>Na mão: ${S.naMao ? 'etilômetro' : 'nada'}`;
    mostrarObjetivos();
  }

  /* ================= quadro ================= */
  let ultimo = performance.now();
  function quadro() {
    const agora = performance.now(), dt = Math.min(.1, (agora - ultimo) / 1000); ultimo = agora;
    if (agora > legAte) { leg.visible = false; const hl = document.getElementById('legendaHTML'); if (hl && !hl.hidden) hl.hidden = true; }
    moverCarro(dt);
    seguirDocumento();
    if (naMaoObj?.userData.naBoca === 2) alvoBoca(naMaoObj.position, naMaoObj.quaternion);
    camera.getWorldPosition(V); camera.getWorldDirection(V2);
    for (const n of [...Object.values(npcs), ...Object.values(figurantes)]) {
      const u = n.userData;
      seguirCarro(n);
      if (u.embriagado) n.rotation.z = (u.assento ? .04 : .075) * Math.sin(agora * .0012) + .02 * Math.sin(agora * .0031);      // oscila
      else if (n.rotation.z) n.rotation.z = 0;
      u.mixer?.update(dt);
      animarRosto(n, dt, agora);
      olhar(n, dt, V);
      ajustarAreaClique(n);
      moverNPC(n, dt);
      if (u.real && !u.assento && !u.destino && !u.semVirar && V.distanceTo(n.position) < 3.5) {     // vira o corpo para o agente
        let d = Math.atan2(V.x - n.position.x, V.z - n.position.z) - n.rotation.y; d = Math.atan2(Math.sin(d), Math.cos(d));
        n.rotation.y += d * Math.min(1, dt * 2.5);
      } else if (u.fig && !u.fala) { let d = u.giroBase - n.rotation.y; d = Math.atan2(Math.sin(d), Math.cos(d)); n.rotation.y += d * Math.min(1, dt * 1.2); }
    }
    if (S.ativo && Math.floor(agora / 1000) !== Math.floor((agora - dt * 1000) / 1000)) status();
  }

  /* ================= entradas ================= */
  addEventListener('keydown', e => {
    if (e.target.tagName === 'INPUT') return;
    if (e.code === 'KeyT') abrirMenu();
    if (e.code === 'KeyK' && S.ativo) abrirChecklist();
  });
  const bt = document.createElement('button'); bt.type = 'button'; bt.textContent = 'Iniciar treinamento'; bt.id = 'bTrein';
  bt.onclick = aviso; document.getElementById('acoes')?.prepend(bt);
  modelosProntos.then(() => { criarFigurantes(); if (!S.ativo) cenaExploracao(); });

  window.__trein = {
    clique: ray => usar(ray), gatilho: ray => usar(ray),
    apontar, painelAberto: () => paineis.some(p => p.mesh.visible) || docVista.visible,
    menu: abrirMenu, quadro, estado: S, relatorio,
    // acesso para testes automatizados e para o instrutor
    _t: { comecar, entrar, poseSentado, levarABoca, trazerDaBoca, visorTexto, etil: () => naMaoObj, fecharVista, docVista, oferecerDocumentos, pegarDocumentos, docMao, docCam, desembarcar, moverPorta, porta, figurantes, cliqueFigurante, menuCondutor, usarItem, encerrar, objetivos, sortear, derivar, novoAtendimento, npcs, carro, C,
      atendimento: () => A, historico: HIST, botoes: () => (dialogo.mesh.visible ? dialogo : menu).botoes, painel: () => (dialogo.mesh.visible ? dialogo : menu.mesh.visible ? menu : null) }
  };
  return window.__trein;
}
