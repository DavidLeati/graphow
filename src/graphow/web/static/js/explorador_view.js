/**
 * Explorador: a árvore Projeto → Setor → Sessão → trabalho.
 *
 * A lista anterior era plana — todos os projetos, depois todos os setores, depois
 * todas as sessões, sem dizer quem pertencia a quem — e clicar num setor não fazia
 * nada. Aqui a árvore segue as arestas `contem`, cada contêiner mostra quanto
 * trabalho segue aberto na subárvore, e abrir um contêiner abre o canvas nele.
 */
import { escapeHtml, gravarPreferencia, lerPreferencia } from "./dom.js";
import { icone } from "./icones.js";
import { abrirMenuDeContexto } from "./menu_contexto.js";
import { apresentarStatus, apresentarTipo, corDoTipo, ehConteiner, ORDEM_DE_TRABALHO, tomDoStatus } from "./ontologia_ui.js";

const toqueRecente = (no) => no.resumo?.seq_ultimo_toque ?? no.seq_atualizacao ?? no.seq_criacao ?? 0;
const abertasDe = (no) => (no.resumo?.tarefas_abertas ?? 0) + (no.resumo?.questoes_abertas ?? 0);
const porCriacao = (a, b) => (a.seq_criacao ?? 0) - (b.seq_criacao ?? 0);
const porNome = (a, b) => (a.rotulo || "").localeCompare(b.rotulo || "", "pt-BR", { sensitivity: "base" });
const posicaoDoTipo = (no) => {
  const posicao = ORDEM_DE_TRABALHO.indexOf(no.tipo);
  return posicao < 0 ? ORDEM_DE_TRABALHO.length : posicao;
};

const ORDENACOES = {
  criacao: { rotulo: "Ordem de criação", comparar: porCriacao },
  nome: { rotulo: "Nome (A a Z)", comparar: porNome },
  nome_invertido: { rotulo: "Nome (Z a A)", comparar: (a, b) => porNome(b, a) },
  recente: { rotulo: "Atividade mais recente", comparar: (a, b) => toqueRecente(b) - toqueRecente(a) },
  abertos: { rotulo: "Trabalho aberto primeiro", comparar: (a, b) => abertasDe(b) - abertasDe(a) || porCriacao(a, b) },
};

const ID_DOS_ORFAOS = "__orfaos__";

export class ExploradorView {
  constructor(raiz, { state, indice, acoes }) {
    this.raiz = raiz;
    this.state = state;
    this.indice = indice;
    this.acoes = acoes;
    this.arvore = raiz.querySelector("[data-arvore]");
    this.ordenacao = lerPreferencia("explorador_ordem", "criacao");
    const salvos = lerPreferencia("explorador_expandidos", null);
    this.expandidos = new Set(salvos || []);
    this.primeiraCarga = salvos === null;
    this.idFocado = null;
    this.ligarBotoes();
    this.ligarArvore();
    indice.aoMudar(() => this.render());
    this.render();
  }

  ligarBotoes() {
    const acoesDosBotoes = {
      "novo-no": () => this.acoes.novoNo(),
      "novo-conteiner": () => this.acoes.novoConteiner(),
      ordenar: (evento) => this.abrirMenuDeOrdenacao(evento),
      recolher: () => this.alternarTudo(),
    };
    this.raiz.querySelectorAll("[data-acao-explorador]").forEach((botao) => {
      botao.addEventListener("click", (evento) => acoesDosBotoes[botao.dataset.acaoExplorador]?.(evento));
    });
  }

  ligarArvore() {
    this.arvore.addEventListener("click", (evento) => this.aoClicar(evento));
    this.arvore.addEventListener("auxclick", (evento) => {
      if (evento.button === 1) this.aoClicar(evento, true);
    });
    this.arvore.addEventListener("contextmenu", (evento) => this.aoMenu(evento));
    this.arvore.addEventListener("keydown", (evento) => this.aoTeclar(evento));
  }

  aoClicar(evento, forcarNovaAba = false) {
    const titulo = evento.target.closest(".arvore-titulo");
    if (!titulo) return;
    const id = titulo.dataset.id;
    const novaAba = forcarNovaAba || evento.ctrlKey || evento.metaKey;
    this.idFocado = id;
    if (id === ID_DOS_ORFAOS || evento.target.closest("[data-seta]")) {
      this.alternar(id);
      return;
    }
    if (titulo.dataset.raiz) {
      this.acoes.abrirEscopo(null, { novaAba });
      return;
    }
    if (ehConteiner(titulo.dataset.tipo)) {
      this.expandir(id);
      this.acoes.abrirEscopo(this.indice.escopoDe(id), { novaAba });
      return;
    }
    this.acoes.focarNo(id, this.indice.info.get(id));
  }

