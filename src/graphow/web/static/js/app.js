/**
 * Graphow — composição da interface e o fluxo de dados entre as partes.
 *
 * A moldura tem faixa de ícones, explorador à esquerda, abas no
 * centro com o canvas, painéis do nó à direita e barra de status no canto. O
 * canvas em si — superfície, cartões, arestas, pan e zoom — é o mesmo de antes;
 * o que mudou foi tudo em volta dele.
 */
import { abrirMenuDeContexto } from "./menu_contexto.js";
import { AbasWorkspace } from "./abas_workspace.js";
import { api } from "./api.js";
import { BarraDeStatus } from "./barra_status.js";
import { BuscaView } from "./busca_view.js";
import { CanvasInteractions } from "./canvas_interactions.js";
import { CanvasRenderer } from "./canvas_renderer.js";
import { registrarComandos } from "./comandos_graphow.js";
import { formatarAtalho, RegistroDeComandos } from "./comandos.js";
import { ConexoesView } from "./conexoes_view.js";
import { DialogosDoGrafo } from "./dialogos_grafo.js";
import { escapeHtml } from "./dom.js";
import { ExploradorView } from "./explorador_view.js";
import { ForkDiffView } from "./fork_diff_view.js";
import { HistoricoView } from "./historico_view.js";
import { hidratarIcones, icone } from "./icones.js";
import { IndiceNavegacao } from "./indice_navegacao.js";
import { InspectorView } from "./inspector_view.js";
import { DivisorVertical, GrupoDeAbas, Lateral } from "./laterais.js";
import { LineageView } from "./lineage_view.js";
import { MarcadoresView } from "./marcadores_view.js";
import { itensDoMenuDaAresta, itensDoMenuDeRamos, itensDoMenuDoFundo, itensDoMenuDoNo } from "./menus_do_grafo.js";
import { Minimap } from "./minimap.js";
import { abrirModal, avisar } from "./modais.js";
import { apresentarTipo, corDoTipo, definirVocabulario, ehConteiner, tiposDeTrabalho } from "./ontologia_ui.js";
import { PatchConsoleView } from "./patch_console_view.js";
import { QuickFinder } from "./quick_finder.js";
import { RecorteView } from "./recorte_view.js";
import { SSEClient } from "./sse_client.js";
import { appState } from "./state.js";
import { TokenSimulatorView } from "./token_simulator_view.js";

const SSE_COALESCE_DELAY_MS = 200;
const PAINEIS_DA_SELECAO = ["conexoes", "linhagem", "agente"];
const ZOOM_MINIMO_AO_FOCAR = 0.75;

function resumirEventos(eventos) {
  const autores = [...new Set(eventos.map((evento) => evento.payload?.autor).filter(Boolean))];
  const contagem = new Map();
  for (const { tipo } of eventos) contagem.set(tipo, (contagem.get(tipo) ?? 0) + 1);
  const partes = [...contagem].map(([tipo, total]) => `${total}× ${tipo.replace(/_/g, " ")}`);
  return `${eventos.length} evento(s)${autores.length ? ` de ${autores.join(", ")}` : ""}: ${partes.join(", ")}`;
}

/** A paleta de cartões precisa existir antes do canvas ligar arrastar-e-soltar nos itens dela. */
function montarPaletaDeCartoes() {
  const alvo = document.getElementById("paleta-cartoes");
  alvo.innerHTML = `<span class="paleta-cartoes-rotulo">Novo</span>${tiposDeTrabalho().map((tipo) => `
    <div class="palette-item" draggable="true" data-type="${tipo}" style="--cor-tipo:${corDoTipo(tipo)}" title="${escapeHtml(apresentarTipo(tipo).nome)} — clique para criar ou arraste para o canvas">${icone(apresentarTipo(tipo).icone, { tamanho: 16 })}</div>`).join("")}`;
}

