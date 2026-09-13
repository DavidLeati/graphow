/**
 * Abas do centro.
 *
 * Cada aba é uma vista: o grafo aberto num escopo — tudo, um projeto, um setor ou
 * uma sessão — ou uma ferramenta, como o comparador de ramos. A aba guarda o
 * próprio histórico, e o cabeçalho abaixo dela mostra a trilha do escopo com
 * voltar e avançar. As abas antigas eram só projetos, sem histórico nem trilha:
 * abrir uma sessão trocava a tela sem deixar caminho de volta.
 */
import { escapeHtml, gravarPreferencia, lerPreferencia } from "./dom.js";
import { icone } from "./icones.js";
import { abrirMenuDeContexto } from "./menu_contexto.js";
import { apresentarTipo } from "./ontologia_ui.js";

const FERRAMENTAS = {
  diff: { titulo: "Comparar ramos", icone: "git-compare" },
  patch: { titulo: "Terminal de patch", icone: "terminal" },
};

let contadorDeAbas = 0;
const novoId = () => `aba-${Date.now().toString(36)}-${(contadorDeAbas++).toString(36)}`;
const mesmoEscopo = (a, b) => (a?.id ?? null) === (b?.id ?? null);

function criarAbaDeGrafo(escopo) {
  return { id: novoId(), tipo: "grafo", escopo, historico: [escopo], posicao: 0, viewport: null };
}

export class AbasWorkspace {
  constructor({ faixa, trilha, botoesDeNavegacao, indice, aoAtivar, aoAntesDeSair }) {
    this.faixa = faixa;
    this.trilha = trilha;
    this.botoesDeNavegacao = botoesDeNavegacao;
    this.indice = indice;
    this.aoAtivar = aoAtivar;
    this.aoAntesDeSair = aoAntesDeSair;
    const salvo = lerPreferencia("abas", null);
    this.abas = Array.isArray(salvo?.abas) && salvo.abas.length ? salvo.abas : [criarAbaDeGrafo(null)];
    this.idAtiva = this.abas.some((aba) => aba.id === salvo?.ativa) ? salvo.ativa : this.abas[0].id;
    this.ligarEventos();
    indice.aoMudar(() => this.atualizarRotulos());
  }

  get ativa() {
    return this.abas.find((aba) => aba.id === this.idAtiva) || this.abas[0];
  }

  ligarEventos() {
    this.faixa.addEventListener("click", (evento) => {
      const fechar = evento.target.closest("[data-fechar-aba]");
      const aba = evento.target.closest(".aba");
      if (fechar) this.fechar(fechar.dataset.fecharAba);
      else if (aba) this.ativar(aba.dataset.aba);
    });
    this.faixa.addEventListener("auxclick", (evento) => {
      const aba = evento.target.closest(".aba");
      if (aba && evento.button === 1) this.fechar(aba.dataset.aba);
    });
    this.faixa.addEventListener("contextmenu", (evento) => {
      const aba = evento.target.closest(".aba");
      if (aba) this.abrirMenuDaAba(evento, aba.dataset.aba);
    });
    this.trilha.addEventListener("click", (evento) => {
      const item = evento.target.closest("[data-trilha]");
      if (!item) return;
      const id = item.dataset.trilha;
      this.abrirEscopo(id === "__todos__" ? null : this.indice.escopoDe(id));
    });
    this.botoesDeNavegacao.voltar.addEventListener("click", () => this.mover(-1));
    this.botoesDeNavegacao.avancar.addEventListener("click", () => this.mover(1));
  }

  /** Abre o escopo na aba ativa, ou numa aba nova quando pedido (Ctrl+clique). */
  async abrirEscopo(escopo, { novaAba = false } = {}) {
    const atual = this.ativa;
    if (novaAba || atual.tipo !== "grafo") {
      const aba = criarAbaDeGrafo(escopo);
      this.abas.splice(this.abas.indexOf(atual) + 1, 0, aba);
      return this.trocarPara(aba, true);
    }
    if (mesmoEscopo(atual.escopo, escopo)) return this.aoAtivar(atual, { mudouEscopo: false, repetido: true });
    atual.historico = [...atual.historico.slice(0, atual.posicao + 1), escopo];
    atual.posicao = atual.historico.length - 1;
    atual.escopo = escopo;
    atual.viewport = null;
    return this.trocarPara(atual, true);
  }

  abrirFerramenta(tipo) {
    const existente = this.abas.find((aba) => aba.tipo === tipo);
    if (existente) return this.ativar(existente.id);
    const aba = { id: novoId(), tipo };
    this.abas.splice(this.abas.indexOf(this.ativa) + 1, 0, aba);
    return this.trocarPara(aba, false);
  }

  novaAba() {
    const aba = criarAbaDeGrafo(null);
    this.abas.push(aba);
    return this.trocarPara(aba, true);
  }

  ativar(id) {
    const aba = this.abas.find((candidata) => candidata.id === id);
    if (!aba || aba.id === this.idAtiva) return Promise.resolve();
    return this.trocarPara(aba, false);
  }

  async trocarPara(aba, mudouEscopo, { salvarAnterior = true } = {}) {
    const anterior = this.abas.find((candidata) => candidata.id === this.idAtiva);
    if (salvarAnterior && anterior && anterior.id !== aba.id) this.aoAntesDeSair?.(anterior);
    this.idAtiva = aba.id;
    this.render();
    this.persistir();
    await this.aoAtivar(aba, { mudouEscopo });
  }

