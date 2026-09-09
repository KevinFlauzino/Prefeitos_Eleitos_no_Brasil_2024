"use strict";

const $ = (sel) => document.querySelector(sel);
const el = (sel) => document.querySelector(sel);

let estado = {
  recurso: null,
  colunas: [],
  linhas: [],
  stats: [],
};

// ---------------------------------------------------------------------------
// Health check
// ---------------------------------------------------------------------------
async function checarSaude() {
  const pill = el("#healthPill");
  try {
    const r = await fetch("/api/health");
    const j = await r.json();
    if (j.ok) {
      pill.textContent = `API online · ${j.body.version || "ok"} · ${j.elapsed_s}s`;
      pill.className = "pill ok";
    } else {
      pill.textContent = `API instável (HTTP ${j.status || "?"})`;
      pill.className = "pill warn";
    }
  } catch (e) {
    pill.textContent = "API inacessível";
    pill.className = "pill bad";
  }
}

// ---------------------------------------------------------------------------
// Seleção de endpoint
// ---------------------------------------------------------------------------
function selecionarEndpoint(btn) {
  document.querySelectorAll(".endpoint").forEach((b) => b.classList.remove("active"));
  btn.classList.add("active");

  estado.recurso = btn.dataset.recurso;
  el("#welcome").classList.add("hidden");
  el("#panel").classList.remove("hidden");
  el("#panelTitle").textContent = btn.querySelector(".ep-title").textContent;
  el("#panelPath").textContent = `/v1/${estado.recurso}`;

  // links de download
  el("#dlJson").href = `/api/download?recurso=${estado.recurso}&format=json`;
  el("#dlCsv").href = `/api/download?recurso=${estado.recurso}&format=csv`;
  el("#dlXlsx").href = `/api/download?recurso=${estado.recurso}&format=xlsx`;

  // limpa
  esconderResultados();
}

function esconderResultados() {
  el("#metaCards").classList.add("hidden");
  el("#tabs").classList.add("hidden");
  el("#error").classList.add("hidden");
  ["dados", "colunas", "grafico"].forEach((t) => el(`#tab-${t}`).classList.add("hidden"));
  el("#dataTable").innerHTML = "";
}

// ---------------------------------------------------------------------------
// Carregar prévia
// ---------------------------------------------------------------------------
async function carregarPrevia() {
  if (!estado.recurso) return;
  const limit = el("#limit").value;

  esconderResultados();
  el("#loader").classList.remove("hidden");
  el("#loaderText").textContent =
    estado.recurso === "transacoes"
      ? "Consultando /v1/transacoes (streaming das primeiras linhas)…"
      : "Consultando a API…";
  el("#btnPreview").disabled = true;

  try {
    const r = await fetch(`/api/preview?recurso=${estado.recurso}&limit=${limit}`);
    const j = await r.json();
    if (!r.ok) {
      mostrarErro(j);
      return;
    }
    estado.colunas = j.colunas;
    estado.linhas = j.linhas;
    estado.stats = j.stats;
    renderMeta(j.meta, j);
    renderTabela(j);
    renderColunas(j.stats);
    prepararGrafico(j.stats);
    el("#tabs").classList.remove("hidden");
    ativarAba("dados");
  } catch (e) {
    mostrarErro({ erro: String(e) });
  } finally {
    el("#loader").classList.add("hidden");
    el("#btnPreview").disabled = false;
  }
}

function mostrarErro(j) {
  const box = el("#error");
  let txt = j.erro || "Erro desconhecido";
  if (j.meta && j.meta.x_request_id) txt += `\nX-Request-Id: ${j.meta.x_request_id}`;
  if (j.corpo) txt += `\n\n${j.corpo}`;
  box.textContent = txt;
  box.classList.remove("hidden");
}

// ---------------------------------------------------------------------------
// Metadados
// ---------------------------------------------------------------------------
function renderMeta(meta, j) {
  const cacheClass =
    meta.x_cache === "HIT" ? "tag-hit" : meta.x_cache === "MISS" ? "tag-miss" : "tag-stale";
  const cards = [
    { k: "Status", v: meta.status, cls: "" },
    { k: "Tempo", v: `${meta.elapsed_s ?? "?"} s`, cls: "" },
    { k: "Cache", v: meta.x_cache || "—", cls: `small ${cacheClass}` },
    { k: "Idade do cache", v: meta.x_cache_age != null ? `${meta.x_cache_age}s` : "—", cls: "small" },
    { k: "Gerado em", v: fmtData(meta.x_data_generated_at), cls: "small" },
    { k: "Linhas na prévia", v: j.linhas_retornadas + (j.truncado ? "+" : ""), cls: "" },
    { k: "Colunas", v: j.colunas.length, cls: "" },
    { k: "Request-Id", v: meta.x_request_id || "—", cls: "small" },
  ];
  el("#metaCards").innerHTML = cards
    .map(
      (c) =>
        `<div class="meta-card"><div class="k">${c.k}</div><div class="v ${c.cls}">${c.v}</div></div>`
    )
    .join("");
  el("#metaCards").classList.remove("hidden");
}

