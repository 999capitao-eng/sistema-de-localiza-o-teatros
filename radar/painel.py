import json
from collections import defaultdict

from .config import WEB
from .contatos import criar_tabelas, norm_fone
from .db import conectar

ORDEM = {"whatsapp": 0, "celular": 1, "fixo": 2}

TEMPLATE = r'''<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Radar de Teatros - Contatos</title>
<style>
:root{color-scheme:light dark;--bg:#f6f7f9;--card:#fff;--txt:#1b1f24;--mut:#667085;--bd:#dfe3e8;--wa:#16a34a}
@media (prefers-color-scheme:dark){:root{--bg:#14171a;--card:#1d2125;--txt:#eceff1;--mut:#9aa4ad;--bd:#2c3238;--wa:#22c55e}}
*{box-sizing:border-box}
body{margin:0;font:16px/1.45 system-ui,sans-serif;background:var(--bg);color:var(--txt)}
header{position:sticky;top:0;background:var(--bg);padding:14px 16px;border-bottom:1px solid var(--bd);z-index:5}
h1{margin:0 0 10px;font-size:20px}
.linha{display:flex;gap:10px;flex-wrap:wrap;align-items:center}
input,select,textarea{font:inherit;padding:10px 12px;border:1px solid var(--bd);border-radius:8px;background:var(--card);color:var(--txt)}
#q{flex:1;min-width:220px;font-size:18px}
main{max-width:1000px;margin:0 auto;padding:16px}
details{margin-top:10px}
textarea{width:100%;min-height:90px}
.info{color:var(--mut);margin:4px 0 14px}
.card{background:var(--card);border:1px solid var(--bd);border-radius:12px;padding:14px;margin-bottom:12px}
.card h3{margin:0 0 4px;font-size:18px}
.mut{color:var(--mut);font-size:14px}
.tags{margin:8px 0;display:flex;gap:6px;flex-wrap:wrap}
.tag{font-size:13px;padding:2px 8px;border-radius:99px;border:1px solid var(--bd)}
.acoes{display:flex;gap:8px;flex-wrap:wrap;margin-top:10px;align-items:center}
.btn{display:inline-block;padding:8px 12px;border-radius:8px;border:1px solid var(--bd);background:var(--card);text-decoration:none;color:var(--txt);font-size:15px;cursor:pointer}
.btn.zap{background:var(--wa);border-color:var(--wa);color:#fff;font-weight:600}
.btn.zap.prov{opacity:.82}
.man{width:230px;padding:8px 10px}
</style>
</head>
<body>
<header>
  <h1>Radar de Teatros</h1>
  <div class="linha">
    <input id="q" type="search" list="cidades" placeholder="Digite a cidade (ex: Teresina) ou o nome do teatro" autofocus>
    <label><input type="checkbox" id="soNum"> só com telefone/WhatsApp</label>
    <select id="stF"></select>
  </div>
  <details>
    <summary>Mensagem padrão (pode editar)</summary>
    <p class="mut">Use {teatro} e {cidade}. Troque ____ pelo seu nome. Os botões só abrem o WhatsApp ou o e-mail: você aperta enviar.</p>
    <textarea id="msg"></textarea>
  </details>
</header>
<main>
  <div class="info" id="info"></div>
  <div id="lista"></div>
</main>
<datalist id="cidades"></datalist>
<script>
const DADOS = /*DADOS*/[];
const STATUS = [["novo","Novo"],["contatado","Contatado"],["respondeu","Respondeu"],["negociando","Negociando"],["fechado","Show fechado"],["descartado","Descartado"]];
const MSG_PADRAO = "Olá! Meu nome é ____ e produzo shows. Tenho interesse em apresentar um espetáculo no {teatro}, em {cidade}. Poderia me passar informações sobre pauta, valores e a capacidade da casa? Obrigado!";
const $ = id => document.getElementById(id);
const esc = s => String(s ?? "").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");
const norm = s => String(s || "").normalize("NFD").replace(/[\u0300-\u036f]/g,"").toLowerCase().trim();
const ler = (k, pad) => { try { const v = localStorage.getItem(k); return v ? JSON.parse(v) : pad; } catch (e) { return pad; } };
const guardar = (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) {} };
const chave = t => norm(t.nome) + "|" + norm(t.cidade);

let status = ler("radar_status2", {});
let manual = ler("radar_manual", {});
$("msg").value = ler("radar_msg", MSG_PADRAO);
$("stF").innerHTML = '<option value="">Todos os status</option>' + STATUS.map(s => `<option value="${s[0]}">${s[1]}</option>`).join("");

const contagem = {};
DADOS.forEach(t => { if (t.cidade) contagem[t.cidade] = (contagem[t.cidade] || 0) + 1; });
$("cidades").innerHTML = Object.keys(contagem).sort().map(c => `<option value="${esc(c)}">`).join("");

function fonesDe(t) {
  const lista = (t.contatos || []).filter(c => ["whatsapp","celular","fixo"].includes(c.t)).map(c => ({n: c.v, t: c.t, o: c.o}));
  (manual[chave(t)] || []).forEach(n => lista.push({n: n, t: "whatsapp", o: "colado por você"}));
  return lista;
}
function fmt(n) {
  if (!/^55\d{10,11}$/.test(n)) return n.startsWith("http") ? "(link)" : n;
  const r = n.slice(4);
  return "(" + n.slice(2, 4) + ") " + r.slice(0, r.length - 4) + "-" + r.slice(-4);
}
const achar = (t, tipo) => (t.contatos || []).find(c => c.t === tipo);

function card(t) {
  const msg = $("msg").value.replace(/\{teatro\}/g, t.nome).replace(/\{cidade\}/g, t.cidade || "sua cidade");
  const k = chave(t), fones = fonesDe(t);
  const zaps = fones.filter(f => f.t !== "fixo").slice(0, 3);
  const fixos = fones.filter(f => f.t === "fixo").slice(0, 2);
  const email = achar(t, "email"), insta = achar(t, "instagram"), face = achar(t, "facebook");
  const hrefZap = f => f.n.startsWith("http") ? f.n : "https://wa.me/" + f.n + "?text=" + encodeURIComponent(msg);
  const site = t.site ? (/^https?:\/\//i.test(t.site) ? t.site : "https://" + t.site) : null;
  const mapa = "https://www.google.com/maps/search/?api=1&query=" +
    (t.lat != null ? t.lat + "," + t.lon : encodeURIComponent(t.nome + " " + (t.cidade || "")));
  const google = "https://www.google.com/search?q=" + encodeURIComponent(t.nome + " " + (t.cidade || "") + " contato whatsapp");
  const atual = status[k] || "novo";
  const opts = STATUS.map(s => `<option value="${s[0]}"${s[0] === atual ? " selected" : ""}>${s[1]}</option>`).join("");
  const capa = t.capacidade ? "Capacidade: " + t.capacidade + " (confiança " + esc(t.confianca) + ")" : "Capacidade: sem dado";
  const link = (url, texto) => '<a class="btn" target="_blank" rel="noopener" href="' + esc(url) + '">' + texto + "</a>";
  return `<div class="card">
    <h3>${esc(t.nome)}</h3>
    <div class="mut">${esc(t.cidade || "cidade não informada")}${t.uf ? " - " + esc(t.uf) : ""}${t.endereco ? " · " + esc(t.endereco) : ""}</div>
    <div class="tags"><span class="tag">${capa}</span><span class="tag">${fones.length ? fones.length + " número(s) achado(s)" : "Nenhum número achado"}</span></div>
    <div class="acoes">
      ${zaps.map(f => `<a class="btn zap${f.t === "celular" ? " prov" : ""}" target="_blank" rel="noopener" href="${esc(hrefZap(f))}" title="${esc(f.o)}">WhatsApp ${esc(fmt(f.n))}</a>`).join("")}
      ${fixos.map(f => `<a class="btn" href="tel:+${esc(f.n)}" title="${esc(f.o)}">Ligar ${esc(fmt(f.n))}</a>`).join("")}
      ${email ? link("mailto:" + email.v + "?subject=" + encodeURIComponent("Proposta de show - " + t.nome) + "&body=" + encodeURIComponent(msg), "E-mail") : ""}
      ${insta ? link(insta.v, "Instagram") : ""}
      ${face ? link(face.v, "Facebook") : ""}
      ${site ? link(site, "Site") : ""}
      ${link(mapa, "Mapa")}
      ${link(google, "Buscar contato")}
    </div>
    ${zaps.some(f => f.t === "celular") ? '<div class="mut">Botão mais claro = celular achado em texto (provável WhatsApp). Passe o mouse para ver de onde veio.</div>' : ""}
    <div class="acoes">
      <input class="man" data-k="${esc(k)}" placeholder="Colar WhatsApp (ex: 86 99999-1111)">
      <button class="btn" data-salvar="${esc(k)}">Salvar número</button>
      <select data-k="${esc(k)}">${opts}</select>
    </div>
  </div>`;
}

function desenhar() {
  const q = norm($("q").value), soNum = $("soNum").checked, st = $("stF").value;
  const semCidade = DADOS.filter(t => !t.cidade).length;
  const comNum = DADOS.filter(t => fonesDe(t).length).length;
  if (!q) {
    $("info").textContent = DADOS.length + " teatros na base, " + comNum + " com número achado. Digite uma cidade para começar." +
      (semCidade ? " (" + semCidade + " ainda sem cidade: rode o comando cidades.)" : "");
    $("lista").innerHTML = "";
    return;
  }
  const lista = DADOS.filter(t => {
    if (!(norm(t.cidade).includes(q) || norm(t.nome).includes(q) || norm(t.uf) === q)) return false;
    if (soNum && !fonesDe(t).length) return false;
    if (st && (status[chave(t)] || "novo") !== st) return false;
    return true;
  });
  const peso = t => fonesDe(t).some(f => f.t !== "fixo") ? 2 : (fonesDe(t).length ? 1 : 0);
  lista.sort((a, b) => (peso(b) - peso(a)) || ((b.capacidade || 0) - (a.capacidade || 0)) || a.nome.localeCompare(b.nome));
  $("info").textContent = lista.length + " teatros encontrados, " + lista.filter(t => fonesDe(t).length).length + " com número." +
    (lista.length > 100 ? " Mostrando os 100 primeiros." : "");
  $("lista").innerHTML = lista.slice(0, 100).map(card).join("") || "<p>Nenhum teatro encontrado.</p>";
}

$("q").addEventListener("input", desenhar);
$("soNum").addEventListener("change", desenhar);
$("stF").addEventListener("change", desenhar);
$("msg").addEventListener("input", () => { guardar("radar_msg", $("msg").value); desenhar(); });
$("lista").addEventListener("change", e => {
  const k = e.target.dataset.k;
  if (k && e.target.tagName === "SELECT") { status[k] = e.target.value; guardar("radar_status2", status); }
});
$("lista").addEventListener("click", e => {
  const k = e.target.dataset.salvar;
  if (!k) return;
  const campo = e.target.parentElement.querySelector("input.man");
  let d = campo.value.replace(/\D/g, "").replace(/^0+/, "");
  if (d.length === 10 || d.length === 11) d = "55" + d;
  if (d.length < 12) { campo.value = ""; campo.placeholder = "Número inválido. Use DDD + número"; return; }
  manual[k] = (manual[k] || []).concat(d);
  guardar("radar_manual", manual);
  desenhar();
});
desenhar();
</script>
</body>
</html>
'''