  fechar(id) {
    const indice = this.abas.findIndex((aba) => aba.id === id);
    if (indice < 0) return;
    const eraAtiva = id === this.idAtiva;
    this.abas.splice(indice, 1);
    if (this.abas.length === 0) this.abas.push(criarAbaDeGrafo(null));
    if (!eraAtiva) {
      this.render();
      this.persistir();
      return;
    }
    const vizinha = this.abas[Math.min(indice, this.abas.length - 1)];
    this.trocarPara(vizinha, !vizinha.viewport, { salvarAnterior: false });
  }

  fecharOutras(id) {
    const mantida = this.abas.find((aba) => aba.id === id);
    if (!mantida) return;
    const eraAtiva = id === this.idAtiva;
    this.abas = [mantida];
    if (eraAtiva) {
      this.render();
      this.persistir();
      return;
    }
    this.trocarPara(mantida, !mantida.viewport, { salvarAnterior: false });
  }

  async mover(passo) {
    const aba = this.ativa;
    if (aba.tipo !== "grafo") return;
    const destino = aba.posicao + passo;
    if (destino < 0 || destino >= aba.historico.length) return;
    aba.posicao = destino;
    aba.escopo = aba.historico[destino];
    aba.viewport = null;
    this.render();
    this.persistir();
    await this.aoAtivar(aba, { mudouEscopo: true });
  }

  abrirMenuDaAba(evento, id) {
    const aba = this.abas.find((candidata) => candidata.id === id);
    if (!aba) return;
    abrirMenuDeContexto(evento, [
      { rotulo: "Fechar", icone: "x", acao: () => this.fechar(id) },
      { rotulo: "Fechar as outras", icone: "x", desabilitado: this.abas.length < 2, acao: () => this.fecharOutras(id) },
      "-",
      {
        rotulo: "Duplicar aba",
        icone: "copy",
        desabilitado: aba.tipo !== "grafo",
        acao: () => this.abrirEscopo(aba.escopo, { novaAba: true }),
      },
    ]);
  }

  /** Um contêiner renomeado muda o título da aba sem precisar reabri-la. */
  atualizarRotulos() {
    let mudou = false;
    for (const aba of this.abas) {
      const atual = aba.escopo && this.indice.conteineres.get(aba.escopo.id);
      if (atual && atual.rotulo !== aba.escopo.rotulo) {
        aba.escopo = { ...aba.escopo, rotulo: atual.rotulo };
        mudou = true;
      }
    }
    if (mudou) this.persistir();
    this.render();
  }

  tituloDe(aba) {
    if (aba.tipo !== "grafo") return FERRAMENTAS[aba.tipo]?.titulo || aba.tipo;
    return aba.escopo?.rotulo || "Todos os projetos";
  }

  iconeDe(aba) {
    if (aba.tipo !== "grafo") return FERRAMENTAS[aba.tipo]?.icone || "file-text";
    return aba.escopo ? apresentarTipo(aba.escopo.tipo).icone : "grafo";
  }

  render() {
    this.faixa.innerHTML = this.abas.map((aba) => this.montarAba(aba)).join("");
    this.renderTrilha();
  }

  montarAba(aba) {
    const titulo = this.tituloDe(aba);
    return `
      <div class="aba ${aba.id === this.idAtiva ? "is-ativa" : ""}" data-aba="${aba.id}" title="${escapeHtml(titulo)}" role="tab">
        <span class="aba-icone">${icone(this.iconeDe(aba), { tamanho: 14 })}</span>
        <span class="aba-titulo">${escapeHtml(titulo)}</span>
        <button class="aba-fechar" data-fechar-aba="${aba.id}" aria-label="Fechar aba">${icone("x", { tamanho: 13 })}</button>
      </div>`;
  }

  /** Trilha no cabeçalho da vista: "Todos / Projeto / Setor / Sessão", cada parte clicável. */
  renderTrilha() {
    const aba = this.ativa;
    const { voltar, avancar } = this.botoesDeNavegacao;
    voltar.disabled = aba.tipo !== "grafo" || aba.posicao <= 0;
    avancar.disabled = aba.tipo !== "grafo" || aba.posicao >= aba.historico.length - 1;
    if (aba.tipo !== "grafo") {
      this.trilha.innerHTML = `<span class="trilha-parte mod-atual">${escapeHtml(this.tituloDe(aba))}</span>`;
      return;
    }
    const cadeia = aba.escopo ? this.indice.ancestrais(aba.escopo.id) : [];
    const partes = [{ id: "__todos__", rotulo: "Todos os projetos" }, ...cadeia];
    if (aba.escopo && cadeia.length === 0) partes.push({ id: aba.escopo.id, rotulo: aba.escopo.rotulo });
    this.trilha.innerHTML = partes
      .map((parte, indice) => {
        const atual = indice === partes.length - 1;
        return `<span class="trilha-parte ${atual ? "mod-atual" : ""}" data-trilha="${escapeHtml(parte.id)}">${escapeHtml(parte.rotulo)}</span>`;
      })
      .join('<span class="trilha-separador">/</span>');
  }

  persistir() {
    gravarPreferencia("abas", { abas: this.abas, ativa: this.idAtiva });
  }
}
