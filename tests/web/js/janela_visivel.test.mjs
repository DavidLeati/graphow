// Testes da conta de quais cartões e arestas cabem na janela do canvas, rodados
// por `node --test`. tests/web/test_javascript.py os chama pela suíte do pytest.

import { test } from "node:test";
import assert from "node:assert/strict";

import {
  expandirRetangulo, FOLGA_DA_CURVA, idsNaJanela, janelaComMargem, retanguloDaAresta, retanguloVisivel, retangulosSeCruzam,
} from "../../../src/graphow/web/static/js/janela_visivel.js";

const PADRAO = { largura: 220, altura: 150 };
const JANELA = { x: 0, y: 0, largura: 1000, altura: 800 };

function ids(posicoes, janela = JANELA, tamanhos = new Map()) {
  return [...idsNaJanela({ posicoes: new Map(posicoes), tamanhos, janela, tamanhoPadrao: PADRAO })].sort();
}

test("o retângulo visível com zoom 1 e pan zero é o próprio viewport", () => {
  const r = retanguloVisivel({ panX: 0, panY: 0, zoom: 1, larguraDoViewport: 1440, alturaDoViewport: 900 });
  assert.deepEqual(r, { x: 0, y: 0, largura: 1440, altura: 900 });
});

test("o pan negativo desloca a janela para a direita e para baixo no mundo", () => {
  const r = retanguloVisivel({ panX: -500, panY: -200, zoom: 1, larguraDoViewport: 1000, alturaDoViewport: 800 });
  assert.equal(r.x, 500);
  assert.equal(r.y, 200);
});

test("o pan positivo mostra o mundo à esquerda do zero", () => {
  const r = retanguloVisivel({ panX: 300, panY: 40, zoom: 1, larguraDoViewport: 1000, alturaDoViewport: 800 });
  assert.equal(r.x, -300);
  assert.equal(r.y, -40);
});

test("com zoom 2 a janela cobre metade do mundo e o pan é dividido pelo zoom", () => {
  const r = retanguloVisivel({ panX: -400, panY: -100, zoom: 2, larguraDoViewport: 1000, alturaDoViewport: 800 });
  assert.deepEqual(r, { x: 200, y: 50, largura: 500, altura: 400 });
});

test("com zoom 0,5 a janela cobre o dobro do mundo", () => {
  const r = retanguloVisivel({ panX: 0, panY: 0, zoom: 0.5, larguraDoViewport: 1000, alturaDoViewport: 800 });
  assert.deepEqual(r, { x: 0, y: 0, largura: 2000, altura: 1600 });
});

test("a margem padrão é meia janela para cada lado", () => {
  const margem = janelaComMargem({ x: 100, y: 50, largura: 1000, altura: 800 });
  assert.deepEqual(margem, { x: -400, y: -350, largura: 2000, altura: 1600 });
});

test("expandir com um valor só cresce os dois eixos", () => {
  assert.deepEqual(expandirRetangulo({ x: 10, y: 10, largura: 20, altura: 20 }, 5), { x: 5, y: 5, largura: 30, altura: 30 });
});

test("um cartão inteiro dentro da janela entra", () => {
  assert.deepEqual(ids([["a", { x: 100, y: 100 }]]), ["a"]);
});

test("um cartão longe da janela fica de fora", () => {
  assert.deepEqual(ids([["a", { x: 5000, y: 100 }], ["b", { x: 100, y: 5000 }], ["c", { x: -3000, y: -3000 }]]), []);
});

test("um cartão que só atravessa a borda entra", () => {
  assert.deepEqual(ids([["a", { x: 900, y: 100 }]]), ["a"]);
  assert.deepEqual(ids([["b", { x: -100, y: 100 }]]), ["b"]);
});

test("encostar na borda conta como dentro", () => {
  // O cartão termina exatamente em x = 0 e começa exatamente em x = 1000.
  assert.deepEqual(ids([["esquerda", { x: -220, y: 10 }], ["direita", { x: 1000, y: 10 }]]), ["direita", "esquerda"]);
});

test("um pixel além da borda fica de fora", () => {
  assert.deepEqual(ids([["a", { x: -221, y: 10 }], ["b", { x: 1001, y: 10 }], ["c", { x: 10, y: 801 }], ["d", { x: 10, y: -151 }]]), []);
});

