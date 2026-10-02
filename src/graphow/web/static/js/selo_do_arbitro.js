/**
 * O selo "pelo árbitro": a marca discreta de um gesto que a política tirou do
 * humano. Uma Question respondida e um Aprendizado promovido guardam o papel de
 * quem os decidiu (`respondida_por_papel`, `promovido_por_papel`); quando é o
 * árbitro, a tela diz isso, com o autor na dica. O humano segue podendo
 * reabrir a dúvida ou retirar o alcance, como com qualquer outra decisão.
 */
import { escapeHtml } from "./dom.js";
import { icone } from "./icones.js";

export const PAPEL_DO_ARBITRO = "arbitro";

/** Verdadeiro quando o papel gravado no nó é o do árbitro. */
export function foiPeloArbitro(papel) {
  return papel === PAPEL_DO_ARBITRO;
}

/**
 * O selo, ou texto vazio quando o gesto não foi do árbitro. `acao` completa a
 * dica ("Respondida", "Promovido"); o autor entra nela quando se sabe quem foi.
 */
export function montarSeloDoArbitro(papel, autor, acao) {
  if (!foiPeloArbitro(papel)) return "";
  const quem = autor ? ` (${autor})` : "";
  return `<span class="selo-arbitro" title="${escapeHtml(`${acao} pelo árbitro${quem}`)}">${icone("shield", { tamanho: 11 })}pelo árbitro</span>`;
}

/** O rótulo do campo de resposta: "Resposta do árbitro" só enquanto a dúvida está respondida por ele. */
export function rotuloDaResposta(propriedades) {
  const peloArbitro = propriedades?.status === "respondida" && foiPeloArbitro(propriedades?.respondida_por_papel);
  return peloArbitro ? "Resposta do árbitro" : "Resposta humana";
}
