/**
 * RFC 6902 JSON Patch Terminal Console & MAST Diagnostics View
 */
export class PatchConsoleView {
  constructor(containerId, state, onAction) {
    this.container = document.getElementById(containerId);
    this.state = state;
    this.onAction = onAction;

    this.inputArea = document.getElementById("patch-json-input");
    this.outputArea = document.getElementById("patch-receipt-output");

    document.getElementById("btn-submit-raw-patch")?.addEventListener("click", () => {
      this.submitRawPatch();
    });
  }

  async submitRawPatch() {
    const raw = this.inputArea?.value;
    if (!raw) return;

    let payload;
    try {
      payload = JSON.parse(raw);
    } catch (e) {
      if (this.outputArea) this.outputArea.textContent = `❌ JSON Malformado: ${e.message}`;
      return;
    }

    if (this.outputArea) this.outputArea.textContent = "// Submetendo ao Kernel...";

    try {
      const operacoes = payload.operacoes || [payload];
      let sucessoGeral = true;
      let resultado = null;

      for (const op of operacoes) {
        if (op.op === "add" && op.path?.startsWith("/nos/")) {
          const res = await fetch("/api/nodes", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              id_no: op.value?.id,
              tipo: op.value?.tipo || "Task",
              rotulo: op.value?.rotulo || "Nó via Console",
              propriedades: op.value?.propriedades || {},
              ramo_id: this.state.currentBranch,
            }),
          });
          resultado = await res.json();
          if (!resultado.sucesso) sucessoGeral = false;
        }
      }

      if (this.outputArea) {
        this.outputArea.textContent = JSON.stringify(resultado || { sucesso: true, mensagem: "Patch processado" }, null, 2);
      }
      this.onAction("REFRESH_CANVAS");
    } catch (err) {
      if (this.outputArea) this.outputArea.textContent = `❌ Erro de transporte: ${err.message}`;
    }
  }
}
