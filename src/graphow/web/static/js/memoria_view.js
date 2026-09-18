/**
 * Memória: os aprendizados do ramo e as sessões, com o fechamento e a condensação.
 *
 * A memória em camadas existia para o agente (a vista) e para o disco (o acervo
 * de notas); aqui é onde a pessoa a vê e a governa. Os aprendizados aparecem
 * com origem, alcance e marcas, promovidos ou não — e promover, o gesto que os
 * faz chegar às outras tarefas, fica a um clique. As sessões aparecem da mais
 * recente para a mais antiga, com o fechamento que o rollup calculou e se a
 * condensação foi pedida, feita ou nem cabe.
 */
import { api } from "./api.js";
import { escapeHtml } from "./dom.js";
import { icone } from "./icones.js";
import { apresentarStatus, apresentarTipo, corDoTipo, tomDoStatus } from "./ontologia_ui.js";

const TEXTO_DA_CONDENSACAO = {
  feita: { rotulo: "condensada", tom: "ok", icone: "circle-check" },
  pendente: { rotulo: "condensação pendente", tom: "espera", icone: "clock" },
  nenhuma: { rotulo: "sem condensação", tom: "neutro", icone: "circle" },
};

export class MemoriaView {
  constructor(raiz, { state, indice, acoes }) {
    this.raiz = raiz;
    this.state = state;
    this.indice = indice;
    this.acoes = acoes;
    this.dados = null;
    this.carregado = false;
    this.pedido = 0;
    this.secoesFechadas = new Set();
    this.raiz.addEventListener("click", (evento) => this.aoClicar(evento));
    this.raiz.addEventListener("contextmenu", (evento) => this.aoMenu(evento));
    this.raiz.addEventListener("toggle", (evento) => this.aoAlternarSecao(evento), true);
    this.raiz.addEventListener("mouseover", (evento) => this.aoPairar(evento));
    this.raiz.addEventListener("mouseleave", () => this.acoes.destacar(null));
    this.raiz.innerHTML = this.montarVazio("Lendo a memória do ramo…");
  }

  /** O grafo mudou: da próxima vez que o painel aparecer, ele relê. */
  invalidar() {
    this.carregado = false;
  }

  /** Chamado quando o painel aparece ou quando o grafo muda com ele visível. */
  async atualizar({ forcar = false } = {}) {
    if (this.carregado && !forcar) return;
    const pedido = ++this.pedido;
    if (!this.dados) this.raiz.innerHTML = this.montarVazio("Lendo a memória do ramo…");
    const resposta = await api.memoria(this.state.currentBranch);
    if (pedido !== this.pedido) return;
    if (!resposta.sucesso) {
      this.raiz.innerHTML = this.montarVazio(resposta.mensagem || "Não foi possível ler a memória.");
      return;
    }
    this.dados = resposta;
    this.carregado = true;
    this.render();
  }

  render() {
    const aprendizados = this.dados?.aprendizados || [];
    const sessoes = this.dados?.sessoes || [];
    const promovidos = aprendizados.filter((item) => item.promovido).map((item) => this.montarAprendizado(item));
    const locais = aprendizados.filter((item) => !item.promovido).map((item) => this.montarAprendizado(item));
    this.raiz.innerHTML = `
      <div class="nav-botoes">
        <button class="clicavel-icone" data-acao-memoria="registrar" title="Registrar aprendizado a partir do nó selecionado">${icone("lightbulb", { tamanho: 16 })}</button>
        <button class="clicavel-icone" data-acao-memoria="recarregar" title="Reler a memória">${icone("refresh", { tamanho: 16 })}</button>
      </div>
      <div class="memoria">
        ${this.montarSecao("promovidos", "Aprendizados promovidos", promovidos, "Nenhum aprendizado promovido. Promover é o que faz um aprendizado chegar à vista das outras tarefas.")}
        ${this.montarSecao("locais", "Aprendizados sem promoção", locais, "Nenhum aprendizado registrado neste ramo. Registre um pelo botão direito numa Decision, Evidence, Note, Artifact ou Task.")}
        ${this.montarSecao("sessoes", "Sessões", sessoes.map((sessao) => this.montarSessao(sessao)), "Nenhuma sessão neste ramo. O hook do harness abre uma a cada sessão do ambiente, no Setor Memoria do repositório.")}
      </div>`;
  }