  aoMenu(evento) {
    const titulo = evento.target.closest(".arvore-titulo");
    if (!titulo || !titulo.dataset.id || titulo.dataset.id === ID_DOS_ORFAOS) return;
    evento.preventDefault();
    if (titulo.dataset.raiz) {
      abrirMenuDeContexto(evento, [
        { rotulo: "Abrir em nova aba", icone: "plus", acao: () => this.acoes.abrirEscopo(null, { novaAba: true }) },
        { rotulo: "Novo projeto…", icone: "briefcase", acao: () => this.acoes.novoConteiner("Projeto") },
      ]);
      return;
    }
    this.acoes.menuDoNo(evento, this.indice.no(titulo.dataset.id));
  }

  /**
   * Setas percorrem as linhas visíveis como numa árvore de arquivos: direita
   * abre o contêiner, esquerda fecha — ou sobe para o pai, se já estava fechado.
   */
  aoTeclar(evento) {
    const linhas = [...this.arvore.querySelectorAll(".arvore-titulo")];
    if (linhas.length === 0) return;
    const atual = Math.max(0, linhas.findIndex((linha) => linha.dataset.id === this.idFocado));
    const linha = linhas[atual];
    const conteiner = linha.classList.contains("mod-conteiner");
    const teclas = {
      ArrowDown: () => this.focar(linhas[Math.min(linhas.length - 1, atual + 1)]),
      ArrowUp: () => this.focar(linhas[Math.max(0, atual - 1)]),
      ArrowRight: () => conteiner && this.expandir(linha.dataset.id),
      ArrowLeft: () => (conteiner && this.expandidos.has(linha.dataset.id) ? this.recolher(linha.dataset.id) : this.focarPai(linha)),
      Enter: () => linha.click(),
    };
    if (!teclas[evento.key]) return;
    evento.preventDefault();
    teclas[evento.key]();
  }

  focarPai(linha) {
    const pai = linha.closest(".arvore-filhos")?.parentElement?.querySelector(":scope > .arvore-titulo");
    this.focar(pai);
  }

  focar(linha) {
    if (!linha) return;
    this.idFocado = linha.dataset.id;
    this.arvore.querySelectorAll(".arvore-titulo.is-focado").forEach((el) => el.classList.remove("is-focado"));
    linha.classList.add("is-focado");
    linha.scrollIntoView({ block: "nearest" });
  }

  alternar(id) {
    if (this.expandidos.has(id)) this.recolher(id);
    else this.expandir(id);
  }

  expandir(id) {
    if (this.expandidos.has(id)) return;
    this.expandidos.add(id);
    this.persistirExpansao();
    this.render();
  }

  recolher(id) {
    if (!this.expandidos.delete(id)) return;
    this.persistirExpansao();
    this.render();
  }

  alternarTudo() {
    if (this.expandidos.size > 0) this.expandidos.clear();
    else this.indice.conteineres.forEach((no) => { if (no.tipo !== "Sessao") this.expandidos.add(no.id); });
    this.persistirExpansao();
    this.render();
  }

  persistirExpansao() {
    gravarPreferencia("explorador_expandidos", [...this.expandidos]);
  }

  /** Abre os ancestrais do nó e o traz para a vista, como "Revelar no explorador". */
  async revelar(id) {
    for (const ancestral of this.indice.ancestrais(id)) this.expandidos.add(ancestral.id);
    this.persistirExpansao();
    this.idFocado = id;
    // O nó de trabalho só entra na árvore depois que a sessão dele é lida.
    const sessao = this.indice.info.get(id)?.sessao_id;
    if (sessao && !this.indice.sessaoCarregada(sessao)) await this.indice.carregarSessao(sessao);
    this.render();
    this.arvore.querySelector(`.arvore-titulo[data-id="${CSS.escape(id)}"]`)?.scrollIntoView({ block: "center" });
  }

  abrirMenuDeOrdenacao(evento) {
    abrirMenuDeContexto(
      evento,
      Object.entries(ORDENACOES).map(([chave, ordem]) => ({
        rotulo: ordem.rotulo,
        marcado: this.ordenacao === chave,
        acao: () => {
          this.ordenacao = chave;
          gravarPreferencia("explorador_ordem", chave);
          this.render();
        },
      }))
    );
  }

