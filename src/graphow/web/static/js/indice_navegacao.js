/**
 * Índice da camada de navegação: Projeto, Setor e Sessão, e o que cada sessão contém.
 *
 * O explorador não pode depender do que está no canvas. O canvas é um recorte —
 * aberto num setor, ele não tem os outros setores; colapsado, não tem trabalho
 * nenhum — e uma árvore montada a partir dele sumia com metade do projeto. Por
 * isso o índice pede ao servidor só a camada de navegação (`colapsar=sessao`,
 * poucos KB, já com o agregado de cada subárvore) e busca o conteúdo de uma
 * sessão apenas quando ela é aberta na árvore.
 */
import { api } from "./api.js";

export class IndiceNavegacao {
  constructor(state) {
    this.state = state;
    this.conteineres = new Map();
    this.filhosDe = new Map();
    this.paiDe = new Map();
    this.raizes = [];
    this.orfaos = [];
    this.conteudoDaSessao = new Map();
    this.pedidosDeSessao = new Map();
    this.info = new Map();
    this.carregado = false;
    this.erro = null;
    this.ouvintes = new Set();
  }

  aoMudar(ouvinte) {
    this.ouvintes.add(ouvinte);
    return () => this.ouvintes.delete(ouvinte);
  }

  avisar() {
    for (const ouvinte of this.ouvintes) ouvinte();
  }

  /**
   * Lê o esqueleto do ramo atual. Uma releitura disparada por evento pode
   * voltar depois de uma troca de ramo: a resposta de um pedido velho, ou de
   * outro ramo, é descartada em vez de pintar a árvore com o ramo errado.
   */
  async carregar() {
    const ramo = this.state.currentBranch;
    const pedido = (this.pedido = (this.pedido || 0) + 1);
    const dados = await api.navegacao(ramo);
    if (pedido !== this.pedido || ramo !== this.state.currentBranch) return;
    if (dados.sucesso === false || !Array.isArray(dados.nos)) {
      this.erro = dados.mensagem || "Falha ao ler a camada de navegação";
      this.avisar();
      return;
    }
    this.erro = null;
    this.montarEsqueleto(dados);
    this.carregado = true;
    this.avisar();
  }

  montarEsqueleto(dados) {
    this.conteineres = new Map(dados.nos.map((no) => [no.id, no]));
    this.filhosDe = new Map();
    this.paiDe = new Map();
    for (const aresta of dados.arestas) {
      if (aresta.tipo !== "contem") continue;
      if (!this.filhosDe.has(aresta.origem_id)) this.filhosDe.set(aresta.origem_id, []);
      this.filhosDe.get(aresta.origem_id).push(aresta.destino_id);
      this.paiDe.set(aresta.destino_id, aresta.origem_id);
    }
    this.raizes = dados.nos.filter((no) => !this.paiDe.has(no.id)).map((no) => no.id);
    this.orfaos = dados.recorte?.nos_orfaos || [];
    this.totalNoGrafo = dados.recorte?.total_no_grafo ?? null;
    this.registrarNos(dados.nos);
  }

  /** Guarda tipo, rótulo e sessão de nós vistos em qualquer resposta, para rotular ids soltos. */
  registrarNos(nos) {
    for (const no of nos || []) {
      const anterior = this.info.get(no.id) || {};
      this.info.set(no.id, {
        id: no.id,
        tipo: no.tipo ?? anterior.tipo,
        rotulo: no.rotulo ?? anterior.rotulo,
        sessao_id: no.sessao_id ?? anterior.sessao_id ?? null,
        status: no.propriedades?.status ?? no.status ?? anterior.status ?? null,
      });
    }
  }

  /** Conteúdo de trabalho de uma sessão, buscado uma vez e guardado até a próxima escrita. */
  carregarSessao(idSessao) {
    if (this.conteudoDaSessao.has(idSessao)) return Promise.resolve(this.conteudoDaSessao.get(idSessao));
    if (this.pedidosDeSessao.has(idSessao)) return this.pedidosDeSessao.get(idSessao);
    const ramo = this.state.currentBranch;
    const pedido = api.sessao(ramo, idSessao).then((dados) => {
      this.pedidosDeSessao.delete(idSessao);
      if (ramo !== this.state.currentBranch) return [];
      const nos = (dados.nos || []).filter((no) => no.sessao_id === idSessao && no.tipo !== "Sessao");
      this.registrarNos(nos);
      this.conteudoDaSessao.set(idSessao, nos);
      this.avisar();
      return nos;
    });
    this.pedidosDeSessao.set(idSessao, pedido);
    return pedido;
  }

  sessaoCarregada(idSessao) {
    return this.conteudoDaSessao.get(idSessao) || null;
  }

  /** Relê o esqueleto e as sessões já abertas depois de uma escrita no log. */
  async recarregar(sessoesAbertas = [...this.conteudoDaSessao.keys()]) {
    this.conteudoDaSessao.clear();
    await this.carregar();
    await Promise.all(sessoesAbertas.filter((id) => this.conteineres.has(id)).map((id) => this.carregarSessao(id)));
  }

  /** Troca de ramo: tudo que se sabia pertence ao outro ramo. */
  esquecer() {
    this.pedido = (this.pedido || 0) + 1;
    this.conteudoDaSessao.clear();
    this.pedidosDeSessao.clear();
    this.info.clear();
    this.carregado = false;
  }

  no(id) {
    return this.conteineres.get(id) || this.info.get(id) || null;
  }

  filhos(id) {
    return this.filhosDe.get(id) || [];
  }

  /** Cadeia de contêineres da raiz até o que guarda o nó, inclusive ele se for contêiner. */
  ancestrais(id) {
    const cadeia = [];
    let atual = this.conteineres.has(id) ? id : this.info.get(id)?.sessao_id;
    const vistos = new Set();
    while (atual && !vistos.has(atual)) {
      vistos.add(atual);
      if (this.conteineres.has(atual)) cadeia.unshift(this.conteineres.get(atual));
      atual = this.paiDe.get(atual);
    }
    return cadeia;
  }

  projetoDe(id) {
    return this.ancestrais(id).find((no) => no.tipo === "Projeto") || null;
  }

  /** Escopo de canvas que abre o contêiner dado — a Sessão leva junto o Projeto dela. */
  escopoDe(id) {
    const no = this.conteineres.get(id);
    if (!no) return null;
    return { tipo: no.tipo, id: no.id, rotulo: no.rotulo, projetoId: this.projetoDe(id)?.id || null };
  }

  /** Lista plana de contêineres de um tipo, com o caminho legível para seletores. */
  listar(tipo) {
    return [...this.conteineres.values()]
      .filter((no) => no.tipo === tipo)
      .map((no) => ({ ...no, caminho: this.ancestrais(no.id).map((anc) => anc.rotulo).join(" › ") }));
  }
}
