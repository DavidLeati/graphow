/**
 * Quadro: a vista paralela ao canvas, para fluxos grandes demais de ler como grafo.
 *
 * As tarefas ficam em raias — por objetivo, sessão ou setor — e colunas por
 * status; um minimapa à esquerda mostra todos os nós do escopo agrupados pela
 * mesma raia. É
 * a mesma fonte do canvas — o escopo e o recorte da aba — e a mesma seleção: o
 * que se escolhe aqui aparece nos painéis da direita, e o painel de impacto diz
 * o que afeta o nó e o que ele afeta.
 *
 * A tela é deliberadamente calma. Cada cartão diz só o que trava a tarefa (quantas
 * perguntas abertas, quantos pré-requisitos, quantas esperam por ela); o resto do
 * contexto está a um clique, no painel. As dependências só aparecem desenhadas
 * enquanto o mouse está sobre um cartão.
 */
import { escapeHtml, gravarPreferencia, lerPreferencia } from "./dom.js";
import { icone } from "./icones.js";
import { lerFluxo, ORDEM_DAS_COLUNAS } from "./leitura_de_fluxo.js";
import { apresentarStatus, apresentarTipo, corDoTipo, tomDoStatus } from "./ontologia_ui.js";

const ROTULO_DA_COLUNA = {
  pendente: "Pendente",
  em_andamento: "Em andamento",
  pronto_para_revisao: "Pronto p/ revisão",
  bloqueado: "Bloqueado",
  concluido: "Concluído",
};
const MODOS_DE_RAIA = { objetivo: "Objetivo", sessao: "Sessão", setor: "Setor" };
const RAIA_SEM_CHAVE = { objetivo: "Sem objetivo nem sessão", sessao: "Sem sessão", setor: "Sem setor" };
const ROTULO_DO_GRUPO = { "#solto": "Sem objetivo", "#estrutura": "Estrutura e execução", "#memoria": "Memória" };
const FILTROS = {
  abertas: { rotulo: "Perguntas abertas", tom: "espera" },
  bloqueadas: { rotulo: "Tarefas bloqueadas", tom: "alerta" },
};
const COR_DE_QUEM_AFETA = "#7fb2ff";
const COR_DE_QUEM_E_AFETADO = "#34c38f";

export class QuadroView {
  constructor(raiz, { state, indice, acoes }) {
    this.raiz = raiz;
    this.state = state;
    this.indice = indice;
    this.acoes = acoes;
    this.visivel = false;
    this.filtro = null;
    this.ocultarConcluidas = lerPreferencia("quadro_ocultar_concluidas", false);
    const modoSalvo = lerPreferencia("quadro_raias", "objetivo");
    this.modoDeRaia = MODOS_DE_RAIA[modoSalvo] ? modoSalvo : "objetivo";
    this.raiasRecolhidas = new Set();
    this.pairado = null;
    this.raiz.addEventListener("click", (evento) => this.aoClicar(evento));
    this.raiz.addEventListener("dblclick", (evento) => {
      if (evento.target.closest("[data-ir]")) this.acoes.mostrarPainel("propriedades");
    });
    this.raiz.addEventListener("contextmenu", (evento) => {
      const alvo = evento.target.closest("[data-ir]");
      const no = alvo && this.state.nodes.get(alvo.dataset.ir);
      if (!no) return;
      evento.preventDefault();
      this.acoes.menuDoNo(evento, no);
    });
    this.raiz.addEventListener("mouseover", (evento) => {
      const id = evento.target.closest("[data-pairar]")?.dataset.pairar || null;
      if (id !== this.pairado) this.pairar(id);
    });
    this.raiz.addEventListener("mouseleave", () => this.pairar(null));
  }

  mostrar(visivel) {
    this.visivel = visivel;
    this.raiz.hidden = !visivel;
    if (visivel) this.render();
  }

  get selecionado() {
    const selecao = this.state.selectedElement;
    return selecao?.type === "node" ? selecao.id : null;
  }

  render() {
    if (!this.visivel) return;
    const rolagens = [...this.raiz.querySelectorAll("[data-rolagem]")].map((el) => [el.dataset.rolagem, el.scrollTop, el.scrollLeft]);
    this.fluxo = lerFluxo([...this.state.nodes.values()], [...this.state.edges.values()]);
    this.pairado = null;
    this.raiz.innerHTML = `
      <div class="quadro">
        ${this.montarMinimapa()}
        <div class="quadro-principal">
          ${this.montarBarra()}
          <div class="quadro-rolagem" data-rolagem="quadro">
            <svg class="quadro-ligacoes"></svg>
            ${this.montarGrade()}
          </div>
        </div>
      </div>`;
    for (const [chave, topo, esquerda] of rolagens) {
      const el = this.raiz.querySelector(`[data-rolagem="${chave}"]`);
      if (el) Object.assign(el, { scrollTop: topo, scrollLeft: esquerda });
    }
  }