class GraphowApp {
  constructor() {
    hidratarIcones();
    montarPaletaDeCartoes();
    this.state = appState;
    this.indice = new IndiceNavegacao(this.state);
    this.renderer = new CanvasRenderer("canvas-viewport", this.state);
    this.interactions = new CanvasInteractions("canvas-viewport", "canvas-surface", this.state, this.renderer, (acao, dados) => this.handleAction(acao, dados));
    this.interactions.aoTransformar = () => this.aoTransformar();
    this.minimap = new Minimap("minimap-container", this.state, this.interactions);
    this.interactions.setMinimap(this.minimap);
    this.comandos = new RegistroDeComandos();
    this.dialogos = new DialogosDoGrafo({
      state: this.state,
      indice: this.indice,
      aoGravar: (opcoes) => this.aposGravar(opcoes),
      eventoNaVersao: (seq) => this.historico.eventos.find((evento) => evento.seq === seq),
      aoCriar: (id, dica) => this.aoCriarNo(id, dica),
      centroDoCanvas: () => (this.abas?.ativa?.tipo === "grafo" ? this.interactions.centroDoMundo() : null),
    });
    this.identidade = null;
    this.focoPendente = null;
    this.pedidoCanvas = 0;
    this.eventosPendentes = [];
    this.viagemEmCurso = false;
    this.proximaViagem = null;
    this.montarLaterais();
    this.montarPaineis();
    this.montarCentro();
    registrarComandos(this);
    this.state.subscribe((tipo) => this.onStateChange(tipo));
    window.addEventListener("resize", () => this.minimap.update());
    window.addEventListener("beforeunload", () => this.guardarViewportDaAba());
  }

  // ------------------------------------------------------------------ montagem

  montarLaterais() {
    const redesenharCanvas = () => this.minimap.updateFrustum();
    this.lateralEsquerda = new Lateral(document.getElementById("left-sidebar"), {
      chave: "esquerda", alca: document.getElementById("alca-esquerda"), larguraPadrao: 272, aoMudar: redesenharCanvas,
    });
    this.lateralDireita = new Lateral(document.getElementById("right-sidebar"), {
      chave: "direita", alca: document.getElementById("alca-direita"), larguraPadrao: 340, minimo: 260, maximo: 620, ladoDaAlca: "esquerda",
      aoMudar: () => { redesenharCanvas(); this.atualizarPaineisDaSelecao(); },
    });
    this.abasEsquerda = new GrupoDeAbas(document.getElementById("grupo-esquerdo"), {
      chave: "esquerda", padrao: "explorador", aoMudar: (nome) => { if (nome === "marcadores") this.marcadores.render(); },
    });
    this.abasDireita = new GrupoDeAbas(document.getElementById("grupo-direito-superior"), {
      chave: "direita", padrao: "propriedades", aoMudar: (nome) => this.aoMostrarPainelDireito(nome),
    });
    this.abasDireitaInferior = new GrupoDeAbas(document.getElementById("grupo-direito-inferior"), { chave: "direita_inferior", padrao: "historico" });
    new DivisorVertical(document.getElementById("divisor-direito"), document.getElementById("grupo-direito-superior"), document.getElementById("grupo-direito-inferior"), { chave: "direita" });
  }

  montarPaineis() {
    const acoes = this.acoesDosPaineis();
    const dependencias = { state: this.state, indice: this.indice, acoes };
    this.explorador = new ExploradorView(document.getElementById("painel-explorador"), dependencias);
    this.busca = new BuscaView(document.getElementById("painel-busca"), dependencias);
    this.marcadores = new MarcadoresView(document.getElementById("painel-marcadores"), dependencias);
    this.inspector = new InspectorView(document.getElementById("painel-propriedades"), dependencias);
    this.conexoes = new ConexoesView(document.getElementById("painel-conexoes"), dependencias);
    this.linhagem = new LineageView(document.getElementById("painel-linhagem"), dependencias);
    this.agente = new TokenSimulatorView(document.getElementById("painel-agente"), dependencias);
    this.historico = new HistoricoView(document.getElementById("painel-historico"), dependencias);
    this.paineisDaSelecao = { conexoes: this.conexoes, linhagem: this.linhagem, agente: this.agente };
    this.quickFinder = new QuickFinder({
      state: this.state,
      indice: this.indice,
      aoEscolher: (item, { novaAba }) => {
        if (ehConteiner(item.tipo)) this.abrirEscopo(this.indice.escopoDe(item.id), { novaAba });
        else this.focarNo(item.id, item);
      },
    });
    this.forkDiffView = new ForkDiffView(document.getElementById("ferramenta-diff"), dependencias);
    this.patchConsoleView = new PatchConsoleView(document.getElementById("ferramenta-patch"), { state: this.state, aoGravar: () => this.aposGravar() });
    this.barraStatus = new BarraDeStatus(document.getElementById("barra-status"), {
      state: this.state,
      acoes: { aoClicar: (item, evento) => this.aoClicarNoStatus(item, evento), zoom: () => this.interactions.zoom },
    });
  }

