/**
 * Diálogos que escrevem no grafo: criar nó, contêiner, aresta e ramo, e excluir.
 *
 * Três correções moram aqui. O contêiner novo nasce pendurado no pai no mesmo
 * lote (`contido_em`), em vez de nascer órfão. A aresta oferece primeiro os
 * tipos que o portão aceita para aquele par, lidos de `/api/ontologia`. E o nó
 * criado num ponto do canvas nasce naquele ponto, não no fim da pilha.
 */
import { api } from "./api.js";
import { escapeHtml } from "./dom.js";
import { icone } from "./icones.js";
import { abrirModal, avisar, confirmar, pedirTexto } from "./modais.js";
import {
  apresentarTipo, arestasPermitidas, corDoTipo, ehConteiner, lerAresta, niveisDeAutonomia,
  tiposDeAresta, tiposDeTrabalho,
} from "./ontologia_ui.js";

const PAI_DO_CONTEINER = { Setor: "Projeto", Sessao: "Setor" };
const STATUS_INICIAL = { Task: "pendente", Question: "aberta" };

// Numa dúvida o corpo não é uma descrição: é a pergunta, e o título é só a
// chamada que o card mostra. Sem esta separação a pergunta inteira ia para o
// rótulo e o cartão crescia até tapar o canvas.
const CORPO_POR_TIPO = {
  Question: {
    chave: "pergunta",
    rotulo: "Pergunta",
    nota: "o título é só a chamada",
    dica: "O contexto e a ambiguidade, por extenso.",
    exemploDeTitulo: "Ex.: Qual formato de autenticação usar?",
  },
};
const CORPO_PADRAO = {
  chave: "descricao",
  rotulo: "Descrição",
  nota: "opcional",
  dica: "",
  exemploDeTitulo: "Ex.: Implementar autenticação JWT",
};

const corpoDoTipo = (tipo) => CORPO_POR_TIPO[tipo] || CORPO_PADRAO;

// O id nasce aqui para a tela poder abrir o nó recém-criado: o recibo do kernel
// devolve os eventos gerados, não o id do que foi criado.
const novoIdDeNo = (tipo) => `${tipo.toLowerCase()}-${crypto.randomUUID().slice(0, 8)}`;

