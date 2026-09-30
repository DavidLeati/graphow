/**
 * Texto corrido de uma propriedade, formatado para leitura.
 *
 * A pergunta de uma dúvida chega como texto puro, com parágrafos, listas de
 * opções e nomes de arquivo entre crases. Num textarea tudo isso vira uma
 * parede de caracteres; aqui vira parágrafo, lista e código, sem aceitar HTML
 * nenhum do dado: o texto é escapado antes de qualquer marcação entrar.
 */
import { escapeHtml } from "./dom.js";

const ITEM_SOLTO = /^\s*[-*]\s+(.*)$/;
const ITEM_NUMERADO = /^\s*(\d+)[.)]\s+(.*)$/;

/** Crases viram `<code>` depois do escape, então o conteúdo delas também sai escapado. */
function formatarTrecho(linha) {
  return escapeHtml(linha).replace(/`([^`]+)`/g, "<code>$1</code>");
}

function lerItem(linha) {
  const numerado = ITEM_NUMERADO.exec(linha);
  if (numerado) return { lista: "ol", numero: Number(numerado[1]), texto: numerado[2] };
  const solto = ITEM_SOLTO.exec(linha);
  return solto ? { lista: "ul", texto: solto[1] } : null;
}

/**
 * Um bloco entre linhas em branco vira parágrafos e listas. Linhas seguidas
 * dentro de um parágrafo ficam como quebras, porque quem escreveu quis a quebra;
 * linha recuada logo abaixo de um item continua o item.
 */
function formatarBloco(linhas) {
  const partes = [];
  let atual = null;
  const fechar = () => {
    if (!atual) return;
    if (atual.tipo === "p") {
      partes.push(`<p>${atual.linhas.map(formatarTrecho).join("<br>")}</p>`);
    } else {
      const inicio = atual.tipo === "ol" && atual.inicio !== 1 ? ` start="${atual.inicio}"` : "";
      const itens = atual.itens.map((item) => `<li>${item.map(formatarTrecho).join("<br>")}</li>`);
      partes.push(`<${atual.tipo}${inicio}>${itens.join("")}</${atual.tipo}>`);
    }
    atual = null;
  };
  for (const linha of linhas) {
    const item = lerItem(linha);
    if (item) {
      if (atual?.tipo !== item.lista) {
        fechar();
        atual = { tipo: item.lista, inicio: item.numero, itens: [] };
      }
      atual.itens.push([item.texto]);
      continue;
    }
    if (atual && atual.tipo !== "p" && /^\s/.test(linha)) {
      atual.itens[atual.itens.length - 1].push(linha.trim());
      continue;
    }
    if (atual?.tipo !== "p") {
      fechar();
      atual = { tipo: "p", linhas: [] };
    }
    atual.linhas.push(linha.trim());
  }
  fechar();
  return partes.join("");
}

/** HTML seguro do texto: parágrafos, quebras, listas e código. Texto vazio devolve "". */
export function formatarTextoDeLeitura(texto) {
  const normalizado = String(texto ?? "").replace(/\r\n?/g, "\n");
  return normalizado
    .split(/\n[ \t]*\n/)
    .map((bloco) => bloco.split("\n").filter((linha) => linha.trim() !== ""))
    .filter((linhas) => linhas.length > 0)
    .map(formatarBloco)
    .join("");
}
