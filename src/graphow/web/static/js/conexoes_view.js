/**
 * Conexões do nó selecionado.
 *
 * O resumo do inspetor só enxerga as arestas que estão no canvas, e o canvas é um
 * recorte. Aqui a leitura vem de `expandir_no` — a mesma ficha que o agente lê —,
 * então aparece toda aresta do nó, mesmo as que levam para fora da tela. Cada
 * linha leva ao vizinho, abrindo o contêiner dele se for preciso.
 */
import { api } from "./api.js";
import { escapeHtml } from "./dom.js";
import { icone } from "./icones.js";
import { apresentarTipo, corDaAresta, corDoTipo, lerAresta } from "./ontologia_ui.js";

const MAXIMO_DE_ROTULOS_RESOLVIDOS = 24;

export class ConexoesView {
  constructor(raiz, { state, indice, acoes }) {
    this.raiz = raiz;
    this.state = state;
    this.indice = indice;
    this.acoes = acoes;
    this.idCarregado = null;
    this.gruposFechados = new Set();
    this.pedido = 0;
    this.raiz.addEventListener("click", (evento) => this.aoClicar(evento));
    this.raiz.addEventListener("contextmenu", (evento) => this.aoMenu(evento));
    this.raiz.addEventListener("mouseover", (evento) => this.aoPairar(evento));
    this.raiz.addEventListener("mouseleave", () => this.acoes.destacar(null));
  }

  /** Chamado quando o painel aparece ou a seleção muda com ele visível. */
  async atualizar({ forcar = false } = {}) {
    const selecao = this.state.selectedElement;
    if (!selecao || selecao.type !== "node") {
      this.idCarregado = null;
      this.raiz.innerHTML = this.montarVazio("Selecione um nó para ver todas as arestas dele, dentro e fora do canvas.");
      return;
    }
    if (!forcar && this.idCarregado === selecao.id) return;
    this.idCarregado = selecao.id;
    const pedido = ++this.pedido;
    this.raiz.innerHTML = this.montarVazio("Lendo as arestas do nó…");
    const resposta = await api.expandir(selecao.id, this.state.currentBranch);
    if (pedido !== this.pedido) return;
    if (!resposta.sucesso) {
      this.raiz.innerHTML = this.montarVazio(resposta.mensagem || "Não foi possível ler as conexões.");
      return;
    }
    this.dados = resposta.no;
    this.render();
    await this.resolverRotulosDesconhecidos(pedido);
  }

  invalidar() {
    this.idCarregado = null;
  }

  vizinhos() {
    const saidas = (this.dados.arestas_saida || []).map((a) => ({ ...a, vizinho: a.destino, direcao: "saida" }));
    const entradas = (this.dados.arestas_entrada || []).map((a) => ({ ...a, vizinho: a.origem, direcao: "entrada" }));
    return { saidas, entradas };
  }

  /** Vizinho fora do canvas e fora do índice chega só com o id; a ficha dele traz o rótulo. */
  async resolverRotulosDesconhecidos(pedido) {
    const { saidas, entradas } = this.vizinhos();
    const desconhecidos = [...new Set([...saidas, ...entradas].map((a) => a.vizinho))]
      .filter((id) => !this.state.nodes.has(id) && !this.indice.info.get(id)?.rotulo)
      .slice(0, MAXIMO_DE_ROTULOS_RESOLVIDOS);
    if (desconhecidos.length === 0) return;
    const fichas = await Promise.all(desconhecidos.map((id) => api.expandir(id, this.state.currentBranch)));
    this.indice.registrarNos(fichas.filter((ficha) => ficha.sucesso).map((ficha) => ficha.no));
    if (pedido === this.pedido) this.render();
  }

  render() {
    const { saidas, entradas } = this.vizinhos();
    const rotulo = this.dados.rotulo || this.dados.id;
    this.raiz.innerHTML = `
      <div class="painel-cabecalho-texto">
        <span class="texto-fraco">Conexões de</span>
        <button class="link-no" data-ir="${escapeHtml(this.dados.id)}">${escapeHtml(rotulo)}</button>
      </div>
      ${this.montarDirecao("saida", "Saídas", saidas)}
      ${this.montarDirecao("entrada", "Entradas", entradas)}`;
  }

