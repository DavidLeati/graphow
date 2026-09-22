/**
 * Inspetor: o painel de propriedades do nó ou da aresta selecionada.
 *
 * Num grafo cujo centro é o canvas, reúne o que se sabe do nó: título editável,
 * caminho até a raiz, a tabela de propriedades, as conexões visíveis e a idade.
 * Salvar é explícito de propósito — cada gravação é um patch que atravessa os
 * quatro portões e vira evento permanente no log, e um salvamento a cada tecla
 * encheria o log de rascunho. Sem seleção, o painel mostra o panorama do escopo.
 */
import { api } from "./api.js";
import { TIPOS_DE_ORIGEM_DE_APRENDIZADO } from "./dialogos_memoria.js";
import { copiarTexto, escapeHtml } from "./dom.js";
import { icone } from "./icones.js";
import { foiAlterado, formatarDataCompleta, formatarIdadeRelativa } from "./idade.js";
import { AMBITO_DO_HOOK, AMBITO_DOS_PROJETOS, ESCOPO_DO_HOOK, ehEscopoDoHook } from "./indice_navegacao.js";
import { avisar } from "./modais.js";
import {
  apresentarStatus, apresentarTipo, corDaAresta, corDoTipo, ehConteiner, lerAresta,
  niveisDeAutonomia, statusDoTipo, tomDoStatus,
} from "./ontologia_ui.js";
import {
  ajustarAltura, CHAVES_OCULTAS, interpretarValorNovo, lerValorDaLinha,
  montarLinhaDePropriedade, ordenarChaves, valoresIguais,
} from "./propriedades_editor.js";

const MAXIMO_DE_CONEXOES_NO_RESUMO = 6;

// Propriedades que o bloco do tipo já edita com um controle próprio.
const CHAVES_DO_BLOCO = { Task: ["status"], Question: ["status", "pergunta", "resposta"], Projeto: ["nivel_autonomia"], Sessao: ["status", "resumo"], Aprendizado: ["como_aplicar", "alcance", "valido_ate"] };

// O mesmo teto que `abrir_questao` aplica no servidor, para o título derivado
// aqui sair igual ao que o agente teria mandado.
const LIMITE_DO_TITULO_DA_QUESTAO = 80;

/** Reduz o corpo da pergunta ao título curto que o card exibe. */
function resumirEmTitulo(texto) {
  const primeiraLinha = texto.split(/\r?\n/).map((linha) => linha.trim()).find(Boolean) || "";
  if (primeiraLinha.length <= LIMITE_DO_TITULO_DA_QUESTAO) return primeiraLinha;
  const corte = primeiraLinha.slice(0, LIMITE_DO_TITULO_DA_QUESTAO).replace(/\s+\S*$/, "").replace(/[\s,;:.-]+$/, "");
  return `${corte || primeiraLinha.slice(0, LIMITE_DO_TITULO_DA_QUESTAO)}…`;
}

export class InspectorView {
  constructor(raiz, { state, indice, acoes }) {
    this.raiz = raiz;
    this.state = state;
    this.indice = indice;
    this.acoes = acoes;
    this.noRenderizado = null;
    this.sujo = false;
    this.secoesFechadas = new Set(["historico"]);
    this.raiz.addEventListener("input", (evento) => this.aoEditar(evento));
    this.raiz.addEventListener("change", (evento) => this.aoEditar(evento));
    this.raiz.addEventListener("click", (evento) => this.aoClicar(evento));
    this.raiz.addEventListener("keydown", (evento) => this.aoTeclar(evento));
    this.raiz.addEventListener("toggle", (evento) => this.aoAlternarSecao(evento), true);
  }

  render() {
    // Durante o salvamento a releitura chega antes do recibo; quem redesenha é o salvar.
    if (this.salvando) return;
    const selecao = this.state.selectedElement;
    if (!selecao || !selecao.data) {
      this.noRenderizado = null;
      this.sujo = false;
      this.renderPanorama();
      return;
    }
    if (selecao.type === "edge") {
      this.noRenderizado = null;
      this.renderAresta(this.state.edges.get(selecao.id) || selecao.data);
      return;
    }
    const no = this.state.nodes.get(selecao.id) || selecao.data;
    if (this.sujo && this.noRenderizado?.id === no.id) {
      this.avisarMudancaExterna(no);
      return;
    }
    this.renderNo(no);
  }

  // ---------------------------------------------------------------- nó

