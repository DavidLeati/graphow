/**
 * Caixa de propostas fora do Goal: o que a tela sabe dizer sem tocar o DOM.
 *
 * Uma descoberta que não atende a critério de aceite nenhum não vira Task: o
 * agente a deixa como proposta, e quem decide é a pessoa, que a aceita ou a
 * descarta. Aqui ficam o agrupamento por Projeto, o corpo da decisão e o HTML
 * da caixa, separados da vista para o `node --test` exercitá-los. Aceitar não
 * cria Task nenhuma: só fecha a proposta; o trabalho, se vier, nasce de um Goal
 * que a pessoa escopa.
 */
import { escapeHtml } from "./dom.js";
import { icone } from "./icones.js";

export const DECISOES = [
  { status: "aceita", rotulo: "Aceitar", dica: "Aceitar a proposta: ela deixa a caixa. Não cria Task; o trabalho nasce de um Goal que você escopa.", icone: "check" },
  { status: "descartada", rotulo: "Descartar", dica: "Descartar a proposta: ela deixa a caixa.", icone: "x" },
];

const SEM_PROJETO = "Sem Projeto";

/** O pedido de decisão que o servidor aceita; o autor e o papel são do servidor, nunca do corpo. */
export function corpoDaDecisao(idProposta, status, ramoId) {
  return { id_proposta: idProposta, status, ramo_id: ramoId };
}

/** Dos mais antigos aos mais novos pela posição no log; no empate, o id. */
export function ordenarPropostas(propostas) {
  return [...propostas].sort((a, b) => (a.seq_criacao - b.seq_criacao) || a.id.localeCompare(b.id));
}

/** As propostas agrupadas por Projeto, os grupos em ordem alfabética e o "Sem Projeto" por último. */
export function agruparPorProjeto(propostas) {
  const grupos = new Map();
  for (const proposta of ordenarPropostas(propostas)) {
    const chave = proposta.projeto_id || "";
    if (!grupos.has(chave)) grupos.set(chave, { projeto_id: chave, rotulo: proposta.projeto_rotulo || proposta.projeto_id || SEM_PROJETO, itens: [] });
    grupos.get(chave).itens.push(proposta);
  }
  return [...grupos.values()].sort((a, b) => Number(!a.projeto_id) - Number(!b.projeto_id) || a.rotulo.localeCompare(b.rotulo));
}

/** Quantas propostas aguardam, em uma frase. */
export function resumoDaCaixa(propostas) {
  if (propostas.length === 0) return "Nenhuma proposta aberta.";
  return propostas.length === 1 ? "1 proposta aberta." : `${propostas.length} propostas abertas.`;
}

/** Quem trouxe a proposta, para a pessoa saber se foi agente. */
export function autoria(proposta) {
  if (!proposta.autor) return "";
  return proposta.papel ? `${proposta.autor} (${proposta.papel})` : proposta.autor;
}

function htmlDaOrigem(origem) {
  return `<button class="memoria-origem" data-ir="${escapeHtml(origem.id)}" title="${escapeHtml(`${origem.tipo || "nó"} · ${origem.id}`)}">${icone("corner-down-right", { tamanho: 11 })}${escapeHtml(origem.rotulo || origem.id)}</button>`;
}

function htmlDasDecisoes(proposta) {
  return DECISOES.map((decisao) => `<button class="arvore-acao" data-decidir="${decisao.status}" data-proposta="${escapeHtml(proposta.id)}" title="${escapeHtml(decisao.dica)}">${icone(decisao.icone, { tamanho: 13 })}</button>`).join("");
}

/** Uma proposta: o texto, de onde veio, quem a trouxe e os botões de aceitar e descartar. */
export function htmlDaProposta(proposta, { viajando = false } = {}) {
  const dica = `${proposta.id} · log #${proposta.seq_criacao}${autoria(proposta) ? ` · ${autoria(proposta)}` : ""}`;
  const sessao = proposta.sessao_id ? `<button class="memoria-origem" data-ir="${escapeHtml(proposta.sessao_id)}" title="Sessão que a propôs">${icone("folder-clock", { tamanho: 11 })}${escapeHtml(proposta.sessao_id)}</button>` : "";
  return `
    <div class="memoria-item proposta-item" data-ir="${escapeHtml(proposta.id)}" title="${escapeHtml(dica)}">
      <div class="memoria-item-topo">
        <span class="arvore-icone">${icone("inbox", { tamanho: 14 })}</span>
        <span class="memoria-afirmacao">${escapeHtml(proposta.rotulo)}</span>
        ${viajando ? "" : htmlDasDecisoes(proposta)}
      </div>
      <div class="memoria-meta">${(proposta.origens || []).map(htmlDaOrigem).join("")}${sessao}</div>
    </div>`;
}

/** Uma seção por Projeto, com o contador; fechada quando a pessoa a recolheu. */
export function htmlDoGrupo(grupo, { viajando = false, fechados = new Set() } = {}) {
  const aberto = !fechados.has(grupo.projeto_id);
  return `
    <details class="secao" data-secao="${escapeHtml(grupo.projeto_id)}" ${aberto ? "open" : ""}>
      <summary class="secao-titulo">${icone("chevron-right", { tamanho: 14, classe: "secao-seta" })}<span>${escapeHtml(grupo.rotulo)}</span><span class="contador">${grupo.itens.length}</span></summary>
      <div class="secao-corpo">${grupo.itens.map((proposta) => htmlDaProposta(proposta, { viajando })).join("")}</div>
    </details>`;
}

/** A caixa inteira; sem proposta, a frase que explica o que ela é. */
export function htmlDaCaixa(propostas, opcoes = {}) {
  if (propostas.length === 0) {
    return `<div class="painel-vazio">${icone("inbox", { tamanho: 22 })}<span>Nenhuma proposta aberta. Quando uma descoberta não atender a critério de aceite algum, o agente a deixa aqui para você decidir.</span></div>`;
  }
  return `<div class="memoria">${agruparPorProjeto(propostas).map((grupo) => htmlDoGrupo(grupo, opcoes)).join("")}</div>`;
}
