/**
 * Empacotamento de blocos retangulares numa faixa de largura dada.
 *
 * Um arranjo em camadas tem a largura do número de camadas e a altura da camada
 * mais cheia. Com centenas de nós rasos isso vira uma coluna de dezenas de
 * metros de altura — a "linha gigante". A saída é não pôr tudo num arranjo só:
 * cada componente vira um bloco, e os blocos se encaixam lado a lado.
 *
 * O encaixe usa o horizonte ("skyline"): guarda o contorno de cima do que já
 * foi posto e desce cada bloco no ponto mais alto onde ele cabe, preferindo a
 * esquerda. Cabe em frestas que prateleiras fixas desperdiçariam.
 */

const LARGURA_PADRAO = 220;
const FOLGA_DA_GRADE_HORIZONTAL = 48;
const FOLGA_DA_GRADE_VERTICAL = 28;
const PROPORCAO_DA_GRADE = 1.6;

/**
 * Encaixa os blocos { largura, altura }, na ordem dada, numa faixa com a
 * largura máxima pedida. Devolve { largura, altura, posicoes } com a posição
 * de cada bloco, na mesma ordem.
 */
export function empacotar(blocos, larguraMaxima, folga) {
  const limite = Math.max(larguraMaxima, ...blocos.map((b) => b.largura));
  let horizonte = [{ x: 0, largura: limite, y: 0 }];
  const posicoes = blocos.map((bloco) => {
    const lugar = melhorLugar(horizonte, bloco.largura, limite);
    horizonte = elevar(horizonte, { x: lugar.x, largura: bloco.largura + folga, y: lugar.y + bloco.altura + folga });
    return lugar;
  });
  const largura = Math.max(0, ...blocos.map((b, i) => posicoes[i].x + b.largura));
  const altura = Math.max(0, ...blocos.map((b, i) => posicoes[i].y + b.altura));
  return { largura, altura, posicoes };
}

/** O ponto mais alto (e, no empate, mais à esquerda) onde a largura cabe. */
function melhorLugar(horizonte, largura, limite) {
  let melhor = null;
  for (let i = 0; i < horizonte.length; i++) {
    const x = horizonte[i].x;
    if (x + largura > limite + 0.5 && i > 0) break;
    const y = alturaSob(horizonte, i, x + largura);
    if (!melhor || y < melhor.y) melhor = { x, y };
  }
  return melhor;
}

/** A maior altura do contorno entre o segmento `inicio` e a abscissa `fim`. */
function alturaSob(horizonte, inicio, fim) {
  let y = 0;
  for (let j = inicio; j < horizonte.length && horizonte[j].x < fim - 0.5; j++) y = Math.max(y, horizonte[j].y);
  return y;
}

/** Sobe o contorno no trecho ocupado pelo bloco novo e junta segmentos da mesma altura. */
function elevar(horizonte, novo) {
  const fim = novo.x + novo.largura;
  const resultado = [];
  for (const segmento of horizonte) {
    const fimDoSegmento = segmento.x + segmento.largura;
    if (fimDoSegmento <= novo.x || segmento.x >= fim) resultado.push(segmento);
    else {
      if (segmento.x < novo.x) resultado.push({ ...segmento, largura: novo.x - segmento.x });
      if (fimDoSegmento > fim) resultado.push({ x: fim, largura: fimDoSegmento - fim, y: segmento.y });
    }
  }
  resultado.push(novo);
  resultado.sort((a, b) => a.x - b.x);
  return resultado.reduce((juntos, segmento) => {
    const anterior = juntos[juntos.length - 1];
    if (anterior && anterior.y === segmento.y) anterior.largura += segmento.largura;
    else juntos.push({ ...segmento });
    return juntos;
  }, []);
}

