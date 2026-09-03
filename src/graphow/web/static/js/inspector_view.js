import { foiAlterado, formatarDataCompleta, formatarIdadeRelativa } from "./idade.js";

/**
 * Contextual Inspector and Property Editor View
 */
export class InspectorView {
  constructor(containerId, state, onAction) {
    this.container = document.getElementById(containerId);
    this.state = state;
    this.onAction = onAction;
    this.typeBadge = document.getElementById("selected-type-badge");
  }

  render() {
    const sel = this.state.selectedElement;
    if (!sel || !sel.data) {
      if (this.typeBadge) this.typeBadge.textContent = "Nenhum";
      this.container.innerHTML = `
        <div class="empty-selection-message" style="padding:24px 8px; text-align:center; color:var(--text-muted);">
          <p style="font-size:11.5px; line-height:1.6;">
            Selecione um nó ou aresta no canvas para visualizar detalhes, editar atributos ou rastrear proveniência causal.
          </p>
        </div>
      `;
      return;
    }

    if (sel.type === "node") {
      this.renderNodeInspector(sel.data);
    } else if (sel.type === "edge") {
      this.renderEdgeInspector(sel.data);
    }
  }

  renderNodeInspector(node) {
    if (this.typeBadge) this.typeBadge.textContent = node.tipo;
    const props = node.propriedades || {};

    let specificFields = "";
    if (node.tipo === "Task") {
      const statusOptions = ["pendente", "em_andamento", "pronto_para_revisao", "concluido", "bloqueado"]
        .map((s) => `<option value="${s}" ${props.status === s ? "selected" : ""}>${s}</option>`)
        .join("");
      specificFields = `
        <div class="form-group">
          <label>Status da Tarefa:</label>
          <select id="inspect-node-status" class="select-input">${statusOptions}</select>
        </div>
      `;
    } else if (node.tipo === "Question") {
      specificFields = `
        <div class="form-group">
          <label>Status da Dúvida:</label>
          <select id="inspect-question-status" class="select-input">
            <option value="aberta" ${props.status === "aberta" ? "selected" : ""}>aberta</option>
            <option value="respondida" ${props.status === "respondida" ? "selected" : ""}>respondida</option>
            <option value="descartada" ${props.status === "descartada" ? "selected" : ""}>descartada</option>
          </select>
        </div>
      `;
    } else if (node.tipo === "Projeto") {
      const autonomiaAtual = props.nivel_autonomia === "ilimitado" ? "ilimitado" : "estrito";
      specificFields = `
        <div class="form-group" style="background:var(--bg-tertiary); padding:10px; border-radius:var(--radius-xs); border:1px solid var(--border-subtle);">
          <label style="font-weight:600; color:var(--text-main);">Nível de Autonomia da IA:</label>
          <select id="inspect-project-autonomy" class="select-input" style="margin-top:4px;">
            <option value="estrito" ${autonomiaAtual === "estrito" ? "selected" : ""}>Estrito (cada papel cria só os seus tipos de nó)</option>
            <option value="ilimitado" ${autonomiaAtual === "ilimitado" ? "selected" : ""}>Ilimitado (agentes criam qualquer tipo, menos Constraint)</option>
          </select>
          <span style="font-size:10px; color:var(--text-muted); margin-top:4px; display:block;">
            Amplia apenas os <strong>tipos de nó</strong> que agentes podem criar neste projeto.
            Não concede Constraint, não permite encerrar dúvidas e não libera as arestas do humano
            (<code>contem</code>, <code>escopa</code> e a remoção de <code>bloqueia</code>).
          </span>
        </div>
      `;
    }

    this.container.innerHTML = `
      <div class="inspector-form" style="display:flex; flex-direction:column; gap:10px;">
        <div style="font-family:var(--font-mono); font-size:10.5px; color:var(--text-muted); background:var(--bg-tertiary); padding:4px 8px; border-radius:var(--radius-xs);">
          ID: <strong>${node.id}</strong>
        </div>

        ${this.montarBlocoDeHistorico(node)}

        <div class="form-group">
          <label>Título / Rótulo:</label>
          <input type="text" id="inspect-node-rotulo" class="text-input" value="${this.escapeHtml(node.rotulo)}">
        </div>

        ${specificFields}

        <details style="border:1px solid var(--border-subtle); border-radius:var(--radius-xs); padding:6px 8px;">
          <summary style="font-size:11px; font-weight:500; cursor:pointer; color:var(--text-secondary);">Propriedades Extras (JSON)</summary>
          <textarea id="inspect-node-props" class="code-editor" rows="4" style="margin-top:6px;">${JSON.stringify(props, null, 2)}</textarea>
        </details>

        <div style="display:flex; gap:6px; margin-top:6px;">
          <button id="btn-save-node" class="btn btn-primary btn-sm" style="flex:1;">Salvar</button>
          <button id="btn-delete-node" class="btn btn-danger btn-sm">${node.tipo === "Projeto" ? "Excluir Nó" : "Excluir"}</button>
        </div>

        ${node.tipo === "Projeto" ? `<button id="btn-delete-project-cascade" class="btn btn-danger btn-sm" style="width:100%;">Excluir Projeto Inteiro (Cascata)</button>` : ""}
      </div>
    `;

    document.getElementById("btn-save-node")?.addEventListener("click", () => this.saveNode(node));
    document.getElementById("btn-delete-node")?.addEventListener("click", () => this.deleteElement("nos", node.id));
    document.getElementById("btn-delete-project-cascade")?.addEventListener("click", () => {
      this.onAction("DELETE_PROJECT_CASCADE", { id_projeto: node.id, rotulo: node.rotulo });
    });
  }

