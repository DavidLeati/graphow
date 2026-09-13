/**
 * Painel de busca da lateral esquerda.
 *
 * A busca rápida (Ctrl+K) serve para pular até um nó; este painel serve para
 * ler os resultados: agrupados por tipo, com o trecho onde o termo apareceu e o
 * caminho até o contêiner. Os filtros de tipo vão para o servidor, que corta
 * depois de ranquear e diz quantos existem no total.
 */
import { api } from "./api.js";
import { debounce, destacarTermo, escapeHtml } from "./dom.js";
import { icone } from "./icones.js";
import { apresentarStatus, apresentarTipo, corDoTipo, ehConteiner, ORDEM_DE_TRABALHO, TIPOS_CONTEINER } from "./ontologia_ui.js";

const LIMITE_DO_PAINEL = 50;

export class BuscaView {
  constructor(raiz, { state, indice, acoes }) {
    this.raiz = raiz;
    this.state = state;
    this.indice = indice;
    this.acoes = acoes;
    this.tiposMarcados = new Set();
    this.gruposFechados = new Set();
    this.resposta = null;
    this.pedido = 0;
    this.montarEstrutura();
  }

  montarEstrutura() {
    const tipos = [...TIPOS_CONTEINER, ...ORDEM_DE_TRABALHO];
    this.raiz.innerHTML = `
      <div class="busca-caixa">
        <span class="busca-lupa">${icone("search", { tamanho: 15 })}</span>
        <input type="search" class="busca-entrada" data-termo placeholder="Buscar no grafo inteiro…" spellcheck="false">
      </div>
      <div class="busca-filtros">${tipos.map((tipo) => `
        <button class="chip-filtro" data-tipo="${tipo}" style="--cor-tipo:${corDoTipo(tipo)}" title="${escapeHtml(apresentarTipo(tipo).descricao)}">${icone(apresentarTipo(tipo).icone, { tamanho: 12 })}${escapeHtml(apresentarTipo(tipo).nome)}</button>`).join("")}
      </div>
      <div class="busca-resumo" data-resumo></div>
      <div class="busca-resultados" data-resultados></div>`;
    this.entrada = this.raiz.querySelector("[data-termo]");
    this.entrada.addEventListener("input", debounce(() => this.buscar(), 180));
    this.raiz.querySelector(".busca-filtros").addEventListener("click", (evento) => this.alternarTipo(evento));
    const resultados = this.raiz.querySelector("[data-resultados]");
    resultados.addEventListener("click", (evento) => this.aoClicar(evento));
    resultados.addEventListener("contextmenu", (evento) => this.aoMenu(evento));
    resultados.addEventListener("mouseover", (evento) => {
      const item = evento.target.closest("[data-ir]");
      this.acoes.destacar(item && this.state.nodes.has(item.dataset.ir) ? item.dataset.ir : null);
    });
    resultados.addEventListener("mouseleave", () => this.acoes.destacar(null));
    this.renderVazio();
  }

  focar(termo) {
    if (termo !== undefined) this.entrada.value = termo;
    this.entrada.focus();
    this.entrada.select();
    if (termo !== undefined) this.buscar();
  }

  alternarTipo(evento) {
    const chip = evento.target.closest("[data-tipo]");
    if (!chip) return;
    const tipo = chip.dataset.tipo;
    if (this.tiposMarcados.has(tipo)) this.tiposMarcados.delete(tipo);
    else this.tiposMarcados.add(tipo);
    chip.classList.toggle("is-ativo", this.tiposMarcados.has(tipo));
    this.buscar();
  }

  async buscar() {
    const termo = this.entrada.value.trim();
    if (!termo) {
      this.resposta = null;
      this.renderVazio();
      return;
    }
    const pedido = ++this.pedido;
    const resposta = await api.buscar({ termo, tipos: [...this.tiposMarcados], limite: LIMITE_DO_PAINEL, ramo: this.state.currentBranch });
    if (pedido !== this.pedido) return;
    this.resposta = { ...resposta, termo };
    if (resposta.sucesso) this.indice.registrarNos(resposta.resultados);
    this.render();
  }

