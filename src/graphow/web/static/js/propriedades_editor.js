/**
 * Tabela de propriedades de um nó.
 *
 * O inspetor antigo mostrava as propriedades como um JSON num textarea: editar a
 * descrição de uma tarefa exigia não quebrar vírgula nem aspa. Aqui cada chave
 * vira uma linha com ícone do tipo do valor e um editor do tamanho dele — texto
 * que cresce, número, liga-desliga — e só listas e objetos ficam em JSON.
 */
import { escapeHtml } from "./dom.js";
import { icone } from "./icones.js";

// Coordenadas pertencem ao arranjo do canvas, não ao conteúdo do nó.
export const CHAVES_OCULTAS = new Set(["pos_x", "pos_y", "x", "y", "tipo"]);

// Primeiro o que descreve o nó; depois quem mexeu; o resto em ordem alfabética.
const CHAVES_PRIORITARIAS = [
  "descricao", "conteudo", "criterio_pronto", "resultado", "observacao", "resposta",
  "assumida_por", "autor", "gerado_por", "fonte", "caminho_local", "formato", "data",
];

const ISO_DATA = /^\d{4}-\d{2}-\d{2}(T[\d:.]+([+-]\d{2}:\d{2}|Z)?)?$/;

export function ordenarChaves(chaves) {
  const peso = (chave) => {
    const posicao = CHAVES_PRIORITARIAS.indexOf(chave);
    return posicao < 0 ? CHAVES_PRIORITARIAS.length : posicao;
  };
  return [...chaves].sort((a, b) => peso(a) - peso(b) || a.localeCompare(b, "pt-BR"));
}

export function iconeDaPropriedade(chave, valor) {
  if (typeof valor === "boolean") return "toggle";
  if (typeof valor === "number") return "hash";
  if (Array.isArray(valor)) return "list";
  if (valor && typeof valor === "object") return "braces";
  const texto = String(valor ?? "");
  if (/^https?:\/\//.test(texto)) return "link";
  if (ISO_DATA.test(texto)) return "calendar";
  if (/caminho|path|arquivo/.test(chave)) return "folder";
  if (/autor|assumida|gerado_por|por$/.test(chave)) return "user";
  return texto.length > 60 ? "align-left" : "type";
}

/** Linha editável de uma propriedade. O tipo original do valor decide o editor. */
export function montarLinhaDePropriedade(chave, valor, { somenteLeitura = false } = {}) {
  const desabilitado = somenteLeitura ? "disabled" : "";
  const tipo = tipoDoValor(valor);
  // Texto longo e JSON ganham a largura toda, abaixo da chave: numa coluna de
  // 170 px uma descrição vira uma torre de palavras.
  const longo = tipo === "lista" || tipo === "objeto" || (tipo === "texto" && String(valor).length > 42);
  return `
    <div class="propriedade ${longo ? "mod-longo" : ""}" data-chave="${escapeHtml(chave)}" data-tipo-valor="${tipo}">
      <span class="propriedade-icone" title="${escapeHtml(tipoDoValor(valor))}">${icone(iconeDaPropriedade(chave, valor), { tamanho: 14 })}</span>
      <span class="propriedade-chave" title="${escapeHtml(chave)}">${escapeHtml(chave)}</span>
      <div class="propriedade-valor">${montarEditor(valor, desabilitado)}</div>
    </div>`;
}

function tipoDoValor(valor) {
  if (valor === null || valor === undefined) return "vazio";
  if (Array.isArray(valor)) return "lista";
  if (typeof valor === "object") return "objeto";
  return { boolean: "booleano", number: "numero" }[typeof valor] || "texto";
}

function montarEditor(valor, desabilitado) {
  const tipo = tipoDoValor(valor);
  if (tipo === "booleano") {
    return `<label class="alternador"><input type="checkbox" data-editor ${valor ? "checked" : ""} ${desabilitado}><span class="alternador-trilho"></span></label>`;
  }
  if (tipo === "numero") {
    return `<input type="number" step="any" class="entrada-propriedade" data-editor value="${escapeHtml(valor)}" ${desabilitado}>`;
  }
  if (tipo === "lista" || tipo === "objeto") {
    return `<textarea class="entrada-propriedade mod-json" data-editor rows="1" spellcheck="false" ${desabilitado}>${escapeHtml(JSON.stringify(valor, null, 2))}</textarea>`;
  }
  return `<textarea class="entrada-propriedade" data-editor rows="1" ${desabilitado}>${escapeHtml(valor ?? "")}</textarea>`;
}

/** Lê o valor editado de volta no tipo original. Lança se o JSON não fecha. */
export function lerValorDaLinha(linha) {
  const editor = linha.querySelector("[data-editor]");
  const tipo = linha.dataset.tipoValor;
  if (tipo === "booleano") return editor.checked;
  if (tipo === "numero") return editor.value === "" ? null : Number(editor.value);
  if (tipo === "lista" || tipo === "objeto") return JSON.parse(editor.value || (tipo === "lista" ? "[]" : "{}"));
  return editor.value;
}

/** Converte o texto digitado numa propriedade nova: número e booleano viram o que parecem. */
export function interpretarValorNovo(texto) {
  const limpo = texto.trim();
  if (limpo === "true" || limpo === "false") return limpo === "true";
  if (limpo !== "" && !Number.isNaN(Number(limpo))) return Number(limpo);
  if (/^[[{]/.test(limpo)) {
    try {
      return JSON.parse(limpo);
    } catch (erro) {
      return texto;
    }
  }
  return texto;
}

export function valoresIguais(a, b) {
  return JSON.stringify(a ?? null) === JSON.stringify(b ?? null);
}

/** Textarea que cresce com o conteúdo até um teto. */
export function ajustarAltura(textarea, teto = 260) {
  textarea.style.height = "auto";
  textarea.style.height = `${Math.min(teto, textarea.scrollHeight + 2)}px`;
}
