/**
 * A conferência da Evidence sobre código na hora da leitura, como o canvas a
 * manda em `no.conferencia` (orquestrador/conferencia_na_leitura.py): o
 * inspetor diz se a Evidence ainda vale na ponta da branch do Goal, com os
 * arquivos que mudaram desde o commit dela. A Evidence que não fala de código
 * vem sem conferência e não ganha chamada nenhuma.
 *
 * A sem âncora e a não conferida não têm texto fixo: o motivo que a leitura
 * manda diz por quê (gravada sem commit, o commit ou a árvore que não existe
 * mais no repositório, o clone do Goal que foi removido). Antes, toda sem
 * âncora dizia "gravada sem o commit", e a revisão rejeitada, que tem commit,
 * saía com um texto falso.
 */
import { escapeHtml } from "./dom.js";
import { icone } from "./icones.js";

const CHAMADAS = {
  vigente: { modo: "mod-info", icone: "circle-check", texto: "Vigente: os arquivos que ela afirma não mudaram desde o commit dela." },
  desatualizada: { modo: "mod-alerta", icone: "alert-triangle", texto: "Desatualizada: não vale como fato na ponta." },
  sem_ancora: { modo: "mod-aviso", icone: "help-circle", titulo: "Sem âncora" },
  nao_conferida: { modo: "mod-neutra", icone: "eye-off", titulo: "Não conferida" },
};

/** A chamada do inspetor para a conferência, ou texto vazio quando o nó não traz uma. */
export function htmlDaConferencia(conferencia) {
  const chamada = CHAMADAS[conferencia?.estado];
  if (!chamada) return "";
  const motivo = conferencia.motivo ? escapeHtml(conferencia.motivo) : "";
  const arquivos = (conferencia.arquivos || []).map((arquivo) => `<code>${escapeHtml(arquivo)}</code>`).join(", ");
  const abertura = chamada.texto || (motivo ? `${chamada.titulo}: ${motivo}.` : `${chamada.titulo}.`);
  const partes = [abertura, arquivos ? `Mudaram: ${arquivos}.` : "", chamada.texto && motivo ? `${motivo}.` : ""];
  return `<div class="chamada ${chamada.modo}" data-conferencia="${escapeHtml(conferencia.estado)}">${icone(chamada.icone, { tamanho: 14 })}<span>${partes.filter(Boolean).join(" ")}</span></div>`;
}
