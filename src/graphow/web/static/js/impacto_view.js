/**
 * Impacto do nó selecionado: o que o afeta e o que ele afeta.
 *
 * As conexões dizem para onde cada aresta aponta, mas "saída" e "entrada" não
 * respondem o que importa num fluxo: a pergunta que bloqueia a tarefa entra
 * nela, o pré-requisito sai dela, e os dois estão a montante. Aqui a mesma ficha
 * de `expandir_no` é lida pelo lado do trabalho. As arestas de sessão ficam de
 * fora, a não ser que o nó seja um contêiner ou uma execução, porque nos demais
 * repetiriam em todo nó a sessão que o produziu.
 */
import { ConexoesView } from "./conexoes_view.js";
import { escapeHtml } from "./dom.js";
import { icone } from "./icones.js";
import { ARESTAS_ESTRUTURAIS, ladoDoVizinho, statusDe } from "./leitura_de_fluxo.js";
import { apresentarStatus, ehConteiner, tomDoStatus } from "./ontologia_ui.js";

const TITULOS = { montante: "O que afeta este nó", jusante: "O que este nó afeta" };
const VAZIOS = { montante: "Nada chega a este nó.", jusante: "Nada depende deste nó." };

export class ImpactoView extends ConexoesView {
  textoSemSelecao() {
    return "Selecione um nó para ver o que o afeta e o que ele afeta, dentro e fora do canvas.";
  }

  lados() {
    const { saidas, entradas } = this.vizinhos();
    const comEstrutura = ehConteiner(this.dados.tipo) || this.dados.tipo === "Run";
    const lados = { montante: [], jusante: [] };
    for (const aresta of [...saidas, ...entradas]) {
      if (!comEstrutura && ARESTAS_ESTRUTURAIS.has(aresta.tipo)) continue;
      lados[ladoDoVizinho(aresta.tipo, aresta.direcao === "saida")].push(aresta);
    }
    return lados;
  }

  render() {
    const lados = this.lados();
    const status = statusDe(this.dados);
    this.raiz.innerHTML = `
      <div class="painel-cabecalho-texto">
        <button class="link-no" data-ir="${escapeHtml(this.dados.id)}">${escapeHtml(this.dados.rotulo || this.dados.id)}</button>
        ${status ? `<span class="impacto-status tom-${tomDoStatus(status)}">${escapeHtml(apresentarStatus(status))}</span>` : ""}
      </div>
      ${this.montarDirecao("montante", TITULOS.montante, lados.montante)}
      ${this.montarDirecao("jusante", TITULOS.jusante, lados.jusante)}`;
  }

  /** Agrupa pelo verbo lido do nó: "bloqueado por", "depende de", "orientado por"… */
  montarDirecao(chave, titulo, arestas) {
    const fechado = this.gruposFechados.has(chave);
    const porLeitura = new Map();
    for (const aresta of arestas) {
      const leitura = `${aresta.tipo}|${aresta.direcao}`;
      if (!porLeitura.has(leitura)) porLeitura.set(leitura, []);
      porLeitura.get(leitura).push(aresta);
    }
    const grupos = [...porLeitura.values()].map((lista) => this.montarGrupo(lista[0].direcao, lista[0].tipo, lista)).join("");
    return `
      <div class="grupo-conexoes">
        <button class="grupo-conexoes-titulo" data-grupo="${chave}">
          ${icone("chevron-down", { tamanho: 14, classe: fechado ? "is-recolhida" : "" })}
          <span>${titulo}</span><span class="contador">${arestas.length}</span>
        </button>
        ${fechado ? "" : grupos || `<div class="secao-vazia mod-recuado">${VAZIOS[chave]}</div>`}
      </div>`;
  }
}
