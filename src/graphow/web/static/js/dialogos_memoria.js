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

  /** Promoção: global, ou um Projeto ou Setor escolhido entre os contêineres do índice. */
  promover(no) {
    if (!no) return;
    const alvos = this.alvosDePromocao();
    const opcoes = alvos.map((alvo) => `<option value="${escapeHtml(alvo.id)}">${escapeHtml(alvo.texto)}</option>`).join("");
    abrirModal({
      titulo: "Promover aprendizado",
      largura: 520,
      corpo: `
        <p class="inspetor-descricao">${escapeHtml(no.rotulo || no.id)}</p>
        <div class="campo"><label class="alternador-rotulado"><input type="checkbox" data-campo="global"><span class="alternador-trilho"></span><span>${ROTULO_DO_GLOBAL}</span></label></div>
        <label class="campo"><span class="campo-rotulo">Ou vale para um contêiner</span>
          <select class="seletor" data-campo="alvo"><option value="">— escolha um Projeto ou Setor —</option>${opcoes}</select></label>
        <p class="campo-nota">Promovido, o aprendizado entra em <strong>Aprendizados Aplicáveis</strong> na vista de toda tarefa sob esse alcance. É gesto humano: nenhum agente promove, nem sob autonomia ilimitada.</p>`,
      botoes: [
        { rotulo: "Cancelar" },
        { rotulo: "Promover", primario: true, acao: (modal) => this.enviarPromocao(modal, no) },
      ],
    });
  }

  /** Projetos e Setores do índice, com o Projeto ao lado do Setor para não haver dois "Memoria" iguais. */
  alvosDePromocao() {
    const conteineres = [...this.indice.conteineres.values()];
    return conteineres
      .filter((no) => no.tipo === "Projeto" || no.tipo === "Setor")
      .map((no) => {
        const pai = no.tipo === "Setor" ? this.indice.conteineres.get(this.indice.paiDe.get(no.id)) : null;
        const contexto = pai ? ` (${pai.rotulo})` : "";
        return { id: no.id, texto: `${apresentarTipo(no.tipo).nome} · ${no.rotulo}${contexto}` };
      });
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