  /** Leva o nó à vista: o cartão da tarefa que ele cerca, e o quadrado dele no minimapa. */
  revelar(id) {
    if (!this.visivel || !this.fluxo) return;
    const tarefa = this.fluxo.tarefaDe(id);
    const raia = tarefa && this.fluxo.raias(this.modoDeRaia).find((candidata) => candidata.tarefas.includes(tarefa));
    if (raia && this.raiasRecolhidas.delete(this.chaveDaRaia(raia.chave))) this.render();
    this.raiz.querySelector(`.quadro-cartao[data-ir="${CSS.escape(tarefa || id)}"]`)?.scrollIntoView({ block: "nearest", inline: "nearest" });
    this.raiz.querySelector(`.quadro-ponto[data-ir="${CSS.escape(id)}"]`)?.scrollIntoView({ block: "nearest" });
  }

  chaveDaRaia(chave) {
    return `${this.modoDeRaia}:${chave ?? ""}`;
  }

  /** O nó que nomeia a raia ou o grupo: no canvas, ou no índice quando o escopo não o traz. */
  noDaChave(chave) {
    return (chave && (this.fluxo.porId.get(chave) || this.indice?.no(chave))) || null;
  }

  // ---------------------------------------------------------------- filtros

  casaComFiltro(id) {
    if (!this.filtro) return true;
    const no = this.fluxo.porId.get(id);
    if (this.filtro === "bloqueadas") return no.tipo === "Task" && this.fluxo.status(id) === "bloqueado";
    if (no.tipo === "Question") return this.fluxo.status(id) === "aberta";
    return no.tipo === "Task" && this.fluxo.perguntasAbertas(id).length > 0;
  }

  contarFiltro(filtro) {
    const [tipo, status] = filtro === "abertas" ? ["Question", "aberta"] : ["Task", "bloqueado"];
    let total = 0;
    for (const [id, no] of this.fluxo.porId) if (no.tipo === tipo && this.fluxo.status(id) === status) total += 1;
    return total;
  }

  montarBarra() {
    const filtros = Object.entries(FILTROS)
      .map(([chave, filtro]) => `
        <button class="quadro-filtro ${this.filtro === chave ? "is-ativo" : ""}" data-filtro="${chave}">
          <span class="quadro-tom tom-${filtro.tom}"></span>${filtro.rotulo}<span class="contador">${this.contarFiltro(chave)}</span>
        </button>`)
      .join("");
    const modos = Object.entries(MODOS_DE_RAIA)
      .map(([modo, rotulo]) => `<button class="${this.modoDeRaia === modo ? "is-ativo" : ""}" data-modo-raia="${modo}">${rotulo}</button>`)
      .join("");
    return `
      <div class="quadro-barra">
        <span class="quadro-barra-rotulo">Raias</span><span class="quadro-segmentos">${modos}</span>
        <span class="quadro-barra-separador"></span>
        ${filtros}
        <button class="quadro-filtro" data-concluidas title="Mostrar ou ocultar a coluna de concluídas">
          ${icone(this.ocultarConcluidas ? "eye-off" : "eye", { tamanho: 13 })}Concluídas
        </button>
        <span class="espacador"></span>
        <span class="texto-fraco">Passe o mouse num cartão para ver as dependências</span>
      </div>`;
  }

  // ---------------------------------------------------------------- minimapa

