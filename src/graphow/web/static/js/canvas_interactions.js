/**
 * Canvas Pan, Anchored Zoom, Drag & Drop, Port Connections and Large-Graph Ergonomics
 */

import { calcularLayoutHierarquico } from "./layout_hierarquico.js";

// O piso do zoom desceu de 0,2 para 0,1 quando o arranjo passou a caber
// centenas de nós numa tela: parar em 0,2 fazia "enquadrar tudo" enquadrar
// só um pedaço. Nessa distância o cartão vira uma tarja, que é o que se quer
// ver de longe — a forma do grafo, não o texto.
const ZOOM_MINIMO = 0.1;
const ZOOM_MAXIMO = 2.5;
const ZOOM_MAXIMO_AO_ENQUADRAR = 1.2;

export class CanvasInteractions {
  constructor(viewportId, surfaceId, state, renderer, onAction) {
    this.viewport = document.getElementById(viewportId);
    this.surface = document.getElementById(surfaceId);
    this.state = state;
    this.renderer = renderer;
    this.onAction = onAction;
    this.minimap = null;

    this.panX = 0;
    this.panY = 0;
    this.zoom = 1;
    this.isPanning = false;
    this.startPan = { x: 0, y: 0 };
    this.isSpacePressed = false;

    this.draggingNode = null;
    this.dragOffset = { x: 0, y: 0 };

    this.connectingFromId = null;
    this.tempEdgePath = null;

    this.initEvents();
  }

  setMinimap(minimap) {
    this.minimap = minimap;
  }

