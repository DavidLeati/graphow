/**
 * Barra de status no canto inferior direito.
 *
 * Reúne o que antes se espalhava pela barra superior — ramo, versão do log,
 * estado do tempo real e identidade — mais o tamanho do que está na tela. Cada
 * item clicável leva à ação natural: o ramo abre o menu de ramos, a versão abre o
 * histórico, o zoom volta a 100%.
 */
import { escapeHtml } from "./dom.js";
import { icone } from "./icones.js";

export class BarraDeStatus {
  constructor(raiz, { state, acoes }) {
    this.raiz = raiz;
    this.state = state;
    this.acoes = acoes;
    this.identidade = null;
    this.raiz.addEventListener("click", (evento) => {
      const item = evento.target.closest("[data-status]");
      if (item) this.acoes.aoClicar(item.dataset.status, evento);
    });
  }

  definirIdentidade(identidade) {
    this.identidade = identidade;
    this.render();
  }

  /**
   * Só a parte dinâmica é redesenhada. O indicador de tempo real fica fora dela
   * porque o cliente SSE guarda a referência do elemento ao conectar: trocá-lo
   * por outro deixaria o cliente pintando um nó que já saiu da página.
   */
  render() {
    const s = this.state;
    const recorte = s.recorteAplicado?.total_oculto ? s.recorteAplicado : null;
    const viajando = s.isTimeTraveling;
    const itens = [
      this.item("ramo", "git-branch", escapeHtml(s.currentBranch), "Ramo atual — clique para trocar ou criar um fork"),
      this.item("versao", "history", viajando ? `log #${s.logVersion} <span class="texto-fraco">de #${s.maxLogVersion}</span>` : `log #${s.logVersion}`, "Versão do log na tela — clique para abrir o histórico", viajando ? "mod-viajando" : ""),
      this.item("contagem", "grafo", `${s.nodes.size} nós · ${s.edges.size} arestas`, "Tamanho do que está no canvas"),
      recorte ? this.item("recorte", "filter", `${recorte.total_exibido}/${recorte.total_no_grafo} na tela`, "Nós ocultos pelo recorte — clique para ajustar", "mod-aviso") : "",
      this.item("zoom", "zoom-in", `<span id="zoom-indicator">${Math.round((this.acoes.zoom?.() || 1) * 100)}%</span>`, "Zoom — clique para voltar a 100%"),
    ];
    this.raiz.querySelector("[data-dinamica]").innerHTML = itens.join("");
    const identidade = this.raiz.querySelector("[data-identidade]");
    identidade.hidden = !this.identidade;
    if (this.identidade) {
      identidade.innerHTML = `${icone("user", { tamanho: 13 })}${escapeHtml(this.identidade.autor)} <span class="texto-fraco">${escapeHtml(this.identidade.papel)}</span>`;
    }
  }

  item(chave, nomeIcone, conteudo, titulo, classe = "") {
    return `<button class="status-item ${classe}" data-status="${chave}" title="${escapeHtml(titulo)}">${icone(nomeIcone, { tamanho: 13 })}<span>${conteudo}</span></button>`;
  }
}