test("a margem traz o que está fora da janela visível, mas perto", () => {
  const posicoes = [["perto", { x: 1300, y: 100 }], ["longe", { x: 1800, y: 100 }]];
  assert.deepEqual(ids(posicoes), []);
  assert.deepEqual(ids(posicoes, janelaComMargem(JANELA)), ["perto"]);
});

test("o tamanho medido vale mais que o padrão", () => {
  // Largo o bastante para alcançar a janela partindo de x = -400.
  const posicoes = [["a", { x: -400, y: 10 }]];
  assert.deepEqual(ids(posicoes), []);
  assert.deepEqual(ids(posicoes, JANELA, new Map([["a", { largura: 500, altura: 100 }]])), ["a"]);
});

test("tamanho medido zero cai no padrão", () => {
  const tamanhos = new Map([["a", { largura: 0, altura: 0 }]]);
  assert.deepEqual(ids([["a", { x: -200, y: 10 }]], JANELA, tamanhos), ["a"]);
});

test("zoom diferente de 1: o que cabe na tela muda no mundo", () => {
  // Com zoom 2 só 500 x 400 do mundo aparecem; o cartão em x = 700 sai.
  const janela = retanguloVisivel({ panX: 0, panY: 0, zoom: 2, larguraDoViewport: 1000, alturaDoViewport: 800 });
  assert.deepEqual(ids([["dentro", { x: 400, y: 100 }], ["fora", { x: 700, y: 100 }]], janela), ["dentro"]);
  // Com zoom 0,5 o mundo visível dobra e o mesmo cartão volta.
  const afastada = retanguloVisivel({ panX: 0, panY: 0, zoom: 0.5, larguraDoViewport: 1000, alturaDoViewport: 800 });
  assert.deepEqual(ids([["fora", { x: 700, y: 100 }]], afastada), ["fora"]);
});

test("pan negativo: o cartão no começo do mundo sai e o distante entra", () => {
  const janela = retanguloVisivel({ panX: -5000, panY: -3000, zoom: 1, larguraDoViewport: 1000, alturaDoViewport: 800 });
  const posicoes = [["origem", { x: 0, y: 0 }], ["alvo", { x: 5400, y: 3300 }]];
  assert.deepEqual(ids(posicoes, janela), ["alvo"]);
});

test("uma aresta longa cuja ponta está fora da janela, mas o meio atravessa, tem retângulo que a cruza", () => {
  const origem = { x: -2000, y: 100, largura: 220, altura: 150 };
  const destino = { x: 3000, y: 100, largura: 220, altura: 150 };
  assert.equal(retangulosSeCruzam(retanguloDaAresta(origem, destino), JANELA), true);
});

test("o retângulo da aresta cresce da folga da curva em volta dos dois cartões", () => {
  const a = { x: 100, y: 100, largura: 200, altura: 100 };
  const b = { x: 500, y: 400, largura: 200, altura: 100 };
  assert.deepEqual(retanguloDaAresta(a, b, 10), { x: 90, y: 90, largura: 620, altura: 420 });
});

test("uma aresta toda fora da janela não cruza, mesmo com a folga", () => {
  const a = { x: 3000, y: 3000, largura: 220, altura: 150 };
  const b = { x: 3500, y: 3200, largura: 220, altura: 150 };
  assert.equal(retangulosSeCruzam(retanguloDaAresta(a, b), JANELA), false);
});

test("a folga da curva alcança a janela quando os cartões ficam logo além dela", () => {
  const b = { x: 1400, y: 100, largura: 220, altura: 150 };
  const perto = { x: 1000 + FOLGA_DA_CURVA - 10, y: 100, largura: 220, altura: 150 };
  const longe = { x: 1000 + FOLGA_DA_CURVA + 10, y: 100, largura: 220, altura: 150 };
  assert.equal(retangulosSeCruzam(retanguloDaAresta(perto, b, 0), JANELA), false);
  assert.equal(retangulosSeCruzam(retanguloDaAresta(perto, b), JANELA), true);
  assert.equal(retangulosSeCruzam(retanguloDaAresta(longe, b), JANELA), false);
});