  montarDirecao(chave, titulo, arestas) {
    const fechado = this.gruposFechados.has(chave);
    const porTipo = new Map();
    for (const aresta of arestas) {
      if (!porTipo.has(aresta.tipo)) porTipo.set(aresta.tipo, []);
      porTipo.get(aresta.tipo).push(aresta);
    }
    const grupos = [...porTipo.entries()].map(([tipo, lista]) => this.montarGrupo(chave, tipo, lista)).join("");
    return `
      <div class="grupo-conexoes">
        <button class="grupo-conexoes-titulo" data-grupo="${chave}">
          ${icone("chevron-down", { tamanho: 14, classe: fechado ? "is-recolhida" : "" })}
          <span>${titulo}</span><span class="contador">${arestas.length}</span>
        </button>
        ${fechado ? "" : grupos || `<div class="secao-vazia mod-recuado">Nenhuma aresta de ${chave === "saida" ? "saída" : "entrada"}.</div>`}
      </div>`;
  }

  montarGrupo(direcao, tipo, arestas) {
    const leitura = lerAresta(tipo);
    const verbo = direcao === "saida" ? leitura.saida : leitura.entrada;
    const itens = arestas.map((aresta) => this.montarItem(aresta)).join("");
    return `
      <div class="subgrupo-conexoes">
        <div class="subgrupo-titulo" title="${escapeHtml(leitura.descricao)}">
          <span class="marca-aresta" style="--cor-aresta:${corDaAresta(tipo)}"></span>${escapeHtml(verbo)}<span class="texto-fraco">${arestas.length}</span>
        </div>
        ${itens}
      </div>`;
  }

  montarItem(aresta) {
    const vizinho = this.state.nodes.get(aresta.vizinho) || this.indice.info.get(aresta.vizinho) || { id: aresta.vizinho, tipo: "", rotulo: "" };
    const tipo = apresentarTipo(vizinho.tipo);
    const naTela = this.state.nodes.has(aresta.vizinho);
    return `
      <div class="item-conexao" data-ir="${escapeHtml(aresta.vizinho)}" title="${naTela ? "No canvas" : "Fora do canvas atual"}">
        <span class="item-conexao-icone" style="color:${corDoTipo(vizinho.tipo)}">${icone(tipo.icone, { tamanho: 14 })}</span>
        <span class="item-conexao-rotulo">${escapeHtml(vizinho.rotulo || aresta.vizinho)}</span>
        ${naTela ? "" : `<span class="item-conexao-fora">${icone("eye-off", { tamanho: 12 })}</span>`}
      </div>`;
  }

  montarVazio(texto) {
    return `<div class="painel-vazio">${icone("link", { tamanho: 22 })}<span>${escapeHtml(texto)}</span></div>`;
  }

  aoClicar(evento) {
    const grupo = evento.target.closest("[data-grupo]");
    if (grupo) {
      const chave = grupo.dataset.grupo;
      if (this.gruposFechados.has(chave)) this.gruposFechados.delete(chave);
      else this.gruposFechados.add(chave);
      this.render();
      return;
    }
    const item = evento.target.closest("[data-ir]");
    if (item) this.acoes.focarNo(item.dataset.ir, this.indice.info.get(item.dataset.ir));
  }

  aoMenu(evento) {
    const item = evento.target.closest("[data-ir]");
    if (!item) return;
    const info = this.state.nodes.get(item.dataset.ir) || this.indice.info.get(item.dataset.ir);
    if (info) this.acoes.menuDoNo(evento, info);
  }

  aoPairar(evento) {
    const item = evento.target.closest("[data-ir]");
    this.acoes.destacar(item && this.state.nodes.has(item.dataset.ir) ? item.dataset.ir : null);
  }
}
