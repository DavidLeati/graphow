/**
 * Graphow Main SPA Application Bootstrap & Orchestrator
 */
import { appState } from "./state.js";
import { SSEClient } from "./sse_client.js";
import { CanvasRenderer } from "./canvas_renderer.js";
import { CanvasInteractions } from "./canvas_interactions.js";
import { HierarchyView } from "./hierarchy_view.js";
import { InspectorView } from "./inspector_view.js";
import { TimelineView } from "./timeline_view.js";
import { LineageView } from "./lineage_view.js";
import { ForkDiffView } from "./fork_diff_view.js";
import { TokenSimulatorView } from "./token_simulator_view.js";
import { PatchConsoleView } from "./patch_console_view.js";
import { Minimap } from "./minimap.js";
import { QuickFinder } from "./quick_finder.js";

const SSE_COALESCE_DELAY_MS = 200;

function resumirEventos(tipos) {
  if (tipos.length === 1) return `Evento recebido: ${tipos[0]}`;
  const contagem = new Map();
  for (const tipo of tipos) contagem.set(tipo, (contagem.get(tipo) ?? 0) + 1);
  const partes = [...contagem].map(([tipo, total]) => `${total}× ${tipo}`);
  return `${tipos.length} eventos: ${partes.join(", ")}`;
}

class GraphowApp {
  constructor() {
    this.state = appState;
    this.renderer = new CanvasRenderer("canvas-viewport", this.state);
    this.interactions = new CanvasInteractions(
      "canvas-viewport",
      "canvas-surface",
      this.state,
      this.renderer,
      (action, payload) => this.handleAction(action, payload)
    );
    this.minimap = new Minimap("minimap-container", this.state, this.interactions);
    this.interactions.setMinimap(this.minimap);

    this.quickFinder = new QuickFinder(this.state, this.interactions, (nodeId) => {
      this.renderer.applyPathHighlight(nodeId);
    });

    this.hierarchyView = new HierarchyView("hierarchy-tree", this.state, (action, payload) => this.handleAction(action, payload));
    this.inspectorView = new InspectorView("inspector-content", this.state, (action, payload) => this.handleAction(action, payload));
    this.timelineView = new TimelineView("tab-timeline", this.state, (action, payload) => this.handleAction(action, payload));
    this.lineageView = new LineageView("tab-lineage", this.state);
    this.forkDiffView = new ForkDiffView("tab-diff", this.state, (action, payload) => this.handleAction(action, payload));
    this.tokenSimView = new TokenSimulatorView("tab-tokens", this.state);
    this.patchConsoleView = new PatchConsoleView("tab-patch", this.state, (action, payload) => this.handleAction(action, payload));
    this.sseClient = new SSEClient(
      this.state,
      (type, payload) => this.onSSEEvent(type, payload),
      () => this.ressincronizarAposReconexao()
    );
    this.cachedProjects = new Map();
    this.eventosPendentes = [];
    this.sseCoalesceTimer = null;

    this.initUI();
    this.initTimeTravel();
    this.state.subscribe((type) => this.onStateChange(type));
  }

  async start() {
    await this.fetchIdentity();
    await this.fetchBranches();
    await this.fetchCanvas();
    this.interactions.restoreViewport();
    this.sseClient.connect();
    this.timelineView.fetchEvents();
    this.forkDiffView.updateBranchOptions();
  }

  async fetchIdentity() {
    // A identidade e lida do servidor, nunca escolhida aqui: o cabecalho mostra
    // quem esta escrevendo, e nada nesta pagina pode mudar isso. Ver A-11.
    try {
      const res = await fetch("/api/identity");
      const dados = await res.json();
      this.state.sessionIdentity = dados;
      const autor = document.getElementById("session-author");
      if (autor) autor.textContent = dados.autor || "humano";
      const papel = document.querySelector(".identity-role");
      if (papel) papel.textContent = dados.papel || "humano";
    } catch (err) {
      console.warn("Falha ao carregar identidade da sessao:", err);
    }
  }

