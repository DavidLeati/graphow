/**
 * Busca rápida de nós (Ctrl+K).
 *
 * A versão anterior procurava só nos nós carregados no canvas — num canvas
 * recortado, isso é uma fração do grafo, e a tarefa procurada simplesmente não
 * existia para ela. Agora a busca vai ao servidor, sobre o ramo inteiro e na
 * ordem de relevância que o agente também usa. Com a caixa vazia aparecem os nós
 * abertos por último.
 */
import { api } from "./api.js";
import { destacarTermo, escapeHtml, gravarPreferencia, lerPreferencia } from "./dom.js";
import { icone } from "./icones.js";
import { apresentarStatus, apresentarTipo, corDoTipo, ehConteiner } from "./ontologia_ui.js";
import { Sugestor } from "./sugestor.js";

const LIMITE_DE_RECENTES = 12;
const LIMITE_DA_BUSCA = 30;

export class QuickFinder {
  constructor({ state, indice, aoEscolher }) {
    this.state = state;
    this.indice = indice;
    this.recentes = lerPreferencia("recentes", []);
    this.sugestor = new Sugestor({
      placeholder: "Buscar nós por título, conteúdo ou ID…",
      instrucoes: [["↑↓", "navegar"], ["↵", "abrir"], ["ctrl ↵", "em nova aba"], ["esc", "fechar"]],
      esperaMs: 140,
      buscar: (termo) => this.buscar(termo),
      montarItem: (item, termo) => this.montarItem(item, termo),
      aoEscolher: (item, evento) => {
        this.lembrar(item.id);
        aoEscolher(item, { novaAba: Boolean(evento?.ctrlKey || evento?.metaKey) });
      },
    });
  }

  abrir(termo = "") {
    this.sugestor.abrir(termo);
  }

  alternar() {
    if (this.sugestor.aberto) this.sugestor.fechar();
    else this.abrir();
  }

  /** Guarda o nó entre os recentes, que aparecem com a caixa vazia. */
  lembrar(id) {
    this.recentes = [id, ...this.recentes.filter((outro) => outro !== id)].slice(0, LIMITE_DE_RECENTES);
    gravarPreferencia("recentes", this.recentes);
  }

  async buscar(termo) {
    const limpo = termo.trim();
    if (!limpo) return this.listarRecentes();
    const resposta = await api.buscar({ termo: limpo, limite: LIMITE_DA_BUSCA, ramo: this.state.currentBranch });
    if (!resposta.sucesso) return { itens: [], rodape: resposta.mensagem || "A busca falhou." };
    this.indice.registrarNos(resposta.resultados);
    const rodape = resposta.truncado ? `Mostrando ${resposta.exibidos} de ${resposta.total}. Refine o termo para ver os demais.` : "";
    return { itens: resposta.resultados, rodape };
  }

  listarRecentes() {
    const itens = this.recentes
      .map((id) => this.state.nodes.get(id) || this.indice.info.get(id))
      .filter(Boolean)
      .map((no) => ({ id: no.id, tipo: no.tipo, rotulo: no.rotulo, sessao_id: no.sessao_id, status: no.propriedades?.status ?? no.status, recente: true }));
    return { itens, rodape: itens.length ? "" : "Digite para buscar no grafo inteiro." };
  }

  montarItem(item, termo) {
    const tipo = apresentarTipo(item.tipo);
    const caminho = this.indice.ancestrais(ehConteiner(item.tipo) ? item.id : item.sessao_id || item.id)
      .filter((anc) => anc.id !== item.id)
      .map((anc) => anc.rotulo)
      .join(" / ");
    const trecho = item.trecho ? `<div class="prompt-item-trecho"><span class="texto-fraco">${escapeHtml(item.trecho.chave)}:</span> ${destacarTermo(item.trecho.texto, termo)}</div>` : "";
    return `
      <span class="prompt-item-icone" style="color:${corDoTipo(item.tipo)}">${icone(tipo.icone, { tamanho: 16 })}</span>
      <div class="prompt-item-conteudo">
        <div class="prompt-item-titulo">${destacarTermo(item.rotulo || item.id, termo)}</div>
        ${trecho}
        ${caminho ? `<div class="prompt-item-caminho">${escapeHtml(caminho)}</div>` : ""}
      </div>
      <span class="prompt-item-aux">${item.status ? `<span class="texto-fraco">${escapeHtml(apresentarStatus(item.status))}</span>` : ""}<span class="etiqueta-tipo" style="--cor-tipo:${corDoTipo(item.tipo)}">${escapeHtml(tipo.nome)}</span></span>`;
  }
}