function fmtData(iso) {
  if (!iso) return "—";
  try {
    const d = new Date(iso);
    return d.toLocaleString("pt-BR");
  } catch {
    return iso;
  }
}

// ---------------------------------------------------------------------------
// Tabela de dados
// ---------------------------------------------------------------------------
function renderTabela(j) {
  const numericas = new Set(
    j.stats.filter((s) => s.tipo === "numerica").map((s) => s.nome)
  );
  const thead = `<thead><tr>${j.colunas
    .map((c) => `<th>${escapar(c)}</th>`)
    .join("")}</tr></thead>`;
  const tbody =
    "<tbody>" +
    j.linhas
      .map(
        (linha) =>
          "<tr>" +
          j.colunas
            .map((c, i) => {
              const cls = numericas.has(c) ? "num" : "";
              return `<td class="${cls}">${escapar(linha[i] ?? "")}</td>`;
            })
            .join("") +
          "</tr>"
      )
      .join("") +
    "</tbody>";
  el("#dataTable").innerHTML = thead + tbody;

  const info = `Mostrando ${j.linhas_retornadas} linha(s)` +
    (j.truncado ? " (truncado — há mais dados no dataset completo)." : ".");
  el("#tableInfo").textContent = info;
}

// ---------------------------------------------------------------------------
// Colunas e estatísticas
// ---------------------------------------------------------------------------
function renderColunas(stats) {
  el("#colsGrid").innerHTML = stats
    .map((s) => {
      let corpo;
      if (s.tipo === "numerica") {
        corpo = `<ul class="col-stats">
          <li><span>mín</span><span>${fmtNum(s.min)}</span></li>
          <li><span>máx</span><span>${fmtNum(s.max)}</span></li>
          <li><span>média</span><span>${fmtNum(s.media)}</span></li>
          <li><span>soma</span><span>${fmtNum(s.soma)}</span></li>
          <li><span>distintos</span><span>${s.distintos}</span></li>
          <li><span>vazios</span><span>${s.vazios}</span></li>
        </ul>`;
      } else {
        const maxc = s.top && s.top.length ? s.top[0].contagem : 1;
        const tops = (s.top || [])
          .map((t) => {
            const w = Math.max(4, Math.round((t.contagem / maxc) * 100));
            return `<li>
              <span class="top-label" title="${escapar(t.valor)}">${escapar(t.valor)}</span>
              <span class="top-bar" style="width:${w}px"></span>
              <span class="top-count">${t.contagem}</span>
            </li>`;
          })
          .join("");
        corpo = `<div style="font-size:12px;color:var(--text-dim);margin:8px 0 4px">
            ${s.distintos} valores distintos · ${s.vazios} vazios</div>
          <ul class="top-list">${tops}</ul>`;
      }
      return `<div class="col-card">
        <h4>${escapar(s.nome)}</h4>
        <span class="col-type ${s.tipo}">${s.tipo}</span>
        ${corpo}
      </div>`;
    })
    .join("");
}

// ---------------------------------------------------------------------------
// Gráfico (canvas puro)
// ---------------------------------------------------------------------------
function prepararGrafico(stats) {
  const sel = el("#chartCol");
  sel.innerHTML = stats
    .map((s, i) => `<option value="${i}">${escapar(s.nome)} (${s.tipo})</option>`)
    .join("");
  sel.onchange = () => desenharGrafico(stats[sel.value]);
  if (stats.length) desenharGrafico(stats[0]);
}

