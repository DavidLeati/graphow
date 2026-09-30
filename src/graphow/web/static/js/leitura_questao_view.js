/**
 * Leitura de uma dúvida, aberta como aba no centro.
 *
 * A lateral direita divide a altura com o histórico e a largura com o canvas:
 * uma pergunta de vinte linhas cabia ali só rolando, e a resposta ficava fora
 * da tela. Aqui a pergunta ocupa o centro numa coluna de leitura, e a resposta
 * com o Responder fica logo abaixo dela, ou ao lado quando a vista é larga.
 * Responder passa pela mesma ação do inspetor; esta vista não grava nada sozinha.
 */
import { api } from "./api.js";
import { escapeHtml } from "./dom.js";
import { icone } from "./icones.js";
import { avisar } from "./modais.js";
import { apresentarStatus, apresentarTipo, corDoTipo, tomDoStatus } from "./ontologia_ui.js";
import { ajustarAltura } from "./propriedades_editor.js";
import { formatarTextoDeLeitura } from "./texto_formatado.js";

/**
 * A resposta cresce com o texto até menos da metade da janela: ao lado da
 * pergunta ela acompanha a rolagem, e mais alta que a tela esconderia o
 * próprio Responder.
 */
function ajustarResposta(campo) {
  ajustarAltura(campo, Math.max(160, Math.round(window.innerHeight * 0.45)));
}

export class LeituraDaQuestaoView {
  constructor(raiz, { state, indice, acoes, aoCarregar }) {
    this.raiz = raiz;
    this.state = state;
    this.indice = indice;
    this.acoes = acoes;
    this.aoCarregar = aoCarregar;
    this.noId = null;
    this.no = null;
    this.erro = null;
    this.pedido = 0;
    this.enviando = false;
    // A resposta em rascunho sobrevive à releitura que o tempo real dispara a
    // cada evento do log, e à troca de aba: perder o que se digitou é pior que
    // mostrá-lo sobre uma versão um pouco mais nova da dúvida.
    this.rascunhos = new Map();
    this.raiz.addEventListener("click", (evento) => this.aoClicar(evento));
    this.raiz.addEventListener("input", (evento) => {
      if (!evento.target.matches("[data-resposta]")) return;
      this.rascunhos.set(this.noId, evento.target.value);
      ajustarResposta(evento.target);
    });
    this.raiz.addEventListener("keydown", (evento) => {
      const atalho = (evento.ctrlKey || evento.metaKey) && evento.key === "Enter";
      if (atalho && evento.target.matches("[data-resposta]")) {
        evento.preventDefault();
        this.responder();
      }
    });
  }

  /** Guarda o que o inspetor tinha digitado na resposta, para a leitura começar dali. */
  lembrarRascunho(id, texto) {
    if (texto && texto.trim()) this.rascunhos.set(id, texto);
  }

  abrir(id) {
    if (id !== this.noId) {
      this.no = null;
      this.erro = null;
    }
    this.noId = id || null;
    if (!this.no) this.render();
    return this.atualizar();
  }

  /** Relê a dúvida do servidor. A resposta de um pedido velho é descartada. */
  async atualizar() {
    if (!this.noId) {
      this.render();
      return;
    }
    const pedido = ++this.pedido;
    const resposta = await api.expandir(this.noId, this.state.currentBranch);
    if (pedido !== this.pedido) return;
    this.no = resposta.sucesso ? resposta.no : null;
    this.erro = resposta.sucesso ? null : resposta.mensagem || "Não foi possível ler o nó.";
    this.render();
    if (this.no) this.aoCarregar?.(this.no);
  }

  render() {
    if (!this.noId || (!this.no && !this.erro)) {
      this.raiz.innerHTML = `<div class="ferramenta"><div class="painel-vazio">${icone("help-circle", { tamanho: 22 })}<span>${this.noId ? "Lendo a dúvida…" : "Abra uma dúvida pelo inspetor para lê-la aqui."}</span></div></div>`;
      return;
    }
    if (!this.no) {
      this.raiz.innerHTML = `<div class="ferramenta"><div class="chamada mod-alerta">${icone("alert-triangle", { tamanho: 14 })}<span>${escapeHtml(this.erro)}</span></div></div>`;
      return;
    }
    const foco = this.lerFoco();
    this.montar(this.no);
    const campo = this.raiz.querySelector("[data-resposta]");
    // Oculta, a aba mediria zero; o campo fica com as linhas que nasceu.
    if (campo && !this.raiz.hidden) ajustarResposta(campo);
    this.restaurarFoco(foco);
  }

  /**
   * A releitura chega a cada evento do log, também no meio da digitação. O
   * texto já está no rascunho; o que se perderia é o cursor e a rolagem.
   */
  lerFoco() {
    const campo = this.raiz.querySelector("[data-resposta]");
    const focado = campo && document.activeElement === campo;
    return { rolagem: this.raiz.scrollTop, focado, inicio: campo?.selectionStart, fim: campo?.selectionEnd };
  }

