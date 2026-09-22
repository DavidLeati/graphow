/**
 * Diálogos da memória de longo prazo: registrar um aprendizado e promovê-lo.
 *
 * Registrar é destilar o que sobrevive ao projeto a partir de nós que existem:
 * a origem é obrigatória, e o portão recusa o lote sem `deriva_de`, então o
 * diálogo só abre a partir de um nó de origem. Promover é o gesto humano que
 * dá alcance — um Projeto, um Setor ou o grafo inteiro — e é só depois dele
 * que o aprendizado entra na vista das outras tarefas.
 */
import { api } from "./api.js";
import { escapeHtml } from "./dom.js";
import { icone } from "./icones.js";
import { abrirModal, avisar } from "./modais.js";
import { apresentarTipo, corDoTipo } from "./ontologia_ui.js";

// Os tipos que o SchemaGate aceita como destino de `deriva_de` vindo de um Aprendizado.
export const TIPOS_DE_ORIGEM_DE_APRENDIZADO = new Set(["Evidence", "Decision", "Note", "Artifact", "Task"]);

const ROTULO_DO_GLOBAL = "Vale para tudo (global)";

export class DialogosDeMemoria {
  constructor({ state, indice, aoGravar }) {
    this.state = state;
    this.indice = indice;
    this.aoGravar = aoGravar;
  }

  get ramo() {
    return this.state.currentBranch;
  }

  /** Recibo do kernel vira aviso; sucesso também relê a tela. */
  async concluir(recibo, mensagemDeSucesso) {
    if (!recibo.sucesso) {
      avisar(`Recusado: ${recibo.mensagem || "falha desconhecida"}`, "erro");
      return false;
    }
    avisar(mensagemDeSucesso, "sucesso");
    await this.aoGravar();
    return true;
  }

  infoDoNo(id) {
    return this.state.nodes.get(id) || this.indice.no(id) || null;
  }

  /**
   * Registro a partir de um ou mais nós de origem. A sessão em que o aprendizado
   * nasce é a do primeiro nó de origem que a declara, ou a sessão aberta na tela.
   */
  registrar({ origens = [], sessaoId = null } = {}) {
    const nos = origens.map((id) => this.infoDoNo(id)).filter(Boolean);
    const validos = nos.filter((no) => TIPOS_DE_ORIGEM_DE_APRENDIZADO.has(no.tipo));
    if (validos.length === 0) {
      avisar("Registre um aprendizado a partir de uma Decision, Evidence, Note, Artifact ou Task: selecione o nó de origem.", "info");
      return;
    }
    const sessao = sessaoId || validos.find((no) => no.sessao_id)?.sessao_id || this.sessaoDaTela();
    if (!sessao) {
      avisar("Não dá para saber em que sessão o aprendizado nasce: abra a sessão do nó de origem.", "erro");
      return;
    }
    abrirModal({
      titulo: "Registrar aprendizado",
      largura: 560,
      corpo: this.montarFormularioDeRegistro(validos, sessao),
      botoes: [
        { rotulo: "Cancelar" },
        { rotulo: "Registrar", primario: true, acao: (modal) => this.enviarRegistro(modal, validos, sessao) },
      ],
    });
  }

  sessaoDaTela() {
    return this.state.escopo?.tipo === "Sessao" ? this.state.escopo.id : null;
  }

  montarFormularioDeRegistro(origens, sessao) {
    const chips = origens.map((no) => `
      <span class="chip-tipo" style="--cor-tipo:${corDoTipo(no.tipo)}" title="${escapeHtml(no.id)}">${icone(apresentarTipo(no.tipo).icone, { tamanho: 12 })}${escapeHtml(no.rotulo || no.id)}</span>`);
    const nomeDaSessao = this.indice.conteineres.get(sessao)?.rotulo || sessao;
    return `
      <label class="campo"><span class="campo-rotulo">Afirmação</span>
        <input type="text" class="entrada" data-campo="afirmacao" placeholder="Ex.: Lote com nó novo sem aresta de contenção é recusado inteiro"></label>
      <label class="campo"><span class="campo-rotulo">Como aplicar <span class="texto-fraco">(o que fazer com isto na próxima vez)</span></span>
        <textarea class="entrada mod-area" data-campo="como_aplicar" rows="3" placeholder="Ex.: Traga o produz ou o decompoe no mesmo lote que cria o nó"></textarea></label>
      <div class="campo"><span class="campo-rotulo">Como se sabe <span class="texto-fraco">(origem, aresta deriva_de)</span></span><div class="chips">${chips.join("")}</div></div>
      <p class="campo-nota">Nasce na sessão <strong>${escapeHtml(nomeDaSessao)}</strong> e vale só nela até ser promovido. Sem origem o portão recusa: memória sem origem é opinião com autoridade de memória.</p>`;
  }

