/**
 * Arranjo automático do canvas.
 *
 * O arranjo antigo punha o grafo inteiro num Sugiyama só. Com trinta nós dava
 * certo; com duzentos, rasos e em poucas camadas, virava uma coluna de dezenas
 * de cartões de altura, com arestas de sessões diferentes cruzando a tela.
 *
 * Este monta o desenho em blocos, de dentro para fora:
 *
 * - cada componente de trabalho vira um bloco em camadas, da esquerda para a
 *   direita no sentido do fluxo (layout_sugiyama + layout_coordenadas), com as
 *   folhas de um mesmo vizinho recolhidas em grade (layout_feixes);
 * - os nós sem ligação nenhuma formam uma grade em ordem de leitura;
 * - o conteúdo de um contêiner se empacota embaixo do cartão dele, como um
 *   corpo embaixo do título (layout_empacotamento);
 * - os filhos de árvore descem numa coluna à direita do pai, e o leque de
 *   arestas `contem` sai sem cruzar nada.
 *
 * Duas medidas dão a forma do conjunto. A altura de página diz quando uma
 * coluna de irmãos quebra para a coluna ao lado — é ela que decide a proporção
 * do desenho, e é refeita até o desenho ter o formato da tela. A largura das
 * faixas de empacotamento decide o quanto cada bloco se espalha, e é buscada
 * pela mais compacta. Juntas, fazem centenas de nós caberem num enquadramento
 * só, em vez de numa fita de dezessete mil pixels.
 */

import { distribuirConteudo, lerEstrutura } from "./layout_estrutura.js";
import { organizarEmCamadas } from "./layout_sugiyama.js";
import { posicionarComponente } from "./layout_coordenadas.js";
import { empacotar, empilharEmColunas, montarGrade } from "./layout_empacotamento.js";
import { recolherFeixes } from "./layout_feixes.js";

const TAMANHO_PADRAO = { largura: 220, altura: 150 };
const PROPORCAO_PADRAO = 16 / 10;
const MARGEM = 50;
const FOLGA_DA_ARVORE = 140;
const FOLGA_ENTRE_IRMAOS = 120;
const FOLGA_ABAIXO_DO_TITULO = 56;
const FOLGA_ENTRE_PECAS = 90;
const TENTATIVAS_DE_LARGURA = 12;
const AJUSTES_DE_PAGINA = 5;
// Doze por cento de erro na proporção não se enxerga; perseguir mais que isso
// só troca um desenho bom por outro igual.
const TOLERANCIA_DA_PROPORCAO = 0.12;
// Altura a partir da qual uma camada se reparte em mais colunas. Cabem doze
// cartões: mais que isso e a coluna deixa de ser lida de uma vez.
const ORCAMENTO_DE_ALTURA = 1800;
// Uma coluna de blocos desce até aqui antes de abrir a coluna ao lado.
const ALTURA_MINIMA_DA_PAGINA = 2600;
// Quanto da área do desenho os cartões ocupam quando o arranjo está bom. O
// resto é a folga que as arestas precisam para serem seguidas com os olhos.
const OCUPACAO_ESPERADA = 0.14;

// Ordem de leitura dentro de uma camada ou grade: nós do mesmo tipo ficam
// juntos, na ordem em que o trabalho costuma andar, e depois pela criação.
const ORDEM_DOS_TIPOS = [
  "Projeto", "Setor", "Sessao", "Goal", "Constraint", "Question",
  "Task", "Decision", "Evidence", "Artifact", "Note", "Aprendizado", "Run",
];

/**
 * Calcula o arranjo de todos os nós. `tamanhos` é um Map de id para
 * { largura, altura } medido no canvas; `proporcao`, a largura sobre a altura
 * da área visível. Devolve um Map de id para { x, y }.
 */
export function calcularLayoutHierarquico(nodes, edges, { tamanhos, proporcao = PROPORCAO_PADRAO } = {}) {
  if (!nodes || nodes.length === 0) return new Map();
  const porId = new Map(nodes.map((n) => [n.id, n]));
  const ctx = {
    proporcao,
    estrutura: lerEstrutura(nodes, edges),
    tamanhoDe: (id) => tamanhos?.get(id) ?? TAMANHO_PADRAO,
    comparar: compararParaLeitura(porId),
  };
  ctx.alturaDaPagina = alturaDaPagina(nodes, ctx, proporcao);
  ctx.pecas = prepararPecas(distribuirConteudo(ctx.estrutura, nodes), ctx);
  ctx.raizes = nodes
    .map((n) => n.id)
    .filter((id) => !ctx.estrutura.pai.has(id) && ctx.estrutura.filhos.has(id))
    .sort(ctx.comparar);
  const bloco = montarNaMelhorForma(ctx, proporcao);
  return new Map(bloco.itens.map(({ id, x, y }) => [id, { x: Math.round(x + MARGEM), y: Math.round(y + MARGEM) }]));
}