  renderNo(no) {
    const tipo = apresentarTipo(no.tipo);
    const somenteLeitura = this.state.isTimeTraveling;
    const fora = !this.state.nodes.has(no.id);
    this.noRenderizado = no;
    this.sujo = false;
    const marcado = this.acoes.ehMarcador(no.id);
    this.raiz.innerHTML = `
      <div class="inspetor">
        ${somenteLeitura ? `<div class="chamada mod-info">${icone("history", { tamanho: 14 })}<span>Vendo o log em #${this.state.logVersion}: somente leitura.</span></div>` : ""}
        ${fora ? `<div class="chamada mod-neutra">${icone("eye-off", { tamanho: 14 })}<span>Este nó não está no canvas atual.</span></div>` : ""}
        <div class="inspetor-topo">
          <span class="pilula-tipo" style="--cor-tipo:${corDoTipo(no.tipo)}">${icone(tipo.icone, { tamanho: 13 })}${escapeHtml(tipo.nome)}</span>
          <button class="inspetor-id" data-acao="copiar-id" title="Copiar o ID">${escapeHtml(no.id)}</button>
          <span class="espacador"></span>
          <button class="clicavel-icone ${marcado ? "is-ativo" : ""}" data-acao="marcar" title="${marcado ? "Remover dos marcadores" : "Fixar nos marcadores"}">${icone("bookmark")}</button>
          <button class="clicavel-icone" data-acao="focar" title="Centralizar no canvas">${icone("crosshair")}</button>
          <button class="clicavel-icone" data-acao="menu" title="Mais ações">${icone("more-horizontal")}</button>
        </div>
        <textarea class="inspetor-titulo" data-campo-rotulo rows="1" spellcheck="false" ${somenteLeitura ? "disabled" : ""}>${escapeHtml(no.rotulo)}</textarea>
        ${this.montarCaminho(no)}
        ${this.montarAlertas(no)}
        ${this.montarBlocoDoTipo(no, somenteLeitura)}
        ${this.montarSecaoPropriedades(no, somenteLeitura)}
        ${this.montarSecaoConexoes(no)}
        ${this.montarSecaoHistorico(no)}
        <div class="inspetor-rodape" data-rodape hidden>
          <span class="inspetor-rodape-texto" data-rodape-texto>Alterações não salvas</span>
          <button class="botao" data-acao="descartar">Descartar</button>
          <button class="botao mod-cta" data-acao="salvar">Salvar</button>
        </div>
      </div>`;
    this.raiz.querySelectorAll("textarea").forEach((campo) => ajustarAltura(campo));
    if (no.tipo === "Aprendizado") this.completarAprendizado(no);
  }

  montarCaminho(no) {
    const cadeia = this.indice.ancestrais(no.id).filter((anc) => anc.id !== no.id);
    if (cadeia.length === 0) return "";
    const partes = cadeia.map(
      (anc) => `<button class="caminho-parte" data-acao="abrir-escopo" data-id="${escapeHtml(anc.id)}" title="Abrir ${escapeHtml(apresentarTipo(anc.tipo).nome)} no canvas">${escapeHtml(anc.rotulo)}</button>`
    );
    return `<div class="inspetor-caminho">${partes.join('<span class="caminho-separador">/</span>')}</div>`;
  }

  montarAlertas(no) {
    const alertas = [];
    if (no.esta_bloqueado) {
      const questoes = [...this.state.edges.values()].filter((a) => a.tipo === "bloqueia" && a.destino_id === no.id);
      const links = questoes.map((a) => this.montarLinkDeNo(a.origem_id)).join(" ");
      alertas.push(`<div class="chamada mod-alerta">${icone("alert-triangle", { tamanho: 14 })}<span>Bloqueada por dúvida aberta. ${links}</span></div>`);
    }
    if (no.lock_ativo) {
      alertas.push(`<div class="chamada mod-aviso">${icone("lock", { tamanho: 14 })}<span>Em posse de <strong>${escapeHtml(no.lock_ativo)}</strong>: só esse agente move o status.</span></div>`);
    }
    return alertas.join("");
  }

  montarBlocoDoTipo(no, somenteLeitura) {
    const desabilitado = somenteLeitura ? "disabled" : "";
    return `${this.montarBlocoEspecifico(no, desabilitado)}${this.montarConviteDeAprendizado(no, desabilitado)}`;
  }

  montarBlocoEspecifico(no, desabilitado) {
    if (no.tipo === "Task") return this.montarCampoDeStatus(no, desabilitado);
    if (no.tipo === "Question") return this.montarBlocoDaQuestao(no, desabilitado);
    if (no.tipo === "Projeto") return this.montarBlocoDoProjeto(no, desabilitado);
    if (no.tipo === "Sessao") return this.montarBlocoDaSessao(no, desabilitado);
    if (no.tipo === "Aprendizado") return this.montarBlocoDoAprendizado(no, desabilitado);
    if (ehConteiner(no.tipo)) return this.montarResumoDoConteiner(no);
    return "";
  }

  /**
   * Encerrar a sessão é o gesto que separa a memória de curto prazo da de longo
   * prazo: a vista dela passa a abrir pelo fechamento e o grafo pede a
   * condensação. Status e resumo estavam escondidos da tabela genérica sem
   * ganhar controle próprio, e só o menu de contexto alcançava o status.
   */
  montarBlocoDaSessao(no, desabilitado) {
    const encerrada = no.propriedades?.status === "concluida";
    return `
      ${this.montarCampoDeStatus(no, desabilitado)}
      ${this.montarCampoDeTexto({
        chave: "resumo",
        rotulo: "Resumo da sessão",
        icone: "align-left",
        valor: no.propriedades?.resumo || "",
        dica: "O que a sessão produziu, em uma ou duas frases…",
        desabilitado,
      })}
      <div class="bloco-nota">${encerrada ? "Encerrada: a vista dela abre pelo fechamento determinístico, e o grafo pediu a condensação." : "Ao encerrar, a vista passa a abrir pelo fechamento e o grafo abre a Task de condensação."}</div>
      ${this.montarResumoDoConteiner(no)}`;
  }

  /**
   * Afirmação no título, como aplicar no corpo, alcance e origem lidos das
   * arestas. O canvas é um recorte: o Setor promovido ou a Evidence de outra
   * sessão podem estar fora dele, então o bloco nasce com o que está na tela e
   * `completarAprendizado` o refaz com a ficha inteira do nó, como as conexões.
   */
  montarBlocoDoAprendizado(no, desabilitado) {
    const arestas = [...this.state.edges.values()];
    const saidas = arestas.filter((a) => a.origem_id === no.id).map((a) => ({ tipo: a.tipo, vizinho: a.destino_id }));
    const entradas = arestas.filter((a) => a.destino_id === no.id).map((a) => ({ tipo: a.tipo, vizinho: a.origem_id }));
    return `
      <div data-bloco="marcas">${this.montarMarcasDoAprendizado(entradas)}</div>
      ${this.montarCampoDeTexto({
        chave: "como_aplicar",
        rotulo: "Como aplicar",
        icone: "corner-down-right",
        valor: no.propriedades?.como_aplicar || "",
        dica: "O que fazer com isto na próxima vez…",
        desabilitado,
      })}
      <div class="bloco-campo mod-coluna">
        <span class="bloco-campo-rotulo">${icone("zap", { tamanho: 14 })} Alcance</span>
        <div class="bloco-nota" data-bloco="alcance">${this.montarAlcanceDoAprendizado(no, saidas)}</div>
        ${desabilitado ? "" : `<button class="botao" data-acao="promover">${icone("lightbulb", { tamanho: 14 })} Promover…</button>`}
      </div>
      <div class="bloco-campo mod-coluna">
        <span class="bloco-campo-rotulo">${icone("route", { tamanho: 14 })} Como se sabe</span>
        <div class="bloco-nota" data-bloco="origem">${this.montarOrigemDoAprendizado(saidas)}</div>
      </div>
      ${this.montarCampoCurto({ chave: "valido_ate", rotulo: "Válido até", icone: "clock", valor: no.propriedades?.valido_ate || "", dica: "Opcional, ISO 8601: vencido, sai da vista", desabilitado })}`;
  }

  montarAlcanceDoAprendizado(no, saidas) {
    const alcances = saidas.filter((a) => a.tipo === "vale_para").map((a) => this.montarLinkDeNo(a.vizinho));
    if (no.propriedades?.alcance === "global") alcances.unshift("<strong>vale para tudo</strong>");
    return alcances.length ? alcances.join(", ") : "Só a sessão em que nasceu. Promover é gesto humano e dá alcance a um Projeto, um Setor ou a tudo.";
  }

  montarOrigemDoAprendizado(saidas) {
    const origens = saidas.filter((a) => a.tipo === "deriva_de").map((a) => this.montarLinkDeNo(a.vizinho));
    return origens.length ? origens.join(", ") : "Sem origem visível: um aprendizado sem deriva_de não passa no portão.";
  }

  montarMarcasDoAprendizado(entradas) {
    const substituto = entradas.find((a) => a.tipo === "substitui");
    const contradicoes = entradas.filter((a) => a.tipo === "contradiz");
    return `
      ${substituto ? `<div class="chamada mod-alerta">${icone("alert-triangle", { tamanho: 14 })}<span>Substituído por ${this.montarLinkDeNo(substituto.vizinho)}: não siga esta nota.</span></div>` : ""}
      ${contradicoes.length ? `<div class="chamada mod-aviso">${icone("flask", { tamanho: 14 })}<span>Contradito por ${contradicoes.map((a) => this.montarLinkDeNo(a.vizinho)).join(", ")}: precisa de revisão.</span></div>` : ""}`;
  }

  /** A ficha do nó traz as arestas que o recorte do canvas não mostra; o bloco é refeito em silêncio. */
  async completarAprendizado(no) {
    const resposta = await api.expandir(no.id, this.state.currentBranch);
    if (!resposta.sucesso || this.noRenderizado?.id !== no.id) return;
    const saidas = (resposta.no.arestas_saida || []).map((a) => ({ tipo: a.tipo, vizinho: a.destino }));
    const entradas = (resposta.no.arestas_entrada || []).map((a) => ({ tipo: a.tipo, vizinho: a.origem }));
    const blocos = {
      marcas: this.montarMarcasDoAprendizado(entradas),
      alcance: this.montarAlcanceDoAprendizado(no, saidas),
      origem: this.montarOrigemDoAprendizado(saidas),
    };
    for (const [chave, html] of Object.entries(blocos)) {
      const alvo = this.raiz.querySelector(`[data-bloco=${chave}]`);
      if (alvo) alvo.innerHTML = html;
    }
  }

  /** Todo nó que pode ser origem de um aprendizado convida a registrá-lo dali. */
  montarConviteDeAprendizado(no, desabilitado) {
    if (desabilitado || !TIPOS_DE_ORIGEM_DE_APRENDIZADO.has(no.tipo)) return "";
    return `<button class="link-acao" data-acao="registrar-aprendizado">${icone("lightbulb", { tamanho: 13 })} Registrar aprendizado a partir deste nó</button>`;
  }

  /** Campo de uma linha de uma propriedade que o bloco do tipo já trata. */
  montarCampoCurto({ chave, rotulo, icone: nomeDoIcone, valor, dica, desabilitado }) {
    return `
      <div class="bloco-campo">
        <span class="bloco-campo-rotulo">${icone(nomeDoIcone, { tamanho: 14 })} ${escapeHtml(rotulo)}</span>
        <input type="text" class="entrada" data-prop="${escapeHtml(chave)}" data-original="${escapeHtml(valor)}" value="${escapeHtml(valor)}" placeholder="${escapeHtml(dica)}" ${desabilitado}>
      </div>`;
  }

  montarCampoDeStatus(no, desabilitado) {
    const opcoes = statusDoTipo(no.tipo) || [];
    const atual = no.propriedades?.status || "";
    const lista = atual && !opcoes.includes(atual) ? [atual, ...opcoes] : opcoes;
    return `
      <div class="bloco-campo">
        <span class="bloco-campo-rotulo">${icone("circle-dot", { tamanho: 14 })} Status</span>
        <select class="seletor mod-status tom-${tomDoStatus(atual)}" data-prop="status" data-original="${escapeHtml(atual)}" ${desabilitado}>
          ${atual ? "" : '<option value="" selected>—</option>'}
          ${lista.map((valor) => `<option value="${escapeHtml(valor)}" ${valor === atual ? "selected" : ""}>${escapeHtml(apresentarStatus(valor))}</option>`).join("")}
        </select>
      </div>`;
  }

  /**
   * A dúvida tem três partes: o título, que é o rótulo e o que o card mostra; o
   * corpo, na propriedade `pergunta`; e a resposta humana. A pergunta inteira
   * morava no rótulo, e um card com vinte linhas de texto tapava o canvas.
   */
  montarBlocoDaQuestao(no, desabilitado) {
    const aberta = (no.propriedades?.status || "aberta") === "aberta";
    const bloqueadas = [...this.state.edges.values()].filter((a) => a.tipo === "bloqueia" && a.origem_id === no.id);
    const alvo = bloqueadas.length ? `<div class="bloco-nota">Bloqueia: ${bloqueadas.map((a) => this.montarLinkDeNo(a.destino_id)).join(" ")}</div>` : "";
    return `
      ${this.montarCampoDeStatus(no, desabilitado)}
      ${this.montarCampoDeTexto({
        chave: "pergunta",
        rotulo: "Pergunta",
        icone: "help-circle",
        valor: no.propriedades?.pergunta || "",
        dica: "O contexto e a ambiguidade, por extenso — o título acima é só a chamada.",
        desabilitado,
      })}
      ${this.montarCampoDeTexto({
        chave: "resposta",
        rotulo: "Resposta humana",
        icone: "corner-down-right",
        valor: no.propriedades?.resposta || "",
        dica: "Escreva a resposta que destrava a tarefa…",
        desabilitado,
      })}
      ${this.montarConviteDeSeparacao(no, desabilitado)}
      ${alvo}
      ${aberta && !desabilitado ? '<button class="botao mod-cta mod-largo" data-acao="responder">Responder e destravar</button>' : ""}`;
  }

  /**
   * Dúvida aberta antes da separação traz o texto inteiro no título. O convite
   * move o corpo para `pergunta` e encurta o título, mas deixa como alteração
   * pendente: quem confirma é a pessoa, pelo Salvar.
   */
  montarConviteDeSeparacao(no, desabilitado) {
    const corpoVazio = !(no.propriedades?.pergunta || "").trim();
    const tituloLongo = (no.rotulo || "").length > LIMITE_DO_TITULO_DA_QUESTAO;
    if (desabilitado || !corpoVazio || !tituloLongo) return "";
    return `<button class="link-acao" data-acao="separar-duvida">${icone("square-pen", { tamanho: 13 })} Mover o texto do título para a pergunta</button>`;
  }

  separarDuvida() {
    const titulo = this.raiz.querySelector("[data-campo-rotulo]");
    const corpo = this.raiz.querySelector("[data-prop=pergunta]");
    if (!titulo || !corpo) return;
    corpo.value = titulo.value;
    titulo.value = resumirEmTitulo(titulo.value);
    [titulo, corpo].forEach((campo) => ajustarAltura(campo));
    this.aoEditar({ target: corpo });
  }

  /** Campo de texto longo de uma propriedade que o bloco do tipo já trata. */
  montarCampoDeTexto({ chave, rotulo, icone: nomeDoIcone, valor, dica, desabilitado }) {
    return `
      <div class="bloco-resposta">
        <span class="bloco-campo-rotulo">${icone(nomeDoIcone, { tamanho: 14 })} ${escapeHtml(rotulo)}</span>
        <textarea class="entrada mod-area" data-prop="${escapeHtml(chave)}" data-original="${escapeHtml(valor)}" rows="3" placeholder="${escapeHtml(dica)}" ${desabilitado}>${escapeHtml(valor)}</textarea>
      </div>`;
  }

  montarBlocoDoProjeto(no, desabilitado) {
    const atual = no.propriedades?.nivel_autonomia === "ilimitado" ? "ilimitado" : "estrito";
    const textos = { estrito: "Estrita — cada papel cria só os seus tipos de nó", ilimitado: "Ilimitada — agentes criam qualquer tipo, menos Constraint" };
    return `
      ${this.montarResumoDoConteiner(no)}
      <div class="bloco-campo mod-coluna">
        <span class="bloco-campo-rotulo">${icone("zap", { tamanho: 14 })} Autonomia dos agentes</span>
        <select class="seletor" data-prop="nivel_autonomia" data-original="${atual}" ${desabilitado}>
          ${niveisDeAutonomia().map((nivel) => `<option value="${nivel}" ${nivel === atual ? "selected" : ""}>${escapeHtml(textos[nivel] || nivel)}</option>`).join("")}
        </select>
        <span class="bloco-nota">Não concede Constraint, não encerra dúvidas e não libera <code>escopa</code> nem a remoção de <code>bloqueia</code>.</span>
      </div>`;
  }

  montarResumoDoConteiner(no) {
    const resumo = no.resumo || this.indice.conteineres.get(no.id)?.resumo;
    const filho = { Projeto: "Novo setor", Setor: "Nova sessão", Sessao: "Novo nó" }[no.tipo];
    return `
      ${montarCartaoDeResumo(resumo)}
      <div class="bloco-botoes">
        <button class="botao" data-acao="abrir-escopo" data-id="${escapeHtml(no.id)}">${icone("folder-open", { tamanho: 14 })} Abrir no canvas</button>
        ${filho ? `<button class="botao" data-acao="novo-filho">${icone("plus", { tamanho: 14 })} ${filho}</button>` : ""}
      </div>`;
  }

  montarSecaoPropriedades(no, somenteLeitura) {
    const tratadas = new Set(CHAVES_DO_BLOCO[no.tipo] || []);
    const propriedades = no.propriedades || {};
    const chaves = ordenarChaves(Object.keys(propriedades).filter((chave) => !CHAVES_OCULTAS.has(chave) && !tratadas.has(chave)));
    const linhas = chaves.map((chave) => montarLinhaDePropriedade(chave, propriedades[chave], { somenteLeitura })).join("");
    const nova = somenteLeitura ? "" : `
      <div class="propriedade mod-nova" data-nova hidden>
        <span class="propriedade-icone">${icone("plus", { tamanho: 14 })}</span>
        <input class="entrada-propriedade mod-chave" data-nova-chave placeholder="chave">
        <input class="entrada-propriedade" data-nova-valor placeholder="valor">
      </div>
      <button class="adicionar-propriedade" data-acao="nova-propriedade">${icone("plus", { tamanho: 14 })} Adicionar propriedade</button>`;
    return this.montarSecao("propriedades", "Propriedades", chaves.length, `
      <div class="propriedades">${linhas || '<div class="secao-vazia">Nenhuma propriedade.</div>'}${nova}</div>`);
  }

  montarSecaoConexoes(no) {
    const arestas = [...this.state.edges.values()];
    const entradas = arestas.filter((a) => a.destino_id === no.id);
    const saidas = arestas.filter((a) => a.origem_id === no.id);
    const total = entradas.length + saidas.length;
    const linhas = [
      ...saidas.map((a) => this.montarLinhaDeConexao(a, a.destino_id, lerAresta(a.tipo).saida, "arrow-up-right")),
      ...entradas.map((a) => this.montarLinhaDeConexao(a, a.origem_id, lerAresta(a.tipo).entrada, "arrow-down-left")),
    ];
    const excedente = linhas.length > MAXIMO_DE_CONEXOES_NO_RESUMO ? `<div class="secao-vazia">+${linhas.length - MAXIMO_DE_CONEXOES_NO_RESUMO} outras</div>` : "";
    return this.montarSecao("conexoes", "Conexões no canvas", total, `
      <div class="conexoes-resumo">${linhas.slice(0, MAXIMO_DE_CONEXOES_NO_RESUMO).join("") || '<div class="secao-vazia">Nenhuma aresta visível no canvas.</div>'}${excedente}</div>
      <button class="link-acao" data-acao="ver-conexoes">${icone("link", { tamanho: 13 })} Ver todas as conexões do grafo</button>`);
  }

  montarLinhaDeConexao(aresta, idVizinho, leitura, direcao) {
    const vizinho = this.state.nodes.get(idVizinho) || this.indice.info.get(idVizinho) || { id: idVizinho, tipo: "", rotulo: idVizinho };
    return `
      <button class="conexao-linha" data-acao="ir-para" data-id="${escapeHtml(idVizinho)}" title="${escapeHtml(lerAresta(aresta.tipo).descricao)}">
        <span class="conexao-direcao">${icone(direcao, { tamanho: 13 })}</span>
        <span class="conexao-tipo" style="--cor-aresta:${corDaAresta(aresta.tipo)}">${escapeHtml(leitura)}</span>
        <span class="conexao-icone" style="color:${corDoTipo(vizinho.tipo)}">${icone(apresentarTipo(vizinho.tipo).icone, { tamanho: 13 })}</span>
        <span class="conexao-rotulo">${escapeHtml(vizinho.rotulo || idVizinho)}</span>
      </button>`;
  }

  montarSecaoHistorico(no) {
    const seq = no.seq_criacao ?? 0;
    const idade = formatarIdadeRelativa(no.criado_em);
    const alteracao = foiAlterado(no)
      ? `<div class="historico-linha"><span>Alterado</span><strong>${formatarDataCompleta(no.atualizado_em)}</strong><span class="texto-fraco">log #${no.seq_atualizacao}</span></div>`
      : '<div class="historico-linha texto-fraco">Sem alterações desde a criação</div>';
    return this.montarSecao("historico", "Histórico", null, `
      <div class="historico-linha"><span>Criado</span><strong>${formatarDataCompleta(no.criado_em)}</strong><span class="texto-fraco">log #${seq}${idade ? ` · ${idade}` : ""}</span></div>
      ${alteracao}
      ${seq ? `<button class="link-acao" data-acao="viajar" data-seq="${seq}">${icone("history", { tamanho: 13 })} Ver o grafo quando este nó nasceu</button>` : ""}`);
  }

