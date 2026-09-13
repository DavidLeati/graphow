/**
 * Painéis laterais da moldura: recolher, redimensionar e alternar entre vistas.
 *
 * Cada lateral tem um cabeçalho de ícones, um por
 * vista, e a lateral direita se divide em duas metades empilhadas. Largura, vista
 * ativa e altura da divisão ficam gravadas: a pessoa arruma a mesa uma vez.
 */
import { gravarPreferencia, lerPreferencia } from "./dom.js";

/** Uma lateral inteira: pode recolher e tem a largura arrastável pela borda. */
export class Lateral {
  constructor(elemento, { chave, alca, larguraPadrao, minimo = 200, maximo = 560, ladoDaAlca = "direita", aoMudar = null }) {
    this.elemento = elemento;
    this.chave = chave;
    this.minimo = minimo;
    this.maximo = maximo;
    this.ladoDaAlca = ladoDaAlca;
    this.aoMudar = aoMudar;
    const salvo = lerPreferencia(`lateral_${chave}`, {});
    this.largura = salvo.largura || larguraPadrao;
    this.recolhida = Boolean(salvo.recolhida);
    this.aplicar();
    if (alca) this.ligarAlca(alca);
  }

  aplicar() {
    this.elemento.style.width = this.recolhida ? "0px" : `${this.largura}px`;
    this.elemento.classList.toggle("is-recolhida", this.recolhida);
    document.body.classList.toggle(`lateral-${this.chave}-recolhida`, this.recolhida);
  }

  alternar() {
    this.recolhida = !this.recolhida;
    this.persistir();
  }

  expandir() {
    if (!this.recolhida) return;
    this.recolhida = false;
    this.persistir();
  }

  persistir() {
    this.aplicar();
    gravarPreferencia(`lateral_${this.chave}`, { largura: this.largura, recolhida: this.recolhida });
    this.aoMudar?.();
  }

  ligarAlca(alca) {
    alca.addEventListener("mousedown", (evento) => {
      if (this.recolhida) return;
      evento.preventDefault();
      const inicioX = evento.clientX;
      const larguraInicial = this.largura;
      document.body.classList.add("is-redimensionando");
      const aoMover = (movimento) => {
        const delta = movimento.clientX - inicioX;
        const sinal = this.ladoDaAlca === "direita" ? 1 : -1;
        this.largura = Math.min(this.maximo, Math.max(this.minimo, larguraInicial + delta * sinal));
        this.aplicar();
        this.aoMudar?.();
      };
      const aoSoltar = () => {
        document.body.classList.remove("is-redimensionando");
        window.removeEventListener("mousemove", aoMover);
        window.removeEventListener("mouseup", aoSoltar);
        this.persistir();
      };
      window.addEventListener("mousemove", aoMover);
      window.addEventListener("mouseup", aoSoltar);
    });
  }
}

/**
 * Grupo de vistas com cabeçalho de ícones. Os botões levam `data-aba` e as
 * seções `data-painel` com o mesmo nome; só uma seção fica visível por vez.
 */
export class GrupoDeAbas {
  constructor(raiz, { chave, padrao, aoMudar = null }) {
    this.raiz = raiz;
    this.chave = chave;
    this.aoMudar = aoMudar;
    this.botoes = [...raiz.querySelectorAll(":scope > .grupo-cabecalho [data-aba]")];
    this.paineis = [...raiz.querySelectorAll(":scope > .grupo-conteudo > [data-painel]")];
    const salva = lerPreferencia(`aba_${chave}`, padrao);
    this.ativa = this.paineis.some((painel) => painel.dataset.painel === salva) ? salva : padrao;
    this.botoes.forEach((botao) => botao.addEventListener("click", () => this.ativar(botao.dataset.aba)));
    this.aplicar();
  }

  ativar(nome) {
    const mudou = this.ativa !== nome;
    this.ativa = nome;
    this.aplicar();
    gravarPreferencia(`aba_${this.chave}`, nome);
    if (mudou) this.aoMudar?.(nome);
  }

  aplicar() {
    this.botoes.forEach((botao) => botao.classList.toggle("is-ativa", botao.dataset.aba === this.ativa));
    this.paineis.forEach((painel) => {
      painel.hidden = painel.dataset.painel !== this.ativa;
    });
    // O nome da vista ativa ao lado dos ícones: ícone sozinho obriga a decorar.
    const titulo = this.raiz.querySelector(":scope > .grupo-cabecalho [data-titulo-grupo]");
    const ativo = this.botoes.find((botao) => botao.dataset.aba === this.ativa);
    if (titulo && ativo) titulo.textContent = ativo.title.replace(/\s*\(.*\)$/, "");
  }

  mostra(nome) {
    return this.ativa === nome;
  }
}

/** Divisão entre as duas metades empilhadas da lateral direita. */
export class DivisorVertical {
  constructor(divisor, superior, inferior, { chave, fracaoPadrao = 0.58 }) {
    this.superior = superior;
    this.inferior = inferior;
    this.chave = chave;
    this.fracao = lerPreferencia(`divisao_${chave}`, fracaoPadrao);
    this.aplicar();
    divisor.addEventListener("mousedown", (evento) => this.arrastar(evento));
    divisor.addEventListener("dblclick", () => this.definir(fracaoPadrao));
  }

  aplicar() {
    this.superior.style.flex = `${this.fracao} 1 0`;
    this.inferior.style.flex = `${1 - this.fracao} 1 0`;
  }

  definir(fracao) {
    this.fracao = Math.min(0.85, Math.max(0.15, fracao));
    this.aplicar();
    gravarPreferencia(`divisao_${this.chave}`, this.fracao);
  }

  arrastar(evento) {
    evento.preventDefault();
    const pai = this.superior.parentElement.getBoundingClientRect();
    document.body.classList.add("is-redimensionando-vertical");
    const aoMover = (movimento) => this.definir((movimento.clientY - pai.top) / pai.height);
    const aoSoltar = () => {
      document.body.classList.remove("is-redimensionando-vertical");
      window.removeEventListener("mousemove", aoMover);
      window.removeEventListener("mouseup", aoSoltar);
    };
    window.addEventListener("mousemove", aoMover);
    window.addEventListener("mouseup", aoSoltar);
  }
}
