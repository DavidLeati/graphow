/**
 * A conferência da Evidence sobre código na hora da leitura, como o canvas a
 * manda em `no.conferencia` (orquestrador/conferencia_na_leitura.py): o
 * inspetor diz se a Evidence ainda vale na ponta da branch do Goal, com os
 * arquivos que mudaram desde o commit dela. A Evidence que não fala de código
 * vem sem conferência e não ganha chamada nenhuma.
 */
import { escapeHtml } from "./dom.js";
import { icone } from "./icones.js";

const CHAMADAS = {
  vigente: { modo: "mod-info", icone: "circle-check", texto: "Vigente: os arquivos que ela afirma não mudaram desde o commit dela." },
  desatualizada: { modo: "mod-alerta", icone: "alert-triangle", texto: "Desatualizada: não vale como fato na ponta." },
  sem_ancora: { modo: "mod-aviso", icone: "help-circle", texto: "Sem âncora: gravada sem o commit em que foi vista." },
  nao_conferida: { modo: "mod-neutra", icone: "eye-off", texto: "Não conferida: sem repositório git à mão." },
};

/** A chamada do inspetor para a conferência, ou texto vazio quando o nó não traz uma. */
export function htmlDaConferencia(conferencia) {
  const chamada = CHAMADAS[conferencia?.estado];
  if (!chamada) return "";
  const arquivos = (conferencia.arquivos || []).map((arquivo) => `<code>${escapeHtml(arquivo)}</code>`).join(", ");
  const partes = [chamada.texto, arquivos ? `Mudaram: ${arquivos}.` : "", conferencia.motivo ? `${escapeHtml(conferencia.motivo)}.` : ""];
  return `<div class="chamada ${chamada.modo}" data-conferencia="${escapeHtml(conferencia.estado)}">${icone(chamada.icone, { tamanho: 14 })}<span>${partes.filter(Boolean).join(" ")}</span></div>`;
}
