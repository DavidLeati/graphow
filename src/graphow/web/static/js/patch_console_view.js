/**
 * Terminal de patch RFC 6902, aberto como aba no centro.
 *
 * Aceita operações `add` em `/nos/{id}` e as envia ao kernel pelo mesmo caminho
 * da interface; o recibo volta com o diagnóstico do portão que recusou, quando
 * algum recusar. Outras operações ficam para o agente, que fala o patch inteiro.
 */
import { api } from "./api.js";
import { escapeHtml } from "./dom.js";
import { icone } from "./icones.js";

const EXEMPLO = `{
  "operacoes": [
    {"op": "add", "path": "/nos/task-exemplo", "value": {"id": "task-exemplo", "tipo": "Task", "rotulo": "Nova tarefa"}}
  ]
}`;

export class PatchConsoleView {
  constructor(raiz, { state, aoGravar }) {
    this.raiz = raiz;
    this.state = state;
    this.aoGravar = aoGravar;
    this.raiz.innerHTML = `
      <div class="ferramenta">
        <div class="ferramenta-cabecalho">
          <h2>${icone("terminal", { tamanho: 18 })} Terminal de patch</h2>
          <p class="texto-fraco">Operações <code>add</code> em <code>/nos/…</code> passam pelos quatro portões como qualquer escrita desta tela.</p>
        </div>
        <div class="terminal-grade">
          <label class="campo"><span class="campo-rotulo">Proposta JSON Patch</span>
            <textarea class="entrada mod-codigo" data-entrada rows="14" spellcheck="false" placeholder="${escapeHtml(EXEMPLO)}"></textarea></label>
          <label class="campo"><span class="campo-rotulo">Recibo do kernel</span>
            <pre class="bloco-codigo mod-alto" data-recibo>// Aguardando submissão…</pre></label>
        </div>
        <div class="bloco-botoes">
          <button class="botao" data-exemplo>Inserir exemplo</button>
          <button class="botao mod-cta" data-enviar>${icone("arrow-right", { tamanho: 14 })} Submeter ao kernel</button>
        </div>
      </div>`;
    this.entrada = this.raiz.querySelector("[data-entrada]");
    this.recibo = this.raiz.querySelector("[data-recibo]");
    this.raiz.querySelector("[data-exemplo]").addEventListener("click", () => { this.entrada.value = EXEMPLO; });
    this.raiz.querySelector("[data-enviar]").addEventListener("click", () => this.submitRawPatch());
    this.entrada.addEventListener("keydown", (evento) => {
      if ((evento.ctrlKey || evento.metaKey) && evento.key === "Enter") this.submitRawPatch();
    });
  }

  async submitRawPatch() {
    const bruto = this.entrada.value.trim();
    if (!bruto) return;
    let proposta;
    try {
      proposta = JSON.parse(bruto);
    } catch (erro) {
      this.recibo.textContent = `JSON malformado: ${erro.message}`;
      return;
    }
    const operacoes = proposta.operacoes || [proposta];
    const suportadas = operacoes.filter((op) => op.op === "add" && op.path?.startsWith("/nos/"));
    if (suportadas.length === 0) {
      this.recibo.textContent = "Nenhuma operação suportada: use add em /nos/{id}.";
      return;
    }
    this.recibo.textContent = "// Submetendo ao kernel…";
    const recibos = [];
    for (const op of suportadas) {
      recibos.push(await api.criarNo({
        id_no: op.value?.id,
        tipo: op.value?.tipo || "Task",
        rotulo: op.value?.rotulo || "Nó via terminal",
        propriedades: op.value?.propriedades || {},
        sessao_id: op.value?.sessao_id || null,
        ramo_id: this.state.currentBranch,
      }));
    }
    const ignoradas = operacoes.length - suportadas.length;
    this.recibo.textContent = JSON.stringify(recibos.length === 1 ? recibos[0] : recibos, null, 2) + (ignoradas ? `\n\n// ${ignoradas} operação(ões) não suportada(s) foram ignoradas.` : "");
    await this.aoGravar();
  }
}
