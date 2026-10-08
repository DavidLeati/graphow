/**
 * Configurações, aberta como aba no centro: a governança global e a de cada projeto.
 *
 * Três cartões de preset (mais "Herdar do global" no projeto), a tabela dos
 * gestos, as propriedades operacionais do projeto e a auditoria do árbitro.
 * A tela só lê e escreve pela API: o catálogo dos gestos e dos valores vem do
 * servidor, e a escrita sai com a identidade do servidor, sempre a do humano.
 * Escolher um cartão ou mudar um gesto grava na hora; a operação grava pelo botão.
 */
import { api } from "./api.js";
import { escapeHtml, gravarPreferencia, lerPreferencia } from "./dom.js";
import { icone } from "./icones.js";
import { avisar } from "./modais.js";
import {
  camposDaOperacao, corpoDoGesto, corpoDoPreset, ESCOPO_GLOBAL, linhasDaTabela, mensagemDeRecusa, operacaoDoFormulario, pedeNumero, valorDoCampoNumerico, valorDoCatalogo,
  PRESET_HERDAR,
} from "./configuracoes_modelo.js";
import {
  htmlDaAuditoria, htmlDaNotaDaTabela, htmlDaOperacao, htmlDaTabela, htmlDoSeletorDeEscopo, htmlDosCartoes,
} from "./configuracoes_html.js";

const LIMITE_DA_AUDITORIA = 30;
const PREFERENCIA_DO_ESCOPO = "configuracoes_escopo";

/** A foto do que a tela mostra, sem o número do log: só muda quando algo visível muda. */
function fotografar(partes) {
  return JSON.stringify(partes, (chave, valor) => (chave === "versao_log" ? undefined : valor));
}

export class ConfiguracoesView {
  constructor(raiz, { state, indice, acoes }) {
    this.raiz = raiz;
    this.state = state;
    this.indice = indice;
    this.acoes = acoes;
    this.escopo = lerPreferencia(PREFERENCIA_DO_ESCOPO, ESCOPO_GLOBAL);
    this.global = null;
    this.projeto = null;
    this.auditoria = null;
    this.erro = null;
    this.rascunho = {};
    this.gravando = false;
    this.pendente = false;
    this.pedido = 0;
    this.foto = "";
    this.montar();
    this.ligarEventos();
    indice.aoMudar(() => this.renderEscopo());
  }

  get ehProjeto() {
    return this.escopo !== ESCOPO_GLOBAL;
  }

  montar() {
    this.raiz.innerHTML = `
      <div class="ferramenta mod-configuracoes">
        <div class="ferramenta-cabecalho">
          <h2>${icone("settings", { tamanho: 18 })} Configurações</h2>
          <p class="texto-fraco">Quem decide cada gesto: o humano ou o árbitro. A configuração global vale para todo projeto; cada projeto pode herdá-la ou sobrescrevê-la.</p>
        </div>
        <div class="ferramenta-controles">
          <label class="campo-compacto"><span>Escopo</span><select class="seletor" data-escopo></select></label>
          <span class="cfg-escopo-nota texto-fraco" data-escopo-nota></span>
        </div>
        <div data-corpo></div>
      </div>`;
    this.seletor = this.raiz.querySelector("[data-escopo]");
    this.corpo = this.raiz.querySelector("[data-corpo]");
    this.nota = this.raiz.querySelector("[data-escopo-nota]");
    this.renderEscopo();
  }

  ligarEventos() {
    this.seletor.addEventListener("change", () => this.trocarEscopo(this.seletor.value));
    this.raiz.addEventListener("click", (evento) => this.aoClicar(evento));
    this.raiz.addEventListener("change", (evento) => this.aoMudar(evento));
    this.raiz.addEventListener("input", (evento) => {
      const campo = evento.target.closest("[data-campo-operacao]");
      if (campo) this.rascunho[campo.dataset.campoOperacao] = campo.value;
    });
    this.raiz.addEventListener("submit", (evento) => {
      evento.preventDefault();
      if (!evento.target.matches("[data-operacao]")) return;
      // Sair do campo antes de gravar deixa a releitura que vem depois redesenhar a tela.
      document.activeElement?.blur?.();
      this.gravarOperacao();
    });
    // A releitura que o tempo real pede espera a saída do formulário: ela apagaria o cursor.
    this.raiz.addEventListener("focusout", () => {
      if (!this.pendente) return;
      setTimeout(() => { if (!this.editandoOperacao()) this.render(); });
    });
  }