  /** O que os painéis podem pedir à aplicação — nada além disso atravessa a fronteira. */
  acoesDosPaineis() {
    return {
      abrirEscopo: (escopo, opcoes) => this.abrirEscopo(escopo, opcoes),
      focarNo: (id, dica) => this.focarNo(id, dica),
      menuDoNo: (evento, no) => this.abrirMenuDoNo(evento, no),
      escopoAtivo: () => (this.abas?.ativa?.tipo === "grafo" ? this.abas.ativa.escopo : this.state.escopo),
      novoNo: () => this.comandos.executar("novo-no"),
      novoConteiner: (tipo) => this.dialogos.novoConteiner({ tipo: tipo || this.tipoDeConteinerSugerido() }),
      novoFilho: (no) => this.novoFilho(no),
      salvarNo: (dados) => this.salvarNo(dados),
      alternarMarcador: (no) => this.alternarMarcador(no),
      ehMarcador: (id) => this.marcadores.contem(id),
      mostrarPainel: (nome) => this.mostrarPainelDireito(nome),
      viajarPara: (versao) => this.viajarPara(versao),
      voltarAoPresente: () => this.voltarAoPresente(),
      excluirAresta: (aresta) => this.dialogos.excluirAresta(aresta),
      destacar: (id) => this.destacar(id),
    };
  }

  montarCentro() {
    this.abas = new AbasWorkspace({
      faixa: document.getElementById("faixa-abas"),
      trilha: document.getElementById("vista-trilha"),
      botoesDeNavegacao: { voltar: document.getElementById("nav-voltar"), avancar: document.getElementById("nav-avancar") },
      indice: this.indice,
      aoAtivar: (aba, opcoes) => this.aoAtivarAba(aba, opcoes),
      aoAntesDeSair: (aba) => { if (aba.tipo === "grafo") aba.viewport = this.interactions.obterViewport(); },
    });
    this.recorteView = new RecorteView({
      painel: document.getElementById("painel-recorte"),
      aviso: document.getElementById("recorte-aviso"),
      state: this.state,
      // Outro recorte é outro conjunto de nós: o enquadramento antigo mira o vazio.
      aoMudar: async () => {
        if (await this.fetchCanvas()) this.interactions.fitToView();
      },
      acoes: {
        autoLayout: () => this.autoLayout(),
        enquadrar: () => this.interactions.fitToView(),
        alternarArestasDeSessao: () => this.alternarArestasDeSessao(),
        alternarMinimapa: () => this.alternarMinimapa(),
      },
    });
    document.getElementById("aviso-viagem").addEventListener("click", (evento) => {
      if (evento.target.closest("[data-voltar-presente]")) this.voltarAoPresente();
    });
    this.sseClient = new SSEClient(this.state, (tipo, payload) => this.onSSEEvent(tipo, payload), () => this.ressincronizarAposReconexao());
    this.aplicarMinimapa();
  }

  // ------------------------------------------------------------------ partida

  async start() {
    await Promise.all([this.fetchIdentity(), this.fetchBranches(), this.fetchOntologia()]);
    this.abas.render();
    await Promise.all([this.indice.carregar(), this.abas.trocarPara(this.abas.ativa, false, { salvarAnterior: false })]);
    this.sseClient.connect();
    this.historico.carregar();
    this.forkDiffView.updateBranchOptions();
    this.marcadores.render();
    this.atualizarPaineisDaSelecao();
  }

  async fetchIdentity() {
    // A identidade e lida do servidor, nunca escolhida aqui: a barra de status
    // mostra quem esta escrevendo, e nada nesta pagina pode mudar isso.
    const dados = await api.identidade();
    if (dados.sucesso === false) return;
    this.identidade = dados;
    this.state.sessionIdentity = dados;
    this.barraStatus.definirIdentidade(dados);
  }

