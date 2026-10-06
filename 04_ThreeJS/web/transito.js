/*
  Operacao Lei Seca - transito nas duas faixas livres, ao lado da blitz.
  Carros, taxi e onibus (transito/*.glb) entram por um lado da via, passam e somem do outro.
  - cada veiculo mantem distancia do que vai a frente (e do carro liberado pela blitz quando ele volta ao transito)
  - o treinamento pode segurar a faixa de perto da blitz para o carro liberado sair: __transito.segurar(true)
  Coordenadas da cena web: o transito segue para +X; as faixas livres ficam em z = 1,75 e z = 5,25.
*/
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';

const TIPOS = [   // arquivo, comprimento (m), peso no sorteio, faixas permitidas
  { nome: 'suv', comp: 4.6, peso: 3, faixas: [0, 1] },
  { nome: 'minivan', comp: 4.6, peso: 3, faixas: [0, 1] },
  { nome: 'onibus', comp: 10.0, peso: 1, faixas: [1] },          // onibus so na faixa da direita
];
const FAIXAS = [1.75, 5.25], X_INI = -62, X_FIM = 62, MAX_ATIVOS = 7;

export async function iniciarTransito({ scene, iluminar, obstaculo }) {
  const gl = new GLTFLoader(), modelos = {};
  await Promise.all(TIPOS.map(t => gl.loadAsync(`transito/${t.nome}.glb`).then(g => {
    g.scene.traverse(o => { if (o.isMesh) { o.material = Array.isArray(o.material) ? o.material.map(m => iluminar(m.clone())) : iluminar(o.material.clone()); o.frustumCulled = true; } });
    modelos[t.nome] = g.scene;
  }).catch(() => console.warn('transito: modelo nao carregou:', t.nome))));
  const tipos = TIPOS.filter(t => modelos[t.nome]);
  if (!tipos.length) return null;

  const ativos = [], reserva = {};
  const prox = [2, 5];                                    // segundos ate o proximo veiculo de cada faixa
  let seguro = false, ligado = true;
  const sorteio = faixa => {
    const ops = tipos.filter(t => t.faixas.includes(faixa)); let r = Math.random() * ops.reduce((s, t) => s + t.peso, 0);
    for (const t of ops) { r -= t.peso; if (r <= 0) return t; }
    return ops[0];
  };
  function novo(faixa) {
    const t = sorteio(faixa);
    const obj = (reserva[t.nome] ||= []).pop() || modelos[t.nome].clone(true);
    const rodas = []; obj.traverse(o => { if (/Roda_[DT][ED]$/.test(o.name)) rodas.push(o); });
    obj.position.set(X_INI, 0, FAIXAS[faixa] + (Math.random() - .5) * .3); obj.rotation.y = 0; obj.visible = true; scene.add(obj);
    const vmax = (t.nome === 'onibus' ? 7.5 : 9) + Math.random() * 3;      // 27 a 43 km/h: reduzem ao passar pela operacao
    ativos.push({ obj, t, faixa, vel: vmax, vmax, rodas });
  }
  function quadro(dt) {
    if (!ligado) return;
    for (let f = 0; f < FAIXAS.length; f++) {
      prox[f] -= dt;
      const entrada = ativos.some(v => v.faixa === f && v.obj.position.x < X_INI + 16);
      if (prox[f] <= 0 && !entrada && ativos.length < MAX_ATIVOS && !(seguro && f === 0)) { novo(f); prox[f] = 3.5 + Math.random() * 8; }
    }
    const ob = obstaculo?.();                              // carro liberado pela blitz, quando esta nas faixas livres
    for (let i = ativos.length - 1; i >= 0; i--) {
      const v = ativos[i], x = v.obj.position.x;
      let folga = Infinity;
      for (const o of ativos) if (o !== v && o.faixa === v.faixa && o.obj.position.x > x) folga = Math.min(folga, o.obj.position.x - x - (o.t.comp + v.t.comp) / 2);
      if (ob && ob.x > x && Math.abs(ob.z - v.obj.position.z) < 2.2) folga = Math.min(folga, ob.x - x - 2.2 - v.t.comp / 2);
      const alvo = Math.max(0, Math.min(v.vmax, (folga - 3) * .9));
      v.vel += (alvo - v.vel) * Math.min(1, dt * (alvo < v.vel ? 3 : .8));
      const passo = v.vel * dt;
      v.obj.position.x += passo;
      for (const r of v.rodas) r.rotation.z -= passo / .32;
      if (x > X_FIM) { scene.remove(v.obj); (reserva[v.t.nome] ||= []).push(v.obj); ativos.splice(i, 1); }
    }
  }
  const api = {
    quadro,
    segurar(s) { seguro = s; },                            // nao entra veiculo novo na faixa de perto da blitz
    // verdadeiro quando nao ha veiculo na faixa de perto entre x0 e x1 (o carro liberado pode sair)
    livre(x0 = -30, x1 = 22) { return !ativos.some(v => v.faixa === 0 && v.obj.position.x > x0 && v.obj.position.x < x1); },
    ligar(v) { ligado = v; if (!v) { for (const a of ativos) scene.remove(a.obj); ativos.length = 0; } },
    ativos: () => ativos.map(v => ({ tipo: v.t.nome, faixa: v.faixa, x: +v.obj.position.x.toFixed(1), vel: +v.vel.toFixed(1) }))
  };
  window.__transito = api;
  return api;
}