  renderVazio() {
    this.raiz.querySelector("[data-resumo]").innerHTML = "";
    this.raiz.querySelector("[data-resultados]").innerHTML = `
      <div class="painel-vazio">${icone("search", { tamanho: 22 })}<span>Busca no rótulo e nas propriedades de todo nó do ramo, na mesma ordem de relevância que o agente usa.</span></div>`;
  }

  render() {
    const resposta = this.resposta;
    const resumo = this.raiz.querySelector("[data-resumo]");
    const alvo = this.raiz.querySelector("[data-resultados]");
    if (!resposta.sucesso) {
      resumo.innerHTML = "";
      alvo.innerHTML = `<div class="chamada mod-alerta">${icone("alert-triangle", { tamanho: 14 })}<span>${escapeHtml(resposta.mensagem || "A busca falhou.")}</span></div>`;
      return;
    }
    resumo.innerHTML = resposta.total
      ? `<strong>${resposta.total}</strong> resultado(s)${resposta.truncado ? ` · mostrando os ${resposta.exibidos} mais relevantes` : ""}`
      : "Nenhum resultado.";
    const grupos = new Map();
    for (const item of resposta.resultados) {
      if (!grupos.has(item.tipo)) grupos.set(item.tipo, []);
      grupos.get(item.tipo).push(item);
    }
    alvo.innerHTML = [...grupos.entries()].map(([tipo, itens]) => this.montarGrupo(tipo, itens, resposta.termo)).join("");
  }

  montarGrupo(tipo, itens, termo) {
    const fechado = this.gruposFechados.has(tipo);
    const apresentacao = apresentarTipo(tipo);
    return `
      <div class="busca-grupo">
        <button class="busca-grupo-titulo" data-grupo="${escapeHtml(tipo)}">
          ${icone("chevron-down", { tamanho: 14, classe: fechado ? "is-recolhida" : "" })}
          <span style="color:${corDoTipo(tipo)}">${icone(apresentacao.icone, { tamanho: 14 })}</span>
          <span>${escapeHtml(apresentacao.plural)}</span><span class="contador">${itens.length}</span>
        </button>
        ${fechado ? "" : itens.map((item) => this.montarItem(item, termo)).join("")}
      </div>`;
  }

  montarItem(item, termo) {
    const referencia = ehConteiner(item.tipo) ? item.id : item.sessao_id;
    const caminho = referencia ? this.indice.ancestrais(referencia).filter((anc) => anc.id !== item.id).map((anc) => anc.rotulo).join(" / ") : "fora da hierarquia";
    const trecho = item.trecho ? `<div class="busca-trecho"><span class="texto-fraco">${escapeHtml(item.trecho.chave)}:</span> ${destacarTermo(item.trecho.texto, termo)}</div>` : "";
    return `
      <div class="busca-item" data-ir="${escapeHtml(item.id)}">
        <div class="busca-item-titulo">${destacarTermo(item.rotulo || item.id, termo)}</div>
        ${trecho}
        <div class="busca-item-meta">${escapeHtml(caminho)}${item.status ? ` · ${escapeHtml(apresentarStatus(item.status))}` : ""}</div>
      </div>`;
  }

  aoClicar(evento) {
    const grupo = evento.target.closest("[data-grupo]");
    if (grupo) {
      const tipo = grupo.dataset.grupo;
      if (this.gruposFechados.has(tipo)) this.gruposFechados.delete(tipo);
      else this.gruposFechados.add(tipo);
      this.render();
      return;
    }
    const item = evento.target.closest("[data-ir]");
    if (!item) return;
    const info = this.indice.info.get(item.dataset.ir);
    if (ehConteiner(info?.tipo)) this.acoes.abrirEscopo(this.indice.escopoDe(item.dataset.ir), { novaAba: evento.ctrlKey || evento.metaKey });
    else this.acoes.focarNo(item.dataset.ir, info);
  }

  aoMenu(evento) {
    const item = evento.target.closest("[data-ir]");
    if (!item) return;
    const info = this.state.nodes.get(item.dataset.ir) || this.indice.info.get(item.dataset.ir);
    if (info) this.acoes.menuDoNo(evento, info);
  }
}