  async fetchBranches() {
    const dados = await api.ramos();
    if (!Array.isArray(dados.ramos) || dados.ramos.length === 0) return;
    this.state.branches = dados.ramos;
    this.forkDiffView?.updateBranchOptions();
  }

  async fetchOntologia() {
    definirVocabulario(await api.ontologia());
  }

  /** Relê o canvas no escopo e no recorte atuais. A resposta de um pedido velho é descartada. */
  async fetchCanvas() {
    if (this.state.isTimeTraveling) return false;
    const pedido = ++this.pedidoCanvas;
    const query = `ramo=${encodeURIComponent(this.state.currentBranch)}${this.state.parametrosDeEscopo()}${this.state.parametrosDeRecorte()}`;
    const dados = await api.canvas(query);
    if (pedido !== this.pedidoCanvas) return false;
    if (dados.sucesso === false || !Array.isArray(dados.nos)) {
      avisar(`Falha ao ler o canvas: ${dados.mensagem || "resposta inválida"}`, "erro");
      return false;
    }
    this.canvasCarregado = true;
    this.indice.registrarNos(dados.nos);
    this.state.setCanvasData(dados);
    // Nó excluído, ou escondido por outro recorte, não pode seguir selecionado.
    this.descartarSelecaoForaDaTela();
    return true;
  }

  async recarregarTudo() {
    const abertas = [...this.indice.conteudoDaSessao.keys()];
    await Promise.all([this.fetchCanvas(), this.indice.recarregar(abertas), this.historico.carregar()]);
    PAINEIS_DA_SELECAO.forEach((nome) => this.paineisDaSelecao[nome].invalidar());
    this.atualizarPaineisDaSelecao();
  }

  async aposGravar({ ramoNovo = null } = {}) {
    if (ramoNovo) {
      await this.fetchBranches();
      await this.trocarRamo(ramoNovo);
      return;
    }
    await this.recarregarTudo();
  }

  // ------------------------------------------------------------------ abas e escopo

  abrirEscopo(escopo, opcoes = {}) {
    return this.abas.abrirEscopo(escopo, opcoes);
  }

  async aoAtivarAba(aba, { mudouEscopo = false, repetido = false } = {}) {
    this.mostrarFerramenta(aba.tipo === "grafo" ? null : aba.tipo);
    if (aba.tipo !== "grafo") return;
    if (repetido) {
      if (!this.consumirFocoPendente()) this.interactions.fitToView();
      return;
    }
    this.state.definirEscopo(aba.escopo);
    if (this.state.isTimeTraveling) this.state.isTimeTraveling = false;
    await this.fetchCanvas();
    this.atualizarViagem();
    if (this.consumirFocoPendente()) return;
    const viewport = mudouEscopo ? null : aba.viewport || this.state.loadViewport();
    if (!this.interactions.aplicarViewport(viewport) || !this.algumNoNaJanela()) this.interactions.fitToView();
    this.explorador.render();
    this.inspector.render();
  }

  /**
   * Nó sem coordenada gravada ganha posição calculada a cada leitura, e ela pode
   * mudar entre uma visita e outra. Um enquadramento guardado que não mostra nó
   * nenhum é pior que enquadrar tudo de novo.
   */
  algumNoNaJanela() {
    const { panX, panY, zoom } = this.interactions.obterViewport();
    const viewport = this.interactions.viewport;
    const esquerda = -panX / zoom;
    const topo = -panY / zoom;
    const direita = esquerda + viewport.clientWidth / zoom;
    const base = topo + viewport.clientHeight / zoom;
    for (const id of this.state.nodes.keys()) {
      const posicao = this.state.nodePositions.get(id);
      if (posicao && posicao.x + 220 > esquerda && posicao.x < direita && posicao.y + 80 > topo && posicao.y < base) return true;
    }
    return this.state.nodes.size === 0;
  }

  guardarViewportDaAba() {
    const aba = this.abas?.ativa;
    if (aba?.tipo !== "grafo") return;
    aba.viewport = this.interactions.obterViewport();
    this.abas.persistir();
  }

