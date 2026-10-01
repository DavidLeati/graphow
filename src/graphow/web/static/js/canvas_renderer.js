import { escapeHtml } from "./dom.js";
import { descreverHistoricoDoNo, foiAlterado, formatarIdadeCurta } from "./idade.js";
import { caminhoSvg, tracarCurva } from "./geometria_aresta.js";

const TAMANHO_PADRAO_DO_CARTAO = { largura: 220, altura: 150 };

// Os tipos de aresta que ganharam um marcador de seta em setupDefs. Os demais
// usam a seta cinza padrao. E um conjunto fixo porque perguntar ao DOM, uma vez
// por aresta, se o marcador existe custava uma busca na camada inteira a cada uma.
const TIPOS_COM_MARCADOR = new Set([
  "contem", "bloqueia", "produz", "decompoe", "depende_de", "escopa", "justifica", "deriva_de", "orienta",
]);

const INTERVALO_DO_RELOGIO_MS = 60000;

/**
 * Precision Spatial Canvas Graph Renderer (Crisp SVG Edges & Clean HTML Node Cards)
 */
export class CanvasRenderer {
  constructor(containerId, state) {
    this.container = document.getElementById(containerId);
    this.nodesLayer = document.getElementById("nodes-layer");
    this.edgesLayer = document.getElementById("edges-layer");
    this.surface = document.getElementById("canvas-surface");
    this.state = state;
    this.nodeElements = new Map();
    // Largura e altura de cada cartao, medidas de uma vez ao fim de renderNodes.
    // Ler offsetWidth no meio do desenho das arestas, entre uma escrita e outra
    // no DOM, forcava um reflow por aresta.
    this.tamanhosDosCartoes = new Map();
    // Id da aresta -> <path> desenhado, e id do no -> ids das arestas que o
    // tocam. Ambos sao refeitos por renderEdges.
    this.elementosDasArestas = new Map();
    this.arestasPorNo = new Map();
    this.hoveredNodeId = null;
    this.setupDefs();
    // A idade e relativa: sem este relogio, um card diria "3 min" a tarde
    // inteira, e uma idade errada e pior do que idade nenhuma.
    this.relogioDeIdade = setInterval(() => this.atualizarIdades(), INTERVALO_DO_RELOGIO_MS);
  }

  atualizarIdades() {
    for (const [id, el] of this.nodeElements.entries()) {
      const node = this.state.nodes.get(id);
      const alvo = el.querySelector(".node-age");
      if (node && alvo) alvo.textContent = formatarIdadeCurta(node.criado_em);
    }
  }

  setupDefs() {
    this.edgesLayer.innerHTML = `
      <defs>
        <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5" markerHeight="5" orient="auto">
          <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill="#94a3b8" />
        </marker>
        <marker id="arrow-contem" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5" markerHeight="5" orient="auto">
          <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill="#3b82f6" />
        </marker>
        <marker id="arrow-bloqueia" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto">
          <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill="#ef4444" />
        </marker>
        <marker id="arrow-produz" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5" markerHeight="5" orient="auto">
          <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill="#a855f7" />
        </marker>
        <marker id="arrow-decompoe" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5" markerHeight="5" orient="auto">
          <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill="#f43f5e" />
        </marker>
        <marker id="arrow-depende_de" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5" markerHeight="5" orient="auto">
          <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill="#0ea5e9" />
        </marker>
        <marker id="arrow-escopa" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5" markerHeight="5" orient="auto">
          <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill="#ef4444" />
        </marker>
        <marker id="arrow-justifica" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5" markerHeight="5" orient="auto">
          <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill="#10b981" />
        </marker>
        <marker id="arrow-deriva_de" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5" markerHeight="5" orient="auto">
          <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill="#06b6d4" />
        </marker>
        <marker id="arrow-orienta" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5" markerHeight="5" orient="auto">
          <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill="#65a30d" />
        </marker>
      </defs>
    `;
  }

  render() {
    this.renderNodes();
    this.renderEdges();
  }