  /**
   * Quando o no nasceu, quando mudou pela ultima vez e em que ponto do log.
   * A sequencia esta aqui porque e ela, e nao a data, que decide a ordem entre
   * dois nos escritos por processos com relogios diferentes.
   */
  montarBlocoDeHistorico(node) {
    const seq = node.seq_criacao ?? 0;
    if (!seq && !node.criado_em) return "";
    const idade = formatarIdadeRelativa(node.criado_em);
    const linhaDeEdicao = foiAlterado(node)
      ? `<div>Alterado: <strong>${formatarDataCompleta(node.atualizado_em)}</strong> <span style="opacity:0.7;">(log #${node.seq_atualizacao})</span></div>`
      : `<div style="opacity:0.7;">Sem alterações desde a criação</div>`;
    return `
      <div style="font-size:10.5px; color:var(--text-secondary); background:var(--bg-tertiary); padding:6px 8px; border-radius:var(--radius-xs); display:flex; flex-direction:column; gap:3px;">
        <div>Criado: <strong>${formatarDataCompleta(node.criado_em)}</strong> <span style="opacity:0.7;">(log #${seq}${idade ? `, ${idade}` : ""})</span></div>
        ${linhaDeEdicao}
      </div>
    `;
  }

  renderEdgeInspector(edge) {
    if (this.typeBadge) this.typeBadge.textContent = `Aresta: ${edge.tipo}`;
    this.container.innerHTML = `
      <div class="inspector-form" style="display:flex; flex-direction:column; gap:10px;">
        <div style="font-family:var(--font-mono); font-size:10.5px; color:var(--text-muted); background:var(--bg-tertiary); padding:4px 8px; border-radius:var(--radius-xs);">
          ID: <strong>${edge.id}</strong>
        </div>
        <div class="form-group">
          <label>Origem:</label>
          <input type="text" class="text-input" value="${edge.origem_id}" readonly>
        </div>
        <div class="form-group">
          <label>Destino:</label>
          <input type="text" class="text-input" value="${edge.destino_id}" readonly>
        </div>
        <div class="form-group">
          <label>Tipo Semântico:</label>
          <input type="text" class="text-input" value="${edge.tipo}" readonly>
        </div>
        <button id="btn-delete-edge" class="btn btn-danger btn-sm" style="margin-top:6px;">Remover Aresta</button>
      </div>
    `;
    document.getElementById("btn-delete-edge")?.addEventListener("click", () => this.deleteElement("arestas", edge.id));
  }

  saveNode(node) {
    const rotulo = document.getElementById("inspect-node-rotulo")?.value;
    const propsJson = document.getElementById("inspect-node-props")?.value;
    let parsedProps = {};
    try {
      parsedProps = JSON.parse(propsJson || "{}");
    } catch (e) {
      alert("JSON de propriedades inválido");
      return;
    }
    const statusSel = document.getElementById("inspect-node-status") || document.getElementById("inspect-question-status");
    if (statusSel) {
      parsedProps.status = statusSel.value;
    }
    const autonomySel = document.getElementById("inspect-project-autonomy");
    if (autonomySel) {
      parsedProps.nivel_autonomia = autonomySel.value;
    }
    this.onAction("SAVE_NODE", {
      id_no: node.id,
      novo_rotulo: rotulo,
      novas_propriedades: parsedProps,
    });
  }

  deleteElement(tipo, id) {
    if (confirm(`Deseja realmente remover ${tipo === "nos" ? "o nó" : "a aresta"} ${id}?`)) {
      this.onAction("DELETE_ELEMENT", { tipo, id });
    }
  }

  escapeHtml(str) {
    if (!str) return "";
    return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }
}
