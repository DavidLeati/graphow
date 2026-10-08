/**
 * Os dois gestos do humano sobre o escopo de um Goal, ligados ao DOM do inspetor:
 * aprovar o plano e responder ao desvio. Cada um escreve pelo servidor (que o passa
 * ao kernel sob a identidade da pessoa) e devolve o placar de depois, que o inspetor
 * redesenha. O que decide o texto e o corpo de cada pedido mora em `escopo_modelo.js`.
 */
import { api } from "./api.js";
import { corpoDaResposta, corpoDoAprovar, respostaValida } from "./escopo_modelo.js";
import { avisar } from "./modais.js";

/** Aprova o plano do Goal; devolve o placar de depois, ou null quando o servidor recusou. */
export async function aprovarPlano(idGoal, ramo) {
  const resposta = await api.aprovarPlano(corpoDoAprovar(idGoal, ramo));
  if (!resposta.sucesso) {
    avisar(resposta.mensagem || "Não foi possível aprovar o plano.", "erro");
    return null;
  }
  avisar(`Plano aprovado: versão ${resposta.recibo?.versao ?? ""}`.trim(), "info");
  return resposta;
}

/** Responde ao desvio com o texto e a raiz do formulário; devolve o placar de depois, ou null. */
export async function responderDesvio(idGoal, ramo, formulario) {
  const texto = formulario.querySelector("[data-escopo-resposta]")?.value;
  if (!respostaValida(texto)) {
    avisar("Escreva a resposta ao desvio antes de enviar.", "erro");
    return null;
  }
  const raiz = formulario.querySelector("[data-escopo-raiz]")?.value;
  const resposta = await api.responderDesvio(corpoDaResposta(idGoal, ramo, texto, raiz));
  if (!resposta.sucesso) {
    avisar(resposta.mensagem || "Não foi possível registrar a resposta.", "erro");
    return null;
  }
  avisar("Resposta ao desvio registrada", "info");
  return resposta;
}
