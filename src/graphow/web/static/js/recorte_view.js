/**
 * Painel de recorte e exibição do canvas, e o aviso do que ficou de fora.
 *
 * O recorte acontece no servidor: colapsar em super-nós, manter só o que está
 * perto de trabalho aberto, ou mostrar apenas quem participa de dependência.
 * Estes controles apenas dizem ao servidor o que pedir. Eles moram num painel
 * flutuante sobre o canvas, com as
 * opções de exibição e de arranjo ao lado.
 *
 * O aviso existe porque uma tela que mostra 6 de 191 nós sem explicar por quê é
 * indistinguível de uma tela quebrada. Ele sempre diz quantos foram escondidos e
 * por qual filtro, e nomeia os nós órfãos — os que não pendem de contêiner
 * nenhum e sumiriam calados em qualquer visão colapsada.
 */
import { escapeHtml, gravarPreferencia, lerPreferencia } from "./dom.js";
import { icone } from "./icones.js";
import { apresentarTipo, corDoTipo } from "./ontologia_ui.js";

const NIVEIS_DE_COLAPSO = [
  { valor: "", rotulo: "Tudo" },
  { valor: "setor", rotulo: "Setores" },
  { valor: "sessao", rotulo: "Sessões" },
];

const NOMES_DOS_FILTROS = {
  "colapsado_em:setor": "agrupado em setores",
  "colapsado_em:sessao": "agrupado em sessões",
  caminho_critico: "caminho crítico",
};

export class RecorteView {
  constructor({ painel, aviso, state, aoMudar, acoes }) {
    this.painel = painel;
    this.aviso = aviso;
    this.state = state;
    this.aoMudar = aoMudar;
    this.acoes = acoes;
    this.secoesFechadas = new Set(lerPreferencia("recorte_secoes_fechadas", ["legenda"]));
    this.painel.addEventListener("click", (evento) => this.aoClicar(evento));
    this.painel.addEventListener("change", (evento) => this.aoMudarCampo(evento));
    this.painel.addEventListener("input", (evento) => this.aoMudarCampo(evento));
    this.aviso.addEventListener("click", (evento) => {
      if (evento.target.closest("[data-limpar-recorte]")) this.limpar();
    });
  }

  get aberto() {
    return !this.painel.hidden;
  }

  alternar(forcar) {
    this.painel.hidden = forcar === undefined ? !this.painel.hidden : !forcar;
    document.querySelectorAll("[data-comando='alternar-recorte']").forEach((botao) => botao.classList.toggle("is-ativo", this.aberto));
    // Com o painel aberto, o aviso encolhe para não ficar escondido embaixo dele.
    this.painel.parentElement.classList.toggle("com-painel-recorte", this.aberto);
    if (this.aberto) this.render();
  }

  render() {
    this.renderAviso();
    if (!this.aberto) return;
    const r = this.state.recorte;
    this.painel.innerHTML = `
      <div class="controles-topo">
        <span>Recorte e exibição</span>
        <button class="clicavel-icone" data-fechar-painel title="Fechar">${icone("x", { tamanho: 14 })}</button>
      </div>
      ${this.montarSecao("filtros", "Recorte no servidor", `
        <div class="controle">
          <span class="controle-rotulo" title="Mostrar só a camada de navegação, cada contêiner com o progresso da sua subárvore">Agrupar em</span>
          <div class="segmentado">${NIVEIS_DE_COLAPSO.map((nivel) => `<button class="${r.colapsar === nivel.valor ? "is-ativo" : ""}" data-colapsar="${nivel.valor}">${nivel.rotulo}</button>`).join("")}</div>
        </div>
        ${this.montarAlternador("escopo", "Só o ativo", "Mantém o que está perto de tarefa não concluída ou dúvida aberta", Boolean(r.escopo))}
        ${r.escopo ? `
          <div class="controle mod-recuado">
            <span class="controle-rotulo">Raio <strong data-raio-valor>${r.raio}</strong> salto(s)</span>
            <input type="range" class="deslizador" min="0" max="3" step="1" value="${r.raio}" data-raio>
          </div>` : ""}
        ${this.montarAlternador("vista", "Caminho crítico", "Mostra apenas quem participa de alguma dependência declarada", Boolean(r.vista))}
        <button class="botao mod-pequeno mod-largo" data-limpar-recorte ${this.state.parametrosDeRecorte() ? "" : "disabled"}>Limpar recorte</button>
      `)}
      ${this.montarSecao("exibicao", "Exibição", `
        ${this.montarAlternador("arestas-sessao", "Arestas de sessão", "Desenha as arestas produz, da sessão até cada nó de trabalho", !this.state.hideStructuralEdges)}
        ${this.montarAlternador("minimapa", "Minimapa", "Mapa do grafo inteiro no canto do canvas", this.state.mostrarMinimapa)}
      `)}
      ${this.montarSecao("arranjo", "Arranjo", `
        <div class="bloco-botoes">
          <button class="botao mod-pequeno" data-arranjo="auto">${icone("workflow", { tamanho: 14 })} Auto-layout</button>
          <button class="botao mod-pequeno" data-arranjo="enquadrar">${icone("maximize", { tamanho: 14 })} Enquadrar</button>
        </div>
      `)}
      ${this.montarSecao("legenda", "Legenda", this.montarLegenda())}`;
  }

