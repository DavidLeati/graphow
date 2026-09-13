/**
 * Histórico do log: calendário de atividade, viagem no tempo e os eventos do dia.
 *
 * O log é a verdade do Graphow, e a linha do tempo antiga era uma lista de 3 mil
 * cartões sem data visível, com a viagem no tempo espremida na barra superior —
 * e os botões de passo e de reprodução nem estavam ligados. Aqui o calendário
 * mostra em que dias o grafo andou, o dia escolhido filtra a lista, e cada evento
 * diz em português o que fez. Movimentos de arranjo (posições no canvas) ficam
 * ocultos por padrão: são metade do log e não dizem nada sobre o trabalho.
 */
import { api } from "./api.js";
import { debounce, escapeHtml, gravarPreferencia, lerPreferencia } from "./dom.js";
import { icone } from "./icones.js";

const DIAS_DA_SEMANA = ["DOM", "SEG", "TER", "QUA", "QUI", "SEX", "SÁB"];
const LIMITE_INICIAL_DA_LISTA = 200;
const INTERVALO_DA_REPRODUCAO_MS = 320;
const CHAVES_DE_ARRANJO = new Set(["pos_x", "pos_y", "x", "y"]);

const ICONE_DO_EVENTO = {
  no_criado: "plus",
  no_atualizado: "pencil",
  no_removido: "trash",
  aresta_criada: "link",
  aresta_removida: "x",
  ramo_criado: "git-fork",
  execucao_solicitada: "activity",
  execucao_iniciada: "activity",
  execucao_concluida: "activity",
};

const diaDe = (iso) => {
  const data = new Date(iso);
  return `${data.getFullYear()}-${String(data.getMonth() + 1).padStart(2, "0")}-${String(data.getDate()).padStart(2, "0")}`;
};

export class HistoricoView {
  constructor(raiz, { state, indice, acoes }) {
    this.raiz = raiz;
    this.state = state;
    this.indice = indice;
    this.acoes = acoes;
    this.eventos = [];
    this.porDia = new Map();
    this.diaSelecionado = null;
    this.mesVisivel = null;
    this.limite = LIMITE_INICIAL_DA_LISTA;
    this.filtroPapel = "";
    this.filtroTexto = "";
    this.ocultarArranjo = lerPreferencia("historico_ocultar_arranjo", true);
    this.reproducao = null;
    this.viajarEmBreve = debounce((versao) => this.acoes.viajarPara(versao), 160);
    this.montarEstrutura();
    this.render();
  }

  montarEstrutura() {
    this.raiz.innerHTML = `
      <div class="viagem">
        <div class="viagem-linha">
          <button class="clicavel-icone" data-viagem="-1" title="Voltar um evento">${icone("skip-back", { tamanho: 15 })}</button>
          <button class="clicavel-icone" data-tocar title="Reproduzir o log a partir daqui">${icone("play", { tamanho: 15 })}</button>
          <button class="clicavel-icone" data-viagem="1" title="Avançar um evento">${icone("skip-forward", { tamanho: 15 })}</button>
          <span class="viagem-versao" data-versao></span>
          <button class="botao mod-pequeno mod-cta" data-presente hidden>Voltar ao presente</button>
        </div>
        <input type="range" class="deslizador" data-deslizador min="0" max="0" value="0" step="1" aria-label="Versão do log">
      </div>
      <div class="calendario" data-calendario></div>
      <div class="eventos-filtros">
        <input type="search" class="entrada mod-busca" data-filtro-texto placeholder="Filtrar eventos…">
        <select class="seletor mod-pequeno" data-filtro-papel>
          <option value="">Todos os papéis</option>
          ${["humano", "planejador", "executor", "revisor", "sistema"].map((papel) => `<option value="${papel}">${papel}</option>`).join("")}
        </select>
      </div>
      <label class="alternador-rotulado"><input type="checkbox" data-ocultar-arranjo ${this.ocultarArranjo ? "checked" : ""}><span class="alternador-trilho"></span><span>Ocultar movimentos no canvas</span></label>
      <div class="eventos-cabecalho" data-cabecalho-eventos></div>
      <div class="eventos-lista" data-lista></div>`;
    this.ligarEventos();
  }