  async enviarRegistro(modal, origens, sessao) {
    const afirmacao = modal.querySelector("[data-campo=afirmacao]").value.trim();
    if (!afirmacao) return false;
    const recibo = await api.registrarAprendizado({
      afirmacao,
      como_aplicar: modal.querySelector("[data-campo=como_aplicar]").value.trim(),
      id_sessao: sessao,
      origens: origens.map((no) => no.id),
      ramo_id: this.ramo,
    });
    return this.concluir(recibo, "Aprendizado registrado: promova-o para chegar às outras tarefas");
  }

  /**
   * Promoção: global, ou um Projeto ou Setor escolhido numa lista com busca.
   * Um <select> nativo cresce até a altura da tela quando há muitos contêineres;
   * a lista tem altura fixa, rola por dentro e agrupa cada Setor sob o seu Projeto.
   */
  promover(no) {
    if (!no) return;
    abrirModal({
      titulo: "Promover aprendizado",
      largura: 520,
      corpo: `
        <p class="inspetor-descricao">${escapeHtml(no.rotulo || no.id)}</p>
        <div class="campo"><label class="alternador-rotulado"><input type="checkbox" data-campo="global"><span class="alternador-trilho"></span><span>${ROTULO_DO_GLOBAL}</span></label></div>
        <div class="campo" data-bloco-alvo><span class="campo-rotulo">Ou vale para um contêiner</span>
          <input type="hidden" data-campo="alvo" value="">
          <input type="text" class="entrada mod-busca" data-busca-alvo placeholder="Filtrar Projetos e Setores…" autocomplete="off">
          <div class="lista-alvos" role="listbox" aria-label="Projetos e Setores" data-lista-alvos>${this.montarListaDeAlvos()}</div>
          <p class="lista-alvos-vazia" data-vazio hidden>Nenhum Projeto ou Setor com esse nome.</p>
        </div>
        <p class="campo-nota">Promovido, o aprendizado entra em <strong>Aprendizados Aplicáveis</strong> na vista de toda tarefa sob esse alcance. É gesto humano: nenhum agente promove, nem sob autonomia ilimitada.</p>`,
      botoes: [
        { rotulo: "Cancelar" },
        { rotulo: "Promover", primario: true, acao: (modal) => this.enviarPromocao(modal, no) },
      ],
      aoAbrir: (modal) => this.ligarListaDeAlvos(modal),
    });
  }

  /**
   * Projetos do índice, cada um com os seus Setores. Setor cujo pai não é um
   * Projeto conhecido vai para um grupo à parte, para não sumir da escolha.
   */
  gruposDePromocao() {
    const conteineres = [...this.indice.conteineres.values()];
    const grupos = new Map();
    for (const no of conteineres.filter((c) => c.tipo === "Projeto")) grupos.set(no.id, { projeto: no, setores: [] });
    const orfaos = [];
    for (const no of conteineres.filter((c) => c.tipo === "Setor")) {
      const grupo = grupos.get(this.indice.paiDe.get(no.id));
      (grupo ? grupo.setores : orfaos).push(no);
    }
    const porRotulo = (a, b) => (a.rotulo || a.id).localeCompare(b.rotulo || b.id, "pt-BR");
    const lista = [...grupos.values()].sort((a, b) => porRotulo(a.projeto, b.projeto));
    for (const grupo of lista) grupo.setores.sort(porRotulo);
    if (orfaos.length) lista.push({ projeto: null, setores: orfaos.sort(porRotulo) });
    return lista;
  }