  montarSecao(chave, titulo, contagem, corpo) {
    const aberta = !this.secoesFechadas.has(chave);
    return `
      <details class="secao" data-secao="${chave}" ${aberta ? "open" : ""}>
        <summary class="secao-titulo">${icone("chevron-right", { tamanho: 14, classe: "secao-seta" })}<span>${titulo}</span>${contagem === null ? "" : `<span class="contador">${contagem}</span>`}</summary>
        <div class="secao-corpo">${corpo}</div>
      </details>`;
  }

  montarLinkDeNo(id) {
    const info = this.state.nodes.get(id) || this.indice.no(id) || { rotulo: id };
    return `<button class="link-no" data-acao="ir-para" data-id="${escapeHtml(id)}">${escapeHtml(info.rotulo || id)}</button>`;
  }

  // ---------------------------------------------------------------- aresta

  renderAresta(aresta) {
    const leitura = lerAresta(aresta.tipo);
    const ponta = (id) => {
      const no = this.state.nodes.get(id) || this.indice.info.get(id) || { id, tipo: "", rotulo: id };
      return `
        <button class="ponta-aresta" data-acao="ir-para" data-id="${escapeHtml(id)}">
          <span class="conexao-icone" style="color:${corDoTipo(no.tipo)}">${icone(apresentarTipo(no.tipo).icone, { tamanho: 15 })}</span>
          <span class="ponta-texto"><span class="ponta-tipo">${escapeHtml(apresentarTipo(no.tipo).nome)}</span><span class="ponta-rotulo">${escapeHtml(no.rotulo || id)}</span></span>
        </button>`;
    };
    this.raiz.innerHTML = `
      <div class="inspetor">
        <div class="inspetor-topo">
          <span class="pilula-tipo" style="--cor-tipo:${corDaAresta(aresta.tipo)}">${icone("link", { tamanho: 13 })}Aresta</span>
          <button class="inspetor-id" data-acao="copiar-id" title="Copiar o ID">${escapeHtml(aresta.id)}</button>
        </div>
        <div class="inspetor-titulo mod-estatico">${escapeHtml(aresta.tipo)}</div>
        <p class="inspetor-descricao">${escapeHtml(leitura.descricao)}</p>
        <div class="aresta-pontas">
          ${ponta(aresta.origem_id)}
          <div class="aresta-verbo" style="--cor-aresta:${corDaAresta(aresta.tipo)}">${icone("arrow-right", { tamanho: 14 })}${escapeHtml(leitura.saida)}</div>
          ${ponta(aresta.destino_id)}
        </div>
        ${this.state.isTimeTraveling ? "" : `<button class="botao mod-perigo mod-largo" data-acao="remover-aresta">${icone("trash", { tamanho: 14 })} Remover aresta</button>`}
      </div>`;
  }

