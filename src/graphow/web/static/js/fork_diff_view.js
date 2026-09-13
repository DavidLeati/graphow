/**
 * Comparador de ramos, aberto como aba no centro.
 *
 * Mostra o que um ramo tem e o outro não — nós adicionados, removidos e arestas
 * que mudaram —, com o rótulo de cada nó quando ele é conhecido.
 */
import { api } from "./api.js";
import { escapeHtml } from "./dom.js";
import { icone } from "./icones.js";
import { apresentarTipo, corDoTipo } from "./ontologia_ui.js";

export class ForkDiffView {
  constructor(raiz, { state, indice, acoes }) {
    this.raiz = raiz;
    this.state = state;
    this.indice = indice;
    this.acoes = acoes;
    this.raiz.innerHTML = `
      <div class="ferramenta">
        <div class="ferramenta-cabecalho">
          <h2>${icone("git-compare", { tamanho: 18 })} Comparar ramos</h2>
          <p class="texto-fraco">Diferença estrutural entre dois ramos do log: o que existe num e não no outro.</p>
        </div>
        <div class="ferramenta-controles">
          <label class="campo-compacto"><span>Ramo base</span><select class="seletor" data-ramo-a></select></label>
          <span class="ferramenta-seta">${icone("arrow-right", { tamanho: 16 })}</span>
          <label class="campo-compacto"><span>Comparado</span><select class="seletor" data-ramo-b></select></label>
          <button class="botao mod-cta" data-comparar>Comparar</button>
        </div>
        <div data-resultado class="ferramenta-resultado"></div>
      </div>`;
    this.seletorA = this.raiz.querySelector("[data-ramo-a]");
    this.seletorB = this.raiz.querySelector("[data-ramo-b]");
    this.raiz.querySelector("[data-comparar]").addEventListener("click", () => this.computeDiff());
    this.raiz.querySelector("[data-resultado]").addEventListener("click", (evento) => {
      const alvo = evento.target.closest("[data-ir]");
      if (alvo) this.acoes.focarNo(alvo.dataset.ir, this.indice.info.get(alvo.dataset.ir));
    });
    this.mostrarDica();
  }

  mostrarDica() {
    const unico = this.state.branches.length < 2;
    this.raiz.querySelector("[data-resultado]").innerHTML = `
      <div class="painel-vazio">${icone("git-fork", { tamanho: 22 })}<span>${unico ? "Só existe um ramo. Crie um fork pela barra de status ou pela paleta de comandos para ter o que comparar." : "Escolha os dois ramos e clique em Comparar."}</span></div>`;
  }

  updateBranchOptions() {
    const opcoes = this.state.branches.map((ramo) => `<option value="${escapeHtml(ramo)}">${escapeHtml(ramo)}</option>`).join("");
    this.seletorA.innerHTML = opcoes;
    this.seletorB.innerHTML = opcoes;
    this.seletorA.value = this.state.currentBranch;
    const outro = this.state.branches.find((ramo) => ramo !== this.state.currentBranch);
    if (outro) this.seletorB.value = outro;
  }

  async computeDiff() {
    const alvo = this.raiz.querySelector("[data-resultado]");
    alvo.innerHTML = '<div class="painel-vazio"><span>Calculando discrepâncias estruturais…</span></div>';
    const dados = await api.diff(this.seletorA.value, this.seletorB.value);
    if (dados.sucesso === false || !dados.nos_adicionados) {
      alvo.innerHTML = `<div class="chamada mod-alerta">${icone("alert-triangle", { tamanho: 14 })}<span>${escapeHtml(dados.mensagem || "Falha ao calcular o diff.")}</span></div>`;
      return;
    }
    alvo.innerHTML = `
      <div class="diff-grade">
        ${this.montarColuna("Nós só no comparado", "plus", "mod-ok", dados.nos_adicionados)}
        ${this.montarColuna("Nós só no base", "trash", "mod-alerta", dados.nos_removidos)}
        ${this.montarColuna("Arestas novas", "link", "mod-info", dados.arestas_adicionadas, false)}
        ${this.montarColuna("Arestas que saíram", "x", "mod-aviso", dados.arestas_removidas, false)}
      </div>
      <p class="texto-fraco">${dados.nos_comuns?.length ?? 0} nós em comum.</p>`;
  }

  montarColuna(titulo, nomeIcone, tom, ids, saoNos = true) {
    const itens = ids.map((id) => {
      const info = saoNos ? this.indice.info.get(id) : null;
      const rotulo = info?.rotulo ? `<span>${escapeHtml(info.rotulo)}</span>` : "";
      const marca = info ? `<span style="color:${corDoTipo(info.tipo)}">${icone(apresentarTipo(info.tipo).icone, { tamanho: 13 })}</span>` : "";
      return `<li ${saoNos ? `data-ir="${escapeHtml(id)}"` : ""}>${marca}<code>${escapeHtml(id)}</code>${rotulo}</li>`;
    });
    return `
      <div class="diff-coluna ${tom}">
        <div class="diff-titulo">${icone(nomeIcone, { tamanho: 14 })}${escapeHtml(titulo)}<span class="contador">${ids.length}</span></div>
        <ul>${itens.join("") || '<li class="texto-fraco">Nenhum</li>'}</ul>
      </div>`;
  }
}
