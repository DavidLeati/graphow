/**
 * Realtime Server-Sent Events (SSE) Client
 */
export class SSEClient {
  constructor(state, onEventReceived) {
    this.state = state;
    this.onEventReceived = onEventReceived;
    this.eventSource = null;
    this.reconnectTimer = null;
  }

  connect() {
    if (this.eventSource) {
      this.eventSource.close();
    }
    const statusEl = document.getElementById("sse-status");
    const statusText = statusEl?.querySelector(".status-text");

    this.eventSource = new EventSource("/api/sse");

    this.eventSource.onopen = () => {
      if (statusEl) {
        statusEl.className = "sse-status sse-connected";
        if (statusText) statusText.textContent = "SSE: Conectado";
      }
    };

    this.eventSource.onerror = () => {
      if (statusEl) {
        statusEl.className = "sse-status sse-disconnected";
        if (statusText) statusText.textContent = "SSE: Reconectando...";
      }
      this.eventSource.close();
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = setTimeout(() => this.connect(), 3000);
    };

    const eventTypes = [
      "no_criado", "no_atualizado", "no_removido",
      "aresta_criada", "aresta_removida", "ramo_criado",
    ];

    for (const evtType of eventTypes) {
      this.eventSource.addEventListener(evtType, (e) => {
        try {
          const payload = JSON.parse(e.data);
          if (this.onEventReceived) {
            this.onEventReceived(evtType, payload);
          }
        } catch (err) {
          console.error("Erro ao processar mensagem SSE:", err);
        }
      });
    }
  }

  disconnect() {
    if (this.eventSource) {
      this.eventSource.close();
      this.eventSource = null;
    }
    clearTimeout(this.reconnectTimer);
  }
}