  // ---------------------------------------------------------------- panorama

  renderPanorama() {
    const escopo = this.acoes.escopoAtivo();
    const doHook = ehEscopoDoHook(escopo);
    const no = escopo && !doHook ? this.indice.conteineres.get(escopo.id) : null;
    const tipo = no ? apresentarTipo(no.tipo) : { nome: doHook ? "Âmbito" : "Grafo", icone: doHook ? "bot" : "grafo" };
    const resumo = no ? no.resumo : this.resumoGeral(doHook ? AMBITO_DO_HOOK : AMBITO_DOS_PROJETOS);
    const titulo = no?.rotulo || (doHook ? ESCOPO_DO_HOOK.rotulo : "Todos os projetos");
    this.raiz.innerHTML = `
      <div class="inspetor mod-panorama">
        <div class="inspetor-topo">
          <span class="pilula-tipo" style="--cor-tipo:${no ? corDoTipo(no.tipo) : "var(--texto-fraco)"}">${icone(tipo.icone, { tamanho: 13 })}${escapeHtml(tipo.nome)}</span>
          <span class="texto-fraco">panorama do escopo</span>
        </div>
        <div class="inspetor-titulo mod-estatico">${escapeHtml(titulo)}</div>
        ${no ? this.montarCaminho(no) : ""}
        ${montarCartaoDeResumo(resumo)}
        ${this.montarDistribuicao()}
        <div class="panorama-dica">${icone("info", { tamanho: 14 })}<span>Selecione um nó no canvas ou no explorador para ver e editar as propriedades dele.</span></div>
      </div>`;
  }

