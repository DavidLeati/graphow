/**
 * Central Reactive State for Graphow Client (ActiveGraph Store)
 */
import { posicionarEmCamadas, PASSO_LINHA } from "./layout_camadas.js";

// Arrastar um nó dispara muitos eventos; o envio é agrupado para não inundar o log.
const LAYOUT_PERSIST_DELAY_MS = 1200;

export class GraphowState {
  constructor() {
    this.currentBranch = "main";
    this.branches = ["main"];
    // Papel apenas do simulador de tokens: e a pergunta "o que um executor
    // veria daqui?", nunca a credencial de quem escreve. Ver achado A-11.
    this.simulationRole = "executor";
    this.activeSessionScope = null;
    this.activeProjectScope = null;
    this.selectedElement = null; // { type: 'node' | 'edge', id: string, data: object }
    this.nodes = new Map(); // id -> nodeData
    this.edges = new Map(); // id -> edgeData
    this.nodePositions = new Map(); // id -> { x, y }
    this.logVersion = 0;
    this.maxLogVersion = 0;
    this.isTimeTraveling = false;
    this.hideStructuralEdges = true;
    this.listeners = new Set();
    this.layoutPersistTimer = null;
  }

  toggleStructuralEdges() {
    this.hideStructuralEdges = !this.hideStructuralEdges;
    this.notify("CANVAS_UPDATED", { hideStructuralEdges: this.hideStructuralEdges });
  }

  subscribe(listener) {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  notify(changeType, payload = {}) {
    for (const listener of this.listeners) {
      listener(changeType, payload, this);
    }
  }

  savePositions() {
    const storageKey = `graphow_positions_${this.currentBranch}`;
    const obj = {};
    for (const [id, pos] of this.nodePositions.entries()) {
      obj[id] = { x: Math.round(pos.x), y: Math.round(pos.y) };
    }
    try {
      localStorage.setItem(storageKey, JSON.stringify(obj));
    } catch (e) {
      console.warn("Falha ao salvar posições no localStorage:", e);
    }
    this.persistPositions(obj);
  }

  // O localStorage é apenas cache local. O arranjo pertence ao grafo, para que a
  // mesma disposição chegue a quem abrir o canvas de outra máquina.
  persistPositions(positionsById) {
    const posicoes = Object.entries(positionsById).map(([id_no, pos]) => ({ id_no, x: pos.x, y: pos.y }));
    if (posicoes.length === 0) return;
    clearTimeout(this.layoutPersistTimer);
    this.layoutPersistTimer = setTimeout(() => this.sendLayout(posicoes), LAYOUT_PERSIST_DELAY_MS);
  }

  async sendLayout(posicoes) {
    try {
      await fetch("/api/layout", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ posicoes, ramo_id: this.currentBranch }),
      });
    } catch (e) {
      console.warn("Falha ao persistir o arranjo no grafo:", e);
    }
  }

  loadSavedPositions() {
    const storageKey = `graphow_positions_${this.currentBranch}`;
    try {
      const raw = localStorage.getItem(storageKey);
      if (raw) return JSON.parse(raw);
    } catch (e) {
      console.warn("Falha ao ler posições do localStorage:", e);
    }
    return null;
  }

  saveViewport(panX, panY, zoom) {
    try {
      localStorage.setItem(`graphow_viewport_${this.currentBranch}`, JSON.stringify({ panX, panY, zoom }));
    } catch (e) {}
  }

  loadViewport() {
    try {
      const raw = localStorage.getItem(`graphow_viewport_${this.currentBranch}`);
      if (raw) return JSON.parse(raw);
    } catch (e) {}
    return null;
  }

  clearSavedPositions() {
    try {
      localStorage.removeItem(`graphow_positions_${this.currentBranch}`);
    } catch (e) {}
  }

  setCanvasData(data) {
    this.logVersion = data.versao_log;
    if (!this.isTimeTraveling) {
      this.maxLogVersion = Math.max(this.maxLogVersion, data.versao_log);
    }

    this.nodes.clear();
    for (const n of data.nos) this.nodes.set(n.id, n);
    this.edges.clear();
    for (const a of data.arestas) this.edges.set(a.id, a);

    this.applyPositions();
    this.notify("CANVAS_UPDATED", { data });
  }

  // A ordem de precedência é deliberada: o que o humano arrastou vale mais que o
  // que o grafo guarda, e ambos valem mais que a grade. Quem não tem coordenada
  // nenhuma entra em camadas, abaixo de tudo que já está posto — assim um nó novo
  // aparece num lugar previsível sem nunca cobrir um arranjo existente.
  applyPositions() {
    const savedPositions = this.loadSavedPositions();
    const semPosicao = [];
    for (const no of this.nodes.values()) {
      const posicao = this.resolveKnownPosition(no, savedPositions);
      if (posicao) this.nodePositions.set(no.id, posicao);
      else semPosicao.push(no.id);
    }
    const abaixoDoOcupado = this.firstFreeRowY();
    const calculadas = posicionarEmCamadas(semPosicao, this.nodes, this.edges, abaixoDoOcupado);
    for (const [id, posicao] of calculadas) {
      this.nodePositions.set(id, posicao);
    }
  }

  // Devolve null quando o nó não tem coordenada de origem alguma.
  resolveKnownPosition(no, savedPositions) {
    const salva = savedPositions?.[no.id];
    if (salva && typeof salva.x === "number") return { x: salva.x, y: salva.y };
    if (this.nodePositions.has(no.id)) return this.nodePositions.get(no.id);
    const px = no.propriedades?.pos_x ?? no.propriedades?.x;
    const py = no.propriedades?.pos_y ?? no.propriedades?.y;
    if (px === undefined || py === undefined) return null;
    return { x: Number(px), y: Number(py) };
  }

  firstFreeRowY() {
    let maisBaixo = null;
    for (const posicao of this.nodePositions.values()) {
      if (maisBaixo === null || posicao.y > maisBaixo) maisBaixo = posicao.y;
    }
    return maisBaixo === null ? 0 : maisBaixo + PASSO_LINHA;
  }

  selectElement(type, id) {
    if (!type || !id) {
      this.selectedElement = null;
    } else if (type === "node") {
      this.selectedElement = { type: "node", id, data: this.nodes.get(id) };
    } else if (type === "edge") {
      this.selectedElement = { type: "edge", id, data: this.edges.get(id) };
    }
    this.notify("SELECTION_CHANGED", { selection: this.selectedElement });
  }

  setSimulationRole(role) {
    this.simulationRole = role;
    this.notify("SIMULATION_ROLE_CHANGED", { role });
  }

  setSessionScope(sessionId) {
    this.activeSessionScope = sessionId;
    this.notify("SCOPE_CHANGED", { sessionId });
  }

  setProjectScope(projectId) {
    this.activeProjectScope = projectId;
    this.notify("PROJECT_SCOPE_CHANGED", { projectId });
  }

  setBranch(branch) {
    this.currentBranch = branch;
    this.nodePositions.clear(); // Reset memory map so branch-specific saved positions load cleanly
    if (!this.branches.includes(branch)) {
      this.branches.push(branch);
    }
    this.notify("BRANCH_CHANGED", { branch });
  }
}

export const appState = new GraphowState();