  mostrarFerramenta(tipo) {
    document.getElementById("ferramenta-diff").hidden = tipo !== "diff";
    document.getElementById("ferramenta-patch").hidden = tipo !== "patch";
    document.querySelector(".vista-acoes").style.visibility = tipo ? "hidden" : "visible";
    if (tipo === "diff") this.forkDiffView.updateBranchOptions();
  }

  descartarSelecaoForaDaTela() {
    const selecao = this.state.selectedElement;
    if (!selecao || this.focoPendente) return;
    const presente = selecao.type === "node" ? this.state.nodes.has(selecao.id) : this.state.edges.has(selecao.id);
    if (!presente) this.state.selectElement(null, null);
  }

  tipoDeConteinerSugerido() {
    const tipo = this.state.escopo?.tipo;
    return { Projeto: "Setor", Setor: "Sessao", Sessao: "Sessao" }[tipo] || "Projeto";
  }

  /** O que acabou de nascer fica à vista: o contêiner na árvore, o nó no canvas e no inspetor. */
  async aoCriarNo(id, dica) {
    if (ehConteiner(dica.tipo)) {
      this.revelarNoExplorador(id);
      return;
    }
    await this.focarNo(id, dica);
    if (this.state.selectedElement?.id === id) this.mostrarPainelDireito("propriedades");
  }

  novoFilho(no) {
    if (no.tipo === "Projeto") this.dialogos.novoConteiner({ tipo: "Setor", paiId: no.id });
    else if (no.tipo === "Setor") this.dialogos.novoConteiner({ tipo: "Sessao", paiId: no.id });
    else this.dialogos.novoNo({ sessaoId: no.id });
  }

  // ------------------------------------------------------------------ foco e seleção

  /**
   * Leva a tela até o nó: se ele está no canvas, seleciona e centraliza; se não
   * está, abre o contêiner que o mostra e termina o foco depois da leitura.
   */
  async focarNo(id, dica = null) {
    if (this.state.nodes.has(id)) {
      this.selecionarECentralizar(id);
      return;
    }
    if (this.state.isTimeTraveling) {
      avisar("Este nó não existia nesta versão do log.", "info");
      return;
    }
    const info = this.indice.no(id) || dica;
    this.focoPendente = id;
    await this.abrirEscopo(this.escopoQueMostra(id, info));
    if (this.focoPendente !== id) return;
    this.focoPendente = null;
    avisar("O nó está fora do recorte atual do canvas.", "info", {
      rotulo: "Mostrar tudo",
      executar: async () => {
        this.recorteView.limpar();
        this.focoPendente = id;
        await this.fetchCanvas();
        this.consumirFocoPendente();
      },
    });
  }

  escopoQueMostra(id, info) {
    if (ehConteiner(info?.tipo)) {
      const pai = this.indice.paiDe.get(id);
      return pai ? this.indice.escopoDe(pai) : null;
    }
    if (info?.sessao_id && this.indice.conteineres.has(info.sessao_id)) return this.indice.escopoDe(info.sessao_id);
    return null;
  }

  consumirFocoPendente() {
    const id = this.focoPendente;
    if (!id || !this.state.nodes.has(id)) return false;
    this.focoPendente = null;
    this.selecionarECentralizar(id);
    return true;
  }

  /** Ir até um nó é querer lê-lo: abaixo de 75% o cartão vira um risco, então o zoom sobe. */
  selecionarECentralizar(id) {
    if (this.interactions.zoom < ZOOM_MINIMO_AO_FOCAR) this.interactions.zoom = ZOOM_MINIMO_AO_FOCAR;
    this.state.selectElement("node", id);
    this.interactions.centralizarNo(id);
    this.quickFinder.lembrar(id);
  }

  selecionarEMostrar(no, painel) {
    if (this.state.nodes.has(no.id)) this.state.selectElement("node", no.id);
    else this.focarNo(no.id, no);
    this.mostrarPainelDireito(painel);
  }

  destacar(id) {
    const selecionado = this.state.selectedElement?.type === "node" ? this.state.selectedElement.id : null;
    this.renderer.applyPathHighlight(id || selecionado);
  }