  montarSecao(chave, titulo, itens, vazio) {
    const aberta = !this.secoesFechadas.has(chave);
    return `
      <details class="secao" data-secao="${chave}" ${aberta ? "open" : ""}>
        <summary class="secao-titulo">${icone("chevron-right", { tamanho: 14, classe: "secao-seta" })}<span>${escapeHtml(titulo)}</span><span class="contador">${itens.length}</span></summary>
        <div class="secao-corpo">${itens.join("") || `<div class="secao-vazia">${escapeHtml(vazio)}</div>`}</div>
      </details>`;
  }

  montarAprendizado(item) {
    const viajando = this.state.isTimeTraveling;
    const alcances = item.alcances.map((alcance) => this.montarAlcance(alcance));
    const origens = item.origens.map((origem) => this.montarCitacao(origem));
    const marcas = [
      item.substituto ? `<span class="memoria-marca mod-alerta">${icone("alert-triangle", { tamanho: 11 })}substituído por ${this.montarLink(item.substituto)}</span>` : "",
      ...item.contradicoes.map((origem) => `<span class="memoria-marca mod-aviso">${icone("flask", { tamanho: 11 })}contradito por ${this.montarLink(origem.id, origem.rotulo)}</span>`),
      item.valido_ate ? `<span class="memoria-marca">${icone("clock", { tamanho: 11 })}válido até ${escapeHtml(item.valido_ate)}</span>` : "",
    ];
    const dica = `${item.id} · log #${item.seq_criacao} · ${item.autor} (${item.papel})`;
    return `
      <div class="memoria-item ${item.vigente ? "" : "is-substituido"}" data-ir="${escapeHtml(item.id)}" data-tipo="Aprendizado" title="${escapeHtml(dica)}">
        <div class="memoria-item-topo">
          <span class="arvore-icone" style="color:${corDoTipo("Aprendizado")}">${icone("lightbulb", { tamanho: 14 })}</span>
          <span class="memoria-afirmacao">${escapeHtml(item.afirmacao)}</span>
          ${viajando ? "" : `<button class="arvore-acao" data-promover="${escapeHtml(item.id)}" title="Promover…">${icone("zap", { tamanho: 13 })}</button>`}
        </div>
        ${item.como_aplicar ? `<div class="memoria-corpo">${icone("corner-down-right", { tamanho: 11 })}<span>${escapeHtml(item.como_aplicar)}</span></div>` : ""}
        <div class="memoria-meta">${[...alcances, ...origens, ...marcas].join("")}</div>
      </div>`;
  }

  montarAlcance(alcance) {
    const global = alcance === "global";
    const rotulo = global ? "vale para tudo" : this.indice.conteineres.get(alcance)?.rotulo || alcance;
    return `<span class="memoria-alcance" title="${global ? "Alcance global" : escapeHtml(alcance)}">${icone(global ? "grafo" : "folder", { tamanho: 11 })}${escapeHtml(rotulo)}</span>`;
  }

  /** A origem, como a nota do acervo a cita: tipo, rótulo e posição no log. */
  montarCitacao(origem) {
    const tipo = apresentarTipo(origem.tipo);
    const dica = `${tipo.nome} · ${origem.id} · log #${origem.seq}`;
    return `<button class="memoria-origem" data-ir="${escapeHtml(origem.id)}" title="${escapeHtml(dica)}" style="--cor-tipo:${corDoTipo(origem.tipo)}">${icone(tipo.icone, { tamanho: 11 })}${escapeHtml(origem.rotulo)}</button>`;
  }

  montarLink(id, rotulo = null) {
    const info = this.state.nodes.get(id) || this.indice.no(id);
    return `<button class="link-no" data-ir="${escapeHtml(id)}">${escapeHtml(rotulo || info?.rotulo || id)}</button>`;
  }