  restaurarFoco({ rolagem, focado, inicio, fim }) {
    this.raiz.scrollTop = rolagem;
    const campo = this.raiz.querySelector("[data-resposta]");
    if (!focado || !campo || campo.disabled) return;
    campo.focus({ preventScroll: true });
    campo.setSelectionRange(inicio, fim);
  }

  montar(no) {
    const tipo = apresentarTipo(no.tipo);
    const status = no.propriedades?.status || "aberta";
    this.raiz.innerHTML = `
      <div class="ferramenta mod-leitura">
        <div class="leitura-topo">
          <span class="pilula-tipo" style="--cor-tipo:${corDoTipo(no.tipo)}">${icone(tipo.icone, { tamanho: 13 })}${escapeHtml(tipo.nome)}</span>
          <span class="leitura-status tom-${tomDoStatus(status)}">${escapeHtml(apresentarStatus(status))}</span>
          <span class="espacador"></span>
          <button class="botao mod-pequeno" data-acao="focar" title="Selecionar a dúvida e centralizá-la no canvas">${icone("crosshair", { tamanho: 14 })} Mostrar no canvas</button>
        </div>
        <h2 class="leitura-titulo">${escapeHtml(no.rotulo)}</h2>
        <div class="leitura-grade">
          <article class="texto-leitura leitura-pergunta">${formatarTextoDeLeitura(no.propriedades?.pergunta) || '<p class="texto-fraco">Sem pergunta por extenso: o título acima é tudo o que foi escrito.</p>'}</article>
          <section class="leitura-resposta">${this.montarResposta(no, status)}</section>
        </div>
      </div>`;
  }

  /** Dúvida aberta pede a resposta; a encerrada mostra a que recebeu. */
  montarResposta(no, status) {
    const rotulo = `<span class="bloco-campo-rotulo">${icone("corner-down-right", { tamanho: 14 })} Resposta humana</span>`;
    if (status !== "aberta") {
      const lida = formatarTextoDeLeitura(no.propriedades?.resposta) || '<p class="texto-fraco">Sem resposta registrada.</p>';
      return `${rotulo}<div class="texto-leitura">${lida}</div>`;
    }
    const valor = this.rascunhos.get(no.id) ?? no.propriedades?.resposta ?? "";
    return `
      ${rotulo}
      <textarea class="entrada mod-area" data-resposta rows="8" placeholder="Escreva a resposta que destrava a tarefa…" ${this.enviando ? "disabled" : ""}>${escapeHtml(valor)}</textarea>
      ${this.montarBloqueadas(no)}
      <button class="botao mod-cta mod-largo" data-acao="responder" ${this.enviando ? "disabled" : ""}>Responder e destravar</button>
      <span class="bloco-nota">Ctrl+Enter também responde. Título e pergunta se editam pelo inspetor.</span>`;
  }

  montarBloqueadas(no) {
    const alvos = (no.arestas_saida || []).filter((aresta) => aresta.tipo === "bloqueia").map((aresta) => aresta.destino);
    if (alvos.length === 0) return "";
    const links = alvos.map((id) => {
      const info = this.state.nodes.get(id) || this.indice.no(id) || { rotulo: id };
      return `<button class="link-no" data-acao="ir-para" data-id="${escapeHtml(id)}">${escapeHtml(info.rotulo || id)}</button>`;
    });
    return `<div class="bloco-nota">Bloqueia: ${links.join(" ")}</div>`;
  }

  /**
   * O mesmo gesto do inspetor: status "respondida" e a resposta, pela ação que
   * a aplicação dá aos painéis. O recibo recusado mantém o texto para correção.
   */
  async responder() {
    if (!this.no || this.enviando) return;
    if (this.state.isTimeTraveling) {
      avisar("A tela mostra o passado. Volte ao presente para responder.", "info");
      return;
    }
    const campo = this.raiz.querySelector("[data-resposta]");
    const resposta = campo?.value.trim();
    if (!resposta) {
      avisar("Escreva a resposta antes de encerrar a dúvida.", "erro");
      return;
    }
    const id = this.no.id;
    this.alternarEnvio(true);
    const recibo = await this.acoes.responderQuestao(this.no, resposta);
    this.alternarEnvio(false);
    if (!recibo?.sucesso) return;
    this.rascunhos.delete(id);
    if (this.noId === id) await this.atualizar();
  }

  alternarEnvio(enviando) {
    this.enviando = enviando;
    this.raiz.querySelectorAll("[data-resposta], [data-acao=responder]").forEach((campo) => {
      campo.disabled = enviando;
    });
  }

  aoClicar(evento) {
    const alvo = evento.target.closest("[data-acao]");
    if (!alvo) return;
    const tratadores = {
      responder: () => this.responder(),
      focar: () => this.no && this.acoes.mostrarNoCanvas(this.no.id, this.no),
      "ir-para": () => this.acoes.mostrarNoCanvas(alvo.dataset.id),
    };
    tratadores[alvo.dataset.acao]?.();
  }
}
