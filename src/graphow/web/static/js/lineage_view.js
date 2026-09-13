/**
 * Linhagem causal do nó selecionado: o caminho de volta do entregável até a intenção.
 *
 * A cadeia é desenhada de cima para baixo, do Goal raiz ao nó alvo, porque é
 * assim que ela se lê — "por que isto existe?" responde-se subindo. Cada passo
 * leva ao nó correspondente no canvas.
 */
import { api } from "./api.js";
import { escapeHtml } from "./dom.js";
import { icone } from "./icones.js";
import { apresentarTipo, corDoTipo } from "./ontologia_ui.js";

export class LineageView {
  constructor(raiz, { state, indice, acoes }) {
    this.raiz = raiz;
    this.state = state;
    this.indice = indice;
    this.acoes = acoes;
    this.idCarregado = null;
    this.pedido = 0;
    this.raiz.addEventListener("click", (evento) => {
      const passo = evento.target.closest("[data-ir]");
      if (passo) this.acoes.focarNo(passo.dataset.ir, this.indice.info.get(passo.dataset.ir));
    });
  }

  invalidar() {
    this.idCarregado = null;
  }

  async atualizar({ forcar = false } = {}) {
    const selecao = this.state.selectedElement;
    if (!selecao || selecao.type !== "node") {
      this.idCarregado = null;
      this.raiz.innerHTML = this.montarVazio("Selecione um nó para rastrear a proveniência dele até o objetivo raiz.");
      return;
    }
    if (!forcar && this.idCarregado === selecao.id) return;
    this.idCarregado = selecao.id;
    const pedido = ++this.pedido;
    this.raiz.innerHTML = this.montarVazio("Rastreando a cadeia causal…");
    const dados = await api.linhagem(selecao.id, this.state.currentBranch);
    if (pedido !== this.pedido) return;
    if (dados.sucesso === false) {
      this.raiz.innerHTML = this.montarVazio(dados.mensagem || "Falha ao rastrear a linhagem.");
      return;
    }
    this.render(dados);
  }

  render(dados) {
    const cadeia = [...(dados.nos_cadeia || [])].reverse();
    const raiz = dados.goal_raiz;
    if (raiz && cadeia[0]?.id !== raiz.id) cadeia.unshift(raiz);
    this.indice.registrarNos(cadeia);
    const cabecalho = raiz
      ? `<div class="chamada mod-ok">${icone("target", { tamanho: 14 })}<span>Chega ao objetivo raiz <strong>${escapeHtml(raiz.rotulo)}</strong>.</span></div>`
      : `<div class="chamada mod-neutra">${icone("info", { tamanho: 14 })}<span>A cadeia não alcança nenhum Goal: o nó não deriva de uma intenção declarada.</span></div>`;
    const passos = cadeia.map((no, indice) => this.montarPasso(no, indice === cadeia.length - 1)).join("");
    this.raiz.innerHTML = `${cabecalho}<ol class="linhagem">${passos}</ol>`;
  }

  montarPasso(no, ehAlvo) {
    const tipo = apresentarTipo(no.tipo);
    return `
      <li class="linhagem-passo ${ehAlvo ? "mod-alvo" : ""}">
        <span class="linhagem-marco" style="--cor-tipo:${corDoTipo(no.tipo)}">${icone(tipo.icone, { tamanho: 13 })}</span>
        <button class="linhagem-cartao" data-ir="${escapeHtml(no.id)}">
          <span class="linhagem-tipo">${escapeHtml(tipo.nome)}${ehAlvo ? " · selecionado" : ""}</span>
          <span class="linhagem-rotulo">${escapeHtml(no.rotulo || no.id)}</span>
        </button>
      </li>`;
  }

  montarVazio(texto) {
    return `<div class="painel-vazio">${icone("route", { tamanho: 22 })}<span>${escapeHtml(texto)}</span></div>`;
  }
}
