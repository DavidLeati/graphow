/**
 * Spotlight-style Quick Finder for Large Graphs (Cmd+K / Ctrl+K)
 */
export class QuickFinder {
  constructor(state, interactions, onSelectNode) {
    this.state = state;
    this.interactions = interactions;
    this.onSelectNode = onSelectNode;

    this.modal = document.getElementById("quick-finder-modal");
    this.input = document.getElementById("quick-finder-input");
    this.list = document.getElementById("quick-finder-list");

    this.activeIndex = 0;
    this.filteredResults = [];

    this.initEvents();
  }

  initEvents() {
    if (!this.modal || !this.input) return;

    // Trigger button in topbar
    document.getElementById("btn-trigger-quick-finder")?.addEventListener("click", () => {
      this.open();
    });

    // Close on backdrop click
    this.modal.addEventListener("click", (e) => {
      if (e.target === this.modal) this.close();
    });

    // Input filter
    this.input.addEventListener("input", () => {
      this.search(this.input.value);
    });

    // Keyboard navigation
    this.input.addEventListener("keydown", (e) => {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        this.moveActive(1);
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        this.moveActive(-1);
      } else if (e.key === "Enter") {
        e.preventDefault();
        this.selectCurrent();
      } else if (e.key === "Escape") {
        e.preventDefault();
        this.close();
      }
    });

    // Global shortcut Cmd+K / Ctrl+K
    window.addEventListener("keydown", (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        if (this.isOpen()) {
          this.close();
        } else {
          this.open();
        }
      } else if (e.key === "/" && document.activeElement.tagName !== "INPUT" && document.activeElement.tagName !== "TEXTAREA") {
        e.preventDefault();
        this.open();
      }
    });
  }

  isOpen() {
    return this.modal && this.modal.style.display === "flex";
  }

  open() {
    if (!this.modal) return;
    this.modal.style.display = "flex";
    this.input.value = "";
    this.activeIndex = 0;
    this.search("");
    setTimeout(() => this.input.focus(), 50);
  }

  close() {
    if (!this.modal) return;
    this.modal.style.display = "none";
  }

  search(query) {
    const q = query.trim().toLowerCase();
    const allNodes = Array.from(this.state.nodes.values());

    if (!q) {
      this.filteredResults = allNodes.slice(0, 15);
    } else {
      this.filteredResults = allNodes.filter((node) => {
        const matchTitle = (node.rotulo || "").toLowerCase().includes(q);
        const matchType = (node.tipo || "").toLowerCase().includes(q);
        const matchId = (node.id || "").toLowerCase().includes(q);
        const matchStatus = (node.propriedades?.status || "").toLowerCase().includes(q);
        return matchTitle || matchType || matchId || matchStatus;
      }).slice(0, 20);
    }

    this.activeIndex = 0;
    this.renderResults();
  }

  renderResults() {
    if (!this.list) return;

    if (this.filteredResults.length === 0) {
      this.list.innerHTML = `
        <div style="padding:16px; text-align:center; color:var(--text-muted); font-size:12px;">
          Nenhum elemento encontrado.
        </div>
      `;
      return;
    }

    this.list.innerHTML = this.filteredResults.map((node, index) => {
      const isSelected = index === this.activeIndex;
      const status = node.propriedades?.status ? `<span class="badge badge-status">${node.propriedades.status}</span>` : "";
      return `
        <div class="quick-finder-item ${isSelected ? 'active' : ''}" data-index="${index}" data-id="${node.id}">
          <div style="display:flex; align-items:center; gap:8px; overflow:hidden;">
            <span class="badge" style="border-left:2px solid var(--color-${node.tipo.toLowerCase()}, var(--accent-blue));">${node.tipo}</span>
            <span style="font-size:12px; font-weight:500; color:var(--text-main); white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">
              ${this.escapeHtml(node.rotulo)}
            </span>
          </div>
          <div style="display:flex; align-items:center; gap:6px;">
            ${status}
            <span style="font-family:var(--font-mono); font-size:10px; color:var(--text-muted);">${node.id.slice(-6)}</span>
          </div>
        </div>
      `;
    }).join("");

    this.list.querySelectorAll(".quick-finder-item").forEach((el) => {
      el.addEventListener("click", () => {
        const index = parseInt(el.getAttribute("data-index"), 10);
        this.activeIndex = index;
        this.selectCurrent();
      });
    });
  }

  moveActive(delta) {
    if (this.filteredResults.length === 0) return;
    this.activeIndex = (this.activeIndex + delta + this.filteredResults.length) % this.filteredResults.length;
    this.renderResults();

    const activeEl = this.list.querySelector(`.quick-finder-item[data-index="${this.activeIndex}"]`);
    activeEl?.scrollIntoView({ block: "nearest" });
  }

  selectCurrent() {
    const selected = this.filteredResults[this.activeIndex];
    if (!selected) return;

    this.close();

    // Select in state
    this.state.selectElement("node", selected.id);

    // Center viewport on node
    const pos = this.state.nodePositions.get(selected.id);
    if (pos) {
      const vpW = this.interactions.viewport.clientWidth;
      const vpH = this.interactions.viewport.clientHeight;
      this.interactions.panX = (vpW / 2) - ((pos.x + 110) * this.interactions.zoom);
      this.interactions.panY = (vpH / 2) - ((pos.y + 40) * this.interactions.zoom);
      this.interactions.updateTransform();
      this.state.saveViewport(this.interactions.panX, this.interactions.panY, this.interactions.zoom);
    }

    if (this.onSelectNode) {
      this.onSelectNode(selected.id);
    }
  }

  escapeHtml(str) {
    if (!str) return "";
    return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }
}