  renderNodes() {
    this.nodesLayer.innerHTML = "";
    this.nodeElements.clear();

    for (const [id, node] of this.state.nodes.entries()) {
      const pos = this.state.nodePositions.get(id) || { x: 100, y: 100 };
      const el = document.createElement("div");
      el.className = `node-card ${this.state.selectedElement?.id === id ? "selected" : ""}`;
      if (node.esta_bloqueado) el.classList.add("blocked-task");
      el.id = `node-${id}`;
      el.style.left = `${pos.x}px`;
      el.style.top = `${pos.y}px`;

      const statusBadge = node.propriedades?.status ? `<span class="badge badge-status">${escapeHtml(node.propriedades.status)}</span>` : "";
      const lockBadge = node.lock_ativo ? `<span class="badge badge-locked">🔒 ${escapeHtml(node.lock_ativo)}</span>` : "";
      const blockBadge = node.esta_bloqueado ? `<span class="badge badge-blocked">⚠️ Bloqueado</span>` : "";

      // Tudo o que vem do grafo passa por escapeHtml: status, posse, tipo e id
      // são escritos por agentes, e o card roda na origem que escreve como humano.
      const tipoSeguro = escapeHtml(node.tipo);
      const idSeguro = escapeHtml(id);
      el.innerHTML = `
        <div class="node-header node-type-${tipoSeguro}">
          <span class="node-type-label">${tipoSeguro}</span>
          <span class="node-id-badge">#${escapeHtml(id.slice(-6))}</span>
        </div>
        <div class="node-body">
          <div class="node-title" title="${escapeHtml(node.rotulo)}">${escapeHtml(node.rotulo)}</div>
          <div class="node-meta">
            ${statusBadge}
            ${lockBadge}
            ${blockBadge}
          </div>
          ${this.montarProgressoDaSubarvore(node)}
          ${this.montarRodapeDeIdade(node)}
        </div>
        <div class="port port-in" data-port-in="${idSeguro}" title="Entrada"></div>
        <div class="port port-out" data-port-out="${idSeguro}" title="Saída"></div>
        <div class="port port-top" data-port-top="${idSeguro}" title="Superior"></div>
        <div class="port port-bottom" data-port-bottom="${idSeguro}" title="Inferior"></div>
      `;

      // Selection on click
      el.addEventListener("click", (e) => {
        e.stopPropagation();
        this.state.selectElement("node", id);
      });

      // Path highlighting on hover
      el.addEventListener("mouseenter", () => {
        this.hoveredNodeId = id;
        this.applyPathHighlight(id);
      });

      el.addEventListener("mouseleave", () => {
        this.hoveredNodeId = null;
        this.applyPathHighlight(this.state.selectedElement?.type === "node" ? this.state.selectedElement.id : null);
      });

      this.nodesLayer.appendChild(el);
      this.nodeElements.set(id, el);
    }

    this.medirTamanhosDosCartoes();
  }

  /**
   * Mede todos os cartoes numa unica passada, so com leituras: o navegador faz
   * o layout uma vez, na primeira, e as demais saem do mesmo layout. O tamanho
   * guardado e o da classe atual da superficie — em lod-macro o CSS encolhe o
   * cartao —, por isso setLOD remede quando a classe muda.
   */
  medirTamanhosDosCartoes() {
    this.tamanhosDosCartoes.clear();
    for (const [id, elemento] of this.nodeElements) {
      this.tamanhosDosCartoes.set(id, { largura: elemento.offsetWidth, altura: elemento.offsetHeight });
    }
  }

  renderEdges() {
    let defs = this.edgesLayer.querySelector("defs");
    if (!defs) {
      this.setupDefs();
      defs = this.edgesLayer.querySelector("defs");
    }

    const oldPaths = this.edgesLayer.querySelectorAll("path.edge-path");
    oldPaths.forEach((p) => p.remove());
    this.elementosDasArestas.clear();
    this.arestasPorNo.clear();

    for (const [id, edge] of this.state.edges.entries()) {
      if (!this.state.nodePositions.has(edge.origem_id) || !this.state.nodePositions.has(edge.destino_id)) continue;

      // O indice cobre tambem as arestas ocultas: quem arrasta ou troca a
      // selecao precisa achar as arestas de um no sem varrer o grafo inteiro.
      this.indexarAresta(edge.origem_id, id);
      this.indexarAresta(edge.destino_id, id);

      if (!this.arestaVisivel(edge)) continue;

      const path = this.criarCaminhoDaAresta(id, edge);
      this.elementosDasArestas.set(id, path);
      this.edgesLayer.appendChild(path);
    }
  }

