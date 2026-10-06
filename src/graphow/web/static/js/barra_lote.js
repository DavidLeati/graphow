/**
 * Barra de ações em lote, que surge no pé do canvas quando mais de um nó está
 * selecionado (Shift ou Ctrl + clique, ou Shift + arrastar no fundo).
 *
 * Os botões são comandos (data-comando): excluir pela barra, pelo Delete ou
 * pela paleta é o mesmo gesto, com a mesma confirmação.
 */
import { icone } from "./icones.js";

export class BarraDeLote {
  constructor(raiz, { state }) {
    this.raiz = raiz;
    this.state = state;
  }

  render() {
    const total = this.state.idsDosNosSelecionados().length;
    this.raiz.hidden = total < 2;
    if (total < 2) return;
    const noPassado = this.state.isTimeTraveling;
    this.raiz.innerHTML = `
      <span class="barra-lote-contagem"><strong>${total}</strong> selecionados</span>
      <span class="barra-lote-separador"></span>
      <button class="botao mod-pequeno mod-perigo" data-comando="excluir-selecao" ${noPassado ? "disabled" : ""} title="${noPassado ? "No passado não se exclui: volte ao presente" : "Excluir os selecionados num lote só (Delete)"}">${icone("trash", { tamanho: 13 })} Excluir</button>
      <button class="botao mod-pequeno" data-comando="copiar-id" title="Copiar os IDs, um por linha">${icone("copy", { tamanho: 13 })} Copiar IDs</button>
      <button class="botao mod-pequeno" data-comando="exclusao-lote" ${noPassado ? "disabled" : ""} title="Abrir a exclusão em lote com estes já marcados">${icone("list-tree", { tamanho: 13 })} Revisar…</button>
      <button class="clicavel-icone" data-comando="limpar-selecao" title="Limpar a seleção (Esc)">${icone("x", { tamanho: 14 })}</button>`;
  }
}
