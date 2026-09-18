/**
 * Menus de contexto do grafo: o mesmo menu de nó serve à árvore, ao canvas, à
 * busca, às conexões e aos marcadores — um nó tem as mesmas ações onde quer que
 * seja clicado. Enquanto a tela mostra o passado, o que escreve fica desabilitado.
 */
import { TIPOS_DE_ORIGEM_DE_APRENDIZADO } from "./dialogos_memoria.js";
import { copiarTexto } from "./dom.js";
import { avisar } from "./modais.js";
import { apresentarStatus, apresentarTipo, ehConteiner, niveisDeAutonomia, statusDoTipo } from "./ontologia_ui.js";

const ROTULO_DO_FILHO = { Projeto: "Novo setor…", Setor: "Nova sessão…", Sessao: "Novo nó nesta sessão…" };

export function itensDoMenuDoNo(app, no) {
  const viajando = app.state.isTimeTraveling;
  const itens = ehConteiner(no.tipo) ? itensDeConteiner(app, no, viajando) : itensDeTrabalho(app, no);
  itens.push(
    { rotulo: "Propriedades", icone: "file-text", acao: () => app.selecionarEMostrar(no, "propriedades") },
    { rotulo: "Conexões", icone: "link", acao: () => app.selecionarEMostrar(no, "conexoes") },
    { rotulo: "Linhagem causal", icone: "route", acao: () => app.selecionarEMostrar(no, "linhagem") },
    { rotulo: "Vista do agente", icone: "bot", acao: () => app.selecionarEMostrar(no, "agente") },
    "-",
    ...itensDeEstado(app, no, viajando),
    {
      rotulo: app.marcadores.contem(no.id) ? "Remover dos marcadores" : "Fixar nos marcadores",
      icone: "bookmark",
      acao: () => app.alternarMarcador(no),
    },
    { rotulo: "Revelar no explorador", icone: "list-tree", acao: () => app.revelarNoExplorador(no.id) },
    { rotulo: "Copiar ID", icone: "copy", acao: async () => avisar((await copiarTexto(no.id)) ? "ID copiado" : "Não foi possível copiar", "info") },
    "-",
    { rotulo: "Renomear…", icone: "pencil", desabilitado: viajando, acao: () => app.dialogos.renomear(no) },
    {
      rotulo: no.tipo === "Projeto" ? "Excluir projeto em cascata…" : "Excluir…",
      icone: "trash",
      perigo: true,
      desabilitado: viajando,
      acao: () => app.dialogos.excluirNo(no),
    }
  );
  return itens;
}

function itensDeConteiner(app, no, viajando) {
  const escopo = app.indice.escopoDe(no.id) || { tipo: no.tipo, id: no.id, rotulo: no.rotulo };
  return [
    { secao: `${apresentarTipo(no.tipo).nome} · ${no.rotulo}` },
    { rotulo: "Abrir no canvas", icone: "folder-open", acao: () => app.abrirEscopo(escopo) },
    { rotulo: "Abrir em nova aba", icone: "plus", acao: () => app.abrirEscopo(escopo, { novaAba: true }) },
    { rotulo: ROTULO_DO_FILHO[no.tipo], icone: "plus", desabilitado: viajando, acao: () => app.novoFilho(no) },
    ...itensDeSessao(app, no, viajando),
    "-",
  ];
}

/**
 * Encerrar a sessão é o gesto que separa a memória de curto prazo da de longo
 * prazo: a vista dela passa a abrir pelo fechamento e o grafo pede a condensação.
 * Reabrir segue livre, porque o fechamento é projeção e atualiza sozinho.
 */
function itensDeSessao(app, no, viajando) {
  if (no.tipo !== "Sessao") return [];
  const encerrada = no.propriedades?.status === "concluida";
  const memoria = { rotulo: "Ver na memória", icone: "lightbulb", acao: () => app.mostrarPainelEsquerdo("memoria") };
  if (encerrada) {
    return [{ rotulo: "Reabrir sessão", icone: "folder-open", desabilitado: viajando, acao: () => app.dialogos.mudarPropriedade(no, "status", "ativa", "Sessão reaberta") }, memoria];
  }
  return [{ rotulo: "Encerrar sessão", icone: "circle-check", desabilitado: viajando, acao: () => app.dialogos.mudarPropriedade(no, "status", "concluida", "Sessão encerrada: a vista dela abre pelo fechamento") }, memoria];
}

function itensDeTrabalho(app, no) {
  const sessao = no.sessao_id && app.indice.escopoDe(no.sessao_id);
  return [
    { secao: `${apresentarTipo(no.tipo).nome} · ${no.rotulo || no.id}` },
    { rotulo: "Centralizar no canvas", icone: "crosshair", acao: () => app.focarNo(no.id, no) },
    sessao ? { rotulo: `Abrir a sessão “${sessao.rotulo}”`, icone: "folder-clock", acao: () => app.abrirEscopo(sessao) } : null,
    ...itensDeMemoria(app, no),
    "-",
  ];
}

/**
 * Memória de longo prazo: de um nó de trabalho se registra um aprendizado; um
 * aprendizado se promove. Promover é gesto humano, e esta tela escreve como humano.
 */