/**
 * A altura em que uma coluna de blocos quebra para a coluna seguinte. É a
 * altura que o desenho inteiro teria se ocupasse a tela na proporção pedida,
 * com a folga que um grafo sempre pede entre os cartões — nunca menor que uma
 * página, para que um grafo pequeno continue sendo uma árvore de uma coluna só.
 */
function alturaDaPagina(nodes, ctx, proporcao) {
  const area = nodes.reduce((soma, no) => {
    const tamanho = ctx.tamanhoDe(no.id);
    return soma + tamanho.largura * tamanho.altura;
  }, 0);
  return Math.max(ALTURA_MINIMA_DA_PAGINA, Math.sqrt(area / OCUPACAO_ESPERADA / proporcao));
}

function compararParaLeitura(porId) {
  const posicaoDoTipo = (id) => {
    const i = ORDEM_DOS_TIPOS.indexOf(porId.get(id)?.tipo);
    return i === -1 ? ORDEM_DOS_TIPOS.length : i;
  };
  const criacao = (id) => porId.get(id)?.seq_criacao ?? Infinity;
  return (a, b) => posicaoDoTipo(a) - posicaoDoTipo(b) || criacao(a) - criacao(b) || a.localeCompare(b);
}

/**
 * O que não depende da largura da faixa é calculado uma vez: o arranjo em
 * camadas de cada componente. Os nós soltos ficam para a grade.
 */
function prepararPecas(porContainer, ctx) {
  const pecas = new Map();
  for (const [dono, componentes] of porContainer) {
    const soltos = componentes.filter((c) => c.length === 1).map((c) => c[0]).sort(ctx.comparar);
    const blocos = componentes.filter((c) => c.length > 1).map((c) => arranjarComponente(c, ctx));
    blocos.sort((a, b) => b.largura * b.altura - a.largura * a.altura);
    pecas.set(dono, { blocos, soltos });
  }
  return pecas;
}

function arranjarComponente(ids, ctx) {
  const membros = new Set(ids);
  const doComponente = ctx.estrutura.trabalho.filter((a) => membros.has(a.de) && membros.has(a.para));
  const { nos, arestas, tamanhoDe, expandir } = recolherFeixes(ids, doComponente, ctx);
  const camadas = organizarEmCamadas(nos, arestas, {
    comparar: ctx.comparar,
    alturaDe: (id) => tamanhoDe(id).altura,
    orcamentoDeAltura: ORCAMENTO_DE_ALTURA,
  });
  return expandir(posicionarComponente(camadas, tamanhoDe));
}

/**
 * A altura da página é uma estimativa: o quanto o desenho deveria ter de
 * altura se ocupasse a tela na proporção certa. Como a estimativa erra — os
 * blocos não se dividem onde se quer —, o desenho é refeito encolhendo ou
 * esticando a página na direção do erro, até acertar a proporção ou até a
 * página bater no piso, que é onde um grafo pequeno para de se repartir.
 */
function montarNaMelhorForma(ctx, proporcao) {
  let melhor = null;
  for (let ajuste = 0; ajuste < AJUSTES_DE_PAGINA; ajuste++) {
    const bloco = montarNaMelhorLargura(ctx);
    const desvio = Math.abs(Math.log(bloco.largura / Math.max(bloco.altura, 1) / proporcao));
    if (!melhor || desvio < melhor.desvio) melhor = { bloco, desvio };
    if (desvio < TOLERANCIA_DA_PROPORCAO) break;
    const anterior = ctx.alturaDaPagina;
    ctx.alturaDaPagina = Math.max(ALTURA_MINIMA_DA_PAGINA, anterior * Math.sqrt(bloco.largura / bloco.altura / proporcao));
    if (ctx.alturaDaPagina === anterior) break;
  }
  return melhor.bloco;
}

/**
 * A proporção do desenho já sai das colunas de leitura; o que sobra para
 * escolher é a largura da faixa em que o conteúdo de cada contêiner se
 * empacota — e a melhor é a que deixa o desenho mais compacto. Faixa estreita
 * demais estica os blocos; larga demais deixa fileiras pela metade. Como a
 * área tem um vale só entre esses dois extremos, uma busca pela razão áurea
 * em escala logarítmica o encontra.
 */