  ligarEventos() {
    const $ = (seletor) => this.raiz.querySelector(seletor);
    this.raiz.querySelectorAll("[data-viagem]").forEach((botao) => {
      botao.addEventListener("click", () => this.acoes.viajarPara(this.state.logVersion + Number(botao.dataset.viagem)));
    });
    $("[data-tocar]").addEventListener("click", () => this.alternarReproducao());
    $("[data-presente]").addEventListener("click", () => this.acoes.voltarAoPresente());
    $("[data-deslizador]").addEventListener("input", (evento) => {
      const versao = Number(evento.target.value);
      this.raiz.querySelector("[data-versao]").innerHTML = this.textoDaVersao(versao);
      this.viajarEmBreve(versao);
    });
    $("[data-filtro-texto]").addEventListener("input", debounce((evento) => { this.filtroTexto = evento.target.value.toLowerCase(); this.renderLista(); }, 150));
    $("[data-filtro-papel]").addEventListener("change", (evento) => { this.filtroPapel = evento.target.value; this.renderLista(); });
    $("[data-ocultar-arranjo]").addEventListener("change", (evento) => {
      this.ocultarArranjo = evento.target.checked;
      gravarPreferencia("historico_ocultar_arranjo", this.ocultarArranjo);
      this.renderLista();
    });
    $("[data-calendario]").addEventListener("click", (evento) => this.aoClicarNoCalendario(evento));
    $("[data-lista]").addEventListener("click", (evento) => this.aoClicarNaLista(evento));
    $("[data-cabecalho-eventos]").addEventListener("click", (evento) => this.aoClicarNaLista(evento));
  }

  async carregar() {
    const ramo = this.state.currentBranch;
    const pedido = (this.pedido = (this.pedido || 0) + 1);
    const dados = await api.timeline(ramo, "");
    if (pedido !== this.pedido || ramo !== this.state.currentBranch || dados.sucesso === false) return;
    this.eventos = dados.eventos || [];
    this.porDia = new Map();
    // O log conhece o nome de todo nó que já existiu, inclusive os removidos e
    // os que estão fora do canvas agora; a lista lê os rótulos daqui.
    this.rotulosDoLog = new Map();
    for (const evento of this.eventos) {
      const dia = diaDe(evento.timestamp);
      if (!this.porDia.has(dia)) this.porDia.set(dia, []);
      this.porDia.get(dia).push(evento);
      if (evento.payload?.rotulo && evento.tipo.startsWith("no_")) this.rotulosDoLog.set(evento.payload.id, evento.payload.rotulo);
    }
    const ultimo = this.eventos[this.eventos.length - 1];
    if (!this.mesVisivel) this.mesVisivel = ultimo ? new Date(ultimo.timestamp) : new Date();
    this.render();
  }

  render() {
    this.atualizarViagem();
    this.renderCalendario();
    this.renderLista();
  }

  /** Sincroniza o deslizador e os botões com a versão que o canvas está mostrando. */
  atualizarViagem() {
    const deslizador = this.raiz.querySelector("[data-deslizador]");
    deslizador.max = this.state.maxLogVersion;
    deslizador.value = this.state.logVersion;
    this.raiz.querySelector("[data-versao]").innerHTML = this.textoDaVersao(this.state.logVersion);
    this.raiz.querySelector("[data-presente]").hidden = !this.state.isTimeTraveling;
    this.raiz.classList.toggle("is-viajando", this.state.isTimeTraveling);
    const tocando = Boolean(this.reproducao);
    const botao = this.raiz.querySelector("[data-tocar]");
    botao.innerHTML = icone(tocando ? "pause" : "play", { tamanho: 15 });
    botao.title = tocando ? "Pausar a reprodução" : "Reproduzir o log a partir daqui";
  }

  textoDaVersao(versao) {
    return `#${versao} <span class="texto-fraco">de #${this.state.maxLogVersion}</span>`;
  }

  alternarReproducao() {
    if (this.reproducao) {
      this.pararReproducao();
      return;
    }
    if (!this.state.isTimeTraveling) this.acoes.viajarPara(Math.max(0, this.state.maxLogVersion - 50));
    this.reproducao = setInterval(() => {
      if (!this.state.isTimeTraveling) {
        this.pararReproducao();
        return;
      }
      this.acoes.viajarPara(this.state.logVersion + 1);
    }, INTERVALO_DA_REPRODUCAO_MS);
    this.atualizarViagem();
  }

  pararReproducao() {
    clearInterval(this.reproducao);
    this.reproducao = null;
    this.atualizarViagem();
  }

  // ---------------------------------------------------------------- calendário

