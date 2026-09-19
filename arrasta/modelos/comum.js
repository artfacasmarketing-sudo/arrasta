// O que os três modelos dividem: montar texto com destaque, aplicar cores e medir o slide para o render conferir.
// Cada molde define montar(s, meta) e, se precisar posicionar depois que a fonte carrega, ajustar().

// métricas da Inter embutida (unitsPerEm 2048): subida 1984, descida 494, altura de maiúscula 1490
const SUBIDA = 1984 / 2048, DESCIDA = 494 / 2048, MAIUSCULA = 1490 / 2048;
// até onde uma letra pinta fora da área da fonte (tabela head dos dois woff2): yMax 2269 (acento empilhado),
// yMin -546 e xMin -400
const PASSA_CIMA = (2269 - 1984) / 2048, PASSA_BAIXO = (546 - 494) / 2048, PASSA_LADO = 400 / 2048;

function esc(s) {
  return s.replace(/[&<>"]/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}[c]));
}
function marcas(s) {
  // *palavra* vira destaque; o resto é texto puro
  return esc(s).replace(/\*([^*]+)\*/g, '<span class="marca">$1</span>');
}
function aplicarCores(cores) {
  const r = document.documentElement.style;
  for (const [k, v] of Object.entries(cores)) r.setProperty("--" + k.replace("_", "-"), v);
}
function papelDe(meta) {
  return meta.i === 1 ? "capa" : meta.i === meta.n ? "final" : "miolo";
}

// linhas de texto de um elemento, de cima para baixo: [{top, bottom, left, right}] da área da fonte (subida + descida)
function linhas(el) {
  const r = document.createRange();
  r.selectNodeContents(el);
  const porTopo = new Map();
  for (const q of r.getClientRects()) {
    if (q.width < 1) continue;
    const k = Math.round(q.top);
    const a = porTopo.get(k);
    porTopo.set(k, a ? {top: Math.min(a.top, q.top), bottom: Math.max(a.bottom, q.bottom), left: Math.min(a.left, q.left), right: Math.max(a.right, q.right)}
                     : {top: q.top, bottom: q.bottom, left: q.left, right: q.right});
  }
  return [...porTopo.values()].sort((a, b) => a.top - b.top);
}
function tamanho(el) { return parseFloat(getComputedStyle(el).fontSize); }
// y da linha de base e do topo da maiúscula, a partir da área da fonte de uma linha
function linhaDeBase(linha, fs) { return linha.bottom - DESCIDA * fs; }
function topoDaMaiuscula(linha, fs) { return linha.bottom - DESCIDA * fs - MAIUSCULA * fs; }

function mover(el, dy) { el.style.top = (parseFloat(el.style.top || 0) + dy) + "px"; }
function capDe(el) { return MAIUSCULA * tamanho(el); }
// vão entre as linhas de um texto: entrelinha menos a altura da maiúscula
function vaoDe(el) { return parseFloat(getComputedStyle(el).lineHeight) - capDe(el); }
function caixaAlta(el) { return getComputedStyle(el).textTransform === "uppercase"; }
function temFundo(el) { return !/rgba\([^)]*,\s*0\)|transparent/.test(getComputedStyle(el).backgroundColor); }
// onde termina a tinta de um texto: a borda da caixa se ele tem fundo; senão a linha de base da última linha,
// mais a perna do p e do g quando não é caixa-alta
function fimDaTinta(el) {
  if (temFundo(el)) return el.getBoundingClientRect().bottom;
  return linhaDeBase(linhas(el).at(-1), tamanho(el)) + (caixaAlta(el) ? 0 : DESCIDA * tamanho(el));
}
// põe o topo da maiúscula de "el" a razao x (maior vão entre linhas dos dois) abaixo da tinta de "acima":
// entre dois blocos sempre mais espaço do que entre as linhas de cada um
function abaixo(el, acima, razao) {
  const alvo = fimDaTinta(acima) + razao * Math.max(vaoDe(acima), vaoDe(el));
  el.style.marginTop = (parseFloat(getComputedStyle(el).marginTop) + alvo - topoDaMaiuscula(linhas(el)[0], tamanho(el))) + "px";
}

// cada pedaço de texto visível com a cor e o tamanho dele, para a conferência de contraste
function trechos() {
  const out = [];
  const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  for (let n = w.nextNode(); n; n = w.nextNode()) {
    if (!n.textContent.trim()) continue;
    const el = n.parentElement, cs = getComputedStyle(el);
    const r = document.createRange();
    r.selectNodeContents(n);
    const caixas = [...r.getClientRects()].filter(q => q.width >= 1).map(q => [q.left, q.top, q.width, q.height]);
    const dono = el.closest("[data-id]");
    out.push({id: dono ? dono.dataset.id : el.tagName.toLowerCase(), cor: cs.color, fs: parseFloat(cs.fontSize),
              peso: parseInt(cs.fontWeight), caixas});
  }
  return out;
}
// espera o navegador pintar um quadro novo: sem isso a foto da tela pode sair com o estado anterior
function quadroNovo() { return new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r))); }
async function esconderTexto() { document.body.classList.add("sem-texto"); await quadroNovo(); }
// mostra só as letras do i-ésimo [data-id]; o resto fica transparente (fundo e caixas continuam)
async function soOTexto(i) {
  document.body.classList.remove("sem-texto");
  document.body.classList.add("so-um");
  for (const el of document.querySelectorAll(".este")) el.classList.remove("este");
  document.querySelectorAll("[data-id]")[i].classList.add("este");
  await quadroNovo();
}
// cada texto do slide, com o vão entre as próprias linhas (entrelinha menos a altura da maiúscula)
function elementos() {
  return [...document.querySelectorAll("[data-id]")].map((el, i) => {
    const cs = getComputedStyle(el), fs = parseFloat(cs.fontSize);
    const lh = cs.lineHeight === "normal" ? (SUBIDA + DESCIDA) * fs : parseFloat(cs.lineHeight);
    const r = el.getBoundingClientRect();
    // folga: quanto a tinta pode sair da caixa do elemento. A área da fonte passa da linha quando a entrelinha é menor
    // que ela, e a letra passa da área da fonte no máximo o que a própria fonte diz
    const sobra = Math.max(0, ((SUBIDA + DESCIDA) * fs - lh) / 2);
    return {i, id: el.dataset.id, texto: el.textContent.trim() !== "", fs, vao: lh - MAIUSCULA * fs, fundo: temFundo(el),
            caixa: [r.left, r.top, r.right, r.bottom],
            folga: [PASSA_LADO * fs, sobra + PASSA_CIMA * fs, PASSA_LADO * fs, sobra + PASSA_BAIXO * fs]};
  }).filter(e => e.texto);
}