  montarSessao(sessao) {
    const viajando = this.state.isTimeTraveling;
    const encerrada = sessao.status === "concluida";
    const condensacao = TEXTO_DA_CONDENSACAO[sessao.condensacao] || TEXTO_DA_CONDENSACAO.nenhuma;
    const setor = sessao.setor_id ? this.indice.conteineres.get(sessao.setor_id)?.rotulo : null;
    const acao = encerrada
      ? `<button class="arvore-acao" data-reabrir="${escapeHtml(sessao.id)}" title="Reabrir sessão">${icone("folder-open", { tamanho: 13 })}</button>`
      : `<button class="arvore-acao" data-encerrar="${escapeHtml(sessao.id)}" title="Encerrar sessão">${icone("circle-check", { tamanho: 13 })}</button>`;
    const dica = `${sessao.id}${setor ? ` · ${setor}` : ""} · log #${sessao.seq_criacao}`;
    return `
      <div class="memoria-item memoria-sessao" data-ir="${escapeHtml(sessao.id)}" data-tipo="Sessao" title="${escapeHtml(dica)}">
        <div class="memoria-item-topo">
          <span class="arvore-icone" style="color:${corDoTipo("Sessao")}">${icone("folder-clock", { tamanho: 14 })}</span>
          <span class="memoria-afirmacao">${escapeHtml(sessao.rotulo || sessao.id)}</span>
          <span class="sinal mod-${tomDoStatus(sessao.status)}" title="${escapeHtml(apresentarStatus(sessao.status))}">${icone(encerrada ? "circle-check" : "circle-dot", { tamanho: 12 })}</span>
          ${viajando ? "" : acao}
        </div>
        ${sessao.resumo ? `<div class="memoria-corpo"><span>${escapeHtml(sessao.resumo)}</span></div>` : ""}
        ${sessao.fechamento.map((linha) => `<div class="memoria-fechamento">${escapeHtml(linha)}</div>`).join("")}
        <div class="memoria-meta">
          <span class="memoria-marca mod-${condensacao.tom}">${icone(condensacao.icone, { tamanho: 11 })}${condensacao.rotulo}</span>
          ${sessao.id_condensacao ? this.montarLink(sessao.id_condensacao, "ler a condensação") : ""}
        </div>
      </div>`;
  }

  montarVazio(texto) {
    return `<div class="painel-vazio">${icone("lightbulb", { tamanho: 22 })}<span>${escapeHtml(texto)}</span></div>`;
  }

  // ------------------------------------------------------------------ eventos

  aoClicar(evento) {
    const botao = evento.target.closest("[data-acao-memoria], [data-promover], [data-encerrar], [data-reabrir]");
    if (botao) {
      this.executarBotao(botao);
      return;
    }
    const item = evento.target.closest("[data-ir]");
    if (!item) return;
    const id = item.dataset.ir;
    if (item.dataset.tipo === "Sessao") this.acoes.abrirEscopo(this.indice.escopoDe(id), { novaAba: evento.ctrlKey || evento.metaKey });
    else this.acoes.focarNo(id, this.indice.no(id));
  }

  executarBotao(botao) {
    const { acaoMemoria, promover, encerrar, reabrir } = botao.dataset;
    if (acaoMemoria === "recarregar") this.atualizar({ forcar: true });
    else if (acaoMemoria === "registrar") this.registrarDaSelecao();
    else if (promover) this.acoes.promoverAprendizado(this.aprendizadoComoNo(promover));
    else if (encerrar) this.acoes.mudarPropriedade({ id: encerrar }, "status", "concluida", "Sessão encerrada: a vista dela abre pelo fechamento");
    else if (reabrir) this.acoes.mudarPropriedade({ id: reabrir }, "status", "ativa", "Sessão reaberta");
  }

  registrarDaSelecao() {
    const selecao = this.state.selectedElement;
    const no = selecao?.type === "node" ? this.state.nodes.get(selecao.id) : null;
    this.acoes.registrarAprendizado({ origens: no ? [no.id] : [], sessaoId: no?.sessao_id });
  }

  /** O diálogo de promoção precisa do id e do rótulo; o painel tem os dois mesmo com o nó fora do canvas. */
  aprendizadoComoNo(id) {
    const item = (this.dados?.aprendizados || []).find((candidato) => candidato.id === id);
    return this.state.nodes.get(id) || { id, tipo: "Aprendizado", rotulo: item?.afirmacao || id };
  }

  aoMenu(evento) {
    const item = evento.target.closest("[data-ir]");
    if (!item) return;
    const info = this.state.nodes.get(item.dataset.ir) || this.indice.no(item.dataset.ir);
    if (info) this.acoes.menuDoNo(evento, info);
  }

  aoPairar(evento) {
    const item = evento.target.closest("[data-ir]");
    this.acoes.destacar(item && this.state.nodes.has(item.dataset.ir) ? item.dataset.ir : null);
  }

  aoAlternarSecao(evento) {
    const secao = evento.target.closest?.("[data-secao]");
    if (!secao) return;
    if (secao.open) this.secoesFechadas.delete(secao.dataset.secao);
    else this.secoesFechadas.add(secao.dataset.secao);
  }
}