  renderCalendario() {
    const mes = this.mesVisivel || new Date();
    const ano = mes.getFullYear();
    const indiceMes = mes.getMonth();
    const primeiro = new Date(ano, indiceMes, 1);
    const inicio = new Date(ano, indiceMes, 1 - primeiro.getDay());
    const hoje = diaDe(new Date().toISOString());
    const celulas = [];
    for (let deslocamento = 0; deslocamento < 42; deslocamento++) {
      const data = new Date(inicio.getFullYear(), inicio.getMonth(), inicio.getDate() + deslocamento);
      celulas.push(this.montarDia(data, indiceMes, hoje));
    }
    const nomeDoMes = primeiro.toLocaleDateString("pt-BR", { month: "long" });
    this.raiz.querySelector("[data-calendario]").innerHTML = `
      <div class="calendario-topo">
        <span class="calendario-mes"><strong>${escapeHtml(nomeDoMes)}</strong> <span class="texto-fraco">${ano}</span></span>
        <span class="espacador"></span>
        <button class="clicavel-icone" data-mes="-1" title="Mês anterior">${icone("chevron-left", { tamanho: 15 })}</button>
        <button class="botao-texto" data-mes="0">HOJE</button>
        <button class="clicavel-icone" data-mes="1" title="Próximo mês">${icone("chevron-right", { tamanho: 15 })}</button>
      </div>
      <div class="calendario-grade">
        ${DIAS_DA_SEMANA.map((dia) => `<span class="calendario-semana">${dia}</span>`).join("")}
        ${celulas.join("")}
      </div>`;
  }

  montarDia(data, indiceMes, hoje) {
    const chave = diaDe(data.toISOString());
    const eventos = this.porDia.get(chave)?.length || 0;
    const pontos = eventos === 0 ? 0 : Math.min(3, String(eventos).length);
    const classes = [
      "calendario-dia",
      data.getMonth() !== indiceMes ? "mod-fora" : "",
      chave === hoje ? "mod-hoje" : "",
      chave === this.diaSelecionado ? "is-selecionado" : "",
      eventos ? "mod-ativo" : "",
    ];
    const titulo = eventos ? `${eventos} evento(s) no log` : "Sem eventos";
    return `
      <button class="${classes.join(" ")}" data-dia="${chave}" title="${titulo}">
        <span>${data.getDate()}</span>
        <span class="calendario-pontos">${"<i></i>".repeat(pontos)}</span>
      </button>`;
  }

  aoClicarNoCalendario(evento) {
    const botaoMes = evento.target.closest("[data-mes]");
    if (botaoMes) {
      const passo = Number(botaoMes.dataset.mes);
      const base = this.mesVisivel || new Date();
      this.mesVisivel = passo === 0 ? new Date() : new Date(base.getFullYear(), base.getMonth() + passo, 1);
      this.renderCalendario();
      return;
    }
    const dia = evento.target.closest("[data-dia]");
    if (!dia) return;
    this.diaSelecionado = this.diaSelecionado === dia.dataset.dia ? null : dia.dataset.dia;
    this.limite = LIMITE_INICIAL_DA_LISTA;
    this.renderCalendario();
    this.renderLista();
  }

  // ---------------------------------------------------------------- lista

  eventosFiltrados() {
    const base = this.diaSelecionado ? this.porDia.get(this.diaSelecionado) || [] : this.eventos;
    return base.filter((evento) => {
      if (this.filtroPapel && evento.papel !== this.filtroPapel) return false;
      if (this.ocultarArranjo && this.ehMovimentoDeArranjo(evento)) return false;
      if (!this.filtroTexto) return true;
      return `${evento.seq} ${evento.tipo} ${evento.autor} ${JSON.stringify(evento.payload)}`.toLowerCase().includes(this.filtroTexto);
    });
  }

  ehMovimentoDeArranjo(evento) {
    if (evento.tipo !== "no_atualizado" || evento.payload?.rotulo) return false;
    const chaves = Object.keys(evento.payload?.propriedades || {});
    return chaves.length > 0 && chaves.every((chave) => CHAVES_DE_ARRANJO.has(chave));
  }

  renderLista() {
    const filtrados = this.eventosFiltrados();
    const visiveis = filtrados.slice(-this.limite).reverse();
    const ultimoDoDia = this.diaSelecionado ? this.porDia.get(this.diaSelecionado)?.at(-1) : null;
    const rotuloDoDia = this.diaSelecionado
      ? new Date(`${this.diaSelecionado}T12:00:00`).toLocaleDateString("pt-BR", { day: "2-digit", month: "short", year: "numeric" })
      : "Todos os dias";
    this.raiz.querySelector("[data-cabecalho-eventos]").innerHTML = `
      <span><strong>${escapeHtml(rotuloDoDia)}</strong> <span class="texto-fraco">· ${filtrados.length} eventos</span></span>
      ${ultimoDoDia ? `<button class="link-acao" data-replay="${ultimoDoDia.seq}" title="Ver o grafo como estava no fim deste dia">${icone("history", { tamanho: 13 })} Fim do dia</button>` : ""}`;
    const linhas = visiveis.map((evento) => this.montarEvento(evento)).join("");
    const mais = filtrados.length > visiveis.length ? `<button class="botao mod-largo mod-pequeno" data-mais>Mostrar mais ${Math.min(LIMITE_INICIAL_DA_LISTA, filtrados.length - visiveis.length)}</button>` : "";
    this.raiz.querySelector("[data-lista]").innerHTML = linhas + mais || '<div class="secao-vazia">Nenhum evento com esses filtros.</div>';
  }

