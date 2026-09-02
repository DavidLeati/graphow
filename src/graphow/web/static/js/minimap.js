/**
 * Interactive Spatial Minimap for Large Graphs
 */
export class Minimap {
  constructor(containerId, state, interactions) {
    this.container = document.getElementById(containerId);
    this.canvas = document.getElementById("minimap-canvas");
    this.frustum = document.getElementById("minimap-frustum");
    this.state = state;
    this.interactions = interactions;

    if (!this.canvas) return;
    this.ctx = this.canvas.getContext("2d");

    this.padding = 150;
    this.bounds = { minX: 0, minY: 0, maxX: 2000, maxY: 2000, width: 2000, height: 2000 };
    this.scale = 1;
    this.offsetX = 0;
    this.offsetY = 0;

    this.isDraggingFrustum = false;
    this.startDrag = { x: 0, y: 0 };

    this.initEvents();
  }

  initEvents() {
    if (!this.container || !this.frustum) return;

    this.frustum.addEventListener("mousedown", (e) => {
      e.stopPropagation();
      this.isDraggingFrustum = true;
      this.startDrag = { x: e.clientX, y: e.clientY };
    });

    window.addEventListener("mousemove", (e) => {
      if (!this.isDraggingFrustum) return;
      const dx = e.clientX - this.startDrag.x;
      const dy = e.clientY - this.startDrag.y;
      this.startDrag = { x: e.clientX, y: e.clientY };

      this.interactions.panX -= (dx / this.scale) * this.interactions.zoom;
      this.interactions.panY -= (dy / this.scale) * this.interactions.zoom;
      this.interactions.updateTransform();
      this.updateFrustum();
    });

    window.addEventListener("mouseup", () => {
      if (this.isDraggingFrustum) {
        this.isDraggingFrustum = false;
        this.state.saveViewport(this.interactions.panX, this.interactions.panY, this.interactions.zoom);
      }
    });

    this.container.addEventListener("click", (e) => {
      if (e.target === this.frustum) return;
      const rect = this.canvas.getBoundingClientRect();
      const clickX = e.clientX - rect.left;
      const clickY = e.clientY - rect.top;

      const worldX = (clickX - this.offsetX) / this.scale;
      const worldY = (clickY - this.offsetY) / this.scale;

      const vpW = this.interactions.viewport.clientWidth;
      const vpH = this.interactions.viewport.clientHeight;

      this.interactions.panX = (vpW / 2) - (worldX * this.interactions.zoom);
      this.interactions.panY = (vpH / 2) - (worldY * this.interactions.zoom);
      this.interactions.updateTransform();
      this.updateFrustum();
      this.state.saveViewport(this.interactions.panX, this.interactions.panY, this.interactions.zoom);
    });
  }

  update() {
    if (!this.canvas || !this.ctx || this.state.nodes.size === 0) return;

    const w = this.container.clientWidth || 200;
    const h = this.container.clientHeight || 130;
    this.canvas.width = w;
    this.canvas.height = h;

    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    for (const id of this.state.nodes.keys()) {
      const pos = this.state.nodePositions.get(id) || { x: 0, y: 0 };
      if (pos.x < minX) minX = pos.x;
      if (pos.y < minY) minY = pos.y;
      if (pos.x + 220 > maxX) maxX = pos.x + 220;
      if (pos.y + 100 > maxY) maxY = pos.y + 100;
    }

    if (minX === Infinity) {
      minX = 0; minY = 0; maxX = 1000; maxY = 800;
    }

    minX -= this.padding;
    minY -= this.padding;
    maxX += this.padding;
    maxY += this.padding;

    const graphW = Math.max(maxX - minX, 400);
    const graphH = Math.max(maxY - minY, 300);

    this.scale = Math.min(w / graphW, h / graphH);
    this.offsetX = (w - (graphW * this.scale)) / 2 - (minX * this.scale);
    this.offsetY = (h - (graphH * this.scale)) / 2 - (minY * this.scale);

    this.bounds = { minX, minY, maxX, maxY, width: graphW, height: graphH };

    this.ctx.clearRect(0, 0, w, h);

    // Draw edges
    this.ctx.strokeStyle = "rgba(148, 163, 184, 0.25)";
    this.ctx.lineWidth = 1;
    for (const edge of this.state.edges.values()) {
      const p1 = this.state.nodePositions.get(edge.origem_id);
      const p2 = this.state.nodePositions.get(edge.destino_id);
      if (!p1 || !p2) continue;

      const x1 = (p1.x + 110) * this.scale + this.offsetX;
      const y1 = (p1.y + 40) * this.scale + this.offsetY;
      const x2 = (p2.x + 110) * this.scale + this.offsetX;
      const y2 = (p2.y + 40) * this.scale + this.offsetY;

      this.ctx.beginPath();
      this.ctx.moveTo(x1, y1);
      this.ctx.lineTo(x2, y2);
      this.ctx.stroke();
    }

    // Draw nodes
    const nodeColors = {
      Goal: "#f43f5e",
      Task: "#0ea5e9",
      Decision: "#10b981",
      Question: "#f59e0b",
      Constraint: "#ef4444",
      Artifact: "#06b6d4",
      Evidence: "#14b8a6",
      Run: "#8b5cf6",
      Note: "#64748b",
      Projeto: "#3b82f6",
      Setor: "#6366f1",
      Sessao: "#a855f7",
    };

    for (const [id, node] of this.state.nodes.entries()) {
      const pos = this.state.nodePositions.get(id) || { x: 0, y: 0 };
      const nx = pos.x * this.scale + this.offsetX;
      const ny = pos.y * this.scale + this.offsetY;
      const nw = 220 * this.scale;
      const nh = 70 * this.scale;

      this.ctx.fillStyle = nodeColors[node.tipo] || "#64748b";
      this.ctx.fillRect(nx, ny, Math.max(nw, 4), Math.max(nh, 3));
    }

    this.updateFrustum();
  }

  updateFrustum() {
    if (!this.frustum || !this.interactions.viewport) return;

    const vpW = this.interactions.viewport.clientWidth;
    const vpH = this.interactions.viewport.clientHeight;

    const left = -this.interactions.panX / this.interactions.zoom;
    const top = -this.interactions.panY / this.interactions.zoom;
    const width = vpW / this.interactions.zoom;
    const height = vpH / this.interactions.zoom;

    const mx = left * this.scale + this.offsetX;
    const my = top * this.scale + this.offsetY;
    const mw = width * this.scale;
    const mh = height * this.scale;

    this.frustum.style.left = `${Math.max(0, mx)}px`;
    this.frustum.style.top = `${Math.max(0, my)}px`;
    this.frustum.style.width = `${Math.min(this.container.clientWidth || 200, mw)}px`;
    this.frustum.style.height = `${Math.min(this.container.clientHeight || 130, mh)}px`;
  }
}