  montarMinimapa() {
    const selecionado = this.selecionado;
    const vizinhos = new Set();
    if (selecionado && this.fluxo.porId.has(selecionado)) {
      const { montante, jusante } = this.fluxo.vizinhos(selecionado);
      [...montante, ...jusante].forEach((vizinho) => vizinhos.add(vizinho.id));
    }
    const grupos = this.fluxo
      .grupos(this.modoDeRaia)
      .map((grupo) => {
        const nomeador = grupo.chave.startsWith("#") ? null : this.noDaChave(grupo.chave);
        const clicavel = nomeador && this.fluxo.porId.has(grupo.chave) ? nomeador : null;
        const titulo = nomeador?.rotulo || ROTULO_DO_GRUPO[grupo.chave] || grupo.chave;
        const pontos = grupo.nos
          .map((id) => {
            const no = this.fluxo.porId.get(id);
            const status = this.fluxo.status(id);
            const classes = [
              "quadro-ponto",
              status ? `st-${status}` : "",
              id === selecionado ? "is-selecionado" : "",
              vizinhos.has(id) ? "is-vizinho" : "",
              this.casaComFiltro(id) ? "" : "is-apagado",
            ];
            const dica = `${apresentarTipo(no.tipo).nome} · ${no.rotulo}${status ? ` · ${apresentarStatus(status)}` : ""}`;
            return `<span class="${classes.join(" ")}" style="--cor-tipo:${corDoTipo(no.tipo)}" data-ir="${escapeHtml(id)}" data-pairar="${escapeHtml(id)}" title="${escapeHtml(dica)}"></span>`;
          })
          .join("");
        const cabecalho = clicavel
          ? `<button class="quadro-minimapa-titulo" data-ir="${escapeHtml(clicavel.id)}" title="${escapeHtml(titulo)}">${escapeHtml(titulo)}</button>`
          : `<span class="quadro-minimapa-titulo">${escapeHtml(titulo)}</span>`;
        return `<div class="quadro-minimapa-grupo">${cabecalho}<div class="quadro-pontos">${pontos}</div></div>`;
      })
      .join("");
    return `<aside class="quadro-minimapa ${selecionado ? "tem-selecao" : ""}" data-rolagem="minimapa" aria-label="Todos os nós do escopo, por objetivo">${grupos}</aside>`;
  }

  // ---------------------------------------------------------------- quadro

  /**
   * Só as colunas que têm tarefa no escopo. Num projeto quase todo concluído, três
   * colunas vazias empurravam a de concluídas para fora da tela; os filtros da
   * barra já dizem quando nada está bloqueado.
   */
  colunas() {
    const vistos = new Set();
    for (const [id, no] of this.fluxo.porId) if (no.tipo === "Task") vistos.add(this.fluxo.status(id));
    const extras = [...vistos].filter((status) => !ORDEM_DAS_COLUNAS.includes(status));
    return [...ORDEM_DAS_COLUNAS, ...extras].filter((status) => vistos.has(status) && !(this.ocultarConcluidas && status === "concluido"));
  }

  montarGrade() {
    const raias = this.fluxo.raias(this.modoDeRaia);
    if (raias.length === 0) {
      return `<div class="quadro-vazio">${icone("kanban", { tamanho: 22 })}<span>Nenhuma Task neste escopo.</span><span class="texto-fraco">O quadro organiza tarefas; abra um projeto, setor ou sessão que tenha alguma.</span></div>`;
    }
    const colunas = this.colunas();
    if (colunas.length === 0) {
      return `<div class="quadro-vazio">${icone("circle-check", { tamanho: 22 })}<span>Todas as tarefas deste escopo estão concluídas.</span><button class="link-acao" data-concluidas>Mostrar as concluídas</button></div>`;
    }
    const totais = Object.fromEntries(colunas.map((coluna) => [coluna, 0]));
    const corpo = raias
      .map((raia) => {
        const visiveis = raia.tarefas.filter((id) => this.casaComFiltro(id));
        if (this.filtro && visiveis.length === 0) return "";
        const chave = this.chaveDaRaia(raia.chave);
        const recolhida = this.raiasRecolhidas.has(chave);
        const celulas = colunas
          .map((coluna) => {
            const tarefas = visiveis.filter((id) => this.fluxo.status(id) === coluna);
            totais[coluna] += tarefas.length;
            const conteudo = recolhida ? (tarefas.length ? `<span class="texto-fraco">${tarefas.length}</span>` : "") : tarefas.map((id) => this.montarCartao(id)).join("");
            return `<div class="quadro-celula" data-coluna="${escapeHtml(coluna)}">${conteudo}</div>`;
          })
          .join("");
        return this.montarCabecalhoDaRaia(raia, chave, recolhida) + celulas;
      })
      .join("");
    const cabecalho = `<div class="quadro-coluna mod-raia">${MODOS_DE_RAIA[this.modoDeRaia]}</div>${colunas
      .map((coluna) => `<div class="quadro-coluna"><span class="quadro-tom tom-${tomDoStatus(coluna)}"></span>${escapeHtml(ROTULO_DA_COLUNA[coluna] || apresentarStatus(coluna))}<span class="contador">${totais[coluna]}</span></div>`)
      .join("")}`;
    return `<div class="quadro-grade" style="grid-template-columns: 200px repeat(${colunas.length}, minmax(170px, 1fr))">${cabecalho}${corpo}</div>`;
  }

