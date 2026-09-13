/**
 * Caixa de sugestões do seletor rápido e da paleta de comandos.
 *
 * Uma entrada no topo, resultados que se navegam com as setas e uma linha de
 * instruções no rodapé. A busca pode ser assíncrona: cada digitação numera o
 * pedido, e a resposta de um pedido velho é descartada em vez de sobrescrever a
 * lista de um termo mais novo.
 */
import { debounce, escapeHtml } from "./dom.js";

// Uma caixa por vez: abrir a paleta com a busca rápida aberta troca uma pela outra.
let sugestorAberto = null;

export class Sugestor {
  constructor({ placeholder, instrucoes = [], buscar, montarItem, aoEscolher, esperaMs = 0 }) {
    this.placeholder = placeholder;
    this.instrucoes = instrucoes;
    this.buscar = buscar;
    this.montarItem = montarItem;
    this.aoEscolher = aoEscolher;
    this.itens = [];
    this.ativo = 0;
    this.pedido = 0;
    this.recipiente = null;
    this.atualizarEmBreve = esperaMs ? debounce(() => this.atualizar(), esperaMs) : () => this.atualizar();
  }

  get aberto() {
    return Boolean(this.recipiente);
  }

  abrir(termoInicial = "") {
    if (this.aberto) {
      this.entrada.focus();
      return;
    }
    if (sugestorAberto && sugestorAberto !== this) sugestorAberto.fechar();
    sugestorAberto = this;
    this.recipiente = document.createElement("div");
    this.recipiente.className = "modal-recipiente mod-sugestor";
    this.recipiente.innerHTML = `
      <div class="modal-fundo"></div>
      <div class="prompt" role="dialog">
        <div class="prompt-caixa-entrada"><input class="prompt-entrada" type="text" spellcheck="false" placeholder="${escapeHtml(this.placeholder)}"></div>
        <div class="prompt-resultados" role="listbox"></div>
        <div class="prompt-instrucoes">${this.instrucoes.map(([tecla, texto]) => `<span><kbd>${escapeHtml(tecla)}</kbd>${escapeHtml(texto)}</span>`).join("")}</div>
      </div>`;
    document.body.appendChild(this.recipiente);
    this.entrada = this.recipiente.querySelector(".prompt-entrada");
    this.lista = this.recipiente.querySelector(".prompt-resultados");
    this.entrada.value = termoInicial;
    this.recipiente.querySelector(".modal-fundo").addEventListener("click", () => this.fechar());
    this.entrada.addEventListener("input", () => this.atualizarEmBreve());
    this.entrada.addEventListener("keydown", (evento) => this.aoTeclar(evento));
    this.lista.addEventListener("mousemove", (evento) => this.aoPairar(evento));
    this.lista.addEventListener("click", (evento) => this.aoClicar(evento));
    this.entrada.focus();
    this.atualizar();
  }

  fechar() {
    this.recipiente?.remove();
    this.recipiente = null;
    if (sugestorAberto === this) sugestorAberto = null;
  }

  async atualizar() {
    if (!this.aberto) return;
    const pedido = ++this.pedido;
    const termo = this.entrada.value;
    const resultado = await this.buscar(termo);
    if (pedido !== this.pedido || !this.aberto) return;
    this.itens = resultado.itens || [];
    this.rodape = resultado.rodape || "";
    this.ativo = 0;
    this.render(termo);
  }

  render(termo) {
    if (this.itens.length === 0) {
      this.lista.innerHTML = `<div class="prompt-vazio">${escapeHtml(this.rodape || "Nada encontrado.")}</div>`;
      return;
    }
    const linhas = this.itens.map((item, indice) => `
      <div class="prompt-item ${indice === this.ativo ? "is-ativo" : ""}" data-indice="${indice}" role="option">${this.montarItem(item, termo)}</div>`);
    this.lista.innerHTML = linhas.join("") + (this.rodape ? `<div class="prompt-rodape-lista">${escapeHtml(this.rodape)}</div>` : "");
  }

  mover(passo) {
    if (this.itens.length === 0) return;
    this.ativo = (this.ativo + passo + this.itens.length) % this.itens.length;
    this.lista.querySelectorAll(".prompt-item").forEach((el) => el.classList.toggle("is-ativo", Number(el.dataset.indice) === this.ativo));
    this.lista.querySelector(".prompt-item.is-ativo")?.scrollIntoView({ block: "nearest" });
  }

  escolher(evento) {
    const item = this.itens[this.ativo];
    if (!item) return;
    this.fechar();
    this.aoEscolher(item, evento);
  }

  aoTeclar(evento) {
    const teclas = {
      ArrowDown: () => this.mover(1),
      ArrowUp: () => this.mover(-1),
      Enter: () => this.escolher(evento),
      Escape: () => this.fechar(),
    };
    if (!teclas[evento.key]) return;
    evento.preventDefault();
    evento.stopPropagation();
    teclas[evento.key]();
  }

  aoPairar(evento) {
    const linha = evento.target.closest(".prompt-item");
    if (!linha || Number(linha.dataset.indice) === this.ativo) return;
    this.ativo = Number(linha.dataset.indice);
    this.lista.querySelectorAll(".prompt-item").forEach((el) => el.classList.toggle("is-ativo", el === linha));
  }

  aoClicar(evento) {
    const linha = evento.target.closest(".prompt-item");
    if (!linha) return;
    this.ativo = Number(linha.dataset.indice);
    this.escolher(evento);
  }
}