  montarEvento(evento) {
    const hora = new Date(evento.timestamp).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
    const atual = this.state.isTimeTraveling && evento.seq === this.state.logVersion;
    const alvo = evento.payload?.id && !evento.tipo.startsWith("aresta") ? evento.payload.id : evento.payload?.origem_id;
    return `
      <div class="evento ${atual ? "is-atual" : ""}" data-alvo="${escapeHtml(alvo || "")}">
        <span class="evento-icone mod-${escapeHtml(evento.tipo)}">${icone(ICONE_DO_EVENTO[evento.tipo] || "git-commit", { tamanho: 13 })}</span>
        <div class="evento-corpo">
          <div class="evento-texto">${this.descrever(evento)}</div>
          <div class="evento-meta">#${evento.seq} · ${hora} · ${escapeHtml(evento.autor)} <span class="texto-fraco">(${escapeHtml(evento.papel)})</span></div>
        </div>
        <button class="clicavel-icone evento-replay" data-replay="${evento.seq}" title="Ver o grafo como estava neste evento">${icone("history", { tamanho: 14 })}</button>
      </div>`;
  }

  rotuloDe(id) {
    const rotulo = this.state.nodes.get(id)?.rotulo || this.indice.info.get(id)?.rotulo || this.rotulosDoLog?.get(id);
    return `<span class="evento-no" title="${escapeHtml(id)}">${escapeHtml(rotulo || id)}</span>`;
  }

  /** Frase curta do que o evento fez, com o nome do nó quando ele é conhecido. */
  descrever(evento) {
    const p = evento.payload || {};
    const descricoes = {
      no_criado: () => `criou ${escapeHtml(p.tipo || "nó")} <span class="evento-no" title="${escapeHtml(p.id)}">${escapeHtml(p.rotulo || p.id)}</span>`,
      no_removido: () => `removeu ${this.rotuloDe(p.id)}`,
      aresta_criada: () => `ligou ${this.rotuloDe(p.origem_id)} <span class="evento-aresta">${escapeHtml(p.tipo)}</span> ${this.rotuloDe(p.destino_id)}`,
      aresta_removida: () => `removeu a aresta <code>${escapeHtml(p.id)}</code>`,
      ramo_criado: () => `criou o ramo <code>${escapeHtml(p.novo_ramo_id || p.id || "")}</code>`,
    };
    if (descricoes[evento.tipo]) return descricoes[evento.tipo]();
    if (evento.tipo === "no_atualizado") return this.descreverAtualizacao(p);
    return escapeHtml(evento.tipo.replace(/_/g, " "));
  }

  descreverAtualizacao(p) {
    if (p.rotulo) return `renomeou para <span class="evento-no" title="${escapeHtml(p.id)}">${escapeHtml(p.rotulo)}</span>`;
    const chaves = Object.keys(p.propriedades || {});
    if (chaves.length && chaves.every((chave) => CHAVES_DE_ARRANJO.has(chave))) return `moveu ${this.rotuloDe(p.id)} no canvas`;
    const status = p.propriedades?.status;
    if (status) return `mudou o status de ${this.rotuloDe(p.id)} para <strong>${escapeHtml(String(status).replace(/_/g, " "))}</strong>`;
    return `alterou <code>${escapeHtml(chaves.join(", ") || "propriedades")}</code> em ${this.rotuloDe(p.id)}`;
  }

  aoClicarNaLista(evento) {
    const replay = evento.target.closest("[data-replay]");
    if (replay) {
      this.acoes.viajarPara(Number(replay.dataset.replay));
      return;
    }
    if (evento.target.closest("[data-mais]")) {
      this.limite += LIMITE_INICIAL_DA_LISTA;
      this.renderLista();
      return;
    }
    const linha = evento.target.closest("[data-alvo]");
    if (linha?.dataset.alvo) this.acoes.focarNo(linha.dataset.alvo, this.indice.info.get(linha.dataset.alvo));
  }
}
