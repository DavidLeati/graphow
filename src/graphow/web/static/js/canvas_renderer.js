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
    this.hoveredNodeId = null;
    this.setupDefs();
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

      const statusBadge = node.propriedades?.status ? `<span class="badge badge-status">${node.propriedades.status}</span>` : "";
      const lockBadge = node.lock_ativo ? `<span class="badge badge-locked">🔒 ${node.lock_ativo}</span>` : "";
      const blockBadge = node.esta_bloqueado ? `<span class="badge badge-blocked">⚠️ Bloqueado</span>` : "";

      el.innerHTML = `
        <div class="node-header node-type-${node.tipo}">
          <span class="node-type-label">${node.tipo}</span>
          <span class="node-id-badge">#${id.slice(-6)}</span>
        </div>
        <div class="node-body">
          <div class="node-title">${this.escapeHtml(node.rotulo)}</div>
          <div class="node-meta">
            ${statusBadge}
            ${lockBadge}
            ${blockBadge}
          </div>
        </div>
        <div class="port port-in" data-port-in="${id}" title="Entrada"></div>
        <div class="port port-out" data-port-out="${id}" title="Saída"></div>
        <div class="port port-top" data-port-top="${id}" title="Superior"></div>
        <div class="port port-bottom" data-port-bottom="${id}" title="Inferior"></div>
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
  }

  renderEdges() {
    let defs = this.edgesLayer.querySelector("defs");
    if (!defs) {
      this.setupDefs();
      defs = this.edgesLayer.querySelector("defs");
    }

    const oldPaths = this.edgesLayer.querySelectorAll("path.edge-path");
    oldPaths.forEach((p) => p.remove());

    for (const [id, edge] of this.state.edges.entries()) {
      const pOrig = this.state.nodePositions.get(edge.origem_id);
      const pDest = this.state.nodePositions.get(edge.destino_id);
      if (!pOrig || !pDest) continue;

      if (this.state.hideStructuralEdges && edge.tipo === "produz") {
        const isSelected = this.state.selectedElement?.id === edge.origem_id ||
                           this.state.selectedElement?.id === edge.destino_id;
        if (!isSelected) continue;
      }

      const elOrig = this.nodeElements.get(edge.origem_id);
      const elDest = this.nodeElements.get(edge.destino_id);
      const wOrig = elOrig?.offsetWidth || 220;
      const hOrig = elOrig?.offsetHeight || 75;
      const wDest = elDest?.offsetWidth || 220;
      const hDest = elDest?.offsetHeight || 75;

      const cx1 = pOrig.x + wOrig / 2;
      const cy1 = pOrig.y + hOrig / 2;
      const cx2 = pDest.x + wDest / 2;
      const cy2 = pDest.y + hDest / 2;

      const dx = cx2 - cx1;
      const dy = cy2 - cy1;

      let x1, y1, x2, y2;
      let c1x, c1y, c2x, c2y;

      if (Math.abs(dx) >= Math.abs(dy)) {
        if (dx >= 0) {
          x1 = pOrig.x + wOrig;
          y1 = cy1;
          x2 = pDest.x;
          y2 = cy2;
          const spanX = Math.max(Math.abs(x2 - x1), 20);
          const curve = Math.min(spanX * 0.45, 100);
          c1x = x1 + curve;
          c1y = y1;
          c2x = x2 - curve;
          c2y = y2;
        } else {
          x1 = pOrig.x;
          y1 = cy1;
          x2 = pDest.x + wDest;
          y2 = cy2;
          const spanX = Math.max(Math.abs(x1 - x2), 20);
          const curve = Math.min(spanX * 0.45, 100);
          c1x = x1 - curve;
          c1y = y1;
          c2x = x2 + curve;
          c2y = y2;
        }
      } else {
        const xJitter = Math.abs(cx2 - cx1) < 0.01 ? 0.2 : 0;
        if (dy >= 0) {
          x1 = cx1;
          y1 = pOrig.y + hOrig;
          x2 = cx2;
          y2 = pDest.y;
          const spanY = Math.max(y2 - y1, 16);
          const curve = Math.min(spanY * 0.5, 80);
          c1x = x1 + xJitter;
          c1y = y1 + curve;
          c2x = x2 - xJitter;
          c2y = y2 - curve;
        } else {
          x1 = cx1;
          y1 = pOrig.y;
          x2 = cx2;
          y2 = pDest.y + hDest;
          const spanY = Math.max(y1 - y2, 16);
          const curve = Math.min(spanY * 0.5, 80);
          c1x = x1 + xJitter;
          c1y = y1 - curve;
          c2x = x2 - xJitter;
          c2y = y2 + curve;
        }
      }

      const d = `M ${x1} ${y1} C ${c1x} ${c1y}, ${c2x} ${c2y}, ${x2} ${y2}`;

      const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
      path.setAttribute("d", d);
      path.setAttribute("class", `edge-path edge-${edge.tipo} ${this.state.selectedElement?.id === id ? "selected" : ""}`);
      path.setAttribute("data-edge-id", id);
      path.setAttribute("data-origem", edge.origem_id);
      path.setAttribute("data-destino", edge.destino_id);

      const markerId = this.edgesLayer.querySelector(`#arrow-${edge.tipo}`) ? `arrow-${edge.tipo}` : "arrow";
      path.setAttribute("marker-end", `url(#${markerId})`);
      path.style.stroke = `var(--edge-${edge.tipo}, var(--edge-default))`;

      path.addEventListener("click", (e) => {
        e.stopPropagation();
        this.state.selectElement("edge", id);
      });

      this.edgesLayer.appendChild(path);
    }
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
    if (zoom < 0.45) {
      this.surface.classList.add("lod-macro");
    } else {
      this.surface.classList.remove("lod-macro");
    }
  }

  escapeHtml(str) {
    if (!str) return "";
    return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }
}