  aoClicar(evento) {
    const cartao = evento.target.closest("[data-preset]");
    if (cartao && cartao.getAttribute("aria-checked") !== "true") this.gravar(corpoDoPreset(cartao.dataset.preset), "Preset");
    const alvo = evento.target.closest("[data-ir]");
    if (alvo) this.acoes.mostrarNoCanvas(alvo.dataset.ir, this.indice.no(alvo.dataset.ir));
  }

  aoMudar(evento) {
    const gesto = evento.target.closest("[data-gesto]");
    if (!gesto) return;
    const catalogado = this.catalogo?.gestos?.find((item) => item.gesto === gesto.dataset.gesto);
    const valor = pedeNumero(catalogado) ? valorDoCampoNumerico(catalogado, gesto.value, this.ehProjeto) : gesto.value === PRESET_HERDAR ? PRESET_HERDAR : valorDoCatalogo(catalogado?.valores, gesto.value);
    if (valor === undefined) return this.render();
    this.gravar(corpoDoGesto(gesto.dataset.gesto, valor), "Gesto");
  }

  get catalogo() {
    return this.global?.catalogo;
  }

  /** Abre a aba: relê tudo, porque outro autor pode ter mexido na política desde a última visita. */
  abrir() {
    return this.atualizar();
  }

  trocarEscopo(escopo) {
    this.escopo = escopo;
    this.projeto = null;
    this.rascunho = {};
    this.foto = "";
    gravarPreferencia(PREFERENCIA_DO_ESCOPO, escopo);
    this.render();
    return this.atualizar();
  }

  /** Relê a política global, a do projeto e a auditoria. A resposta de um pedido velho é descartada. */
  async atualizar() {
    this.garantirEscopoExistente();
    const pedido = ++this.pedido;
    const ramo = this.state.currentBranch;
    const [global, projeto, auditoria] = await Promise.all([
      api.governanca(ramo),
      this.ehProjeto ? api.governancaDoProjeto(this.escopo, ramo) : Promise.resolve(null),
      api.auditoriaDoArbitro(ramo, LIMITE_DA_AUDITORIA),
    ]);
    if (pedido !== this.pedido) return;
    this.erro = [global, projeto].find((resposta) => resposta && resposta.sucesso === false)?.mensagem || null;
    if (global.sucesso !== false) this.global = global;
    this.projeto = projeto && projeto.sucesso !== false ? projeto : null;
    this.auditoria = auditoria;
    const foto = fotografar([this.global, this.projeto, this.auditoria, this.erro, this.escopo]);
    if (foto === this.foto) return;
    this.foto = foto;
    this.render();
  }

  /** O projeto que sumiu do índice (excluído) devolve a tela ao escopo global em vez de a deixar num erro. */
  garantirEscopoExistente() {
    const conhecidos = this.indice.listar("Projeto");
    if (!this.ehProjeto || conhecidos.length === 0 || conhecidos.some((projeto) => projeto.id === this.escopo)) return;
    this.escopo = ESCOPO_GLOBAL;
    this.projeto = null;
    gravarPreferencia(PREFERENCIA_DO_ESCOPO, this.escopo);
  }

  editandoOperacao() {
    const ativo = document.activeElement;
    return Boolean(ativo?.matches?.("[data-campo-operacao]")) && this.raiz.contains(ativo);
  }

