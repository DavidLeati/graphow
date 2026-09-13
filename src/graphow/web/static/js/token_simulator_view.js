/**
 * Vista do agente: o que um papel leria deste nó, dentro de um orçamento de tokens.
 *
 * O papel aqui é uma pergunta — "o que um executor veria daqui?" —, nunca a
 * credencial de quem escreve; a identidade da escrita é da sessão do servidor.
 * A simulação só roda com o painel visível: antes ela disparava
 * a cada clique no canvas, mesmo com a aba fechada.
 */
import { api } from "./api.js";
import { debounce, escapeHtml, gravarPreferencia, lerPreferencia } from "./dom.js";
import { icone } from "./icones.js";

const PAPEIS = ["planejador", "executor", "revisor"];
const ORCAMENTOS_SUGERIDOS = [200, 500, 1000, 1500, 3000];

export class TokenSimulatorView {
  constructor(raiz, { state, indice, acoes }) {
    this.raiz = raiz;
    this.state = state;
    this.indice = indice;
    this.acoes = acoes;
    this.papel = lerPreferencia("simulador_papel", "executor");
    this.orcamento = lerPreferencia("simulador_orcamento", 1000);
    this.idCarregado = null;
    this.pedido = 0;
    this.simularEmBreve = debounce(() => this.atualizar({ forcar: true }), 250);
    this.montarEstrutura();
  }

  montarEstrutura() {
    this.raiz.innerHTML = `
      <div class="simulador-controles">
        <label class="campo-compacto"><span>Papel</span>
          <select class="seletor" data-papel>${PAPEIS.map((papel) => `<option value="${papel}" ${papel === this.papel ? "selected" : ""}>${papel}</option>`).join("")}</select>
        </label>
        <label class="campo-compacto"><span>Orçamento</span>
          <input type="number" class="entrada mod-numero" data-orcamento min="50" step="50" value="${this.orcamento}">
        </label>
      </div>
      <div class="chips mod-orcamentos">${ORCAMENTOS_SUGERIDOS.map((valor) => `<button class="chip-botao" data-sugestao="${valor}">${valor}</button>`).join("")}</div>
      <div data-resultado></div>`;
    this.resultado = this.raiz.querySelector("[data-resultado]");
    this.raiz.querySelector("[data-papel]").addEventListener("change", (evento) => {
      this.papel = evento.target.value;
      gravarPreferencia("simulador_papel", this.papel);
      this.state.setSimulationRole?.(this.papel);
      this.atualizar({ forcar: true });
    });
    this.raiz.querySelector("[data-orcamento]").addEventListener("input", (evento) => this.definirOrcamento(evento.target.value));
    this.raiz.querySelectorAll("[data-sugestao]").forEach((botao) => {
      botao.addEventListener("click", () => {
        this.raiz.querySelector("[data-orcamento]").value = botao.dataset.sugestao;
        this.definirOrcamento(botao.dataset.sugestao);
      });
    });
    this.resultado.addEventListener("click", (evento) => {
      const alvo = evento.target.closest("[data-ir]");
      if (alvo) this.acoes.focarNo(alvo.dataset.ir, this.indice.info.get(alvo.dataset.ir));
    });
  }

  definirOrcamento(valor) {
    const numero = Number.parseInt(valor, 10);
    if (!Number.isFinite(numero) || numero <= 0) return;
    this.orcamento = numero;
    gravarPreferencia("simulador_orcamento", numero);
    this.simularEmBreve();
  }

  invalidar() {
    this.idCarregado = null;
  }

  async atualizar({ forcar = false } = {}) {
    const selecao = this.state.selectedElement;
    if (!selecao || selecao.type !== "node") {
      this.idCarregado = null;
      this.resultado.innerHTML = `<div class="painel-vazio">${icone("bot", { tamanho: 22 })}<span>Selecione um nó para ver o recorte de contexto que um agente leria dele.</span></div>`;
      return;
    }
    if (!forcar && this.idCarregado === selecao.id) return;
    this.idCarregado = selecao.id;
    const pedido = ++this.pedido;
    this.resultado.innerHTML = '<div class="painel-vazio"><span>Materializando o recorte…</span></div>';
    const dados = await api.simular({
      id_alvo: selecao.id,
      papel: this.papel,
      orcamento_tokens: this.orcamento,
      ramo_id: this.state.currentBranch,
    });
    if (pedido === this.pedido) this.render(dados);
  }

  render(dados) {
    if (!dados.sucesso) {
      this.resultado.innerHTML = `<div class="chamada mod-alerta">${icone("alert-triangle", { tamanho: 14 })}<span>${escapeHtml(dados.mensagem || "Falha na simulação")}</span></div>`;
      return;
    }
    const fracao = Math.min(100, Math.round((dados.tokens_estimados / dados.orcamento_tokens) * 100));
    const tom = fracao > 90 ? "mod-alerta" : fracao > 70 ? "mod-aviso" : "mod-ok";
    const vizinhos = (dados.vizinhos_expansiveis || []).map((id) => this.montarChipDeNo(id)).join("");
    this.resultado.innerHTML = `
      <div class="medidor ${tom}">
        <div class="medidor-numeros"><strong>${dados.tokens_estimados}</strong><span>de ${dados.orcamento_tokens} tokens · ${fracao}%</span></div>
        <div class="medidor-barra"><div class="medidor-preenchido" style="width:${fracao}%"></div></div>
        <div class="medidor-legenda">${dados.nos_incluidos?.length || 0} nós incluídos · ${dados.vizinhos_expansiveis?.length || 0} vizinhos a 1 salto</div>
      </div>
      ${vizinhos ? `<div class="panorama-rotulo">Expansíveis sob demanda</div><div class="chips">${vizinhos}</div>` : ""}
      <div class="panorama-rotulo">Markdown entregue ao agente</div>
      <pre class="bloco-codigo">${escapeHtml(dados.conteudo_markdown || "// vazio")}</pre>`;
  }

  montarChipDeNo(id) {
    const info = this.state.nodes.get(id) || this.indice.info.get(id);
    return `<button class="chip-botao" data-ir="${escapeHtml(id)}" title="${escapeHtml(id)}">${escapeHtml(info?.rotulo || id)}</button>`;
  }
}
