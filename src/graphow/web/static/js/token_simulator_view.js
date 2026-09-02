/**
 * AI Context Materializer & Token Budget Simulator View
 */
export class TokenSimulatorView {
  constructor(containerId, state) {
    this.container = document.getElementById(containerId);
    this.state = state;
    this.targetInput = document.getElementById("token-target-id");
    this.roleSelect = document.getElementById("token-sim-role");
    this.budgetInput = document.getElementById("token-budget-input");
    this.metricsInfo = document.getElementById("token-metrics-info");
    this.previewEl = document.getElementById("token-preview-content");

    document.getElementById("btn-run-token-sim")?.addEventListener("click", () => {
      this.runSimulation();
    });

    // Re-run automatically on role or budget change
    this.roleSelect?.addEventListener("change", () => {
      if (this.targetInput?.value) this.runSimulation();
    });

    this.budgetInput?.addEventListener("input", () => {
      if (this.targetInput?.value) {
        clearTimeout(this._debounceTimer);
        this._debounceTimer = setTimeout(() => this.runSimulation(), 250);
      }
    });
  }

  clear() {
    if (this.targetInput) this.targetInput.value = "";
    if (this.metricsInfo) {
      this.metricsInfo.textContent = "Selecione um nó no canvas para simular o orçamento de tokens da IA automaticamente.";
    }
    if (this.previewEl) {
      this.previewEl.textContent = "// Selecione um nó no canvas para visualizar o recorte de contexto.";
    }
  }

  setTargetNode(nodeId) {
    if (!nodeId) {
      this.clear();
      return;
    }
    if (this.targetInput) {
      this.targetInput.value = nodeId;
    }
    this.runSimulation();
  }

  async runSimulation() {
    const idAlvo = this.targetInput?.value;
    if (!idAlvo) {
      this.clear();
      return;
    }
    const papel = this.roleSelect?.value || this.state?.simulationRole || "executor";
    this.state?.setSimulationRole?.(papel);
    const orcamento = parseInt(this.budgetInput?.value || "1000", 10);

    if (this.metricsInfo) this.metricsInfo.textContent = `Materializando recorte de contexto para ${idAlvo}...`;

    try {
      const res = await fetch("/api/simulation/view", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          id_alvo: idAlvo,
          papel: papel,
          orcamento_tokens: orcamento,
          ramo_id: this.state.currentBranch,
        }),
      });
      const data = await res.json();
      this.render(data);
    } catch (err) {
      if (this.metricsInfo) this.metricsInfo.textContent = `Erro ao simular tokens: ${err.message}`;
    }
  }

  render(data) {
    if (!data.sucesso) {
      if (this.metricsInfo) this.metricsInfo.textContent = `❌ ${data.mensagem || "Falha na simulação"}`;
      if (this.previewEl) this.previewEl.textContent = JSON.stringify(data, null, 2);
      return;
    }

    if (this.metricsInfo) {
      const percent = Math.round((data.tokens_estimados / data.orcamento_tokens) * 100);
      this.metricsInfo.innerHTML = `
        🪙 Tokens Estimados: <strong style="color:var(--text-main);">${data.tokens_estimados}</strong> / <strong>${data.orcamento_tokens}</strong> (<span style="color:${percent > 90 ? 'var(--accent-red)' : 'var(--accent-green)'};">${percent}%</span> do orçamento)
        | Nós incluídos: <strong style="color:var(--text-main);">${data.nos_incluidos?.length || 0}</strong>
        | Vizinhos a 1 salto: <strong style="color:var(--text-main);">${data.vizinhos_expansiveis?.length || 0}</strong>
      `;
    }

    if (this.previewEl) {
      this.previewEl.textContent = data.conteudo_markdown || "// Vazio";
    }
  }
}
