/**
 * Realtime Server-Sent Events (SSE) Client
 */

// Nome do bloco final que o servidor emite ao descartar um assinante lento.
// Precisa ser o mesmo de NOME_EVENTO_DESCARTE em web/sse_controller.py.
const EVENTO_DE_DESCARTE = "assinante_descartado";

const RECONNECT_DELAY_MS = 3000;

export class SSEClient {
  constructor(state, onEventReceived, onReconexao = null) {
    this.state = state;
    this.onEventReceived = onEventReceived;
    this.onReconexao = onReconexao;
    this.eventSource = null;
    this.reconnectTimer = null;
    this.jaConectou = false;
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
      this.aoAbrirConexao();
    };

    this.eventSource.onerror = () => {
      if (statusEl) {
        statusEl.className = "sse-status sse-disconnected";
        if (statusText) statusText.textContent = "SSE: Reconectando...";
      }
      this.eventSource.close();
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = setTimeout(() => this.connect(), RECONNECT_DELAY_MS);
    };

    this.registrarOuvintes();
  }

  /**
   * Toda reconexao e uma lacuna: o log andou enquanto o stream esteve fora e
   * esses eventos nao voltam. Reconectar sem reler deixaria o canvas parado num
   * passado silencioso — o mesmo sintoma de nao ter stream algum.
   */
  aoAbrirConexao() {
    const eraReconexao = this.jaConectou;
    this.jaConectou = true;
    if (eraReconexao && this.onReconexao) {
      this.onReconexao();
    }
  }

  registrarOuvintes() {
    // Precisa cobrir todo o TipoEvento do log: um tipo ausente aqui e um fato
    // que chega ao servidor e nunca ao canvas.
    const eventTypes = [
      "no_criado", "no_atualizado", "no_removido",
      "aresta_criada", "aresta_removida", "ramo_criado",
      "execucao_solicitada", "execucao_iniciada", "execucao_concluida",
    ];

    for (const evtType of eventTypes) {
      this.eventSource.addEventListener(evtType, (e) => this.receber(evtType, e));
    }

    // O servidor encerra o stream logo em seguida; quem faz a reconexao e o
    // onerror. Este ouvinte existe para o motivo aparecer no console, em vez de
    // a pagina simplesmente parecer travada.
    this.eventSource.addEventListener(EVENTO_DE_DESCARTE, (e) => {
      console.warn("Stream SSE encerrado pelo servidor:", e.data);
    });
  }

  receber(evtType, evento) {
    try {
      const payload = JSON.parse(evento.data);
      if (this.onEventReceived) {
        this.onEventReceived(evtType, payload);
      }
    } catch (err) {
      console.error("Erro ao processar mensagem SSE:", err);
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