  onStateChange(tipo) {
    if (tipo === "CANVAS_UPDATED") {
      this.renderer.render();
      this.destacar(null);
      this.inspector.render();
      this.minimap.update();
      this.recorteView.render();
      this.barraStatus.render();
      this.atualizarVazio();
    } else if (tipo === "SELECTION_CHANGED") {
      this.renderer.render();
      this.destacar(null);
      this.inspector.render();
      this.explorador.render();
      this.marcadores.render();
      this.atualizarPaineisDaSelecao();
    }
  }

  // ------------------------------------------------------------------ painéis

  painelVisivel(nome) {
    return !this.lateralDireita.recolhida && this.abasDireita.mostra(nome);
  }

  atualizarPaineisDaSelecao() {
    for (const nome of PAINEIS_DA_SELECAO) {
      if (this.painelVisivel(nome)) this.paineisDaSelecao[nome].atualizar();
    }
  }

  aoMostrarPainelDireito(nome) {
    if (this.paineisDaSelecao[nome]) this.paineisDaSelecao[nome].atualizar();
    if (nome === "propriedades") this.inspector.render();
  }

  mostrarPainelDireito(nome) {
    this.lateralDireita.expandir();
    if (this.abasDireita.mostra(nome)) this.aoMostrarPainelDireito(nome);
    else this.abasDireita.ativar(nome);
  }

  mostrarPainelEsquerdo(nome) {
    this.lateralEsquerda.expandir();
    this.abasEsquerda.ativar(nome);
    if (nome === "busca") this.busca.focar();
  }

  mostrarHistorico() {
    this.lateralDireita.expandir();
    document.getElementById("painel-historico").scrollTo({ top: 0, behavior: "smooth" });
  }

  revelarNoExplorador(id) {
    this.mostrarPainelEsquerdo("explorador");
    this.explorador.revelar(id);
  }

  alternarMarcador(no) {
    if (!no) return;
    const marcado = this.marcadores.alternar(no);
    avisar(marcado ? `“${no.rotulo}” fixado nos marcadores` : "Marcador removido", "info");
    if (this.state.selectedElement?.id === no.id) this.inspector.render();
  }

  async salvarNo(dados) {
    const recibo = await api.editarNo({ ...dados, ramo_id: this.state.currentBranch });
    if (!recibo.sucesso) {
      avisar(`Recusado: ${recibo.mensagem || "falha desconhecida"}`, "erro");
      return recibo;
    }
    avisar("Nó atualizado", "sucesso");
    await this.recarregarTudo();
    return recibo;
  }

  // ------------------------------------------------------------------ canvas

  handleAction(acao, dados = {}) {
    const escrita = ["OPEN_CREATE_NODE_MODAL", "OPEN_CREATE_EDGE_MODAL"].includes(acao);
    if (escrita && this.state.isTimeTraveling) {
      avisar("A tela mostra o passado. Volte ao presente para editar.", "info", { rotulo: "Voltar ao presente", executar: () => this.voltarAoPresente() });
      return;
    }
    const tratadores = {
      OPEN_CREATE_NODE_MODAL: () => this.dialogos.novoNo({ tipo: dados.type, x: dados.x, y: dados.y }),
      OPEN_CREATE_EDGE_MODAL: () => this.dialogos.novaAresta(dados.origem_id, dados.destino_id),
      NODE_DOUBLE_CLICK: () => this.aoDuploCliqueNoNo(dados.id),
      CANVAS_CONTEXT_MENU: () => this.aoMenuDoCanvas(dados),
      REFRESH_CANVAS: () => this.fetchCanvas(),
    };
    tratadores[acao]?.();
  }

  aoDuploCliqueNoNo(id) {
    const no = this.state.nodes.get(id);
    if (!no) return;
    if (ehConteiner(no.tipo)) this.abrirEscopo(this.indice.escopoDe(id) || { tipo: no.tipo, id, rotulo: no.rotulo });
    else this.mostrarPainelDireito("propriedades");
  }

  aoMenuDoCanvas({ evento, noId, arestaId, x, y }) {
    if (noId && this.state.nodes.has(noId)) {
      this.state.selectElement("node", noId);
      abrirMenuDeContexto(evento, itensDoMenuDoNo(this, this.state.nodes.get(noId)));
    } else if (arestaId && this.state.edges.has(arestaId)) {
      this.state.selectElement("edge", arestaId);
      abrirMenuDeContexto(evento, itensDoMenuDaAresta(this, this.state.edges.get(arestaId)));
    } else {
      abrirMenuDeContexto(evento, itensDoMenuDoFundo(this, { x, y }));
    }
  }

