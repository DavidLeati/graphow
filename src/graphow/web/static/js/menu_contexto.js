/**
 * Menu de contexto.
 *
 * O clique direito responde "o que dá para fazer com isto?" no lugar em que a
 * pessoa já está olhando, em vez de exigir que ela lembre em qual painel mora
 * cada botão. Um item é `{ rotulo, icone, acao, perigo, desabilitado, marcado,
 * atalho, submenu }`; `"-"` separa grupos e `{ secao }` rotula um grupo.
 */
import { escapeHtml } from "./dom.js";
import { icone } from "./icones.js";

let menuAberto = null;

export function fecharMenuDeContexto() {
  if (!menuAberto) return;
  menuAberto.destruir();
  menuAberto = null;
}

/** Abre o menu na posição do evento (ou de um `{ x, y }`) com os itens dados. */
export function abrirMenuDeContexto(posicao, itens) {
  fecharMenuDeContexto();
  const x = posicao.clientX ?? posicao.x;
  const y = posicao.clientY ?? posicao.y;
  posicao.preventDefault?.();
  posicao.stopPropagation?.();
  menuAberto = new Menu(itens, { x, y });
}

class Menu {
  constructor(itens, ponto, pai = null) {
    this.itens = itens.filter(Boolean);
    this.pai = pai;
    this.submenu = null;
    this.indiceFoco = -1;
    this.raiz = document.createElement("div");
    this.raiz.className = "menu";
    this.raiz.setAttribute("role", "menu");
    this.raiz.innerHTML = this.itens.map((item, indice) => this.montarItem(item, indice)).join("");
    document.body.appendChild(this.raiz);
    this.posicionar(ponto);
    this.ligarEventos();
  }

  montarItem(item, indice) {
    if (item === "-") return '<div class="menu-separador"></div>';
    if (item.secao) return `<div class="menu-secao">${escapeHtml(item.secao)}</div>`;
    const classes = ["menu-item", item.perigo ? "mod-perigo" : "", item.desabilitado ? "is-desabilitado" : ""];
    const marca = item.marcado ? `<span class="menu-item-marca">${icone("check", { tamanho: 14 })}</span>` : "";
    const atalho = item.atalho ? `<span class="menu-item-atalho">${escapeHtml(item.atalho)}</span>` : "";
    const seta = item.submenu ? `<span class="menu-item-seta">${icone("chevron-right", { tamanho: 14 })}</span>` : "";
    return `
      <div class="${classes.join(" ")}" role="menuitem" data-indice="${indice}" tabindex="-1">
        <span class="menu-item-icone">${item.icone ? icone(item.icone) : ""}</span>
        <span class="menu-item-rotulo">${escapeHtml(item.rotulo)}</span>
        ${atalho}${marca}${seta}
      </div>`;
  }

  posicionar({ x, y }) {
    const largura = this.raiz.offsetWidth;
    const altura = this.raiz.offsetHeight;
    const esquerda = Math.min(x, window.innerWidth - largura - 6);
    const topo = Math.min(y, window.innerHeight - altura - 6);
    this.raiz.style.left = `${Math.max(6, esquerda)}px`;
    this.raiz.style.top = `${Math.max(6, topo)}px`;
  }

  ligarEventos() {
    this.raiz.addEventListener("click", (evento) => this.aoClicar(evento));
    this.raiz.addEventListener("mouseover", (evento) => this.aoPairar(evento));
    this.raiz.addEventListener("contextmenu", (evento) => evento.preventDefault());
    if (this.pai) return;
    this.aoPressionarFora = (evento) => {
      if (!evento.target.closest(".menu")) fecharMenuDeContexto();
    };
    this.aoTeclar = (evento) => this.navegarPorTeclado(evento);
    this.aoSair = () => fecharMenuDeContexto();
    setTimeout(() => document.addEventListener("mousedown", this.aoPressionarFora, true), 0);
    document.addEventListener("keydown", this.aoTeclar, true);
    window.addEventListener("blur", this.aoSair);
    window.addEventListener("resize", this.aoSair);
  }

  itemDoEvento(evento) {
    const alvo = evento.target.closest(".menu-item");
    if (!alvo) return null;
    return { alvo, item: this.itens[Number(alvo.dataset.indice)], indice: Number(alvo.dataset.indice) };
  }

  aoClicar(evento) {
    const achado = this.itemDoEvento(evento);
    if (!achado || achado.item.desabilitado) return;
    if (achado.item.submenu) {
      this.abrirSubmenu(achado.alvo, achado.item);
      return;
    }
    fecharMenuDeContexto();
    achado.item.acao?.();
  }

  aoPairar(evento) {
    const achado = this.itemDoEvento(evento);
    if (!achado) return;
    this.focar(achado.indice);
    if (achado.item.submenu && !achado.item.desabilitado) this.abrirSubmenu(achado.alvo, achado.item);
    else this.fecharSubmenu();
  }

  abrirSubmenu(alvo, item) {
    if (this.submenu?.origem === item) return;
    this.fecharSubmenu();
    const caixa = alvo.getBoundingClientRect();
    this.submenu = new Menu(item.submenu, { x: caixa.right - 4, y: caixa.top - 5 }, this);
    this.submenu.origem = item;
  }

  fecharSubmenu() {
    this.submenu?.destruir();
    this.submenu = null;
  }

  focar(indice) {
    this.indiceFoco = indice;
    this.raiz.querySelectorAll(".menu-item").forEach((el) => {
      el.classList.toggle("is-foco", Number(el.dataset.indice) === indice);
    });
  }

  navegarPorTeclado(evento) {
    const alvoDoTeclado = this.submenu || this;
    const selecionaveis = alvoDoTeclado.itens
      .map((item, indice) => ({ item, indice }))
      .filter(({ item }) => item !== "-" && !item.secao && !item.desabilitado);
    if (evento.key === "Escape") fecharMenuDeContexto();
    else if (evento.key === "ArrowDown" || evento.key === "ArrowUp") alvoDoTeclado.moverFoco(selecionaveis, evento.key === "ArrowDown" ? 1 : -1);
    else if (evento.key === "ArrowLeft" && this.submenu) this.fecharSubmenu();
    else if (evento.key === "Enter" || evento.key === "ArrowRight") alvoDoTeclado.ativarFoco();
    else return;
    evento.preventDefault();
    evento.stopPropagation();
  }

  moverFoco(selecionaveis, passo) {
    if (selecionaveis.length === 0) return;
    const posicaoAtual = selecionaveis.findIndex(({ indice }) => indice === this.indiceFoco);
    const proxima = (posicaoAtual + passo + selecionaveis.length) % selecionaveis.length;
    this.focar(selecionaveis[posicaoAtual === -1 && passo < 0 ? selecionaveis.length - 1 : proxima].indice);
  }

  ativarFoco() {
    const alvo = this.raiz.querySelector(`.menu-item[data-indice="${this.indiceFoco}"]`);
    alvo?.click();
  }

  destruir() {
    this.fecharSubmenu();
    this.raiz.remove();
    if (this.pai) return;
    document.removeEventListener("mousedown", this.aoPressionarFora, true);
    document.removeEventListener("keydown", this.aoTeclar, true);
    window.removeEventListener("blur", this.aoSair);
    window.removeEventListener("resize", this.aoSair);
  }
}