function montarNaMelhorLargura(ctx) {
  const dourada = (Math.sqrt(5) - 1) / 2;
  const busca = { baixo: Math.log(TAMANHO_PADRAO.largura * 2), alto: Math.log(larguraDeUmaFila(ctx)), melhor: null };
  const avaliar = (escala) => {
    const bloco = montarRaiz({ ...ctx, largura: Math.exp(escala) });
    const area = bloco.largura * bloco.altura;
    if (!busca.melhor || area < busca.melhor.area) busca.melhor = { bloco, area };
    return { escala, area };
  };
  let esquerda = avaliar(busca.alto - dourada * (busca.alto - busca.baixo));
  let direita = avaliar(busca.baixo + dourada * (busca.alto - busca.baixo));
  for (let tentativa = 0; tentativa < TENTATIVAS_DE_LARGURA; tentativa++) {
    if (esquerda.area <= direita.area) {
      busca.alto = direita.escala;
      [direita, esquerda] = [esquerda, avaliar(busca.alto - dourada * (busca.alto - busca.baixo))];
    } else {
      busca.baixo = esquerda.escala;
      [esquerda, direita] = [direita, avaliar(busca.baixo + dourada * (busca.alto - busca.baixo))];
    }
  }
  return busca.melhor.bloco;
}

/** Uma faixa larga o bastante para que todo o conteúdo coubesse numa fila só. */
function larguraDeUmaFila(ctx) {
  let total = TAMANHO_PADRAO.largura * 2;
  for (const { blocos, soltos } of ctx.pecas.values()) {
    total += blocos.reduce((soma, b) => soma + b.largura + FOLGA_ENTRE_PECAS, 0);
    total += soltos.reduce((soma, id) => soma + ctx.tamanhoDe(id).largura + FOLGA_ENTRE_PECAS, 0);
  }
  return total;
}

/** A raiz não tem cartão: seus contêineres e seu conteúdo solto se empacotam juntos. */
function montarRaiz(ctx) {
  const blocos = ctx.raizes.map((id) => montarContainer(id, ctx));
  const conteudo = montarConteudo(null, ctx);
  if (conteudo) blocos.push(conteudo);
  if (blocos.length === 1) return blocos[0];
  return empilhar(blocos, ctx);
}

/**
 * Um contêiner é o seu cartão no canto, os filhos de árvore em coluna à
 * direita e o conteúdo embaixo do cartão. Se houver filhos de árvore, o
 * conteúdo entra no fim da coluna, para não passar por baixo do leque.
 */
function montarContainer(id, ctx) {
  const titulo = ctx.tamanhoDe(id);
  const ramos = (ctx.estrutura.filhos.get(id) ?? []).filter((f) => ehRamo(f, ctx)).sort(ctx.comparar);
  const conteudo = montarConteudo(id, ctx);
  const cartao = { largura: titulo.largura, altura: titulo.altura, itens: [{ id, x: 0, y: 0 }] };
  if (ramos.length > 0) {
    const regiao = empilhar([...ramos.map((r) => montarContainer(r, ctx)), conteudo].filter(Boolean), ctx);
    // O cartão no meio da altura dos filhos encurta o leque: nenhuma aresta
    // precisa descer a região inteira para chegar ao último bloco.
    const meio = Math.max(0, (regiao.altura - titulo.altura) / 2);
    return juntar([cartao, regiao], { posicoes: [{ x: 0, y: meio }, { x: titulo.largura + FOLGA_DA_ARVORE, y: 0 }] });
  }
  if (!conteudo) return cartao;
  return juntar([cartao, conteudo], { posicoes: [{ x: 0, y: 0 }, { x: 0, y: titulo.altura + FOLGA_ABAIXO_DO_TITULO }] });
}

/** Filho que entra na coluna da árvore: outro contêiner, ou um nó pendurado por `contem`. */
function ehRamo(id, ctx) {
  return ctx.estrutura.filhos.has(id) || ctx.estrutura.papel.get(id) === "arvore";
}

/** Componentes do contêiner primeiro, do maior ao menor, e a grade dos soltos por último. */
function montarConteudo(dono, ctx) {
  const pecas = ctx.pecas.get(dono);
  if (!pecas) return null;
  const blocos = [...pecas.blocos];
  if (pecas.soltos.length > 0) blocos.push(montarGrade(pecas.soltos, ctx.tamanhoDe, ctx.largura));
  const arranjo = empacotar(blocos, ctx.largura, FOLGA_ENTRE_PECAS);
  return juntar(blocos, arranjo);
}

function empilhar(blocos, ctx) {
  return juntar(blocos, empilharEmColunas(blocos, ctx.alturaDaPagina, FOLGA_ENTRE_IRMAOS));
}

/** Funde blocos já posicionados num bloco só, com os itens deslocados. */
function juntar(blocos, { posicoes }) {
  const itens = [];
  let largura = 0;
  let altura = 0;
  blocos.forEach((bloco, i) => {
    const { x, y } = posicoes[i];
    for (const item of bloco.itens) itens.push({ id: item.id, x: item.x + x, y: item.y + y });
    largura = Math.max(largura, x + bloco.largura);
    altura = Math.max(altura, y + bloco.altura);
  });
  return { largura, altura, itens };
}