  async fetchBranches() {
    try {
      const res = await fetch("/api/branches");
      const data = await res.json();
      if (data.ramos && data.ramos.length > 0) {
        this.state.branches = data.ramos;
        const branchSelect = document.getElementById("branch-select");
        if (branchSelect) {
          branchSelect.innerHTML = data.ramos.map((b) => `<option value="${b}">${b}</option>`).join("");
          branchSelect.value = this.state.currentBranch;
        }
      }
    } catch (err) {
      console.warn("Falha ao carregar ramos:", err);
    }
  }

  initUI() {
    // O papel deixou de ser escolhido no cliente: a identidade da escrita e da
    // sessao do servidor, e o corpo que a declara e recusado. Ver achado A-11.
    // Branch selection
    const branchSelect = document.getElementById("branch-select");
    branchSelect?.addEventListener("change", (e) => {
      this.state.setBranch(e.target.value);
      this.fetchCanvas();
    });

    // Fork button
    document.getElementById("btn-new-fork")?.addEventListener("click", () => {
      this.handleAction("OPEN_CREATE_FORK_MODAL");
    });

    // Add container button
    document.getElementById("btn-add-container")?.addEventListener("click", () => {
      this.handleAction("OPEN_CREATE_CONTAINER_MODAL");
    });

    // Add project tab button
    document.getElementById("btn-add-project-tab")?.addEventListener("click", () => {
      this.showCreateContainerModal("Projeto");
    });

    // Batch delete button
    document.getElementById("btn-batch-delete")?.addEventListener("click", () => {
      this.showBatchDeleteModal();
    });

    // Auto layout button
    document.getElementById("btn-layout-hierarchical")?.addEventListener("click", () => {
      this.interactions.applyAutoLayout();
    });

    // Fit view button (F)
    document.getElementById("btn-canvas-fit-view")?.addEventListener("click", () => {
      this.interactions.fitToView();
    });

    // Toggle structural edges button
    const btnToggleStruct = document.getElementById("btn-toggle-structural");
    btnToggleStruct?.addEventListener("click", () => {
      this.state.toggleStructuralEdges();
      const isHidden = this.state.hideStructuralEdges;
      btnToggleStruct.textContent = isHidden ? "👁️ Arestas de Sessão: Ocultas" : "👁️ Arestas de Sessão: Visíveis";
      this.renderer.renderEdges();
      this.minimap.update();
    });

    // Workbench tabs & collapse
    const wb = document.getElementById("bottom-workbench");
    document.getElementById("btn-toggle-workbench")?.addEventListener("click", () => {
      wb.classList.toggle("workbench-expanded");
      wb.classList.toggle("workbench-collapsed");
    });

    const tabs = document.querySelectorAll(".wb-tab");
    tabs.forEach((tab) => {
      tab.addEventListener("click", () => {
        tabs.forEach((t) => t.classList.remove("active"));
        document.querySelectorAll(".wb-content").forEach((c) => c.classList.remove("active"));
        tab.classList.add("active");
        const target = document.getElementById(`tab-${tab.dataset.tab}`);
        if (target) target.classList.add("active");
        if (wb.classList.contains("workbench-collapsed")) {
          wb.classList.remove("workbench-collapsed");
          wb.classList.add("workbench-expanded");
        }
      });
    });
  }

  initTimeTravel() {
    const slider = document.getElementById("time-travel-slider");
    slider?.addEventListener("input", async (e) => {
      const v = parseInt(e.target.value, 10);
      await this.timeTravelTo(v);
    });
  }

  async timeTravelTo(version) {
    this.state.isTimeTraveling = version < this.state.maxLogVersion;
    const res = await fetch(`/api/timeline/state?versao=${version}&ramo=${this.state.currentBranch}`);
    const data = await res.json();
    this.state.setCanvasData(data);
    this.updateTimeTravelDisplay();
  }

  updateTimeTravelDisplay() {
    const slider = document.getElementById("time-travel-slider");
    const badge = document.getElementById("time-travel-version");
    if (slider) {
      slider.max = this.state.maxLogVersion;
      slider.value = this.state.logVersion;
    }
    if (badge) {
      badge.textContent = `#${this.state.logVersion} / #${this.state.maxLogVersion}`;
    }
  }