  /** O agregado de uma raiz da árvore: os projetos de trabalho ou os ambientes das sessões do hook. */
  resumoGeral(ambito) {
    const projetos = [...this.indice.conteineres.values()].filter(
      (no) => no.tipo === "Projeto" && no.resumo && this.indice.ambitoDe(no.id) === ambito
    );
    if (projetos.length === 0) return null;
    const soma = (campo) => projetos.reduce((total, no) => total + (no.resumo[campo] || 0), 0);
    return {
      total_nos: this.indice.totalPorAmbito[ambito] ?? soma("total_nos"),
      tarefas_totais: soma("tarefas_totais"),
      tarefas_concluidas: soma("tarefas_concluidas"),
      tarefas_abertas: soma("tarefas_abertas"),
      questoes_abertas: soma("questoes_abertas"),
    };
  }

  montarDistribuicao() {
    const contagem = new Map();
    for (const no of this.state.nodes.values()) contagem.set(no.tipo, (contagem.get(no.tipo) || 0) + 1);
    if (contagem.size === 0) return "";
    const chips = [...contagem.entries()]
      .sort((a, b) => b[1] - a[1])
      .map(([tipo, total]) => `<span class="chip-tipo" style="--cor-tipo:${corDoTipo(tipo)}">${icone(apresentarTipo(tipo).icone, { tamanho: 12 })}${escapeHtml(apresentarTipo(tipo).nome)}<strong>${total}</strong></span>`);
    return `<div class="panorama-bloco"><div class="panorama-rotulo">No canvas agora · ${this.state.nodes.size} nós</div><div class="chips">${chips.join("")}</div></div>`;
  }