function itensDeMemoria(app, no) {
  const viajando = app.state.isTimeTraveling;
  if (no.tipo === "Aprendizado") {
    return [{ rotulo: "Promover aprendizado…", icone: "lightbulb", desabilitado: viajando, acao: () => app.dialogosDeMemoria.promover(no) }];
  }
  if (!TIPOS_DE_ORIGEM_DE_APRENDIZADO.has(no.tipo)) return [];
  return [{
    rotulo: "Registrar aprendizado a partir daqui…",
    icone: "lightbulb",
    desabilitado: viajando,
    acao: () => app.dialogosDeMemoria.registrar({ origens: [no.id], sessaoId: no.sessao_id }),
  }];
}

function itensDeEstado(app, no, viajando) {
  const itens = [];
  const status = statusDoTipo(no.tipo);
  if (status) {
    itens.push({
      rotulo: "Mudar status",
      icone: "circle-dot",
      desabilitado: viajando,
      submenu: status.map((valor) => ({
        rotulo: apresentarStatus(valor),
        marcado: no.propriedades?.status === valor,
        acao: () => app.dialogos.mudarPropriedade(no, "status", valor, `Status: ${apresentarStatus(valor)}`),
      })),
    });
  }
  if (no.tipo === "Projeto") {
    const atual = no.propriedades?.nivel_autonomia === "ilimitado" ? "ilimitado" : "estrito";
    itens.push({
      rotulo: "Autonomia dos agentes",
      icone: "zap",
      desabilitado: viajando,
      submenu: niveisDeAutonomia().map((nivel) => ({
        rotulo: nivel === "estrito" ? "Estrita" : "Ilimitada",
        marcado: atual === nivel,
        acao: () => app.dialogos.mudarPropriedade(no, "nivel_autonomia", nivel, `Autonomia: ${nivel}`),
      })),
    });
  }
  return itens;
}

export function itensDoMenuDaAresta(app, aresta) {
  const ponta = (id) => app.state.nodes.get(id)?.rotulo || id;
  return [
    { secao: `Aresta · ${aresta.tipo}` },
    { rotulo: `Ir para a origem: ${ponta(aresta.origem_id)}`, icone: "arrow-left", acao: () => app.focarNo(aresta.origem_id) },
    { rotulo: `Ir para o destino: ${ponta(aresta.destino_id)}`, icone: "arrow-right", acao: () => app.focarNo(aresta.destino_id) },
    "-",
    { rotulo: "Remover aresta…", icone: "trash", perigo: true, desabilitado: app.state.isTimeTraveling, acao: () => app.dialogos.excluirAresta(aresta) },
  ];
}

export function itensDoMenuDoFundo(app, { x, y }) {
  const viajando = app.state.isTimeTraveling;
  return [
    { rotulo: "Novo nó aqui…", icone: "square-pen", desabilitado: viajando, acao: () => app.dialogos.novoNo({ x, y }) },
    { rotulo: "Novo contêiner…", icone: "folder-plus", desabilitado: viajando, acao: () => app.comandos.executar("novo-conteiner") },
    "-",
    ...itensDeExibicao(app),
  ];
}

export function itensDeExibicao(app) {
  return [
    { rotulo: "Enquadrar tudo", icone: "maximize", atalho: "F", acao: () => app.interactions.fitToView() },
    { rotulo: "Auto-layout hierárquico", icone: "workflow", acao: () => app.comandos.executar("auto-layout") },
    { rotulo: "Arestas de sessão", icone: "eye", marcado: !app.state.hideStructuralEdges, acao: () => app.comandos.executar("alternar-arestas-sessao") },
    { rotulo: "Minimapa", icone: "map", marcado: app.state.mostrarMinimapa, acao: () => app.comandos.executar("alternar-minimapa") },
    { rotulo: "Recorte e exibição…", icone: "sliders", acao: () => app.recorteView.alternar(true) },
  ];
}

export function itensDoMenuDaVista(app) {
  const aba = app.abas.ativa;
  return [
    ...itensDeExibicao(app),
    "-",
    { rotulo: "Novo nó…", icone: "square-pen", desabilitado: app.state.isTimeTraveling, acao: () => app.comandos.executar("novo-no") },
    { rotulo: "Exclusão em lote…", icone: "trash", desabilitado: app.state.isTimeTraveling, acao: () => app.comandos.executar("exclusao-lote") },
    "-",
    { rotulo: "Duplicar aba", icone: "copy", desabilitado: aba.tipo !== "grafo", acao: () => app.abrirEscopo(aba.escopo, { novaAba: true }) },
    { rotulo: "Fechar aba", icone: "x", acao: () => app.abas.fechar(aba.id) },
  ];
}

export function itensDoMenuDeRamos(app) {
  const atual = app.state.currentBranch;
  return [
    { secao: "Ramos" },
    ...app.state.branches.map((ramo) => ({
      rotulo: ramo,
      icone: "git-branch",
      marcado: ramo === atual,
      acao: () => app.trocarRamo(ramo),
    })),
    "-",
    {
      rotulo: app.state.isTimeTraveling ? `Criar fork a partir do log #${app.state.logVersion}…` : "Criar fork a partir daqui…",
      icone: "git-fork",
      acao: () => app.dialogos.criarFork(),
    },
    { rotulo: "Comparar ramos", icone: "git-compare", acao: () => app.comandos.executar("comparar-ramos") },
  ];
}
