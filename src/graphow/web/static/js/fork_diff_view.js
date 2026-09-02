/**
 * Branch Diff & Historical Fork Studio View
 */
export class ForkDiffView {
  constructor(containerId, state, onAction) {
    this.container = document.getElementById(containerId);
    this.state = state;
    this.onAction = onAction;

    this.branchASel = document.getElementById("diff-branch-a");
    this.branchBSel = document.getElementById("diff-branch-b");

    document.getElementById("btn-compute-diff")?.addEventListener("click", () => {
      this.computeDiff();
    });
  }

  updateBranchOptions() {
    if (!this.branchASel || !this.branchBSel) return;
    const branches = this.state.branches;
    const html = branches.map((b) => `<option value="${b}">${b}</option>`).join("");
    this.branchASel.innerHTML = html;
    this.branchBSel.innerHTML = html;
    if (branches.length > 1) {
      this.branchBSel.selectedIndex = 1;
    }
  }

  async computeDiff() {
    const rA = this.branchASel?.value || "main";
    const rB = this.branchBSel?.value || "main";

    this.container.innerHTML = `<div style="padding:10px; font-size:11px;">Calculando discrepâncias estruturais...</div>`;
    try {
      const res = await fetch(`/api/diff?ramo_a=${rA}&ramo_b=${rB}`);
      const data = await res.json();
      this.render(data);
    } catch (err) {
      this.container.innerHTML = `<div style="color:var(--accent-danger); padding:10px;">Erro ao calcular diff: ${err.message}</div>`;
    }
  }

  render(data) {
    this.container.innerHTML = `
      <div style="display:grid; grid-template-columns:1fr 1fr 1fr; gap:12px; padding:8px 0; font-size:12px;">
        <div style="background:var(--bg-tertiary); padding:8px; border-radius:var(--radius-sm); border:1px solid var(--border-color);">
          <h4 style="color:var(--accent-success); margin-bottom:6px;">➕ Nós Adicionados (${data.nos_adicionados.length})</h4>
          <ul style="padding-left:16px;">${data.nos_adicionados.map((id) => `<li><code>${id}</code></li>`).join("") || "<em>Nenhum</em>"}</ul>
        </div>
        <div style="background:var(--bg-tertiary); padding:8px; border-radius:var(--radius-sm); border:1px solid var(--border-color);">
          <h4 style="color:var(--accent-danger); margin-bottom:6px;">➖ Nós Removidos (${data.nos_removidos.length})</h4>
          <ul style="padding-left:16px;">${data.nos_removidos.map((id) => `<li><code>${id}</code></li>`).join("") || "<em>Nenhum</em>"}</ul>
        </div>
        <div style="background:var(--bg-tertiary); padding:8px; border-radius:var(--radius-sm); border:1px solid var(--border-color);">
          <h4 style="color:var(--accent-cyan); margin-bottom:6px;">🔀 Arestas Modificadas (+${data.arestas_adicionadas.length} / -${data.arestas_removidas.length})</h4>
          <ul style="padding-left:16px;">${data.arestas_adicionadas.map((id) => `<li>+ <code>${id}</code></li>`).join("") || "<em>Nenhuma adição</em>"}</ul>
        </div>
      </div>
    `;
  }
}