  initEvents() {
    // Spacebar pan tracking
    window.addEventListener("keydown", (e) => {
      if (e.code === "Space" && document.activeElement.tagName !== "INPUT" && document.activeElement.tagName !== "TEXTAREA") {
        this.isSpacePressed = true;
        this.viewport.style.cursor = "grab";
      } else if (e.key === "f" || e.key === "F") {
        if (document.activeElement.tagName !== "INPUT" && document.activeElement.tagName !== "TEXTAREA") {
          e.preventDefault();
          this.fitToView();
        }
      } else if (e.key === "z" || e.key === "Z") {
        if (document.activeElement.tagName !== "INPUT" && document.activeElement.tagName !== "TEXTAREA") {
          e.preventDefault();
          this.zoomToSelection();
        }
      } else if (e.key === "0") {
        if (document.activeElement.tagName !== "INPUT" && document.activeElement.tagName !== "TEXTAREA") {
          e.preventDefault();
          this.resetZoom();
        }
      } else if (e.key === "Escape") {
        // Esc dentro de um campo do inspetor é desistir da digitação, não da seleção.
        const emCampo = ["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement.tagName);
        if (this.state.selectedElement && !emCampo) {
          this.state.selectElement(null, null);
        }
      }
    });

    window.addEventListener("keyup", (e) => {
      if (e.code === "Space") {
        this.isSpacePressed = false;
        this.viewport.style.cursor = "default";
      }
    });

    // Mouse handlers
    this.viewport.addEventListener("mousedown", (e) => this.onMouseDown(e));
    window.addEventListener("mousemove", (e) => this.onMouseMove(e));
    window.addEventListener("mouseup", (e) => this.onMouseUp(e));
    this.viewport.addEventListener("wheel", (e) => this.onWheel(e), { passive: false });

    // Double click to create node; on a container card, open it
    this.viewport.addEventListener("dblclick", (e) => {
      const card = e.target.closest(".node-card");
      if (card) {
        this.onAction("NODE_DOUBLE_CLICK", { id: card.id.replace("node-", "") });
        return;
      }
      // A camada de nós cobre a superfície inteira: um clique no fundo cai nela.
      const noFundo = [this.viewport, this.surface, this.renderer.nodesLayer].includes(e.target) || e.target.tagName === "svg";
      if (noFundo) {
        const { x, y } = this.pontoNoMundo(e);
        this.onAction("OPEN_CREATE_NODE_MODAL", { x, y, type: "Task" });
      }
    });

    // Clique direito: o menu depende do que está sob o cursor — nó, aresta ou fundo.
    this.viewport.addEventListener("contextmenu", (e) => {
      const card = e.target.closest(".node-card");
      const aresta = e.target.closest(".edge-path");
      this.onAction("CANVAS_CONTEXT_MENU", {
        evento: e,
        noId: card ? card.id.replace("node-", "") : null,
        arestaId: aresta ? aresta.getAttribute("data-edge-id") : null,
        ...this.pontoNoMundo(e),
      });
    });

    // Floating Palette Popover Toggle
    const btnFloatingPalette = document.getElementById("btn-floating-palette");
    const popoverFloatingPalette = document.getElementById("floating-palette-popover");

    if (btnFloatingPalette && popoverFloatingPalette) {
      btnFloatingPalette.addEventListener("click", (e) => {
        e.stopPropagation();
        const isOpen = popoverFloatingPalette.style.display !== "none";
        popoverFloatingPalette.style.display = isOpen ? "none" : "block";
      });

      window.addEventListener("click", (e) => {
        if (!e.target.closest("#floating-palette-container")) {
          popoverFloatingPalette.style.display = "none";
        }
      });

      window.addEventListener("keydown", (e) => {
        if (e.key === "Escape" && popoverFloatingPalette.style.display !== "none") {
          popoverFloatingPalette.style.display = "none";
        }
      });
    }

    // Palette Drag & Drop and Click-to-Create
    const paletteItems = document.querySelectorAll(".palette-item");
    for (const item of paletteItems) {
      item.addEventListener("dragstart", (e) => {
        e.dataTransfer.setData("text/plain", item.dataset.type);
      });

      item.addEventListener("click", (e) => {
        e.stopPropagation();
        if (popoverFloatingPalette) popoverFloatingPalette.style.display = "none";
        const nodeType = item.dataset.type || "Task";
        const vpW = this.viewport.clientWidth;
        const vpH = this.viewport.clientHeight;
        const x = (vpW / 2 - this.panX) / this.zoom - 110;
        const y = (vpH / 2 - this.panY) / this.zoom - 40;
        this.onAction("OPEN_CREATE_NODE_MODAL", { x, y, type: nodeType });
      });
    }

    this.viewport.addEventListener("dragover", (e) => e.preventDefault());
    this.viewport.addEventListener("drop", (e) => {
      e.preventDefault();
      const nodeType = e.dataTransfer.getData("text/plain");
      if (!nodeType) return;
      const { x, y } = this.pontoNoMundo(e);
      this.onAction("OPEN_CREATE_NODE_MODAL", { x, y, type: nodeType });
    });
  }

  /** Converte a posição do ponteiro em coordenada da superfície do canvas. */
  pontoNoMundo(e) {
    const rect = this.surface.getBoundingClientRect();
    return { x: (e.clientX - rect.left) / this.zoom, y: (e.clientY - rect.top) / this.zoom };
  }

  /** Ponto da superfície no centro da janela, onde nasce um nó criado sem clique no canvas. */
  centroDoMundo() {
    return {
      x: (this.viewport.clientWidth / 2 - this.panX) / this.zoom - 110,
      y: (this.viewport.clientHeight / 2 - this.panY) / this.zoom - 40,
    };
  }

  /** Centraliza o nó na janela sem mudar o zoom — o que a busca e a árvore pedem. */
  centralizarNo(id) {
    const pos = this.state.nodePositions.get(id);
    if (!pos) return false;
    const card = document.getElementById(`node-${id}`);
    const largura = card?.offsetWidth || 220;
    const altura = card?.offsetHeight || 80;
    this.panX = this.viewport.clientWidth / 2 - (pos.x + largura / 2) * this.zoom;
    this.panY = this.viewport.clientHeight / 2 - (pos.y + altura / 2) * this.zoom;
    this.updateTransform();
    this.state.saveViewport(this.panX, this.panY, this.zoom);
    return true;
  }

  /** Aproxima ou afasta mantendo o centro da janela parado. */
  aproximar(fator) {
    const cx = this.viewport.clientWidth / 2;
    const cy = this.viewport.clientHeight / 2;
    const novoZoom = Math.min(Math.max(this.zoom * fator, ZOOM_MINIMO), ZOOM_MAXIMO);
    this.panX = cx - (cx - this.panX) * (novoZoom / this.zoom);
    this.panY = cy - (cy - this.panY) * (novoZoom / this.zoom);
    this.zoom = novoZoom;
    this.updateTransform();
    this.state.saveViewport(this.panX, this.panY, this.zoom);
  }

  obterViewport() {
    return { panX: this.panX, panY: this.panY, zoom: this.zoom };
  }

  aplicarViewport(viewport) {
    if (!viewport || typeof viewport.zoom !== "number") return false;
    this.panX = viewport.panX;
    this.panY = viewport.panY;
    this.zoom = viewport.zoom;
    this.updateTransform();
    return true;
  }

  onMouseDown(e) {
    // Middle click (button 1) or Space+Left click or click on background
    if (e.button === 1 || this.isSpacePressed) {
      e.preventDefault();
      this.isPanning = true;
      this.startPan = { x: e.clientX - this.panX, y: e.clientY - this.panY };
      this.viewport.style.cursor = "grabbing";
      return;
    }

    if (e.button !== 0) return;

    // Check port connection drag
    const portOut = e.target.closest(".port-out, .port-bottom, .port-top");
    if (portOut) {
      const portId = portOut.dataset.portOut || portOut.dataset.portBottom || portOut.dataset.portTop;
      this.startEdgeConnection(portId, e);
      return;
    }

    // Check node drag
    const nodeCard = e.target.closest(".node-card");
    if (nodeCard) {
      const id = nodeCard.id.replace("node-", "");
      this.draggingNode = id;
      const pos = this.state.nodePositions.get(id) || { x: 0, y: 0 };
      this.dragOffset = { x: (e.clientX / this.zoom) - pos.x, y: (e.clientY / this.zoom) - pos.y };
      return;
    }

    // Background pan
    this.isPanning = true;
    this.startPan = { x: e.clientX - this.panX, y: e.clientY - this.panY };
    this.mouseDownPos = { x: e.clientX, y: e.clientY };
  }

  onMouseMove(e) {
    if (this.isPanning) {
      this.panX = e.clientX - this.startPan.x;
      this.panY = e.clientY - this.startPan.y;
      this.updateTransform();
      return;
    }

    if (this.draggingNode) {
      const newX = (e.clientX / this.zoom) - this.dragOffset.x;
      const newY = (e.clientY / this.zoom) - this.dragOffset.y;
      this.state.nodePositions.set(this.draggingNode, { x: newX, y: newY });
      const nodeEl = document.getElementById(`node-${this.draggingNode}`);
      if (nodeEl) {
        nodeEl.style.left = `${newX}px`;
        nodeEl.style.top = `${newY}px`;
      }
      this.renderer.renderEdges();
      if (this.minimap) this.minimap.update();
      return;
    }

    if (this.connectingFromId && this.tempEdgePath) {
      const pOrig = this.state.nodePositions.get(this.connectingFromId);
      if (!pOrig) return;
      const x1 = pOrig.x + 220;
      const y1 = pOrig.y + 35;
      const rect = this.surface.getBoundingClientRect();
      const x2 = (e.clientX - rect.left) / this.zoom;
      const y2 = (e.clientY - rect.top) / this.zoom;
      this.tempEdgePath.setAttribute("d", `M ${x1} ${y1} L ${x2} ${y2}`);
    }
  }

  onMouseUp(e) {
    if (this.draggingNode) {
      this.state.savePositions();
      this.draggingNode = null;
      if (this.minimap) this.minimap.update();
    }
    if (this.isPanning) {
      this.isPanning = false;
      this.viewport.style.cursor = this.isSpacePressed ? "grab" : "default";
      this.state.saveViewport(this.panX, this.panY, this.zoom);

      // Deselect if clicked on empty canvas background without dragging
      const dist = Math.hypot(e.clientX - (this.mouseDownPos?.x ?? e.clientX), e.clientY - (this.mouseDownPos?.y ?? e.clientY));
      if (dist < 5 && !e.target.closest(".node-card, .edge-path, .port, .canvas-floating-toolbar, #floating-palette-container, #minimap-container")) {
        this.state.selectElement(null, null);
      }
    }
    if (this.connectingFromId) {
      this.surface.classList.remove("canvas-connecting-mode");
      const portIn = e.target.closest(".port-in, .port-top, .port-bottom, .port-out");
      if (portIn) {
        const destId = portIn.dataset.portIn || portIn.dataset.portTop || portIn.dataset.portBottom || portIn.dataset.portOut;
        if (destId && destId !== this.connectingFromId) {
          this.onAction("OPEN_CREATE_EDGE_MODAL", {
            origem_id: this.connectingFromId,
            destino_id: destId,
          });
        }
      }
      if (this.tempEdgePath) {
        this.tempEdgePath.remove();
        this.tempEdgePath = null;
      }
      this.connectingFromId = null;
    }
  }

  startEdgeConnection(origemId, e) {
    this.connectingFromId = origemId;
    this.surface.classList.add("canvas-connecting-mode");
    this.tempEdgePath = document.createElementNS("http://www.w3.org/2000/svg", "path");
    this.tempEdgePath.setAttribute("class", "edge-path");
    this.tempEdgePath.style.stroke = "var(--accent-blue)";
    this.tempEdgePath.style.strokeDasharray = "4 3";
    this.renderer.edgesLayer.appendChild(this.tempEdgePath);
  }

  onWheel(e) {
    e.preventDefault();
    const zoomFactor = e.deltaY < 0 ? 1.1 : 0.9;
    const rect = this.viewport.getBoundingClientRect();
    const mouseX = e.clientX - rect.left;
    const mouseY = e.clientY - rect.top;

    const newZoom = Math.min(Math.max(this.zoom * zoomFactor, ZOOM_MINIMO), ZOOM_MAXIMO);
    if (newZoom === this.zoom) return;

    // Anchor zoom strictly at cursor
    this.panX = mouseX - (mouseX - this.panX) * (newZoom / this.zoom);
    this.panY = mouseY - (mouseY - this.panY) * (newZoom / this.zoom);
    this.zoom = newZoom;

    this.updateTransform();
    this.state.saveViewport(this.panX, this.panY, this.zoom);
  }

  updateTransform() {
    this.surface.style.transform = `translate(${this.panX}px, ${this.panY}px) scale(${this.zoom})`;
    const zoomInd = document.getElementById("zoom-indicator");
    if (zoomInd) zoomInd.textContent = `${Math.round(this.zoom * 100)}%`;

    this.renderer.setLOD(this.zoom);
    if (this.minimap) this.minimap.updateFrustum();
    this.aoTransformar?.(this.zoom);
  }

  applyAutoLayout() {
    // O arranjo precisa do tamanho que o cartão tem de verdade — um rótulo
    // longo faz um cartão de 380 px — e da proporção da área visível, que é o
    // formato que o desenho inteiro deve tentar ter.
    const posicoes = calcularLayoutHierarquico(
      Array.from(this.state.nodes.values()),
      Array.from(this.state.edges.values()),
      {
        tamanhos: this.renderer.medirCartoes(),
        proporcao: Math.max(this.viewport.clientWidth, 1) / Math.max(this.viewport.clientHeight, 1),
      }
    );
    for (const [id, posicao] of posicoes) {
      this.state.nodePositions.set(id, posicao);
    }
    this.renderer.render();
    this.state.savePositions();
    if (this.minimap) this.minimap.update();
    this.fitToView();
  }

  fitToView() {
    if (this.state.nodes.size === 0) {
      this.resetZoom();
      return;
    }

    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    for (const id of this.state.nodes.keys()) {
      const cartao = this.renderer.retanguloDoCartao(id);
      if (cartao.x < minX) minX = cartao.x;
      if (cartao.y < minY) minY = cartao.y;
      if (cartao.x + cartao.largura > maxX) maxX = cartao.x + cartao.largura;
      if (cartao.y + cartao.altura > maxY) maxY = cartao.y + cartao.altura;
    }

    const padding = 60;
    const graphW = Math.max(maxX - minX + padding * 2, 300);
    const graphH = Math.max(maxY - minY + padding * 2, 200);

    const vpW = this.viewport.clientWidth;
    const vpH = this.viewport.clientHeight;

    const scaleX = vpW / graphW;
    const scaleY = vpH / graphH;
    // O piso é o mesmo do zoom pela roda: um grafo de centenas de nós só cabe
    // na tela bem longe, e parar antes disso seria enquadrar pela metade.
    const newZoom = Math.min(Math.max(Math.min(scaleX, scaleY), ZOOM_MINIMO), ZOOM_MAXIMO_AO_ENQUADRAR);

    this.zoom = newZoom;
    this.panX = (vpW - (maxX + minX) * newZoom) / 2;
    this.panY = (vpH - (maxY + minY) * newZoom) / 2;

    this.updateTransform();
    this.state.saveViewport(this.panX, this.panY, this.zoom);
  }

  zoomToSelection() {
    const sel = this.state.selectedElement;
    if (!sel || sel.type !== "node") return;

    const pos = this.state.nodePositions.get(sel.id);
    if (!pos) return;

    this.zoom = 1.0;
    const vpW = this.viewport.clientWidth;
    const vpH = this.viewport.clientHeight;
    this.panX = (vpW / 2) - ((pos.x + 110) * this.zoom);
    this.panY = (vpH / 2) - ((pos.y + 40) * this.zoom);

    this.updateTransform();
    this.state.saveViewport(this.panX, this.panY, this.zoom);
  }

  resetZoom() {
    this.zoom = 0.85;
    this.panX = 40;
    this.panY = 40;
    this.updateTransform();
    this.state.saveViewport(this.panX, this.panY, this.zoom);
  }

  restoreViewport() {
    const saved = this.state.loadViewport();
    if (saved && typeof saved.zoom === "number") {
      this.panX = saved.panX;
      this.panY = saved.panY;
      this.zoom = saved.zoom;
    } else {
      this.panX = 40;
      this.panY = 40;
      this.zoom = 0.85;
    }
    this.updateTransform();
  }
}
