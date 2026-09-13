/**
 * Marcadores: os nós que a pessoa quer ter a um clique.
 *
 * Ficam no navegador, por ramo — são preferência de quem olha, não fato do grafo,
 * e por isso não viram evento no log. O rótulo é guardado junto do id para o
 * marcador continuar legível quando o nó está fora do canvas.
 */
import { escapeHtml, gravarPreferencia, lerPreferencia } from "./dom.js";
import { icone } from "./icones.js";
import { apresentarTipo, corDoTipo, ehConteiner } from "./ontologia_ui.js";

export class MarcadoresView {
  constructor(raiz, { state, indice, acoes }) {
    this.raiz = raiz;
    this.state = state;
    this.indice = indice;
    this.acoes = acoes;
    this.raiz.addEventListener("click", (evento) => this.aoClicar(evento));
    this.raiz.addEventListener("contextmenu", (evento) => this.aoMenu(evento));
  }

  get chave() {
    return `marcadores_${this.state.currentBranch}`;
  }

  listar() {
    return lerPreferencia(this.chave, []);
  }

  contem(id) {
    return this.listar().some((marcador) => marcador.id === id);
  }

  alternar(no) {
    const marcadores = this.listar();
    const existe = marcadores.some((marcador) => marcador.id === no.id);
    const novos = existe
      ? marcadores.filter((marcador) => marcador.id !== no.id)
      : [...marcadores, { id: no.id, tipo: no.tipo, rotulo: no.rotulo }];
    gravarPreferencia(this.chave, novos);
    this.render();
    return !existe;
  }

  render() {
    const marcadores = this.listar();
    if (marcadores.length === 0) {
      this.raiz.innerHTML = `<div class="painel-vazio">${icone("bookmark", { tamanho: 22 })}<span>Nenhum marcador. Fixe um nó pelo ícone de marcador no inspetor ou pelo botão direito.</span></div>`;
      return;
    }
    this.raiz.innerHTML = `<div class="lista-marcadores">${marcadores.map((marcador) => this.montarItem(marcador)).join("")}</div>`;
  }

  montarItem(marcador) {
    const atual = this.state.nodes.get(marcador.id) || this.indice.info.get(marcador.id) || marcador;
    const tipo = apresentarTipo(atual.tipo);
    const selecionado = this.state.selectedElement?.id === marcador.id;
    return `
      <div class="arvore-titulo mod-item ${selecionado ? "is-selecionado" : ""}" data-ir="${escapeHtml(marcador.id)}" title="${escapeHtml(tipo.nome)} · ${escapeHtml(marcador.id)}">
        <span class="arvore-icone" style="color:${corDoTipo(atual.tipo)}">${icone(tipo.icone, { tamanho: 15 })}</span>
        <span class="arvore-rotulo">${escapeHtml(atual.rotulo || marcador.id)}</span>
        <button class="arvore-acao" data-remover="${escapeHtml(marcador.id)}" title="Remover marcador">${icone("x", { tamanho: 13 })}</button>
      </div>`;
  }

  aoClicar(evento) {
    const remover = evento.target.closest("[data-remover]");
    if (remover) {
      const alvo = this.listar().find((marcador) => marcador.id === remover.dataset.remover);
      if (alvo) this.alternar(alvo);
      return;
    }
    const item = evento.target.closest("[data-ir]");
    if (!item) return;
    const info = this.indice.info.get(item.dataset.ir) || this.listar().find((marcador) => marcador.id === item.dataset.ir);
    if (ehConteiner(info?.tipo)) this.acoes.abrirEscopo(this.indice.escopoDe(item.dataset.ir), { novaAba: evento.ctrlKey || evento.metaKey });
    else this.acoes.focarNo(item.dataset.ir, info);
  }

  aoMenu(evento) {
    const item = evento.target.closest("[data-ir]");
    if (!item) return;
    const info = this.state.nodes.get(item.dataset.ir) || this.indice.no(item.dataset.ir) || this.listar().find((marcador) => marcador.id === item.dataset.ir);
    if (info) this.acoes.menuDoNo(evento, info);
  }
}
