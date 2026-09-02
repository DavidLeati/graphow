/**
 * Hierarchical Navigation View (Projeto -> Setor -> Sessao)
 */
export class HierarchyView {
  constructor(containerId, state, onAction) {
    this.container = document.getElementById(containerId);
    this.state = state;
    this.onAction = onAction;
    this.activeScopeLabel = document.getElementById("active-scope-label");
    this.clearScopeBtn = document.getElementById("btn-clear-scope");
    this.filterQuery = "";

    if (this.clearScopeBtn) {
      this.clearScopeBtn.addEventListener("click", () => {
        this.state.setSessionScope(null);
        this.onAction("REFRESH_CANVAS");
      });
    }

    const searchInput = document.getElementById("hierarchy-search-input");
    searchInput?.addEventListener("input", (e) => {
      this.filterQuery = e.target.value.toLowerCase().trim();
      this.render();
    });
  }

  render() {
    this.container.innerHTML = "";
    const nodes = Array.from(this.state.nodes.values());
    let projetos = nodes.filter((n) => n.tipo === "Projeto");
    let setores = nodes.filter((n) => n.tipo === "Setor");
    let sessoes = nodes.filter((n) => n.tipo === "Sessao");

    if (this.filterQuery) {
      projetos = projetos.filter((n) => (n.rotulo || "").toLowerCase().includes(this.filterQuery));
      setores = setores.filter((n) => (n.rotulo || "").toLowerCase().includes(this.filterQuery));
      sessoes = sessoes.filter((n) => (n.rotulo || "").toLowerCase().includes(this.filterQuery));
    }

    if (projetos.length === 0 && setores.length === 0 && sessoes.length === 0) {
      this.container.innerHTML = `
        <div style="font-size:11px; color:var(--text-muted); padding:16px 8px; text-align:center;">
          ${this.filterQuery ? "Nenhum contêiner corresponde à busca." : "Nenhum contêiner de navegação criado ainda."}
        </div>
      `;
      return;
    }

    const treeEl = document.createElement("div");
    treeEl.className = "hierarchy-tree";
    treeEl.style.display = "flex";
    treeEl.style.flexDirection = "column";
    treeEl.style.gap = "2px";

    for (const proj of projetos) {
      const projItem = document.createElement("div");
      projItem.className = `tree-node-item ${this.state.activeProjectScope === proj.id ? "active" : ""}`;
      const isIlimitado = proj.propriedades?.nivel_autonomia === "ilimitado";
      const badgeAutonomia = isIlimitado
        ? `<span class="badge badge-status" style="font-size:9px;">⚡ Ilimitado</span>`
        : `<span class="badge" style="font-size:9px;">🔒 Estrito</span>`;

      projItem.innerHTML = `
        <div style="display:flex; align-items:center; gap:6px; overflow:hidden;">
          <span style="color:var(--color-projeto);">📂</span>
          <span style="font-weight:500; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">${this.escapeHtml(proj.rotulo)}</span>
        </div>
        ${badgeAutonomia}
      `;
      projItem.addEventListener("click", () => {
        this.state.setProjectScope(this.state.activeProjectScope === proj.id ? null : proj.id);
      });
      treeEl.appendChild(projItem);
    }

    for (const setor of setores) {
      const setorItem = document.createElement("div");
      setorItem.className = "tree-node-item";
      setorItem.innerHTML = `
        <div style="display:flex; align-items:center; gap:6px; padding-left:10px;">
          <span style="color:var(--color-setor);">🏷️</span>
          <span>${this.escapeHtml(setor.rotulo)}</span>
        </div>
      `;
      treeEl.appendChild(setorItem);
    }

    for (const sess of sessoes) {
      const isSelected = this.state.activeSessionScope === sess.id;
      const sessItem = document.createElement("div");
      sessItem.className = `tree-node-item ${isSelected ? "active" : ""}`;
      sessItem.innerHTML = `
        <div style="display:flex; align-items:center; gap:6px; padding-left:18px;">
          <span style="color:var(--color-sessao);">⚡</span>
          <span>${this.escapeHtml(sess.rotulo)}</span>
        </div>
        ${isSelected ? `<span style="font-size:10px; color:var(--accent-blue);">✓</span>` : ""}
      `;
      sessItem.addEventListener("click", () => {
        const nextScope = isSelected ? null : sess.id;
        this.state.setSessionScope(nextScope);
        this.onAction("REFRESH_CANVAS");
      });
      treeEl.appendChild(sessItem);
    }

    this.container.appendChild(treeEl);

    if (this.activeScopeLabel) {
      if (this.state.activeSessionScope) {
        const sessNode = this.state.nodes.get(this.state.activeSessionScope);
        this.activeScopeLabel.textContent = sessNode ? sessNode.rotulo : this.state.activeSessionScope;
        if (this.clearScopeBtn) this.clearScopeBtn.style.display = "inline";
      } else {
        this.activeScopeLabel.textContent = "Todas as Sessões";
        if (this.clearScopeBtn) this.clearScopeBtn.style.display = "none";
      }
    }
  }

  escapeHtml(str) {
    if (!str) return "";
    return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }
}