  renderEscopo() {
    const projetos = this.indice.listar("Projeto").sort((a, b) => a.rotulo.localeCompare(b.rotulo));
    this.seletor.innerHTML = htmlDoSeletorDeEscopo(projetos, this.escopo);
    const atual = projetos.find((projeto) => projeto.id === this.escopo);
    this.nota.textContent = this.ehProjeto ? atual?.caminho || "" : "Vale para todo projeto que não a sobrescreve.";
  }

  render() {
    if (this.editandoOperacao()) {
      this.pendente = true;
      return;
    }
    this.pendente = false;
    this.renderEscopo();
    this.corpo.innerHTML = this.erro && !this.global ? this.htmlDoErro() : this.htmlDoCorpo();
  }

  htmlDoErro() {
    return `<div class="chamada mod-alerta">${icone("alert-triangle", { tamanho: 14 })}<span>${escapeHtml(this.erro)}</span></div>`;
  }

  htmlDoCorpo() {
    if (!this.global) return `<div class="painel-vazio"><span>Lendo a configuração…</span></div>`;
    const dados = this.ehProjeto ? this.projeto : this.global;
    if (!dados) return this.erro ? this.htmlDoErro() : `<div class="painel-vazio"><span>Lendo a configuração…</span></div>`;
    const contexto = { catalogo: this.catalogo, dados, global: this.global, ehProjeto: this.ehProjeto, gravando: this.gravando };
    const linhas = linhasDaTabela(this.catalogo, dados, this.ehProjeto);
    return `
      ${this.erro ? this.htmlDoErro() : ""}
      <section class="cfg-secao">
        <h3 class="cfg-titulo">${icone("shield", { tamanho: 15 })} Governança</h3>
        ${htmlDosCartoes(contexto)}
      </section>
      <section class="cfg-secao">
        <h3 class="cfg-titulo">${icone("list", { tamanho: 15 })} Gestos</h3>
        ${htmlDaNotaDaTabela(contexto)}
        ${htmlDaTabela(linhas, this.gravando)}
      </section>
      ${this.ehProjeto ? this.htmlDaSecaoDeOperacao(dados) : ""}
      <section class="cfg-secao">
        <h3 class="cfg-titulo">${icone("bot", { tamanho: 15 })} Auditoria do árbitro</h3>
        ${htmlDaAuditoria(this.auditoria)}
      </section>`;
  }

  htmlDaSecaoDeOperacao(dados) {
    const valores = { ...camposDaOperacao(dados.operacao), ...this.rascunho };
    return `
      <section class="cfg-secao">
        <h3 class="cfg-titulo">${icone("workflow", { tamanho: 15 })} Operação do projeto</h3>
        <p class="texto-fraco cfg-secao-texto">Como a orquestração trata este projeto. Vale só aqui, e não depende do preset.</p>
        ${htmlDaOperacao(this.catalogo, valores, this.gravando)}
      </section>`;
  }

  async gravarOperacao() {
    const campos = { ...camposDaOperacao(this.projeto?.operacao), ...this.rascunho };
    const { corpo, erro } = operacaoDoFormulario(campos);
    if (erro) {
      avisar(erro, "erro");
      return;
    }
    if (await this.gravar(corpo, "Operação")) this.rascunho = {};
    this.render();
  }

  /** Grava no escopo aberto e relê: o que a tela mostra depois é o que o servidor confirmou. */
  async gravar(corpo, rotulo) {
    if (this.gravando) return false;
    this.gravando = true;
    this.render();
    const payload = { ...corpo, ramo_id: this.state.currentBranch };
    const recibo = this.ehProjeto
      ? await api.gravarGovernancaDoProjeto(this.escopo, payload)
      : await api.gravarGovernancaGlobal(payload);
    this.gravando = false;
    const gravou = recibo.sucesso !== false;
    avisar(gravou ? `${rotulo} gravado.` : `Não foi possível gravar: ${mensagemDeRecusa(recibo)}`, gravou ? "sucesso" : "erro");
    this.foto = "";
    await this.atualizar();
    return gravou;
  }
}