  abrirMenuDoNo(evento, no) {
    if (!no) return;
    const completo = this.state.nodes.get(no.id) || this.indice.no(no.id) || no;
    abrirMenuDeContexto(evento, itensDoMenuDoNo(this, completo));
  }

  autoLayout() {
    this.interactions.applyAutoLayout();
    avisar("Arranjo hierárquico aplicado e gravado no grafo", "sucesso");
  }

  alternarArestasDeSessao() {
    this.state.toggleStructuralEdges();
    this.recorteView.render();
  }

  alternarMinimapa() {
    this.state.alternarMinimapa();
    this.aplicarMinimapa();
    this.recorteView.render();
  }

  aplicarMinimapa() {
    document.getElementById("minimap-container").classList.toggle("is-oculto", !this.state.mostrarMinimapa);
    if (this.state.mostrarMinimapa) this.minimap.update();
  }

  aoTransformar() {
    const indicador = document.getElementById("zoom-indicator");
    if (indicador) indicador.textContent = `${Math.round(this.interactions.zoom * 100)}%`;
  }

  /** Canvas vazio diz se o escopo não tem nada ou se foi o recorte que escondeu tudo. */
  atualizarVazio() {
    const vazio = document.getElementById("canvas-vazio");
    vazio.hidden = !this.canvasCarregado || this.state.nodes.size > 0;
    const pelaRecorte = Boolean(this.state.parametrosDeRecorte());
    vazio.querySelector(".canvas-vazio-titulo").textContent = pelaRecorte ? "O recorte atual esconde tudo neste escopo" : "Nada neste escopo ainda";
    vazio.querySelector("[data-so-com-recorte]").hidden = !pelaRecorte;
  }

  // ------------------------------------------------------------------ ramos e log

  async trocarRamo(ramo) {
    if (ramo === this.state.currentBranch) return;
    this.historico.pararReproducao();
    this.state.isTimeTraveling = false;
    this.state.selectElement(null, null);
    this.state.setBranch(ramo);
    this.state.maxLogVersion = 0;
    this.indice.esquecer();
    document.querySelector("[data-ramo-atual]").textContent = ramo;
    await Promise.all([this.fetchCanvas(), this.indice.carregar(), this.historico.carregar()]);
    this.interactions.fitToView();
    this.atualizarViagem();
    this.marcadores.render();
    this.forkDiffView.updateBranchOptions();
    avisar(`Ramo “${ramo}”`, "info");
  }

  /** Mostra o grafo como estava numa versão do log. Pedidos durante uma leitura se fundem no último. */
  async viajarPara(versao) {
    const alvo = Math.max(0, Math.min(Math.round(versao), this.state.maxLogVersion));
    if (alvo >= this.state.maxLogVersion) {
      await this.voltarAoPresente();
      return;
    }
    if (this.viagemEmCurso) {
      this.proximaViagem = alvo;
      return;
    }
    this.viagemEmCurso = true;
    this.state.isTimeTraveling = true;
    const dados = await api.estadoNaVersao(alvo, this.state.currentBranch);
    this.viagemEmCurso = false;
    if (this.state.isTimeTraveling && Array.isArray(dados.nos)) this.state.setCanvasData(dados);
    else if (!Array.isArray(dados.nos)) avisar(`Falha ao reconstruir a versão #${alvo}`, "erro");
    this.atualizarViagem();
    const proxima = this.proximaViagem;
    this.proximaViagem = null;
    if (proxima !== null && proxima !== alvo) this.viajarPara(proxima);
  }

  async voltarAoPresente() {
    this.historico.pararReproducao();
    this.proximaViagem = null;
    this.state.isTimeTraveling = false;
    await this.fetchCanvas();
    this.atualizarViagem();
  }