  // ---------------------------------------------------------------- edição

  aoEditar(evento) {
    if (!this.noRenderizado) return;
    if (evento.target.tagName === "TEXTAREA") ajustarAltura(evento.target);
    this.sujo = this.temAlteracoes();
    const rodape = this.raiz.querySelector("[data-rodape]");
    if (rodape) rodape.hidden = !this.sujo;
  }

  temAlteracoes() {
    try {
      const { novo_rotulo, novas_propriedades } = this.coletarAlteracoes();
      return novo_rotulo !== undefined || Object.keys(novas_propriedades).length > 0;
    } catch (erro) {
      return true;
    }
  }

  /** Só o que mudou vai para o patch: cada chave reescrita é um evento no log. */
  coletarAlteracoes() {
    const original = this.noRenderizado;
    const propriedades = original.propriedades || {};
    const novas = {};
    this.raiz.querySelectorAll(".propriedade[data-chave]").forEach((linha) => {
      const valor = lerValorDaLinha(linha);
      if (!valoresIguais(valor, propriedades[linha.dataset.chave])) novas[linha.dataset.chave] = valor;
    });
    this.raiz.querySelectorAll("[data-prop]").forEach((campo) => {
      if (campo.value !== campo.dataset.original) novas[campo.dataset.prop] = campo.value;
    });
    const chaveNova = this.raiz.querySelector("[data-nova-chave]")?.value.trim();
    if (chaveNova) novas[chaveNova] = interpretarValorNovo(this.raiz.querySelector("[data-nova-valor]").value);
    const rotulo = this.raiz.querySelector("[data-campo-rotulo]")?.value.trim();
    return { novo_rotulo: rotulo && rotulo !== original.rotulo ? rotulo : undefined, novas_propriedades: novas };
  }