// linha de título ou pedido com uma palavra só (viúva). Palavra partida pelo *destaque* conta como uma.
function viuvas() {
  const out = [];
  for (const el of document.querySelectorAll('[data-id="titulo"], [data-id="pedido"]')) {
    const pal = [];
    const w = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
    for (let n = w.nextNode(); n; n = w.nextNode()) {
      const re = /\S+/g; let m;
      while ((m = re.exec(n.textContent))) {
        const r = document.createRange(); r.setStart(n, m.index); r.setEnd(n, m.index + m[0].length);
        const q = r.getClientRects()[0]; if (q) pal.push({t: m[0], top: Math.round(q.top), l: q.left, r: q.right});
      }
    }
    const lin = [];
    for (const p of pal) {
      const L = lin.find(x => Math.abs(x.top - p.top) < 4);
      if (!L) lin.push({top: p.top, n: 1, r: p.r, txt: [p.t]});
      else { if (p.l - L.r >= 2) L.n++; L.r = Math.max(L.r, p.r); L.txt.push(p.t); }
    }
    lin.sort((a, b) => a.top - b.top);
    if (lin.length > 1) lin.forEach((L, k) => { if (L.n === 1) out.push({id: el.dataset.id, palavra: L.txt.join(""), ultima: k === lin.length - 1}); });
  }
  return out;
}

async function medir() {
  await document.fonts.ready;
  const imagens = [];
  for (const im of document.images) {
    let ok = true;
    try { await im.decode(); } catch (e) { ok = false; }
    imagens.push({src: im.getAttribute("src"), ok: ok && im.naturalWidth > 0, w: im.naturalWidth, h: im.naturalHeight});
  }
  if (typeof ajustar === "function") ajustar();
  const fontes = [];
  for (const el of document.querySelectorAll("[data-id]")) {
    if (!el.textContent.trim()) continue;
    const cs = getComputedStyle(el);
    let usadas = [];
    try {
      usadas = await document.fonts.load(cs.fontWeight + " " + cs.fontSize + ' "Inter Arrasta"', el.textContent);
    } catch (e) {
      usadas = [];  // arquivo da fonte não abriu: conta como não carregada
    }
    fontes.push({id: el.dataset.id, faces: usadas.length, carregadas: usadas.filter(f => f.status === "loaded").length,
                 familia: cs.fontFamily.startsWith('"Inter Arrasta"')});
  }
  // cada caixa [data-caixa] tem limites; o que está dentro dela ([data-id]) não pode passar deles
  const caixas = [...document.querySelectorAll("[data-caixa]")].map(z => {
    const zr = z.getBoundingClientRect();
    const lim = {top: zr.top, bottom: zr.bottom, left: zr.left, right: zr.right};
    for (const k of ["top", "bottom"]) if (z.dataset[k] !== undefined) lim[k] = parseFloat(z.dataset[k]);
    const filhos = [...z.querySelectorAll("[data-id]")].map(el => {
      const b = el.getBoundingClientRect(), cs = getComputedStyle(el);
      return {id: el.dataset.id, top: b.top - parseFloat(cs.marginTop), bottom: b.bottom + parseFloat(cs.marginBottom),
              left: b.left, right: b.right, sw: el.scrollWidth, cw: el.clientWidth};
    });
    return {id: z.dataset.caixa, ...lim, filhos};
  });
  return {
    caixas: caixas,
    fontes: fontes,
    imagens: imagens,
    canvas: [window.innerWidth, window.innerHeight],
    texto: document.body.innerText,
    trechos: trechos(),
    elementos: elementos(),
    viuvas: viuvas(),
  };
}