  atualizarViagem() {
    const viajando = this.state.isTimeTraveling;
    document.body.classList.toggle("is-viajando", viajando);
    const aviso = document.getElementById("aviso-viagem");
    aviso.hidden = !viajando;
    if (viajando) {
      aviso.innerHTML = `${icone("history", { tamanho: 15 })}<span>Vendo o grafo no log <strong>#${this.state.logVersion}</strong> de #${this.state.maxLogVersion} · somente leitura, sem recorte</span><button class="botao mod-pequeno mod-cta" data-voltar-presente>Voltar ao presente</button>`;
    }
    this.historico.atualizarViagem();
    this.historico.renderLista();
    this.barraStatus.render();
    this.recorteView.render();
  }

  // ------------------------------------------------------------------ tempo real

  onSSEEvent(tipo, payload) {
    if (tipo === "ramo_criado") this.fetchBranches();
    if (payload?.ramo_id && payload.ramo_id !== this.state.currentBranch) return;
    if (payload?.seq) this.state.maxLogVersion = Math.max(this.state.maxLogVersion, payload.seq);
    this.eventosPendentes.push({ tipo, payload });
    clearTimeout(this.temporizadorSSE);
    this.temporizadorSSE = setTimeout(() => this.drenarEventos(), SSE_COALESCE_DELAY_MS);
  }

  /** Relê tudo uma vez por rajada; só avisa do que veio de outro autor — o próprio já foi avisado. */
  async drenarEventos() {
    const eventos = this.eventosPendentes;
    this.eventosPendentes = [];
    if (eventos.length === 0) return;
    await this.recarregarTudo();
    if (this.state.isTimeTraveling) this.atualizarViagem();
    const externos = eventos.filter((evento) => evento.payload?.autor !== this.identidade?.autor);
    if (externos.length) avisar(resumirEventos(externos), "info");
  }

  /**
   * O stream caiu e voltou: o que passou no intervalo nao e reenviado. So a
   * releitura do canvas e da linha do tempo devolve a pagina ao presente.
   */
  ressincronizarAposReconexao() {
    this.eventosPendentes = [];
    clearTimeout(this.temporizadorSSE);
    this.recarregarTudo();
    avisar("Conexão restabelecida: dados relidos do servidor", "info");
  }

  // ------------------------------------------------------------------ status e ajuda

  aoClicarNoStatus(item, evento) {
    const acoes = {
      ramo: () => abrirMenuDeContexto({ x: evento.clientX, y: evento.clientY - 8 }, itensDoMenuDeRamos(this)),
      versao: () => this.mostrarHistorico(),
      recorte: () => this.recorteView.alternar(true),
      zoom: () => this.interactions.resetZoom(),
      contagem: () => this.interactions.fitToView(),
    };
    acoes[item]?.();
  }

  mostrarAtalhos() {
    const doCanvas = [
      ["Arrastar o fundo", "Mover o canvas"], ["Espaço + arrastar", "Mover o canvas"], ["Roda do mouse", "Zoom no cursor"],
      ["Duplo clique no fundo", "Novo nó naquele ponto"], ["Duplo clique num contêiner", "Abrir o contêiner"],
      ["Arrastar de uma porta", "Criar aresta"], ["Clique direito", "Menu do nó, da aresta ou do fundo"], ["Esc", "Limpar a seleção"],
    ];
    const comAtalho = [...this.comandos.comandos.values()].filter((comando) => comando.atalho || comando.atalhoExibido);
    const linhas = comAtalho.map((comando) => {
      const teclas = comando.atalhoExibido ? [comando.atalhoExibido] : [].concat(comando.atalho);
      return `<span>${escapeHtml(comando.nome)}</span><span>${teclas.map((tecla) => `<kbd>${escapeHtml(formatarAtalho(tecla))}</kbd>`).join(" ")}</span>`;
    });
    abrirModal({
      titulo: "Atalhos de teclado",
      largura: 560,
      corpo: `
        <div class="tabela-atalhos">
          <div class="secao-atalhos">Comandos</div>${linhas.join("")}
          <div class="secao-atalhos">Canvas</div>${doCanvas.map(([gesto, efeito]) => `<span>${efeito}</span><span><kbd>${escapeHtml(gesto)}</kbd></span>`).join("")}
        </div>`,
      botoes: [{ rotulo: "Fechar", primario: true }],
    });
  }
}

window.addEventListener("DOMContentLoaded", () => {
  new GraphowApp().start();
});