export class DialogosDoGrafo {
  constructor({ state, indice, aoGravar, eventoNaVersao, aoCriar, centroDoCanvas }) {
    this.state = state;
    this.indice = indice;
    this.aoGravar = aoGravar;
    this.eventoNaVersao = eventoNaVersao;
    this.aoCriar = aoCriar;
    this.centroDoCanvas = centroDoCanvas;
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

  opcoesDeSessao(selecionada) {
    const sessoes = this.indice.listar("Sessao");
    const opcoes = sessoes.map((sessao) => `<option value="${escapeHtml(sessao.id)}" ${sessao.id === selecionada ? "selected" : ""}>${escapeHtml(sessao.caminho)}</option>`);
    return `<option value="">(sem sessão — fica fora da hierarquia)</option>${opcoes.join("")}`;
  }

  sessaoSugerida() {
    const escopo = this.state.escopo;
    if (escopo?.tipo === "Sessao") return escopo.id;
    const selecionado = this.state.selectedElement?.type === "node" ? this.state.selectedElement.data : null;
    return selecionado?.tipo === "Sessao" ? selecionado.id : selecionado?.sessao_id || "";
  }

  novoNo({ tipo = "Task", x = null, y = null, sessaoId = null } = {}) {
    const tipos = tiposDeTrabalho();
    abrirModal({
      titulo: "Novo nó",
      corpo: `
        <div class="grade-tipos">${tipos.map((opcao) => `
          <label class="opcao-tipo" style="--cor-tipo:${corDoTipo(opcao)}" title="${escapeHtml(apresentarTipo(opcao).descricao)}">
            <input type="radio" name="tipo-no" value="${opcao}" ${opcao === tipo ? "checked" : ""}>
            <span>${icone(apresentarTipo(opcao).icone, { tamanho: 15 })}${escapeHtml(apresentarTipo(opcao).nome)}</span>
          </label>`).join("")}
        </div>
        <label class="campo"><span class="campo-rotulo">Título</span>
          <input type="text" class="entrada" data-campo="rotulo"></label>
        <label class="campo"><span class="campo-rotulo">Sessão</span>
          <select class="seletor" data-campo="sessao">${this.opcoesDeSessao(sessaoId ?? this.sessaoSugerida())}</select></label>
        <label class="campo"><span class="campo-rotulo" data-rotulo-corpo></span>
          <textarea class="entrada mod-area" data-campo="corpo" rows="3"></textarea></label>`,
      botoes: [
        { rotulo: "Cancelar" },
        { rotulo: "Criar nó", primario: true, acao: (modal) => this.enviarNovoNo(modal, { x, y }) },
      ],
      aoAbrir: (modal) => this.ligarCorpoDoTipo(modal),
    });
  }

  /** O campo de texto longo acompanha o tipo escolhido: numa dúvida ele é a pergunta. */
  ligarCorpoDoTipo(modal) {
    const aplicar = () => {
      const tipo = modal.querySelector("input[name=tipo-no]:checked")?.value || "Task";
      const corpo = corpoDoTipo(tipo);
      modal.querySelector("[data-rotulo-corpo]").innerHTML = `${escapeHtml(corpo.rotulo)} <span class="texto-fraco">(${escapeHtml(corpo.nota)})</span>`;
      modal.querySelector("[data-campo=corpo]").placeholder = corpo.dica;
      modal.querySelector("[data-campo=rotulo]").placeholder = corpo.exemploDeTitulo;
    };
    modal.addEventListener("change", aplicar);
    aplicar();
  }

  async enviarNovoNo(modal, { x, y }) {
    const campo = (nome) => modal.querySelector(`[data-campo=${nome}]`).value.trim();
    const tipo = modal.querySelector("input[name=tipo-no]:checked")?.value || "Task";
    const rotulo = campo("rotulo");
    if (!rotulo) {
      avisar("Dê um título ao nó.", "erro");
      return false;
    }
    const propriedades = {};
    if (STATUS_INICIAL[tipo]) propriedades.status = STATUS_INICIAL[tipo];
    if (campo("corpo")) propriedades[corpoDoTipo(tipo).chave] = campo("corpo");
    const ponto = x !== null && y !== null ? { x, y } : this.centroDoCanvas?.();
    if (ponto) Object.assign(propriedades, { pos_x: Math.round(ponto.x), pos_y: Math.round(ponto.y) });
    const id = novoIdDeNo(tipo);
    const recibo = await api.criarNo({ id_no: id, tipo, rotulo, propriedades, sessao_id: campo("sessao") || null, ramo_id: this.ramo });
    const criou = await this.concluir(recibo, `${apresentarTipo(tipo).nome} criado`);
    if (criou) this.aoCriar?.(id, { tipo, sessao_id: campo("sessao") || null });
    return criou;
  }

  novoConteiner({ tipo = "Projeto", paiId = null } = {}) {
    abrirModal({
      titulo: "Novo contêiner",
      corpo: `
        <div class="segmentado mod-largo" data-tipos>${["Projeto", "Setor", "Sessao"].map((opcao) => `
          <button type="button" class="${opcao === tipo ? "is-ativo" : ""}" data-tipo="${opcao}">${icone(apresentarTipo(opcao).icone, { tamanho: 14 })} ${apresentarTipo(opcao).nome}</button>`).join("")}
        </div>
        <label class="campo"><span class="campo-rotulo">Título</span><input type="text" class="entrada" data-campo="rotulo" placeholder="Ex.: Sprint 1"></label>
        <div data-bloco-pai></div>
        <div data-bloco-autonomia></div>`,
      botoes: [
        { rotulo: "Cancelar" },
        { rotulo: "Criar", primario: true, acao: (modal) => this.enviarNovoConteiner(modal) },
      ],
      aoAbrir: (modal) => {
        modal.dataset.tipo = tipo;
        modal.querySelector("[data-tipos]").addEventListener("click", (evento) => {
          const botao = evento.target.closest("[data-tipo]");
          if (!botao) return;
          modal.dataset.tipo = botao.dataset.tipo;
          modal.querySelectorAll("[data-tipo]").forEach((el) => el.classList.toggle("is-ativo", el === botao));
          this.preencherBlocosDoConteiner(modal, null);
        });
        this.preencherBlocosDoConteiner(modal, paiId);
      },
    });
  }

  preencherBlocosDoConteiner(modal, paiId) {
    const tipo = modal.dataset.tipo;
    const tipoDoPai = PAI_DO_CONTEINER[tipo];
    const candidatos = tipoDoPai ? this.indice.listar(tipoDoPai) : [];
    const sugerido = paiId || this.paiSugerido(tipoDoPai);
    modal.querySelector("[data-bloco-pai]").innerHTML = tipoDoPai ? `
      <label class="campo"><span class="campo-rotulo">Dentro de (${apresentarTipo(tipoDoPai).nome})</span>
        <select class="seletor" data-campo="pai">
          ${candidatos.length ? "" : `<option value="">Nenhum ${apresentarTipo(tipoDoPai).nome} existe ainda</option>`}
          ${candidatos.map((pai) => `<option value="${escapeHtml(pai.id)}" ${pai.id === sugerido ? "selected" : ""}>${escapeHtml(pai.caminho)}</option>`).join("")}
        </select></label>
      <p class="campo-nota">A aresta <code>contem</code> é criada no mesmo lote: se o portão recusar, nada é gravado.</p>` : "";
    modal.querySelector("[data-bloco-autonomia]").innerHTML = tipo === "Projeto" ? `
      <label class="campo"><span class="campo-rotulo">Autonomia dos agentes</span>
        <select class="seletor" data-campo="autonomia">${niveisDeAutonomia().map((nivel) => `<option value="${nivel}">${nivel === "estrito" ? "Estrita — cada papel cria só os seus tipos" : "Ilimitada — agentes criam qualquer tipo, menos Constraint"}</option>`).join("")}</select></label>
      <p class="campo-nota">Não concede Constraint, não encerra dúvidas e não libera <code>escopa</code> nem a remoção de <code>bloqueia</code>.</p>` : "";
  }

  paiSugerido(tipoDoPai) {
    if (!tipoDoPai) return null;
    const escopo = this.state.escopo;
    if (!escopo) return null;
    return this.indice.ancestrais(escopo.id).find((no) => no.tipo === tipoDoPai)?.id || null;
  }

  async enviarNovoConteiner(modal) {
    const tipo = modal.dataset.tipo;
    const rotulo = modal.querySelector("[data-campo=rotulo]").value.trim();
    const pai = modal.querySelector("[data-campo=pai]")?.value || null;
    if (!rotulo) {
      avisar("Dê um título ao contêiner.", "erro");
      return false;
    }
    if (PAI_DO_CONTEINER[tipo] && !pai) {
      avisar(`Um ${apresentarTipo(tipo).nome} precisa estar dentro de um ${apresentarTipo(PAI_DO_CONTEINER[tipo]).nome}.`, "erro");
      return false;
    }
    const propriedades = tipo === "Projeto" ? { nivel_autonomia: modal.querySelector("[data-campo=autonomia]").value } : {};
    const id = novoIdDeNo(tipo);
    const recibo = await api.criarNo({ id_no: id, tipo, rotulo, propriedades, contido_em: pai, ramo_id: this.ramo });
    const criou = await this.concluir(recibo, `${apresentarTipo(tipo).nome} “${rotulo}” criado`);
    if (criou) this.aoCriar?.(id, { tipo });
    return criou;
  }

  novaAresta(origemId, destinoId) {
    const pontas = { origem: origemId, destino: destinoId };
    const controle = abrirModal({
      titulo: "Nova aresta",
      corpo: '<div data-aresta></div>',
      botoes: [
        { rotulo: "Cancelar" },
        { rotulo: "Criar aresta", primario: true, acao: (modal) => this.enviarNovaAresta(modal, pontas) },
      ],
    });
    this.preencherAresta(controle.elemento, pontas);
  }

  preencherAresta(modal, pontas) {
    const [origem, destino] = [pontas.origem, pontas.destino].map((id) => this.state.nodes.get(id) || this.indice.info.get(id) || { id, tipo: "?", rotulo: id });
    const permitidas = arestasPermitidas(origem.tipo, destino.tipo);
    const demais = tiposDeAresta().filter((tipo) => !permitidas.includes(tipo));
    const opcao = (tipo) => `<option value="${tipo}">${tipo} — ${escapeHtml(lerAresta(tipo).descricao)}</option>`;
    const ponta = (no) => `<div class="ponta-aresta mod-estatica"><span class="conexao-icone" style="color:${corDoTipo(no.tipo)}">${icone(apresentarTipo(no.tipo).icone, { tamanho: 15 })}</span><span class="ponta-texto"><span class="ponta-tipo">${escapeHtml(apresentarTipo(no.tipo).nome)}</span><span class="ponta-rotulo">${escapeHtml(no.rotulo)}</span></span></div>`;
    modal.querySelector("[data-aresta]").innerHTML = `
      <div class="aresta-pontas">${ponta(origem)}<button class="botao mod-pequeno" data-inverter title="Inverter a direção">${icone("refresh", { tamanho: 13 })} Inverter</button>${ponta(destino)}</div>
      <label class="campo"><span class="campo-rotulo">Tipo de relação</span>
        <select class="seletor" data-campo="tipo">
          ${permitidas.length ? `<optgroup label="Aceitas para ${escapeHtml(apresentarTipo(origem.tipo).nome)} → ${escapeHtml(apresentarTipo(destino.tipo).nome)}">${permitidas.map(opcao).join("")}</optgroup>` : ""}
          <optgroup label="${permitidas.length ? "Demais tipos (o portão vai recusar)" : "Nenhum tipo é aceito para este par"}">${demais.map(opcao).join("")}</optgroup>
        </select></label>
      ${permitidas.length ? "" : '<p class="campo-nota mod-alerta">A ontologia não prevê aresta nenhuma entre estes dois tipos. Tente inverter a direção.</p>'}`;
    modal.querySelector("[data-inverter]").addEventListener("click", () => {
      [pontas.origem, pontas.destino] = [pontas.destino, pontas.origem];
      this.preencherAresta(modal, pontas);
    });
  }

  async enviarNovaAresta(modal, pontas) {
    const tipo = modal.querySelector("[data-campo=tipo]").value;
    const recibo = await api.criarAresta({ origem_id: pontas.origem, destino_id: pontas.destino, tipo, ramo_id: this.ramo });
    return this.concluir(recibo, `Aresta ${tipo} criada`);
  }

  criarFork() {
    const versao = this.state.logVersion;
    const evento = this.state.isTimeTraveling ? this.eventoNaVersao(versao) : null;
    const ponto = evento ? `o evento <strong>#${versao}</strong> que você está vendo` : `o fim atual do log (<strong>#${versao}</strong>)`;
    abrirModal({
      titulo: "Novo ramo (fork)",
      corpo: `
        <label class="campo"><span class="campo-rotulo">Nome do ramo</span><input type="text" class="entrada" data-campo="nome" placeholder="Ex.: experimento-v2"></label>
        <p class="campo-nota">O ramo herda o histórico de <code>${escapeHtml(this.ramo)}</code> até ${ponto}, como ponteiro — sem copiar o prefixo.</p>`,
      botoes: [
        { rotulo: "Cancelar" },
        {
          rotulo: "Criar ramo",
          primario: true,
          acao: async (modal) => {
            const nome = modal.querySelector("[data-campo=nome]").value.trim();
            if (!nome) return false;
            const recibo = await api.criarFork({ novo_ramo: nome, ramo_origem: this.ramo, evento_id_ponto_corte: evento?.id || null });
            if (!recibo.sucesso) {
              avisar(`Falha ao criar o ramo: ${recibo.mensagem}`, "erro");
              return false;
            }
            avisar(`Ramo “${nome}” criado`, "sucesso");
            await this.aoGravar({ ramoNovo: nome });
            return true;
          },
        },
      ],
    });
  }

  async renomear(no) {
    const rotulo = await pedirTexto({ titulo: `Renomear ${apresentarTipo(no.tipo).nome}`, rotulo: "Novo título", valorInicial: no.rotulo });
    if (!rotulo || rotulo === no.rotulo) return;
    const recibo = await api.editarNo({ id_no: no.id, novo_rotulo: rotulo, novas_propriedades: {}, ramo_id: this.ramo });
    await this.concluir(recibo, "Renomeado");
  }

  async mudarPropriedade(no, chave, valor, mensagem) {
    const recibo = await api.editarNo({ id_no: no.id, novas_propriedades: { [chave]: valor }, ramo_id: this.ramo });
    return this.concluir(recibo, mensagem);
  }

  async excluirNo(no) {
    if (no.tipo === "Projeto") return this.excluirProjeto(no);
    const aviso = ehConteiner(no.tipo) ? "<br><br>O que ele contém <strong>não</strong> é removido junto e fica fora da hierarquia." : "";
    const ok = await confirmar({ titulo: `Excluir ${apresentarTipo(no.tipo).nome}`, mensagem: `Remover <strong>${escapeHtml(no.rotulo)}</strong> do grafo?${aviso}`, rotuloConfirmar: "Excluir", perigo: true });
    if (!ok) return false;
    const recibo = await api.remover({ tipo: "nos", id: no.id, ramo_id: this.ramo });
    return this.concluir(recibo, "Nó removido");
  }

  async excluirAresta(aresta) {
    if (!aresta) return false;
    const ok = await confirmar({ titulo: "Remover aresta", mensagem: `Remover a aresta <code>${escapeHtml(aresta.tipo)}</code> (<code>${escapeHtml(aresta.id)}</code>)?`, rotuloConfirmar: "Remover", perigo: true });
    if (!ok) return false;
    const recibo = await api.remover({ tipo: "arestas", id: aresta.id, ramo_id: this.ramo });
    return this.concluir(recibo, "Aresta removida");
  }

  async excluirProjeto(no) {
    const total = (no.resumo || this.indice.conteineres.get(no.id)?.resumo)?.total_nos;
    const ok = await confirmar({
      titulo: "Excluir projeto em cascata",
      mensagem: `Apagar <strong>${escapeHtml(no.rotulo)}</strong> e tudo que pende dele${total ? ` — <strong>${total} nós</strong>` : ""}: setores, sessões, tarefas e arestas.<br><br>O log guarda a remoção, mas o grafo atual perde tudo isso de uma vez.`,
      rotuloConfirmar: "Excluir tudo",
      perigo: true,
    });
    if (!ok) return false;
    const recibo = await api.removerProjeto({ id_projeto: no.id, ramo_id: this.ramo });
    return this.concluir(recibo, "Projeto excluído");
  }

  exclusaoEmLote() {
    const nos = [...this.state.nodes.values()];
    if (nos.length === 0) {
      avisar("Nenhum nó no escopo atual.", "info");
      return;
    }
    const linhas = nos.map((no) => `
      <label class="linha-lote" data-texto="${escapeHtml(`${no.rotulo} ${no.id} ${no.tipo}`.toLowerCase())}">
        <input type="checkbox" value="${escapeHtml(no.id)}">
        <span class="conexao-icone" style="color:${corDoTipo(no.tipo)}">${icone(apresentarTipo(no.tipo).icone, { tamanho: 14 })}</span>
        <span class="linha-lote-rotulo">${escapeHtml(no.rotulo)}</span><code>${escapeHtml(no.id)}</code>
      </label>`).join("");
    abrirModal({
      titulo: "Exclusão em lote",
      largura: 620,
      corpo: `
        <div class="lote-topo"><input type="search" class="entrada mod-busca" data-filtro placeholder="Filtrar por título, tipo ou ID…"><label class="alternador-rotulado"><input type="checkbox" data-todos><span>Marcar os visíveis</span></label></div>
        <div class="lote-lista">${linhas}</div>
        <p class="campo-nota" data-contagem>0 selecionados · o lote é atômico: ou tudo sai, ou nada sai.</p>`,
      botoes: [
        { rotulo: "Cancelar" },
        { rotulo: "Excluir selecionados", primario: true, perigo: true, acao: (modal) => this.enviarLote(modal) },
      ],
      aoAbrir: (modal) => this.ligarLote(modal),
    });
  }

  ligarLote(modal) {
    const atualizar = () => {
      const total = modal.querySelectorAll(".lote-lista input:checked").length;
      modal.querySelector("[data-contagem]").textContent = `${total} selecionados · o lote é atômico: ou tudo sai, ou nada sai.`;
    };
    modal.querySelector("[data-filtro]").addEventListener("input", (evento) => {
      const termo = evento.target.value.toLowerCase();
      modal.querySelectorAll(".linha-lote").forEach((linha) => { linha.hidden = !linha.dataset.texto.includes(termo); });
    });
    modal.querySelector("[data-todos]").addEventListener("change", (evento) => {
      modal.querySelectorAll(".linha-lote:not([hidden]) input").forEach((caixa) => { caixa.checked = evento.target.checked; });
      atualizar();
    });
    modal.querySelector(".lote-lista").addEventListener("change", atualizar);
  }

  async enviarLote(modal) {
    const ids = [...modal.querySelectorAll(".lote-lista input:checked")].map((caixa) => caixa.value);
    if (ids.length === 0) {
      avisar("Nenhum nó selecionado.", "info");
      return false;
    }
    const ok = await confirmar({ titulo: "Confirmar exclusão", mensagem: `Remover <strong>${ids.length}</strong> nós num único lote?`, rotuloConfirmar: "Excluir", perigo: true });
    if (!ok) return false;
    const recibo = await api.removerLote({ ids_nos: ids, ids_arestas: [], ramo_id: this.ramo });
    return this.concluir(recibo, `${ids.length} nós removidos`);
  }
}
