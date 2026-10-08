/**
 * Propostas fora do Goal: a caixa onde a pessoa aceita ou descarta o que o
 * agente achou e não coube em critério de aceite algum.
 *
 * O painel lê as propostas abertas do ramo e, a cada decisão, escreve pelo
 * servidor (que a passa ao kernel sob a identidade da pessoa) e relê. O que
 * decide o que aparece e como é o HTML mora em `propostas_modelo.js`.
 */
import { api } from "./api.js";
import { avisar } from "./modais.js";
import { corpoDaDecisao, htmlDaCaixa, resumoDaCaixa } from "./propostas_modelo.js";
import { icone } from "./icones.js";
import { escapeHtml } from "./dom.js";

export class PropostasView {
  constructor(raiz, { state, indice, acoes }) {
    this.raiz = raiz;
    this.state = state;
    this.indice = indice;
    this.acoes = acoes;
    this.propostas = [];
    this.carregado = false;
    this.pedido = 0;
    this.secoesFechadas = new Set();
    this.raiz.addEventListener("click", (evento) => this.aoClicar(evento));
    this.raiz.addEventListener("toggle", (evento) => this.aoAlternarSecao(evento), true);
    this.raiz.addEventListener("mouseover", (evento) => this.aoPairar(evento));
    this.raiz.addEventListener("mouseleave", () => this.acoes.destacar(null));
    this.raiz.innerHTML = this.montarVazio("Lendo as propostas do ramo…");
  }

  /** O grafo mudou: da próxima vez que o painel aparecer, ele relê. */
  invalidar() {
    this.carregado = false;
  }

  /** Quantas propostas aguardam, para o rótulo da aba. */
  get total() {
    return this.propostas.length;
  }

  async atualizar({ forcar = false } = {}) {
    if (this.carregado && !forcar) return;
    const pedido = ++this.pedido;
    const resposta = await api.propostas(this.state.currentBranch);
    if (pedido !== this.pedido) return;
    if (!resposta.sucesso) {
      this.raiz.innerHTML = this.montarVazio(resposta.mensagem || "Não foi possível ler as propostas.");
      return;
    }
    this.propostas = resposta.propostas || [];
    this.carregado = true;
    this.render();
  }

  render() {
    this.raiz.innerHTML = `
      <div class="nav-botoes">
        <span class="nav-resumo">${escapeHtml(this.propostas.length ? resumoDaCaixa(this.propostas) : "")}</span>
        <button class="clicavel-icone" data-acao-propostas="recarregar" title="Reler as propostas">${icone("refresh", { tamanho: 16 })}</button>
      </div>
      ${htmlDaCaixa(this.propostas, { viajando: this.state.isTimeTraveling, fechados: this.secoesFechadas })}`;
  }

  montarVazio(texto) {
    return `<div class="painel-vazio">${icone("inbox", { tamanho: 22 })}<span>${escapeHtml(texto)}</span></div>`;
  }

  async decidir(idProposta, status) {
    const recibo = await api.decidirProposta(corpoDaDecisao(idProposta, status, this.state.currentBranch));
    if (!recibo.sucesso) {
      avisar(recibo.mensagem || "Não foi possível registrar a decisão.", "erro");
      return;
    }
    avisar(`Proposta ${status}`, "info");
    await this.atualizar({ forcar: true });
  }

  aoClicar(evento) {
    const decidir = evento.target.closest("[data-decidir]");
    if (decidir) {
      this.decidir(decidir.dataset.proposta, decidir.dataset.decidir);
      return;
    }
    if (evento.target.closest("[data-acao-propostas=recarregar]")) {
      this.atualizar({ forcar: true });
      return;
    }
    const item = evento.target.closest("[data-ir]");
    if (item) this.acoes.focarNo(item.dataset.ir, this.indice.no(item.dataset.ir));
  }

  aoPairar(evento) {
    const item = evento.target.closest("[data-ir]");
    this.acoes.destacar(item && this.state.nodes.has(item.dataset.ir) ? item.dataset.ir : null);
  }

  aoAlternarSecao(evento) {
    const secao = evento.target.closest?.("[data-secao]");
    if (!secao) return;
    if (secao.open) this.secoesFechadas.delete(secao.dataset.secao);
    else this.secoesFechadas.add(secao.dataset.secao);
  }
}