function desenharGrafico(stat) {
  const canvas = el("#chart");
  const ctx = canvas.getContext("2d");
  const W = canvas.width, H = canvas.height;
  ctx.clearRect(0, 0, W, H);

  let labels = [], valores = [];
  if (stat.tipo === "categorica") {
    (stat.top || []).forEach((t) => {
      labels.push(t.valor);
      valores.push(t.contagem);
    });
  } else {
    // histograma da coluna numérica sobre as linhas carregadas
    const idx = estado.colunas.indexOf(stat.nome);
    const nums = estado.linhas
      .map((l) => parseNum(l[idx]))
      .filter((x) => x !== null);
    if (!nums.length) return desenharVazio(ctx, W, H);
    const min = Math.min(...nums), max = Math.max(...nums);
    const bins = 12;
    const largura = (max - min) / bins || 1;
    const contagem = new Array(bins).fill(0);
    nums.forEach((v) => {
      let b = Math.floor((v - min) / largura);
      if (b >= bins) b = bins - 1;
      if (b < 0) b = 0;
      contagem[b]++;
    });
    valores = contagem;
    labels = contagem.map((_, i) => fmtNum(min + i * largura, true));
  }

  if (!valores.length) return desenharVazio(ctx, W, H);

  const padL = 48, padR = 20, padT = 20, padB = 70;
  const cw = W - padL - padR, ch = H - padT - padB;
  const maxV = Math.max(...valores);
  const n = valores.length;
  const gap = 8;
  const bw = (cw - gap * (n - 1)) / n;

  // eixo Y (grade)
  ctx.strokeStyle = "#2a3140";
  ctx.fillStyle = "#9aa7b8";
  ctx.font = "11px system-ui";
  ctx.textAlign = "right";
  const ticks = 4;
  for (let i = 0; i <= ticks; i++) {
    const y = padT + ch - (ch * i) / ticks;
    ctx.beginPath();
    ctx.moveTo(padL, y);
    ctx.lineTo(W - padR, y);
    ctx.stroke();
    ctx.fillText(Math.round((maxV * i) / ticks).toString(), padL - 6, y + 3);
  }

  // barras
  const grad = ctx.createLinearGradient(0, padT, 0, padT + ch);
  grad.addColorStop(0, "#57d3ac");
  grad.addColorStop(1, "#2ea88a");
  valores.forEach((v, i) => {
    const bh = maxV ? (v / maxV) * ch : 0;
    const x = padL + i * (bw + gap);
    const y = padT + ch - bh;
    ctx.fillStyle = grad;
    roundRect(ctx, x, y, bw, bh, 4);
    ctx.fill();

    // rótulo do eixo X
    ctx.save();
    ctx.translate(x + bw / 2, padT + ch + 10);
    ctx.rotate(-Math.PI / 4);
    ctx.fillStyle = "#9aa7b8";
    ctx.textAlign = "right";
    const lab = String(labels[i]).slice(0, 16);
    ctx.fillText(lab, 0, 0);
    ctx.restore();
  });
}

function desenharVazio(ctx, W, H) {
  ctx.fillStyle = "#9aa7b8";
  ctx.font = "14px system-ui";
  ctx.textAlign = "center";
  ctx.fillText("Sem dados numéricos para plotar.", W / 2, H / 2);
}

function roundRect(ctx, x, y, w, h, r) {
  if (h <= 0) return;
  r = Math.min(r, w / 2, h / 2);
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath();
}

// ---------------------------------------------------------------------------
// Abas
// ---------------------------------------------------------------------------
function ativarAba(nome) {
  document.querySelectorAll(".tab").forEach((t) =>
    t.classList.toggle("active", t.dataset.tab === nome)
  );
  ["dados", "colunas", "grafico"].forEach((t) =>
    el(`#tab-${t}`).classList.toggle("hidden", t !== nome)
  );
}

// ---------------------------------------------------------------------------
// Utilidades
// ---------------------------------------------------------------------------
function escapar(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}
function parseNum(v) {
  if (v == null || v === "") return null;
  let n = Number(v);
  if (!isNaN(n)) return n;
  n = Number(String(v).replace(/\./g, "").replace(",", "."));
  return isNaN(n) ? null : n;
}
function fmtNum(v, curto = false) {
  if (v == null) return "—";
  if (curto) {
    if (Math.abs(v) >= 1e6) return (v / 1e6).toFixed(1) + "M";
    if (Math.abs(v) >= 1e3) return (v / 1e3).toFixed(1) + "k";
    return Number.isInteger(v) ? v.toString() : v.toFixed(1);
  }
  return v.toLocaleString("pt-BR", { maximumFractionDigits: 2 });
}

// ---------------------------------------------------------------------------
// Eventos
// ---------------------------------------------------------------------------
document.querySelectorAll(".endpoint").forEach((btn) =>
  btn.addEventListener("click", () => selecionarEndpoint(btn))
);
el("#btnPreview").addEventListener("click", carregarPrevia);
document.querySelectorAll(".tab").forEach((t) =>
  t.addEventListener("click", () => ativarAba(t.dataset.tab))
);

checarSaude();