  ordenar(nos) {
    const comparar = (ORDENACOES[this.ordenacao] || ORDENACOES.criacao).comparar;
    return [...nos].filter(Boolean).sort(comparar);
  }

  /** Trabalho dentro da sessão: agrupado pela ordem de leitura dos tipos, depois pela ordenação. */
  ordenarTrabalho(nos) {
    const comparar = (ORDENACOES[this.ordenacao] || ORDENACOES.criacao).comparar;
    const agrupar = this.ordenacao === "criacao";
    return [...nos].sort((a, b) => (agrupar ? posicaoDoTipo(a) - posicaoDoTipo(b) : 0) || comparar(a, b));
  }

  render() {
    if (!this.indice.carregado) {
      this.arvore.innerHTML = `<div class="arvore-aviso">${this.indice.erro ? escapeHtml(this.indice.erro) : "Carregando a árvore…"}</div>`;
      return;
    }
    if (this.primeiraCarga) {
      this.indice.raizes.forEach((id) => this.expandidos.add(id));
      this.primeiraCarga = false;
    }
    const raizes = this.ordenar(this.indice.raizes.map((id) => this.indice.conteineres.get(id)));
    const partes = [this.montarRaiz(), ...raizes.map((no) => this.montarConteiner(no))];
    if (raizes.length === 0) partes.push(this.montarVazio());
    if (this.indice.orfaos.length) partes.push(this.montarOrfaos());
    this.arvore.innerHTML = partes.join("");
  }

  montarRaiz() {
    const ativo = this.acoes.escopoAtivo() === null;
    const total = this.indice.totalNoGrafo;
    return `
      <div class="arvore-titulo mod-raiz ${ativo ? "is-ativo" : ""}" data-id="__raiz__" data-raiz="1" title="Abrir o grafo inteiro">
        <span class="arvore-icone">${icone("grafo", { tamanho: 15 })}</span>
        <span class="arvore-rotulo">Todos os projetos</span>
        ${total !== null ? `<span class="arvore-sinais"><span class="contador">${total}</span></span>` : ""}
      </div>`;
  }

  montarVazio() {
    return `<div class="arvore-aviso">Nenhum projeto ainda. Use <strong>Novo contêiner</strong> acima ou o botão direito em “Todos os projetos”.</div>`;
  }

  montarConteiner(no) {
    const expandido = this.expandidos.has(no.id);
    const filhos = expandido ? this.montarFilhos(no) : "";
    return `
      <div class="arvore-no" data-no="${escapeHtml(no.id)}">
        ${this.montarTitulo(no, { conteiner: true, expandido })}
        ${expandido ? `<div class="arvore-filhos">${filhos}</div>` : ""}
      </div>`;
  }

  montarFilhos(no) {
    const conteineres = this.ordenar(this.indice.filhos(no.id).map((id) => this.indice.conteineres.get(id)));
    const partes = conteineres.map((filho) => this.montarConteiner(filho));
    if (no.tipo === "Sessao") partes.push(this.montarTrabalhoDaSessao(no.id));
    const conteudo = partes.join("");
    return conteudo || '<div class="arvore-aviso mod-recuado">Vazio</div>';
  }

  montarTrabalhoDaSessao(idSessao) {
    const nos = this.indice.sessaoCarregada(idSessao);
    if (!nos) {
      this.indice.carregarSessao(idSessao);
      return '<div class="arvore-aviso mod-recuado">Carregando…</div>';
    }
    if (nos.length === 0) return '<div class="arvore-aviso mod-recuado">Nenhum nó de trabalho</div>';
    return this.ordenarTrabalho(nos).map((filho) => this.montarTitulo(filho, { conteiner: false })).join("");
  }