  indexarAresta(noId, arestaId) {
    let ids = this.arestasPorNo.get(noId);
    if (!ids) {
      ids = new Set();
      this.arestasPorNo.set(noId, ids);
    }
    ids.add(arestaId);
  }

  /** Arestas `produz` ficam ocultas, a menos que uma ponta esteja selecionada. */
  arestaVisivel(edge) {
    if (!this.state.hideStructuralEdges || edge.tipo !== "produz") return true;
    const selecionado = this.state.selectedElement?.id;
    return selecionado === edge.origem_id || selecionado === edge.destino_id;
  }

  /** O atributo `d` da aresta, a partir da posicao e do tamanho em cache dos dois cartoes. */
  caminhoDaAresta(edge) {
    return caminhoSvg(tracarCurva(this.retanguloDoCartao(edge.origem_id), this.retanguloDoCartao(edge.destino_id)));
  }

  criarCaminhoDaAresta(id, edge) {
    const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
    path.setAttribute("d", this.caminhoDaAresta(edge));
    path.setAttribute("class", `edge-path edge-${edge.tipo} ${this.state.selectedElement?.id === id ? "selected" : ""}`);
    path.setAttribute("data-edge-id", id);
    path.setAttribute("data-origem", edge.origem_id);
    path.setAttribute("data-destino", edge.destino_id);

    const markerId = TIPOS_COM_MARCADOR.has(edge.tipo) ? `arrow-${edge.tipo}` : "arrow";
    path.setAttribute("marker-end", `url(#${markerId})`);
    path.style.stroke = `var(--edge-${edge.tipo}, var(--edge-default))`;

    path.addEventListener("click", (e) => {
      e.stopPropagation();
      this.state.selectElement("edge", id);
    });
    return path;
  }

  /**
   * Recalcula so o `d` das arestas ligadas ao no — o que arrastar um cartao
   * muda. Refazer todas as arestas a cada mousemove custava O(arestas) em DOM
   * para mover algo que toca meia duzia delas.
   */
  redesenharArestasDoNo(noId) {
    const ids = this.arestasPorNo.get(noId);
    if (!ids) return;
    for (const id of ids) {
      const path = this.elementosDasArestas.get(id);
      const edge = this.state.edges.get(id);
      if (path && edge) path.setAttribute("d", this.caminhoDaAresta(edge));
    }
  }

  /** O cartão como retângulo no plano do canvas, para a geometria das arestas. */
  retanguloDoCartao(id) {
    const posicao = this.state.nodePositions.get(id) ?? { x: 0, y: 0 };
    // Le do cache, nunca do DOM: esta funcao roda uma vez por ponta de aresta,
    // no meio de um laco que escreve no DOM, e uma leitura de layout ali
    // forcaria um reflow a cada chamada.
    const tamanho = this.tamanhosDosCartoes.get(id);
    return {
      x: posicao.x,
      y: posicao.y,
      largura: tamanho?.largura || TAMANHO_PADRAO_DO_CARTAO.largura,
      altura: tamanho?.altura || TAMANHO_PADRAO_DO_CARTAO.altura,
    };
  }

  /**
   * Mede cada cartão no tamanho cheio, para quem precisa do espaço que ele
   * ocupa de verdade — o arranjo automático. Em zoom distante o cartão encolhe
   * por CSS, e arranjar pelo tamanho encolhido deixaria os cartões colados
   * assim que a vista se aproximasse.
   */
  medirCartoes() {
    const encolhido = this.surface?.classList.contains("lod-macro");
    if (encolhido) this.surface.classList.remove("lod-macro");
    const tamanhos = new Map();
    for (const [id, elemento] of this.nodeElements) {
      tamanhos.set(id, { largura: elemento.offsetWidth, altura: elemento.offsetHeight });
    }
    if (encolhido) this.surface.classList.add("lod-macro");
    return tamanhos;
  }