  /** Alterações do formulário, ou null quando alguma propriedade tem JSON quebrado. */
  lerAlteracoes() {
    try {
      return this.coletarAlteracoes();
    } catch (erro) {
      avisar(`JSON inválido numa propriedade: ${erro.message}`, "erro");
      return null;
    }
  }

  async salvar() {
    const alteracoes = this.lerAlteracoes();
    if (!alteracoes) return;
    await this.enviar({ id_no: this.noRenderizado.id, ...alteracoes });
  }

  /**
   * Responder leva junto o que mais estiver editado no painel — título e corpo
   * da pergunta inclusive. Enviar só o status e a resposta descartava, em
   * silêncio, a correção que a pessoa tinha acabado de digitar acima.
   */
  async responder() {
    const resposta = this.raiz.querySelector("[data-prop=resposta]")?.value.trim();
    if (!resposta) {
      avisar("Escreva a resposta antes de encerrar a dúvida.", "erro");
      return;
    }
    const alteracoes = this.lerAlteracoes();
    if (!alteracoes) return;
    const propriedades = { ...alteracoes.novas_propriedades, status: "respondida", resposta };
    await this.enviar({ id_no: this.noRenderizado.id, novo_rotulo: alteracoes.novo_rotulo, novas_propriedades: propriedades });
  }