  montarOrfaos() {
    const expandido = this.expandidos.has(ID_DOS_ORFAOS);
    const itens = this.indice.orfaos.map((id) => {
      const info = this.indice.info.get(id) || { id, tipo: "Note", rotulo: id };
      return this.montarTitulo(info, { conteiner: false });
    });
    return `
      <div class="arvore-no">
        <div class="arvore-titulo mod-conteiner mod-orfaos" data-id="${ID_DOS_ORFAOS}" title="Nós que não pendem de contêiner nenhum: somem calados em qualquer visão colapsada">
          <span class="arvore-seta ${expandido ? "" : "is-recolhida"}" data-seta>${icone("chevron-down", { tamanho: 14 })}</span>
          <span class="arvore-icone">${icone("inbox", { tamanho: 15 })}</span>
          <span class="arvore-rotulo">Fora da hierarquia</span>
          <span class="arvore-sinais"><span class="contador mod-aviso">${this.indice.orfaos.length}</span></span>
        </div>
        ${expandido ? `<div class="arvore-filhos">${itens.join("")}</div>` : ""}
      </div>`;
  }

  montarTitulo(no, { conteiner, expandido = false }) {
    const tipo = apresentarTipo(no.tipo);
    const ativo = conteiner && this.acoes.escopoAtivo()?.id === no.id;
    const selecionado = this.state.selectedElement?.id === no.id;
    const classes = [
      "arvore-titulo",
      conteiner ? "mod-conteiner" : "mod-item",
      ativo ? "is-ativo" : "",
      selecionado ? "is-selecionado" : "",
      this.idFocado === no.id ? "is-focado" : "",
    ];
    const seta = conteiner
      ? `<span class="arvore-seta ${expandido ? "" : "is-recolhida"}" data-seta>${icone("chevron-down", { tamanho: 14 })}</span>`
      : '<span class="arvore-seta mod-vazia"></span>';
    const aria = `role="treeitem" aria-selected="${selecionado}"${conteiner ? ` aria-expanded="${expandido}"` : ""}`;
    return `
      <div class="${classes.join(" ")}" ${aria} data-id="${escapeHtml(no.id)}" data-tipo="${escapeHtml(no.tipo)}" title="${escapeHtml(this.dica(no, tipo))}">
        ${seta}
        <span class="arvore-icone" style="color:${corDoTipo(no.tipo)}">${icone(tipo.icone, { tamanho: 15 })}</span>
        <span class="arvore-rotulo">${escapeHtml(no.rotulo || no.id)}</span>
        <span class="arvore-sinais">${conteiner ? this.sinaisDoConteiner(no) : this.sinaisDoItem(no)}</span>
      </div>`;
  }

  dica(no, tipo) {
    const r = no.resumo;
    if (!r) return `${tipo.nome} · ${no.rotulo || no.id}`;
    const tarefas = r.tarefas_totais ? `${r.tarefas_concluidas}/${r.tarefas_totais} tarefas concluídas` : "sem tarefas";
    return `${tipo.nome} · ${no.rotulo}\n${tarefas} · ${r.total_nos} nós na subárvore`;
  }

  sinaisDoConteiner(no) {
    const r = no.resumo;
    const partes = [];
    if (no.propriedades?.nivel_autonomia === "ilimitado") {
      partes.push(`<span class="sinal mod-autonomia" title="Autonomia ilimitada dos agentes">${icone("zap", { tamanho: 12 })}</span>`);
    }
    if (!r) return partes.join("");
    if (r.questoes_abertas) partes.push(`<span class="contador mod-duvida" title="${r.questoes_abertas} dúvida(s) aberta(s)">?${r.questoes_abertas}</span>`);
    if (r.tarefas_abertas) partes.push(`<span class="contador mod-aberto" title="${r.tarefas_abertas} tarefa(s) aberta(s)">${r.tarefas_abertas}</span>`);
    else if (r.tarefas_totais) partes.push(`<span class="sinal mod-ok" title="Todas as tarefas concluídas">${icone("check", { tamanho: 13 })}</span>`);
    return partes.join("");
  }

  sinaisDoItem(no) {
    if (no.esta_bloqueado) return `<span class="sinal mod-alerta" title="Bloqueado por dúvida aberta">${icone("alert-triangle", { tamanho: 13 })}</span>`;
    if (no.lock_ativo) return `<span class="sinal mod-andamento" title="Posse de ${escapeHtml(no.lock_ativo)}">${icone("lock", { tamanho: 12 })}</span>`;
    const status = no.propriedades?.status ?? no.status;
    if (!status) return "";
    const iconePorTom = { ok: "check", andamento: "circle-half", alerta: "alert-triangle", espera: "circle", neutro: "circle-dot" };
    const tom = tomDoStatus(status);
    return `<span class="sinal mod-${tom}" title="${escapeHtml(apresentarStatus(status))}">${icone(iconePorTom[tom], { tamanho: 12 })}</span>`;
  }
}