  applyPathHighlight(targetNodeId) {
    if (!targetNodeId) {
      this.nodesLayer.querySelectorAll(".node-card").forEach((el) => {
        el.classList.remove("node-dimmed", "node-highlighted");
      });
      this.edgesLayer.querySelectorAll(".edge-path").forEach((el) => {
        el.classList.remove("edge-dimmed", "edge-highlighted");
      });
      return;
    }

    const connectedNodes = new Set([targetNodeId]);
    const connectedEdges = new Set();

    for (const [edgeId, edge] of this.state.edges.entries()) {
      if (edge.origem_id === targetNodeId || edge.destino_id === targetNodeId) {
        connectedNodes.add(edge.origem_id);
        connectedNodes.add(edge.destino_id);
        connectedEdges.add(edgeId);
      }
    }

    this.nodesLayer.querySelectorAll(".node-card").forEach((el) => {
      const id = el.id.replace("node-", "");
      if (connectedNodes.has(id)) {
        el.classList.add("node-highlighted");
        el.classList.remove("node-dimmed");
      } else {
        el.classList.add("node-dimmed");
        el.classList.remove("node-highlighted");
      }
    });

    this.edgesLayer.querySelectorAll(".edge-path").forEach((el) => {
      const id = el.getAttribute("data-edge-id");
      if (connectedEdges.has(id)) {
        el.classList.add("edge-highlighted");
        el.classList.remove("edge-dimmed");
      } else {
        el.classList.add("edge-dimmed");
        el.classList.remove("edge-highlighted");
      }
    });
  }

  setLOD(zoom) {
    if (!this.surface) return;
    const macro = zoom < 0.45;
    // Roda a cada passo da roda do mouse; so a troca real de classe muda o
    // tamanho dos cartoes e justifica remedir e redesenhar as arestas.
    if (macro === this.surface.classList.contains("lod-macro")) return;
    this.surface.classList.toggle("lod-macro", macro);
    this.medirTamanhosDosCartoes();
    this.renderEdges();
  }

  /**
   * Barra de progresso do super-no: quantas tarefas da subarvore fecharam.
   * So aparece em quem tem subarvore com tarefa; um no folha nao ganha barra,
   * e um contêiner sem tarefa nenhuma tambem nao — uma barra vazia diria que
   * ha trabalho parado onde nao ha trabalho.
   */
  montarProgressoDaSubarvore(node) {
    const r = node.resumo;
    if (!r || !r.tarefas_totais) return "";
    const fracao = Math.round((r.tarefas_concluidas / r.tarefas_totais) * 100);
    const abertas = r.tarefas_abertas
      ? `<span class="rollup-abertas">${r.tarefas_abertas} abertas</span>`
      : `<span class="rollup-fechado">completo</span>`;
    const duvidas = r.questoes_abertas
      ? `<span class="rollup-duvidas">${r.questoes_abertas} dúvidas</span>`
      : "";
    return `
      <div class="node-rollup" title="${r.total_nos} nós na subárvore">
        <div class="rollup-barra"><div class="rollup-preenchida" style="width:${fracao}%"></div></div>
        <div class="rollup-legenda">
          <span class="rollup-contagem">${r.tarefas_concluidas}/${r.tarefas_totais}</span>
          ${abertas}
          ${duvidas}
        </div>
      </div>
    `;
  }

  /**
   * Rodape que responde as duas perguntas que o card nao respondia: ha quanto
   * tempo ele existe e se veio antes ou depois de outro. A sequencia do log e
   * quem decide a ordem; o "ha 3 min" so diz a idade.
   */
  montarRodapeDeIdade(node) {
    const seq = node.seq_criacao ?? 0;
    if (!seq && !node.criado_em) return "";
    const marcaDeEdicao = foiAlterado(node) ? `<span class="node-edited" title="Alterado depois de criado">editado</span>` : "";
    return `
      <div class="node-footer" title="${escapeHtml(descreverHistoricoDoNo(node))}">
        <span class="node-seq">log #${seq}</span>
        ${marcaDeEdicao}
        <span class="node-age">${formatarIdadeCurta(node.criado_em)}</span>
      </div>
    `;
  }
}
