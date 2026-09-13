/**
 * Utilitários de DOM compartilhados pela moldura da interface.
 *
 * Cada painel escapava HTML com a própria cópia de `escapeHtml`, e cada cópia
 * esquecia uma aspa diferente. Um rótulo com `"` dentro de um atributo `title`
 * quebrava o HTML do card. Aqui fica a versão que escapa as cinco.
 */

export function escapeHtml(valor) {
  if (valor === null || valor === undefined) return "";
  return String(valor)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

/** Cria um elemento a partir de um trecho de HTML com um único nó raiz. */
export function elemento(html) {
  const molde = document.createElement("template");
  molde.innerHTML = html.trim();
  return molde.content.firstElementChild;
}

export function debounce(funcao, esperaMs) {
  let temporizador = null;
  const chamada = (...argumentos) => {
    clearTimeout(temporizador);
    temporizador = setTimeout(() => funcao(...argumentos), esperaMs);
  };
  chamada.cancelar = () => clearTimeout(temporizador);
  return chamada;
}

/**
 * Preferências da interface ficam no navegador. O acesso ao localStorage lança
 * em janela privada e em navegador que bloqueia dados do site; uma preferência
 * perdida é aceitável, uma tela que não abre por causa dela não é.
 */
export function lerPreferencia(chave, padrao) {
  try {
    const bruto = localStorage.getItem(`graphow_${chave}`);
    return bruto === null ? padrao : JSON.parse(bruto);
  } catch (erro) {
    return padrao;
  }
}

export function gravarPreferencia(chave, valor) {
  try {
    localStorage.setItem(`graphow_${chave}`, JSON.stringify(valor));
  } catch (erro) {
    // Sem armazenamento a preferência vale só para esta aba, e tudo bem.
  }
}

/** Destaca as ocorrências do termo num texto já escapado para HTML. */
export function destacarTermo(texto, termo) {
  const seguro = escapeHtml(texto);
  const alvo = (termo || "").trim();
  if (!alvo) return seguro;
  const padrao = new RegExp(`(${escapeHtml(alvo).replace(/[.*+?^${}()|[\]\\]/g, "\\$&")})`, "gi");
  return seguro.replace(padrao, '<mark class="realce-busca">$1</mark>');
}

/** Copia texto para a área de transferência, devolvendo se deu certo. */
export async function copiarTexto(texto) {
  try {
    await navigator.clipboard.writeText(texto);
    return true;
  } catch (erro) {
    return false;
  }
}

/** Indica se o foco está num campo de texto, onde atalhos de uma tecla não valem. */
export function focoEmCampoDeTexto() {
  const ativo = document.activeElement;
  if (!ativo) return false;
  return ativo.tagName === "INPUT" || ativo.tagName === "TEXTAREA" || ativo.tagName === "SELECT" || ativo.isContentEditable;
}