  montarSecao(chave, titulo, corpo) {
    const fechada = this.secoesFechadas.has(chave);
    return `
      <div class="controles-secao ${fechada ? "is-fechada" : ""}">
        <button class="controles-secao-titulo" data-secao="${chave}">${icone("chevron-down", { tamanho: 14 })}<span>${titulo}</span></button>
        ${fechada ? "" : `<div class="controles-secao-corpo">${corpo}</div>`}
      </div>`;
  }

  montarAlternador(chave, rotulo, descricao, ligado) {
    return `
      <label class="controle mod-alternador" title="${escapeHtml(descricao)}">
        <span class="controle-rotulo">${rotulo}</span>
        <span class="alternador"><input type="checkbox" data-alternar="${chave}" ${ligado ? "checked" : ""}><span class="alternador-trilho"></span></span>
      </label>`;
  }

  montarLegenda() {
    const contagem = new Map();
    for (const no of this.state.nodes.values()) contagem.set(no.tipo, (contagem.get(no.tipo) || 0) + 1);
    const tipos = [...contagem.keys()].sort((a, b) => contagem.get(b) - contagem.get(a));
    if (tipos.length === 0) return '<div class="secao-vazia">Canvas vazio.</div>';
    return `<div class="legenda">${tipos.map((tipo) => `
      <div class="legenda-item"><span class="legenda-cor" style="background:${corDoTipo(tipo)}"></span>${escapeHtml(apresentarTipo(tipo).nome)}<span class="texto-fraco">${contagem.get(tipo)}</span></div>`).join("")}</div>`;
  }

  renderAviso() {
    const info = this.state.recorteAplicado;
    if (!info || !info.total_oculto || this.state.isTimeTraveling) {
      this.aviso.hidden = true;
      return;
    }
    const filtros = (info.filtros || []).map((filtro) => NOMES_DOS_FILTROS[filtro] || filtro.replace(/_/g, " ").replace(/:raio /, ", raio ")).join(" + ");
    const orfaos = info.nos_orfaos || [];
    this.aviso.hidden = false;
    this.aviso.innerHTML = `
      ${icone("filter", { tamanho: 14 })}
      <span><strong>${info.total_exibido}</strong> de ${info.total_no_grafo} nós na tela · ${info.total_oculto} ocultos por <em>${escapeHtml(filtros)}</em>
      ${orfaos.length ? `<span class="aviso-orfaos" title="${escapeHtml(orfaos.join(", "))}"> · ${orfaos.length} fora da hierarquia</span>` : ""}</span>
      <button class="link-acao" data-limpar-recorte>Mostrar tudo</button>`;
  }

  aoClicar(evento) {
    const alvo = evento.target.closest("button");
    if (!alvo) return;
    if (alvo.dataset.fecharPainel !== undefined) this.alternar(false);
    else if (alvo.dataset.colapsar !== undefined) this.aplicar({ colapsar: alvo.dataset.colapsar });
    else if (alvo.dataset.secao) this.alternarSecao(alvo.dataset.secao);
    else if (alvo.dataset.limparRecorte !== undefined) this.limpar();
    else if (alvo.dataset.arranjo === "auto") this.acoes.autoLayout();
    else if (alvo.dataset.arranjo === "enquadrar") this.acoes.enquadrar();
  }

  aoMudarCampo(evento) {
    const alvo = evento.target;
    if (alvo.dataset.raio !== undefined) {
      this.painel.querySelector("[data-raio-valor]").textContent = alvo.value;
      if (evento.type === "change") this.aplicar({ raio: Number(alvo.value) });
      return;
    }
    if (evento.type !== "change" || !alvo.dataset.alternar) return;
    const acoesDosAlternadores = {
      escopo: () => this.aplicar({ escopo: alvo.checked ? "ativo" : "" }),
      vista: () => this.aplicar({ vista: alvo.checked ? "caminho_critico" : "" }),
      "arestas-sessao": () => this.acoes.alternarArestasDeSessao(),
      minimapa: () => this.acoes.alternarMinimapa(),
    };
    acoesDosAlternadores[alvo.dataset.alternar]?.();
  }

  alternarSecao(chave) {
    if (this.secoesFechadas.has(chave)) this.secoesFechadas.delete(chave);
    else this.secoesFechadas.add(chave);
    gravarPreferencia("recorte_secoes_fechadas", [...this.secoesFechadas]);
    this.render();
  }

  limpar() {
    this.aplicar({ colapsar: "", escopo: "", vista: "" });
  }

  aplicar(mudanca) {
    this.state.definirRecorte(mudanca);
    this.render();
    this.aoMudar();
  }
}
