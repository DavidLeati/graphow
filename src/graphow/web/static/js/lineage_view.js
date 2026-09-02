/**
 * Causal Lineage and Provenance Tree View
 */
export class LineageView {
  constructor(containerId, state) {
    this.container = document.getElementById(containerId);
    this.state = state;
    this.targetLabel = document.getElementById("lineage-target-label");
  }

  clear() {
    if (this.targetLabel) {
      this.targetLabel.textContent = "Selecione um nó no canvas para visualizar sua linhagem causal automaticamente.";
    }
    if (this.container) {
      this.container.innerHTML = `<div style="padding:16px 8px; font-size:11.5px; color:var(--text-muted); text-align:center;">Nenhum nó selecionado.</div>`;
    }
  }

  async traceLineage(nodeId) {
    if (!nodeId) {
      this.clear();
      return;
    }
    if (this.targetLabel) {
      this.targetLabel.innerHTML = `Rastreando proveniência de <code>${nodeId}</code>...`;
    }
    this.container.innerHTML = `<div style="padding:10px; font-size:11px; color:var(--text-secondary);">Carregando cadeia causal...</div>`;
    try {
      const res = await fetch(`/api/lineage?id=${nodeId}&ramo=${this.state.currentBranch}`);
      const data = await res.json();
      this.render(data);
    } catch (err) {
      this.container.innerHTML = `<div style="color:var(--accent-red); padding:10px; font-size:11.5px;">Erro ao rastrear linhagem: ${err.message}</div>`;
    }
  }

  render(data) {
    if (this.targetLabel) {
      if (data.goal_raiz) {
        this.targetLabel.innerHTML = `Linhagem de <code>${data.id_alvo}</code> ➔ 🎯 Goal Raiz: <strong style="color:var(--text-main);">${data.goal_raiz.rotulo}</strong>`;
      } else {
        this.targetLabel.innerHTML = `Linhagem de <code>${data.id_alvo}</code> (Nenhum Goal raiz alcançado)`;
      }
    }

    if (!data.passos || data.passos.length === 0) {
      this.container.innerHTML = `<div style="padding:12px; font-size:11.5px; color:var(--text-muted);">Nenhum passo causal intermediário encontrado até a raiz.</div>`;
      return;
    }

    const stepsList = document.createElement("div");
    stepsList.style.display = "flex";
    stepsList.style.flexDirection = "column";
    stepsList.style.gap = "6px";
    stepsList.style.padding = "8px 0";

    data.passos.forEach((step, idx) => {
      const stepItem = document.createElement("div");
      stepItem.style.fontSize = "11.5px";
      stepItem.style.display = "flex";
      stepItem.style.alignItems = "center";
      stepItem.style.gap = "8px";
      stepItem.style.padding = "4px 8px";
      stepItem.style.background = "var(--bg-tertiary)";
      stepItem.style.borderRadius = "var(--radius-xs)";
      stepItem.style.border = "1px solid var(--border-subtle)";
      stepItem.innerHTML = `
        <span style="font-family:var(--font-mono); color:var(--accent-blue); font-weight:600; font-size:10.5px;">#${idx + 1}</span>
        <span style="color:var(--text-main);">${step}</span>
      `;
      stepsList.appendChild(stepItem);
    });

    this.container.innerHTML = "";
    this.container.appendChild(stepsList);
  }
}