  async fetchCanvas() {
    let scopeParam = this.state.activeSessionScope ? `&sessao=${this.state.activeSessionScope}` : "";
    if (this.state.activeProjectScope) {
      scopeParam += `&projeto=${this.state.activeProjectScope}`;
    }
    const res = await fetch(`/api/canvas?ramo=${this.state.currentBranch}${scopeParam}`);
    const data = await res.json();
    this.state.setCanvasData(data);
    this.updateTimeTravelDisplay();
    this.renderProjectTabs();
    this.minimap.update();
  }

  onSSEEvent(type) {
    this.eventosPendentes.push(type);
    clearTimeout(this.sseCoalesceTimer);
    this.sseCoalesceTimer = setTimeout(() => this.drainSSEEvents(), SSE_COALESCE_DELAY_MS);
  }

  drainSSEEvents() {
    const eventos = this.eventosPendentes;
    this.eventosPendentes = [];
    if (eventos.length === 0) return;
    this.fetchCanvas();
    this.timelineView.fetchEvents();
    this.showToast(resumirEventos(eventos), "info");
  }

  /**
   * O stream caiu e voltou: o que passou no intervalo nao e reenviado. So a
   * releitura do canvas e da linha do tempo devolve a pagina ao presente.
   */
  ressincronizarAposReconexao() {
    this.eventosPendentes = [];
    clearTimeout(this.sseCoalesceTimer);
    this.fetchCanvas();
    this.timelineView.fetchEvents();
    this.showToast("Conexao restabelecida: canvas ressincronizado", "info");
  }

  onStateChange(type) {
    if (type === "CANVAS_UPDATED") {
      this.renderer.render();
      this.hierarchyView.render();
      this.inspectorView.render();
      this.minimap.update();
    } else if (type === "SELECTION_CHANGED") {
      this.renderer.render();
      this.inspectorView.render();
      const selId = this.state.selectedElement?.type === "node" ? this.state.selectedElement.id : null;
      this.renderer.applyPathHighlight(selId);
      if (selId) {
        this.lineageView.traceLineage(selId);
        this.tokenSimView.setTargetNode(selId);
      } else {
        this.lineageView.clear();
        this.tokenSimView.clear();
      }
    } else if (type === "SCOPE_CHANGED") {
      this.hierarchyView.render();
    } else if (type === "PROJECT_SCOPE_CHANGED") {
      this.fetchCanvas();
      this.hierarchyView.render();
    }
  }

  async handleAction(action, payload = {}) {
    if (action === "REFRESH_CANVAS") {
      await this.fetchCanvas();
    } else if (action === "SAVE_NODE") {
      await this.saveNode(payload);
    } else if (action === "DELETE_ELEMENT") {
      await this.deleteElement(payload.tipo, payload.id);
    } else if (action === "DELETE_PROJECT_CASCADE") {
      await this.showDeleteProjectModal(payload.id_projeto, payload.rotulo);
    } else if (action === "OPEN_BATCH_DELETE_MODAL") {
      this.showBatchDeleteModal();
    } else if (action === "OPEN_LINEAGE_TAB") {
      this.switchTab("lineage");
      this.lineageView.traceLineage(payload.id);
    } else if (action === "OPEN_TOKEN_SIM_TAB") {
      this.switchTab("tokens");
      this.tokenSimView.setTargetNode(payload.id);
      this.tokenSimView.runSimulation();
    } else if (action === "OPEN_CREATE_NODE_MODAL") {
      this.showCreateNodeModal(payload.x, payload.y, payload.type);
    } else if (action === "OPEN_CREATE_EDGE_MODAL") {
      this.showCreateEdgeModal(payload.origem_id, payload.destino_id);
    } else if (action === "OPEN_CREATE_FORK_MODAL") {
      this.showCreateForkModal();
    } else if (action === "OPEN_CREATE_CONTAINER_MODAL") {
      this.showCreateContainerModal();
    } else if (action === "TIME_TRAVEL_TO") {
      await this.timeTravelTo(payload.version);
    }
  }