  /** Recusa mantém o formulário como está, para a pessoa corrigir; sucesso redesenha com o grafo novo. */
  async enviar(dados) {
    this.salvando = true;
    const recibo = await this.acoes.salvarNo(dados);
    this.salvando = false;
    if (!recibo?.sucesso) return;
    this.sujo = false;
    this.render();
  }

  avisarMudancaExterna(no) {
    if (no.seq_atualizacao === this.noRenderizado.seq_atualizacao) return;
    const texto = this.raiz.querySelector("[data-rodape-texto]");
    if (texto) texto.textContent = "Este nó mudou fora daqui — salvar sobrescreve";
  }

  aoAlternarSecao(evento) {
    const secao = evento.target.closest?.("[data-secao]");
    if (!secao) return;
    if (secao.open) this.secoesFechadas.delete(secao.dataset.secao);
    else this.secoesFechadas.add(secao.dataset.secao);
  }

  aoTeclar(evento) {
    const salvarAtalho = (evento.ctrlKey || evento.metaKey) && (evento.key === "s" || evento.key === "Enter");
    const enterNoTitulo = evento.key === "Enter" && evento.target.matches("[data-campo-rotulo]");
    if (!salvarAtalho && !enterNoTitulo) return;
    evento.preventDefault();
    if (this.sujo) this.salvar();
  }

  aoClicar(evento) {
    const alvo = evento.target.closest("[data-acao]");
    if (!alvo) return;
    const acao = alvo.dataset.acao;
    const selecao = this.state.selectedElement;
    const tratadores = {
      "copiar-id": async () => avisar((await copiarTexto(selecao?.id || "")) ? "ID copiado" : "Não foi possível copiar", "info"),
      marcar: () => { this.acoes.alternarMarcador(this.noRenderizado); this.renderNo(this.noRenderizado); },
      focar: () => this.acoes.focarNo(this.noRenderizado.id),
      menu: () => this.acoes.menuDoNo(evento, this.noRenderizado),
      salvar: () => this.salvar(),
      descartar: () => this.renderNo(this.state.nodes.get(this.noRenderizado.id) || this.noRenderizado),
      responder: () => this.responder(),
      "separar-duvida": () => this.separarDuvida(),
      "nova-propriedade": () => this.revelarNovaPropriedade(alvo),
      "abrir-escopo": () => this.acoes.abrirEscopo(this.indice.escopoDe(alvo.dataset.id)),
      "novo-filho": () => this.acoes.novoFilho(this.noRenderizado),
      "ir-para": () => this.acoes.focarNo(alvo.dataset.id),
      "ver-conexoes": () => this.acoes.mostrarPainel("conexoes"),
      viajar: () => this.acoes.viajarPara(Number(alvo.dataset.seq)),
      "remover-aresta": () => this.acoes.excluirAresta(selecao?.data),
      promover: () => this.acoes.promoverAprendizado(this.noRenderizado),
      "registrar-aprendizado": () => this.acoes.registrarAprendizado({ origens: [this.noRenderizado.id], sessaoId: this.noRenderizado.sessao_id }),
    };
    tratadores[acao]?.();
  }

  revelarNovaPropriedade(botao) {
    const linha = this.raiz.querySelector("[data-nova]");
    if (!linha) return;
    linha.hidden = false;
    botao.hidden = true;
    linha.querySelector("[data-nova-chave]").focus();
  }
}

/** Cartão de progresso da subárvore: a mesma conta do rollup que o super-nó mostra no canvas. */
export function montarCartaoDeResumo(resumo) {
  if (!resumo) return "";
  const total = resumo.tarefas_totais || 0;
  const feitas = resumo.tarefas_concluidas || 0;
  const fracao = total ? Math.round((feitas / total) * 100) : 0;
  const barra = total ? `<div class="resumo-barra"><div class="resumo-preenchida" style="width:${fracao}%"></div></div>` : "";
  return `
    <div class="cartao-resumo">
      <div class="resumo-numeros">
        <div class="resumo-numero"><strong>${total ? `${feitas}/${total}` : "—"}</strong><span>tarefas</span></div>
        <div class="resumo-numero ${resumo.tarefas_abertas ? "mod-aberto" : ""}"><strong>${resumo.tarefas_abertas || 0}</strong><span>abertas</span></div>
        <div class="resumo-numero ${resumo.questoes_abertas ? "mod-duvida" : ""}"><strong>${resumo.questoes_abertas || 0}</strong><span>dúvidas</span></div>
        <div class="resumo-numero"><strong>${resumo.total_nos ?? "—"}</strong><span>nós</span></div>
      </div>
      ${barra}
    </div>`;
}