  montarCabecalhoDaRaia(raia, chave, recolhida) {
    const nomeador = this.noDaChave(raia.chave);
    const feitas = raia.tarefas.filter((id) => this.fluxo.status(id) === "concluido").length;
    const progresso = Math.round((100 * feitas) / raia.tarefas.length);
    // No modo por objetivo, uma raia de sessão é a das tarefas que não sobem a
    // objetivo nenhum: o ícone do tipo diz isso sem mais uma linha de texto.
    const tipo = nomeador && apresentarTipo(nomeador.tipo);
    const marcaDoTipo = nomeador ? `<span class="quadro-raia-tipo" style="color:${corDoTipo(nomeador.tipo)}" title="${escapeHtml(tipo.nome)}">${icone(tipo.icone, { tamanho: 13 })}</span>` : "";
    const titulo = nomeador
      ? `<button class="quadro-raia-titulo ${this.selecionado === nomeador.id ? "is-selecionado" : ""}" data-ir="${escapeHtml(nomeador.id)}" data-pairar="${escapeHtml(nomeador.id)}">${escapeHtml(nomeador.rotulo)}</button>`
      : `<span class="quadro-raia-titulo mod-sem-chave">${RAIA_SEM_CHAVE[this.modoDeRaia]}</span>`;
    return `
      <div class="quadro-raia">
        <div class="quadro-raia-linha">
          <button class="quadro-raia-alternar" data-raia="${escapeHtml(chave)}" aria-label="${recolhida ? "Expandir" : "Recolher"} a raia">${icone(recolhida ? "chevron-right" : "chevron-down", { tamanho: 13 })}</button>
          ${marcaDoTipo}${titulo}
        </div>
        <div class="quadro-progresso" title="${feitas} de ${raia.tarefas.length} concluídas"><i style="width:${progresso}%"></i></div>
      </div>`;
  }

  montarCartao(id) {
    const no = this.fluxo.porId.get(id);
    const abertas = this.fluxo.perguntasAbertas(id).length;
    const pre = this.fluxo.dependeDe(id);
    const pendentes = pre.filter((outra) => this.fluxo.status(outra) !== "concluido").length;
    const libera = this.fluxo.liberaQuem(id).length;
    const selecionado = this.selecionado;
    const cercaSelecionado = selecionado && selecionado !== id && this.fluxo.tarefaDe(selecionado) === id;
    const marcas = [
      abertas ? `<span class="quadro-marca mod-pergunta" title="${abertas} pergunta(s) aberta(s) bloqueando">? ${abertas}</span>` : "",
      pre.length ? `<span class="quadro-marca ${pendentes ? "mod-pendente" : ""}" title="Depende de ${pre.length} (${pendentes} pendente(s))">↑${pre.length}</span>` : "",
      libera ? `<span class="quadro-marca" title="${libera} tarefa(s) esperam por esta">↓${libera}</span>` : "",
    ].join("");
    return `
      <div class="quadro-cartao st-${escapeHtml(this.fluxo.status(id))} ${id === selecionado || cercaSelecionado ? "is-selecionado" : ""}" data-ir="${escapeHtml(id)}" data-pairar="${escapeHtml(id)}" title="${escapeHtml(no.rotulo)}">
        <span class="quadro-cartao-rotulo">${escapeHtml(no.rotulo)}</span>
        ${marcas ? `<span class="quadro-marcas">${marcas}</span>` : ""}
      </div>`;
  }

  // ---------------------------------------------------------------- interação

  aoClicar(evento) {
    const filtro = evento.target.closest("[data-filtro]");
    if (filtro) {
      this.filtro = this.filtro === filtro.dataset.filtro ? null : filtro.dataset.filtro;
      this.render();
      return;
    }
    const modo = evento.target.closest("[data-modo-raia]");
    if (modo) {
      this.modoDeRaia = modo.dataset.modoRaia;
      gravarPreferencia("quadro_raias", this.modoDeRaia);
      this.render();
      return;
    }
    if (evento.target.closest("[data-concluidas]")) {
      this.ocultarConcluidas = !this.ocultarConcluidas;
      gravarPreferencia("quadro_ocultar_concluidas", this.ocultarConcluidas);
      this.render();
      return;
    }
    const raia = evento.target.closest("[data-raia]");
    if (raia) {
      const chave = raia.dataset.raia;
      if (!this.raiasRecolhidas.delete(chave)) this.raiasRecolhidas.add(chave);
      this.render();
      return;
    }
    const alvo = evento.target.closest("[data-ir]");
    if (alvo) this.acoes.selecionar(alvo.dataset.ir);
  }

