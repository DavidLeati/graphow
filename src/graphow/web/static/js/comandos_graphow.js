/**
 * Os comandos da interface, num lugar só. A faixa de ícones, os menus, os
 * atalhos e a paleta (Ctrl+P) disparam estes mesmos comandos.
 *
 * F, Z e 0 aparecem aqui só como atalho exibido: quem os trata é o próprio
 * canvas, que já os ouvia antes desta moldura existir.
 */
import { copiarTexto } from "./dom.js";
import { avisar } from "./modais.js";
import { abrirMenuDeContexto } from "./menu_contexto.js";
import { itensDoMenuDaVista, itensDoMenuDeRamos } from "./menus_do_grafo.js";

export function registrarComandos(app) {
  const registro = app.comandos;
  const selecionado = () => (app.state.selectedElement?.type === "node" ? app.state.nodes.get(app.state.selectedElement.id) : null);
  const noPresente = () => !app.state.isTimeTraveling;
  const junto = (elemento) => {
    const caixa = elemento?.getBoundingClientRect();
    return caixa ? { x: caixa.left, y: caixa.bottom + 4 } : { x: window.innerWidth / 2, y: 80 };
  };
  const recorte = (mudanca) => app.recorteView.aplicar(mudanca);

  const comandos = [
    // Navegar
    { id: "busca-rapida", nome: "Abrir busca rápida", icone: "search", atalho: ["ctrl+k", "ctrl+o", "/"], executar: () => app.quickFinder.alternar() },
    { id: "paleta", nome: "Abrir paleta de comandos", icone: "command", atalho: "ctrl+p", executar: () => registro.abrirPaleta() },
    { id: "buscar-no-grafo", nome: "Buscar no grafo (painel de busca)", icone: "search", atalho: "ctrl+shift+f", executar: () => app.mostrarPainelEsquerdo("busca") },
    { id: "abrir-explorador", nome: "Mostrar o explorador", icone: "folder-closed", executar: () => app.mostrarPainelEsquerdo("explorador") },
    { id: "abrir-marcadores", nome: "Mostrar os marcadores", icone: "bookmark", executar: () => app.mostrarPainelEsquerdo("marcadores") },
    { id: "abrir-grafo", nome: "Abrir o grafo inteiro", icone: "grafo", executar: () => app.abrirEscopo(null) },
    { id: "nova-aba", nome: "Nova aba", icone: "plus", executar: () => app.abas.novaAba() },
    { id: "fechar-aba", nome: "Fechar a aba atual", icone: "x", executar: () => app.abas.fechar(app.abas.ativa.id) },
    { id: "voltar", nome: "Voltar no histórico da aba", icone: "arrow-left", atalho: "alt+arrowleft", executar: () => app.abas.mover(-1) },
    { id: "avancar", nome: "Avançar no histórico da aba", icone: "arrow-right", atalho: "alt+arrowright", executar: () => app.abas.mover(1) },
    { id: "alternar-painel-esquerdo", nome: "Recolher ou expandir o painel esquerdo", icone: "panel-left", executar: () => app.lateralEsquerda.alternar() },
    { id: "alternar-painel-direito", nome: "Recolher ou expandir o painel direito", icone: "panel-right", executar: () => app.lateralDireita.alternar() },
    { id: "mostrar-propriedades", nome: "Mostrar propriedades", icone: "file-text", executar: () => app.mostrarPainelDireito("propriedades") },
    { id: "mostrar-conexoes", nome: "Mostrar conexões do nó", icone: "link", executar: () => app.mostrarPainelDireito("conexoes") },
    { id: "mostrar-linhagem", nome: "Mostrar linhagem causal", icone: "route", executar: () => app.mostrarPainelDireito("linhagem") },
    { id: "mostrar-agente", nome: "Mostrar a vista do agente", icone: "bot", executar: () => app.mostrarPainelDireito("agente") },
    { id: "abrir-historico", nome: "Abrir o histórico do log", icone: "history", executar: () => app.mostrarHistorico() },
    { id: "revelar-selecao", nome: "Revelar a seleção no explorador", icone: "list-tree", disponivel: () => Boolean(selecionado()), executar: () => app.revelarNoExplorador(selecionado().id) },

    // Criar e editar
    { id: "novo-no", nome: "Novo nó", icone: "square-pen", atalho: "n", disponivel: noPresente, executar: () => app.dialogos.novoNo() },
    { id: "novo-conteiner", nome: "Novo projeto, setor ou sessão", icone: "folder-plus", disponivel: noPresente, executar: () => app.dialogos.novoConteiner({ tipo: app.tipoDeConteinerSugerido() }) },
    { id: "novo-projeto", nome: "Novo projeto", icone: "briefcase", disponivel: noPresente, executar: () => app.dialogos.novoConteiner({ tipo: "Projeto" }) },
    { id: "renomear-selecao", nome: "Renomear a seleção", icone: "pencil", atalho: "f2", disponivel: () => noPresente() && Boolean(selecionado()), executar: () => app.dialogos.renomear(selecionado()) },
    { id: "fixar-selecao", nome: "Fixar ou desafixar a seleção nos marcadores", icone: "bookmark", disponivel: () => Boolean(selecionado()), executar: () => app.alternarMarcador(selecionado()) },
    { id: "copiar-id", nome: "Copiar o ID da seleção", icone: "copy", disponivel: () => Boolean(app.state.selectedElement), executar: async () => avisar((await copiarTexto(app.state.selectedElement.id)) ? "ID copiado" : "Não foi possível copiar", "info") },
    { id: "excluir-selecao", nome: "Excluir a seleção…", icone: "trash", disponivel: () => noPresente() && Boolean(selecionado()), executar: () => app.dialogos.excluirNo(selecionado()) },
    { id: "exclusao-lote", nome: "Exclusão em lote…", icone: "trash", disponivel: noPresente, executar: () => app.dialogos.exclusaoEmLote() },

    // Canvas
    { id: "enquadrar", nome: "Enquadrar tudo", icone: "maximize", atalhoExibido: "F", executar: () => app.interactions.fitToView() },
    { id: "zoom-selecao", nome: "Aproximar da seleção", icone: "crosshair", atalhoExibido: "Z", executar: () => app.interactions.zoomToSelection() },
    { id: "resetar-zoom", nome: "Zoom padrão", icone: "rotate-ccw", atalhoExibido: "0", executar: () => app.interactions.resetZoom() },
    { id: "aproximar", nome: "Aproximar", icone: "zoom-in", atalho: ["=", "+"], executar: () => app.interactions.aproximar(1.2) },
    { id: "afastar", nome: "Afastar", icone: "zoom-out", atalho: "-", executar: () => app.interactions.aproximar(1 / 1.2) },
    { id: "auto-layout", nome: "Auto-layout hierárquico", icone: "workflow", executar: () => app.autoLayout() },
    { id: "alternar-arestas-sessao", nome: "Mostrar ou ocultar as arestas de sessão", icone: "eye", executar: () => app.alternarArestasDeSessao() },
    { id: "alternar-minimapa", nome: "Mostrar ou ocultar o minimapa", icone: "map", executar: () => app.alternarMinimapa() },
    { id: "alternar-recorte", nome: "Recorte e exibição", icone: "sliders", executar: () => app.recorteView.alternar() },
    { id: "recorte-tudo", nome: "Recorte: mostrar tudo", icone: "layers", executar: () => app.recorteView.limpar() },
    { id: "agrupar-setores", nome: "Recorte: agrupar em setores", icone: "layers", executar: () => recorte({ colapsar: "setor" }) },
    { id: "agrupar-sessoes", nome: "Recorte: agrupar em sessões", icone: "layers", executar: () => recorte({ colapsar: "sessao" }) },
    { id: "alternar-so-ativo", nome: "Recorte: alternar só o ativo", icone: "filter", executar: () => recorte({ escopo: app.state.recorte.escopo ? "" : "ativo" }) },
    { id: "alternar-caminho-critico", nome: "Recorte: alternar caminho crítico", icone: "route", executar: () => recorte({ vista: app.state.recorte.vista ? "" : "caminho_critico" }) },
    { id: "menu-vista", nome: "Mais opções da vista", icone: "more-vertical", oculto: true, executar: () => abrirMenuDeContexto(junto(document.querySelector("[data-comando='menu-vista']")), itensDoMenuDaVista(app)) },

    // Log e ramos
    { id: "voltar-ao-presente", nome: "Voltar ao presente", icone: "rotate-ccw", disponivel: () => app.state.isTimeTraveling, executar: () => app.voltarAoPresente() },
    { id: "menu-ramos", nome: "Trocar de ramo…", icone: "git-branch", executar: () => abrirMenuDeContexto(junto(document.querySelector(".cofre-botao")), itensDoMenuDeRamos(app)) },
    { id: "criar-fork", nome: "Criar fork (novo ramo)…", icone: "git-fork", executar: () => app.dialogos.criarFork() },
    { id: "comparar-ramos", nome: "Comparar ramos", icone: "git-compare", executar: () => app.abas.abrirFerramenta("diff") },
    { id: "terminal-patch", nome: "Terminal de patch", icone: "terminal", executar: () => app.abas.abrirFerramenta("patch") },
    { id: "recarregar", nome: "Reler os dados do servidor", icone: "refresh", executar: () => app.recarregarTudo() },
    { id: "atalhos", nome: "Atalhos de teclado", icone: "keyboard", atalho: "?", executar: () => app.mostrarAtalhos() },
  ];
  comandos.forEach((comando) => registro.registrar(comando));

  // Todo botão com data-comando dispara o comando do mesmo nome.
  document.addEventListener("click", (evento) => {
    const botao = evento.target.closest("[data-comando]");
    if (botao) registro.executar(botao.dataset.comando);
  });
}