/**
 * Empilha os blocos na ordem dada, em colunas de leitura: desce até a altura
 * de uma página e recomeça ao lado. Serve para irmãos — sessões de um setor,
 * setores de um projeto —, onde a ordem diz alguma coisa (é a cronologia do
 * trabalho) e o encaixe por frestas embaralharia a leitura.
 *
 * Só se abre uma segunda coluna quando a primeira passaria da altura de uma
 * página. Doze sessões numa coluna só são uma árvore que se lê de cima a
 * baixo; reparti-las em três para acertar a proporção seria estragar um
 * desenho que já cabia na tela.
 */
export function empilharEmColunas(blocos, alturaDaPagina, folga) {
  const alturaTotal = blocos.reduce((soma, b) => soma + b.altura + folga, 0);
  const quantas = Math.min(blocos.length, Math.max(1, Math.round(alturaTotal / alturaDaPagina)));
  return distribuirEmColunas(blocos, quantas, folga);
}

/**
 * Cada bloco desce na coluna mais curta do momento. Preencher uma coluna até
 * uma altura fixa antes de abrir a próxima deixaria um setor gigante sozinho
 * numa coluna e um buraco do tamanho dele ao lado; assim as colunas terminam
 * emparelhadas, e a ordem de leitura se mantém dentro de cada uma.
 */
function distribuirEmColunas(blocos, quantas, folga) {
  const colunas = Array.from({ length: quantas }, () => ({ altura: 0, largura: 0, blocos: [] }));
  for (const bloco of blocos) {
    const coluna = colunas.reduce((menor, atual) => (atual.altura < menor.altura ? atual : menor));
    coluna.blocos.push({ bloco, y: coluna.altura });
    coluna.altura += bloco.altura + folga;
    coluna.largura = Math.max(coluna.largura, bloco.largura);
  }
  const posicoes = new Map();
  let x = 0;
  for (const coluna of colunas) {
    for (const { bloco, y } of coluna.blocos) posicoes.set(bloco, { x, y });
    x += coluna.largura + folga;
  }
  return { posicoes: blocos.map((bloco) => posicoes.get(bloco)) };
}

/**
 * Os nós sem ligação de trabalho numa grade, em ordem de leitura: sozinhos no
 * empacotamento eles se espalhariam pelas frestas e a leitura se perderia.
 * A grade é a mais quadrada que cabe na largura — vinte e três cartões numa
 * fila só atravessariam a tela sem que ninguém lesse o vigésimo.
 */
export function montarGrade(ids, tamanhoDe, larguraMaxima) {
  const passo = Math.max(LARGURA_PADRAO, ...ids.map((id) => tamanhoDe(id).largura)) + FOLGA_DA_GRADE_HORIZONTAL;
  const cabem = Math.max(1, Math.floor((larguraMaxima + FOLGA_DA_GRADE_HORIZONTAL) / passo));
  const linhas = Math.ceil(ids.length / Math.min(cabem, ids.length, colunasQuadradas(ids, tamanhoDe, passo)));
  const colunas = Math.ceil(ids.length / linhas);
  const itens = [];
  let y = 0;
  for (let linha = 0; linha < linhas; linha++) {
    const daLinha = ids.slice(linha * colunas, (linha + 1) * colunas);
    daLinha.forEach((id, coluna) => itens.push({ id, x: coluna * passo, y }));
    y += Math.max(...daLinha.map((id) => tamanhoDe(id).altura)) + FOLGA_DA_GRADE_VERTICAL;
  }
  return { largura: colunas * passo - FOLGA_DA_GRADE_HORIZONTAL, altura: y - FOLGA_DA_GRADE_VERTICAL, itens };
}

/** Colunas que deixam a grade com a proporção de uma tela, e não de uma fita. */
function colunasQuadradas(ids, tamanhoDe, passo) {
  const alturaMedia = ids.reduce((soma, id) => soma + tamanhoDe(id).altura, 0) / ids.length + FOLGA_DA_GRADE_VERTICAL;
  return Math.max(1, Math.round(Math.sqrt((ids.length * PROPORCAO_DA_GRADE * alturaMedia) / passo)));
}