  /** Acende o nó nas duas metades: no minimapa os vizinhos, no quadro os pré-requisitos e quem espera. */
  pairar(id) {
    this.pairado = id;
    const minimapa = this.raiz.querySelector(".quadro-minimapa");
    const rolagem = this.raiz.querySelector(".quadro-rolagem");
    const svg = this.raiz.querySelector(".quadro-ligacoes");
    if (!minimapa || !rolagem) return;
    this.raiz.querySelectorAll(".is-pairado, .is-afeta, .is-afetado").forEach((el) => el.classList.remove("is-pairado", "is-afeta", "is-afetado"));
    svg.innerHTML = "";
    minimapa.classList.toggle("tem-pairado", Boolean(id));
    rolagem.classList.toggle("tem-pairado", false);
    if (!id || !this.fluxo.porId.has(id)) return;

    const { montante, jusante } = this.fluxo.vizinhos(id);
    const marcar = (seletor, classe) => this.raiz.querySelectorAll(seletor).forEach((el) => el.classList.add(classe));
    marcar(`.quadro-ponto[data-ir="${CSS.escape(id)}"]`, "is-pairado");
    montante.forEach((vizinho) => marcar(`.quadro-ponto[data-ir="${CSS.escape(vizinho.id)}"]`, "is-afeta"));
    jusante.forEach((vizinho) => marcar(`.quadro-ponto[data-ir="${CSS.escape(vizinho.id)}"]`, "is-afetado"));

    const tarefa = this.fluxo.tarefaDe(id);
    if (!tarefa) return;
    rolagem.classList.add("tem-pairado");
    marcar(`.quadro-cartao[data-ir="${CSS.escape(tarefa)}"]`, "is-pairado");
    if (this.fluxo.porId.get(id).tipo !== "Task") return;
    const antes = this.fluxo.dependeDe(id);
    const depois = this.fluxo.liberaQuem(id);
    antes.forEach((outra) => marcar(`.quadro-cartao[data-ir="${CSS.escape(outra)}"]`, "is-afeta"));
    depois.forEach((outra) => marcar(`.quadro-cartao[data-ir="${CSS.escape(outra)}"]`, "is-afetado"));
    this.desenharLigacoes(id, antes, depois);
  }

  desenharLigacoes(id, antes, depois) {
    const rolagem = this.raiz.querySelector(".quadro-rolagem");
    const svg = this.raiz.querySelector(".quadro-ligacoes");
    const origem = rolagem.getBoundingClientRect();
    const caixa = (alvo) => {
      const el = rolagem.querySelector(`.quadro-cartao[data-ir="${CSS.escape(alvo)}"]`);
      if (!el) return null;
      const r = el.getBoundingClientRect();
      return { x: r.left - origem.left + rolagem.scrollLeft, y: r.top - origem.top + rolagem.scrollTop, w: r.width, h: r.height };
    };
    const centro = caixa(id);
    if (!centro) return;
    svg.setAttribute("width", rolagem.scrollWidth);
    svg.setAttribute("height", rolagem.scrollHeight);
    const curva = (de, para, cor) => {
      const y1 = de.y + Math.min(de.h / 2, 16);
      const y2 = para.y + Math.min(para.h / 2, 16);
      let x1 = de.x;
      let x2 = para.x;
      let c1;
      let c2;
      if (Math.abs(de.x - para.x) < 4) {
        c1 = x1 - 48;
        c2 = x2 - 48;
      } else {
        if (para.x > de.x) x1 = de.x + de.w;
        else x2 = para.x + para.w;
        const sentido = x2 >= x1 ? 1 : -1;
        const folga = Math.max(40, Math.abs(x2 - x1) / 2);
        c1 = x1 + sentido * folga;
        c2 = x2 - sentido * folga;
      }
      return `<path d="M${x1},${y1} C${c1},${y1} ${c2},${y2} ${x2},${y2}" stroke="${cor}" marker-end="url(#quadro-seta-${cor === COR_DE_QUEM_AFETA ? "afeta" : "afetado"})"/>`;
    };
    const caminhos = [
      ...antes.map((outra) => caixa(outra)).filter(Boolean).map((de) => curva(de, centro, COR_DE_QUEM_AFETA)),
      ...depois.map((outra) => caixa(outra)).filter(Boolean).map((para) => curva(centro, para, COR_DE_QUEM_E_AFETADO)),
    ];
    const seta = (nome, cor) => `<marker id="quadro-seta-${nome}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0,0L10,5L0,10z" fill="${cor}"/></marker>`;
    svg.innerHTML = `<defs>${seta("afeta", COR_DE_QUEM_AFETA)}${seta("afetado", COR_DE_QUEM_E_AFETADO)}</defs>${caminhos.join("")}`;
  }
}