def gerar():
    con = conectar()
    criar_tabelas(con)
    teatros = [dict(r) for r in con.execute(
        "SELECT id, nome, cidade, uf, lat, lon, capacidade, confianca, site, endereco "
        "FROM teatros ORDER BY uf, cidade, nome")]
    membros = defaultdict(list)
    for r in con.execute(
        "SELECT v.teatro_id, r.fonte, r.id_fonte, r.site, r.telefone "
        "FROM vinculos v JOIN registros r ON r.id = v.registro_id"
    ):
        membros[r["teatro_id"]].append(dict(r))
    guardados = defaultdict(list)
    for r in con.execute("SELECT chave, tipo, valor, origem FROM contatos"):
        guardados[r["chave"]].append(dict(r))
    con.close()

    for t in teatros:
        achados = {}

        def juntar(tipo, valor, origem):
            k = valor if tipo in ORDEM else tipo + "|" + valor
            atual = achados.get(k)
            if atual is None or ORDEM.get(tipo, 9) < ORDEM.get(atual["t"], 9):
                achados[k] = {"t": tipo, "v": valor, "o": origem}

        for m in membros[t["id"]]:
            chaves = [f"{m['fonte']}:{m['id_fonte']}"]
            if m["site"]:
                chaves.append(f"site:{m['site']}")
            for ch in chaves:
                for c in guardados.get(ch, []):
                    juntar(c["tipo"], c["valor"], c["origem"])
            for texto in (m["telefone"] or "").split(";"):
                r = norm_fone(texto)
                if r:
                    juntar(r[1], r[0], "cadastro " + m["fonte"])
        t["contatos"] = sorted(achados.values(), key=lambda c: ORDEM.get(c["t"], 9))[:10]

    dados = json.dumps(teatros, ensure_ascii=False).replace("</", "<\\/")
    destino = WEB / "sistema.html"
    destino.write_text(TEMPLATE.replace("/*DADOS*/[]", dados), encoding="utf-8")
    com_zap = sum(1 for t in teatros if any(c["t"] in ("whatsapp", "celular") for c in t["contatos"]))
    com_fone = sum(1 for t in teatros if any(c["t"] in ORDEM for c in t["contatos"]))
    print(f"[painel] {len(teatros)} teatros | {com_zap} com WhatsApp/celular | "
          f"{com_fone} com algum telefone")
    print(f"[painel] painel gerado em {destino}")
