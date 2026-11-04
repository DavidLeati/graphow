/**
 * O bloco "Rastro" do inspetor de um Criterio, sem DOM: a leitura de
 * `/api/rastro?criterio=<id>` (orquestrador/rastro.py, o mesmo dado do
 * `graphow orquestrar --rastro`) vira HTML em quatro partes: os testes que o
 * provam com o commit do aceite, as fatias que o cobrem com o commit de cada
 * uma, a verificação que o julgou por último com o commit e a conferência dela
 * na ponta (a `marca`, o mesmo texto da vista e do `--rastro`: o motivo da sem
 * âncora e da não conferida), e os achados que o ferem com o estado. O
 * critério retirado pelo humano vem com a chamada da retirada e o motivo.
 * Testado por `node --test` em tests/web/js/rastro_do_criterio.test.mjs.
 */
import { escapeHtml } from "./dom.js";
import { icone } from "./icones.js";

const curto = (commit) => (commit ? escapeHtml(String(commit).slice(0, 12)) : "-");

function parte(rotulo, itens, vazio) {
  const corpo = itens.length ? `<ul class="escopo-linhas">${itens.map((item) => `<li>${item}</li>`).join("")}</ul>` : `<div class="secao-vazia">${vazio}</div>`;
  return `<div class="bloco-campo mod-coluna"><span class="bloco-campo-rotulo">${rotulo}</span>${corpo}</div>`;
}

function provas(criterio) {
  const testes = (criterio.testes || []).map((t) => `<code>${escapeHtml(t.arquivo)}::${escapeHtml(t.nome)}</code>`);
  const checagem = (criterio.checagem || []).map((item) => `Checagem: ${escapeHtml(item)}`);
  return [...testes, ...checagem, ...(criterio.ja_atendido ? [`Já atendido: ${escapeHtml(criterio.ja_atendido)}`] : [])];
}

function fatia(f) {
  const corrige = f.corrige ? `, corrige ${escapeHtml(f.corrige)}` : "";
  return `${escapeHtml(f.codigo)} em <code>${curto(f.commit)}</code> (${escapeHtml(f.status)}${corrige})`;
}

function atestado(a) {
  if (!a) return [];
  const texto = a.conferencia?.marca || a.conferencia?.rotulo;
  const marca = a.conferencia ? ` <span data-conferencia="${escapeHtml(a.conferencia.estado)}">[${escapeHtml(texto)}]</span>` : "";
  return [`${escapeHtml(a.verificacao)} (${escapeHtml(a.tipo || "-")}, ${escapeHtml(a.marco || "-")}): ${escapeHtml(a.veredito)} em <code>${curto(a.commit)}</code>${marca}`];
}

function achado(x) {
  return `${escapeHtml(x.titulo)} (${escapeHtml(x.gravidade)}, ${escapeHtml(x.estado)}) <code>${escapeHtml(x.id)}</code>`;
}

function retirada(r) {
  if (!r) return "";
  const por = r.por ? `, por ${escapeHtml(r.por)}` : "";
  return `<div class="chamada mod-aviso" data-rastro="retirado">${icone("alert-triangle", { tamanho: 14 })}<span>Retirado pelo humano (${escapeHtml(r.decisao || "")}${por}): ${escapeHtml(r.motivo || "")}</span></div>`;
}

/** O bloco do critério da resposta, ou a frase de quando o Criterio não está no plano de um Goal do orquestrador. */
export function htmlDoRastro(resposta) {
  const criterio = (resposta?.criterios || [])[0];
  if (!criterio) return `<div class="bloco-nota">Sem rastro: este Criterio não está no plano de um Goal do orquestrador.</div>`;
  const aceite = criterio.commit_do_aceite ? ` (aceite em <code>${curto(criterio.commit_do_aceite)}</code>)` : "";
  return `
    <div class="bloco-campo mod-coluna" data-rastro="criterio">
      <span class="bloco-campo-rotulo">${icone("route", { tamanho: 14 })} Rastro no Goal ${escapeHtml(resposta.goal)}</span>
      ${retirada(criterio.retirada)}
      ${parte(`Testes${aceite}`, provas(criterio), "Nenhum ainda.")}
      ${parte("Fatias", (criterio.fatias || []).map(fatia), "Nenhuma.")}
      ${parte("Verificação", atestado(criterio.atestado), "Nenhuma o julgou.")}
      ${parte("Achados", (criterio.achados || []).map(achado), "Nenhum.")}
    </div>`;
}

/** A frase do bloco quando a leitura falha. */
export function htmlDoRastroIndisponivel(mensagem) {
  return `<div class="bloco-nota">${escapeHtml(mensagem || "Não foi possível ler o rastro deste Criterio.")}</div>`;
}