  switchTab(tabName) {
    const tabBtn = document.querySelector(`.wb-tab[data-tab="${tabName}"]`);
    tabBtn?.click();
  }

  async saveNode(data) {
    const res = await fetch("/api/nodes", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        ...data,
        ramo_id: this.state.currentBranch,
      }),
    });
    const recibo = await res.json();
    if (recibo.sucesso) {
      this.showToast("Nó atualizado com sucesso!", "success");
      await this.fetchCanvas();
    } else {
      this.showToast(`Erro: ${recibo.mensagem}`, "error");
    }
  }

  async deleteElement(tipo, id) {
    const res = await fetch("/api/elements", {
      method: "DELETE",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ tipo, id, ramo_id: this.state.currentBranch }),
    });
    const recibo = await res.json();
    if (recibo.sucesso) {
      this.showToast("Elemento removido com sucesso!", "success");
      this.state.selectElement(null, null);
      await this.fetchCanvas();
    } else {
      this.showToast(`Erro: ${recibo.mensagem}`, "error");
    }
  }

  showCreateNodeModal(x, y, defaultType = "Task") {
    const modal = document.getElementById("app-modal");
    document.getElementById("modal-title").textContent = `Criar Nó: ${defaultType}`;
    const body = document.getElementById("modal-body");
    body.innerHTML = `
      <div class="form-group">
        <label>Tipo de Nó:</label>
        <select id="modal-node-type" class="select-input" style="width:100%;">
          ${["Goal", "Task", "Decision", "Question", "Constraint", "Artifact", "Evidence", "Run", "Note"]
            .map((t) => `<option value="${t}" ${t === defaultType ? "selected" : ""}>${t}</option>`)
            .join("")}
        </select>
      </div>
      <div class="form-group">
        <label>Título / Rótulo:</label>
        <input type="text" id="modal-node-title" class="text-input" style="width:100%;" placeholder="Ex: Implementar autenticação JWT">
      </div>
    `;
    this.openModal(async () => {
      const tipo = document.getElementById("modal-node-type").value;
      const rotulo = document.getElementById("modal-node-title").value;
      if (!rotulo) return;

      const res = await fetch("/api/nodes", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          tipo,
          rotulo,
          sessao_id: this.state.activeSessionScope,
          ramo_id: this.state.currentBranch,
        }),
      });
      const recibo = await res.json();
      if (recibo.sucesso) {
        this.showToast(`Nó ${tipo} criado!`, "success");
        await this.fetchCanvas();
      } else {
        this.showToast(`Erro: ${recibo.mensagem}`, "error");
      }
    });
  }

  showCreateEdgeModal(origemId, destinoId) {
    const edgeTypes = [
      "contem", "produz", "ocorreu_em", "decompoe", "depende_de",
      "bloqueia", "justifica", "contradiz", "substitui", "escopa", "deriva_de",
    ];
    document.getElementById("modal-title").textContent = "Criar Aresta Tipada";
    const body = document.getElementById("modal-body");
    body.innerHTML = `
      <div style="font-family:var(--font-mono); font-size:11px; color:var(--text-secondary); margin-bottom:8px;">
        <div>Origem: <code>${origemId}</code></div>
        <div>Destino: <code>${destinoId}</code></div>
      </div>
      <div class="form-group">
        <label>Tipo de Relação:</label>
        <select id="modal-edge-type" class="select-input" style="width:100%;">
          ${edgeTypes.map((t) => `<option value="${t}">${t}</option>`).join("")}
        </select>
      </div>
    `;
    this.openModal(async () => {
      const tipo = document.getElementById("modal-edge-type").value;
      const res = await fetch("/api/edges", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          origem_id: origemId,
          destino_id: destinoId,
          tipo,
          ramo_id: this.state.currentBranch,
        }),
      });
      const recibo = await res.json();
      if (recibo.sucesso) {
        this.showToast(`Aresta ${tipo} criada com sucesso!`, "success");
        await this.fetchCanvas();
      } else {
        this.showToast(`Erro: ${recibo.mensagem}`, "error");
      }
    });
  }

  showCreateForkModal() {
    document.getElementById("modal-title").textContent = "Criar Novo Ramo (Fork)";
    const body = document.getElementById("modal-body");
    body.innerHTML = `
      <div class="form-group">
        <label>Nome do Novo Ramo:</label>
        <input type="text" id="modal-fork-name" class="text-input" style="width:100%;" placeholder="Ex: experimento-v2">
      </div>
      <div style="font-size:11px; color:var(--text-muted); margin-top:6px;">
        O novo ramo herdará o histórico do ramo atual (<code>${this.state.currentBranch}</code>) até a versão <strong>#${this.state.logVersion}</strong>.
      </div>
    `;
    this.openModal(async () => {
      const novoRamo = document.getElementById("modal-fork-name").value;
      if (!novoRamo) return;
      const res = await fetch("/api/forks", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          novo_ramo: novoRamo,
          ramo_origem: this.state.currentBranch,
        }),
      });
      const recibo = await res.json();
      if (recibo.sucesso) {
        this.showToast(`Ramo '${novoRamo}' criado!`, "success");
        this.state.setBranch(novoRamo);
        this.forkDiffView.updateBranchOptions();
        await this.fetchCanvas();
      } else {
        this.showToast(`Erro ao criar fork: ${recibo.mensagem}`, "error");
      }
    });
  }

  showCreateContainerModal(preselectedType = "Sessao") {
    document.getElementById("modal-title").textContent = "Criar Contêiner de Navegação";
    const body = document.getElementById("modal-body");
    const isProject = preselectedType === "Projeto";
    body.innerHTML = `
      <div class="form-group">
        <label>Tipo de Contêiner:</label>
        <select id="modal-container-type" class="select-input" style="width:100%;">
          <option value="Projeto" ${preselectedType === "Projeto" ? "selected" : ""}>Projeto</option>
          <option value="Setor" ${preselectedType === "Setor" ? "selected" : ""}>Setor</option>
          <option value="Sessao" ${preselectedType === "Sessao" ? "selected" : ""}>Sessão</option>
        </select>
      </div>
      <div class="form-group">
        <label>Título / Identificador:</label>
        <input type="text" id="modal-container-title" class="text-input" style="width:100%;" placeholder="Ex: Sprint 1">
      </div>
      <div id="modal-project-autonomy-group" class="form-group" style="display:${isProject ? 'block' : 'none'}; margin-top:8px;">
        <label style="font-size:11px; font-weight:600; color:var(--text-main);">Autonomia dos Agentes:</label>
        <select id="modal-container-autonomy" class="select-input" style="width:100%; margin-top:4px;">
          <option value="estrito" selected>🔒 Estrito (cada papel cria só os seus tipos de nó)</option>
          <option value="ilimitado">⚡ Ilimitado (agentes criam qualquer tipo, menos Constraint)</option>
        </select>
        <span style="font-size:10px; color:var(--text-muted); margin-top:4px; display:block;">
          Amplia os tipos de nó e as arestas de estrutura dentro deste projeto.
          Não concede Constraint, não permite encerrar dúvidas e não libera
          <code>escopa</code> nem a remoção de <code>bloqueia</code>.
        </span>
      </div>
    `;

    const typeSelect = document.getElementById("modal-container-type");
    const autonomyGroup = document.getElementById("modal-project-autonomy-group");
    typeSelect?.addEventListener("change", () => {
      if (autonomyGroup) {
        autonomyGroup.style.display = typeSelect.value === "Projeto" ? "block" : "none";
      }
    });

    this.openModal(async () => {
      const tipo = document.getElementById("modal-container-type").value;
      const rotulo = document.getElementById("modal-container-title").value;
      if (!rotulo) return;
      const props = {};
      if (tipo === "Projeto") {
        props.nivel_autonomia = document.getElementById("modal-container-autonomy")?.value || "estrito";
      }
      const res = await fetch("/api/nodes", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          tipo,
          rotulo,
          propriedades: props,
          ramo_id: this.state.currentBranch,
        }),
      });
      const recibo = await res.json();
      if (recibo.sucesso) {
        this.showToast(`Contêiner ${tipo} criado!`, "success");
        await this.fetchCanvas();
      } else {
        this.showToast(`Erro: ${recibo.mensagem}`, "error");
      }
    });
  }

  renderProjectTabs() {
    const listContainer = document.getElementById("project-tabs-list");
    if (!listContainer) return;

    for (const n of this.state.nodes.values()) {
      if (n.tipo === "Projeto") {
        this.cachedProjects.set(n.id, n);
      }
    }

    let html = `
      <div class="project-tab ${!this.state.activeProjectScope ? 'active' : ''}" data-project-id="">
        🌐 <span>Todos os Projetos</span>
      </div>
    `;

    for (const p of this.cachedProjects.values()) {
      const isSelected = this.state.activeProjectScope === p.id;
      const isIlimitado = p.propriedades?.nivel_autonomia === "ilimitado";
      const iconAuto = isIlimitado ? "⚡" : "🔒";
      html += `
        <div class="project-tab ${isSelected ? 'active' : ''}" data-project-id="${p.id}" title="Projeto: ${this.escapeHtml(p.rotulo)}">
          📂 <span>${this.escapeHtml(p.rotulo)}</span>
          <span style="font-size:10px;" title="Autonomia: ${isIlimitado ? 'Ilimitada' : 'Estrita'}">${iconAuto}</span>
          <button class="project-tab-close" data-delete-id="${p.id}" data-delete-title="${this.escapeHtml(p.rotulo)}" title="Excluir projeto">✕</button>
        </div>
      `;
    }

    listContainer.innerHTML = html;

    listContainer.querySelectorAll(".project-tab").forEach((tabEl) => {
      tabEl.addEventListener("click", (e) => {
        if (e.target.classList.contains("project-tab-close")) {
          e.stopPropagation();
          const pid = e.target.getAttribute("data-delete-id");
          const ptitle = e.target.getAttribute("data-delete-title");
          this.showDeleteProjectModal(pid, ptitle);
          return;
        }
        const pid = tabEl.getAttribute("data-project-id");
        this.state.setProjectScope(pid || null);
      });
    });
  }

  showDeleteProjectModal(id_projeto, rotulo) {
    document.getElementById("modal-title").textContent = "Excluir Projeto em Cascata";
    const body = document.getElementById("modal-body");
    body.innerHTML = `
      <div style="font-size:12px; line-height:1.6; color:var(--text-main);">
        <p style="color:var(--accent-red); font-weight:600; margin-bottom:8px;">
          ⚠️ Atenção: Esta ação é destrutiva e atômica.
        </p>
        <p>
          Tem certeza de que deseja apagar o projeto <strong>${this.escapeHtml(rotulo)}</strong> (<code>${id_projeto}</code>)?
        </p>
        <div style="background:var(--accent-red-subtle); border:1px solid rgba(239,68,68,0.25); border-radius:4px; padding:10px; margin:12px 0; font-size:11px; color:#fca5a5;">
          Todos os contêineres filhos (Setores, Sessões), tarefas e arestas vinculadas a este projeto serão completamente excluídos.
        </div>
      </div>
    `;
    this.openModal(async () => {
      const res = await fetch("/api/projects", {
        method: "DELETE",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id_projeto, ramo_id: this.state.currentBranch }),
      });
      const recibo = await res.json();
      if (recibo.sucesso) {
        this.cachedProjects.delete(id_projeto);
        if (this.state.activeProjectScope === id_projeto) {
          this.state.setProjectScope(null);
        }
        this.showToast(`Projeto excluído com sucesso!`, "success");
        await this.fetchCanvas();
      } else {
        this.showToast(`Erro ao excluir projeto: ${recibo.mensagem}`, "error");
      }
    });
  }

  showBatchDeleteModal() {
    document.getElementById("modal-title").textContent = "Exclusão em Lote";
    const body = document.getElementById("modal-body");
    const visibleNodes = Array.from(this.state.nodes.values());

    if (visibleNodes.length === 0) {
      body.innerHTML = `<p style="color:var(--text-muted); font-size:12px;">Nenhum nó disponível no escopo atual.</p>`;
      this.openModal(async () => {});
      return;
    }

    const itemsHtml = visibleNodes
      .map((n) => `
      <label style="display:flex; align-items:center; gap:8px; padding:5px 8px; font-size:11.5px; cursor:pointer; background:var(--bg-tertiary); border-radius:3px; margin-bottom:4px;">
        <input type="checkbox" class="batch-node-checkbox" value="${n.id}">
        <span class="badge" style="font-size:9.5px;">${n.tipo}</span>
        <strong style="color:var(--text-main);">${this.escapeHtml(n.rotulo)}</strong>
        <code style="color:var(--text-muted); margin-left:auto; font-size:10px;">${n.id}</code>
      </label>
    `)
      .join("");

    body.innerHTML = `
      <div style="font-size:11.5px;">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
          <label style="cursor:pointer; display:flex; align-items:center; gap:6px;">
            <input type="checkbox" id="batch-select-all"> <strong>Selecionar Todos (${visibleNodes.length})</strong>
          </label>
          <span id="batch-selected-count" style="color:var(--text-secondary);">0 selecionados</span>
        </div>
        <div id="batch-items-container" style="max-height:260px; overflow-y:auto; border:1px solid var(--border-subtle); padding:6px; border-radius:4px;">
          ${itemsHtml}
        </div>
      </div>
    `;

    const selectAllBox = document.getElementById("batch-select-all");
    const checkboxes = document.querySelectorAll(".batch-node-checkbox");
    const countLabel = document.getElementById("batch-selected-count");

    const updateCount = () => {
      const selected = document.querySelectorAll(".batch-node-checkbox:checked").length;
      if (countLabel) countLabel.textContent = `${selected} selecionados`;
    };

    selectAllBox?.addEventListener("change", (e) => {
      checkboxes.forEach((cb) => (cb.checked = e.target.checked));
      updateCount();
    });

    checkboxes.forEach((cb) => {
      cb.addEventListener("change", updateCount);
    });

    this.openModal(async () => {
      const selectedIds = Array.from(document.querySelectorAll(".batch-node-checkbox:checked")).map((cb) => cb.value);
      if (selectedIds.length === 0) {
        this.showToast("Nenhum item selecionado", "info");
        return;
      }
      const res = await fetch("/api/elements/batch", {
        method: "DELETE",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ids_nos: selectedIds,
          ids_arestas: [],
          ramo_id: this.state.currentBranch,
        }),
      });
      const recibo = await res.json();
      if (recibo.sucesso) {
        this.showToast(`${selectedIds.length} elementos excluídos!`, "success");
        await this.fetchCanvas();
      } else {
        this.showToast(`Erro na exclusão: ${recibo.mensagem}`, "error");
      }
    });
  }

  escapeHtml(str) {
    if (!str) return "";
    return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  openModal(onConfirm) {
    const modal = document.getElementById("app-modal");
    modal.style.display = "flex";
    const confirmBtn = document.getElementById("btn-modal-confirm");
    const cancelBtn = document.getElementById("btn-modal-cancel");
    const closeBtn = document.getElementById("btn-close-modal");

    const closeHandler = () => {
      modal.style.display = "none";
      confirmBtn.onclick = null;
      cancelBtn.onclick = null;
      closeBtn.onclick = null;
    };

    cancelBtn.onclick = closeHandler;
    closeBtn.onclick = closeHandler;
    confirmBtn.onclick = async () => {
      await onConfirm();
      closeHandler();
    };
  }

  showToast(message, type = "info") {
    const container = document.getElementById("toast-container");
    if (!container) return;
    const toast = document.createElement("div");
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(() => {
      toast.remove();
    }, 3500);
  }
}

window.addEventListener("DOMContentLoaded", () => {
  const app = new GraphowApp();
  app.start();
});