  montarListaDeAlvos() {
    const item = (no, classe) => {
      const tipo = apresentarTipo(no.tipo);
      const rotulo = no.rotulo || no.id;
      return `<button type="button" class="lista-alvos-item ${classe}" role="option" aria-selected="false" tabindex="-1"
          data-alvo="${escapeHtml(no.id)}" data-texto="${escapeHtml(rotulo.toLowerCase())}" title="${escapeHtml(`${tipo.nome} · ${rotulo}`)}">
          <span class="lista-alvos-icone" style="color:${corDoTipo(no.tipo)}">${icone(tipo.icone, { tamanho: 13 })}</span>
          <span class="lista-alvos-rotulo">${escapeHtml(rotulo)}</span></button>`;
    };
    return this.gruposDePromocao().map(({ projeto, setores }) => `
      <div class="lista-alvos-grupo" data-grupo>
        ${projeto ? item(projeto, "mod-projeto") : '<div class="lista-alvos-cabeca">Setores sem Projeto</div>'}
        ${setores.map((setor) => item(setor, "mod-setor")).join("")}
      </div>`).join("");
  }

  /** Busca, escolha por clique ou setas, e o alternador global que desliga a lista. */
  ligarListaDeAlvos(modal) {
    const campo = modal.querySelector("[data-campo=alvo]");
    const busca = modal.querySelector("[data-busca-alvo]");
    const lista = modal.querySelector("[data-lista-alvos]");
    const vazio = modal.querySelector("[data-vazio]");
    const global = modal.querySelector("[data-campo=global]");
    const bloco = modal.querySelector("[data-bloco-alvo]");
    const visiveis = () => [...lista.querySelectorAll(".lista-alvos-item:not([hidden])")];

    const escolher = (botao, focar = false) => {
      for (const outro of lista.querySelectorAll("[aria-selected=true]")) outro.setAttribute("aria-selected", "false");
      campo.value = botao?.dataset.alvo || "";
      if (!botao) return;
      botao.setAttribute("aria-selected", "true");
      botao.scrollIntoView({ block: "nearest" });
      if (focar) botao.focus();
    };

    const filtrar = () => {
      const termo = busca.value.trim().toLowerCase();
      for (const grupo of lista.querySelectorAll("[data-grupo]")) {
        const projeto = grupo.querySelector(".mod-projeto");
        const setores = [...grupo.querySelectorAll(".mod-setor")];
        // Projeto que casa mostra todos os seus Setores; Setor que casa traz o Projeto junto, como contexto.
        const projetoCasa = !termo || (projeto?.dataset.texto.includes(termo) ?? false);
        let algumSetor = false;
        for (const setor of setores) {
          setor.hidden = !(projetoCasa || setor.dataset.texto.includes(termo));
          algumSetor ||= !setor.hidden;
        }
        if (projeto) projeto.hidden = !(projetoCasa || algumSetor);
        grupo.hidden = !(projetoCasa && projeto) && !algumSetor;
      }
      vazio.hidden = visiveis().length > 0;
    };

    busca.addEventListener("input", filtrar);
    busca.addEventListener("keydown", (evento) => {
      if (evento.key !== "ArrowDown") return;
      evento.preventDefault();
      const atual = lista.querySelector("[aria-selected=true]:not([hidden])");
      escolher(atual || visiveis()[0], true);
    });
    lista.addEventListener("click", (evento) => {
      const botao = evento.target.closest(".lista-alvos-item");
      if (botao) escolher(botao);
    });
    lista.addEventListener("keydown", (evento) => {
      const itens = visiveis();
      const posicao = itens.indexOf(document.activeElement);
      const destino = { ArrowDown: posicao + 1, ArrowUp: posicao - 1, Home: 0, End: itens.length - 1 }[evento.key];
      if (destino === undefined) return;
      evento.preventDefault();
      if (destino < 0) { busca.focus(); return; }
      escolher(itens[Math.min(destino, itens.length - 1)], true);
    });
    global.addEventListener("change", () => bloco.classList.toggle("mod-desligado", global.checked));
  }

  async enviarPromocao(modal, no) {
    const global = modal.querySelector("[data-campo=global]").checked;
    const alvo = modal.querySelector("[data-campo=alvo]").value;
    if (!global && !alvo) {
      avisar("Escolha o alcance: global, ou um Projeto ou Setor.", "info");
      return false;
    }
    const recibo = await api.promoverAprendizado({ id_aprendizado: no.id, id_alvo: alvo, global, ramo_id: this.ramo });
    const onde = global ? "todo o grafo" : this.indice.conteineres.get(alvo)?.rotulo || alvo;
    return this.concluir(recibo, `Aprendizado promovido: vale para ${onde}`);
  }
}
