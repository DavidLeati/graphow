// Testes do recolhimento da metade de baixo da lateral direita (o histórico),
// do tamanho do texto, da largura das laterais na janela e do Esc da sobreposta,
// rodados por `node --test`. tests/web/test_javascript.py os chama pela suíte do pytest.

import { test } from "node:test";
import assert from "node:assert/strict";

import {
  ALTURA_PARA_RECOLHER, editandoTexto, formatarTamanhoDoTexto, larguraNaJanela, MINIMO_DO_CENTRO, proximoTamanhoDoTexto,
  recolhidaDeInicio, RecolhimentoDaMetade, TAMANHO_PADRAO_DO_TEXTO, TAMANHOS_DO_TEXTO, tamanhoDoTextoValido, tetoDaLargura,
} from "../../../src/graphow/web/static/js/laterais.js";

test("sem escolha gravada, a janela baixa começa com o histórico recolhido", () => {
  assert.equal(recolhidaDeInicio(null, 720), true);
  assert.equal(recolhidaDeInicio(undefined, ALTURA_PARA_RECOLHER - 1), true);
});

test("sem escolha gravada, a janela alta começa com o histórico aberto", () => {
  assert.equal(recolhidaDeInicio(null, ALTURA_PARA_RECOLHER), false);
  assert.equal(recolhidaDeInicio(null, 1080), false);
});

test("a escolha gravada vence a altura da janela nos dois sentidos", () => {
  assert.equal(recolhidaDeInicio(false, 600), false);
  assert.equal(recolhidaDeInicio(true, 1400), true);
});

test("preferência corrompida não é escolha: vale o padrão da janela", () => {
  assert.equal(recolhidaDeInicio("sim", 1080), false);
  assert.equal(recolhidaDeInicio(0, 600), true);
});

test("o gesto da pessoa troca o estado e fica como a escolha", () => {
  const estado = new RecolhimentoDaMetade(null, 600);
  assert.equal(estado.recolhida, true);
  estado.definir(false);
  assert.equal(estado.recolhida, false);
  assert.equal(estado.escolhida, false);
  estado.definir(true);
  assert.equal(estado.recolhida, true);
});

test("a seleção que pede espaço recolhe só enquanto dura, sem virar escolha", () => {
  const estado = new RecolhimentoDaMetade(null, 1080);
  assert.equal(estado.acompanhar("q1", true), true);
  assert.equal(estado.recolhida, true);
  assert.equal(estado.escolhida, false);
  assert.equal(estado.acompanhar("t1", false), true);
  assert.equal(estado.recolhida, false);
  assert.equal(estado.acompanhar(null, false), false);
  assert.equal(estado.recolhida, false);
});

test("a mesma seleção de novo não recolhe o que a pessoa expandiu", () => {
  const estado = new RecolhimentoDaMetade(null, 1080);
  estado.acompanhar("q1", true);
  estado.definir(false);
  assert.equal(estado.recolhida, false);
  assert.equal(estado.acompanhar("q1", true), false);
  assert.equal(estado.recolhida, false);
  // Outra seleção que pede espaço volta a recolher.
  assert.equal(estado.acompanhar("q2", true), true);
  assert.equal(estado.recolhida, true);
});

test("a mesma seleção que deixou de pedir espaço segue recolhida até a seleção mudar", () => {
  const estado = new RecolhimentoDaMetade(null, 1080);
  estado.acompanhar("q1", true);
  assert.equal(estado.acompanhar("q1", false), false);
  assert.equal(estado.recolhida, true);
  estado.acompanhar(null, false);
  assert.equal(estado.recolhida, false);
});

test("com o histórico recolhido por escolha, a seleção não muda nada e ele segue recolhido", () => {
  const estado = new RecolhimentoDaMetade(true, 1080);
  assert.equal(estado.acompanhar("q1", true), false);
  assert.equal(estado.acompanhar("t1", false), false);
  assert.equal(estado.recolhida, true);
});

test("recolher por gesto durante o temporário fica como escolha depois que a seleção muda", () => {
  const estado = new RecolhimentoDaMetade(false, 1080);
  estado.acompanhar("q1", true);
  estado.definir(true);
  estado.acompanhar("t1", false);
  assert.equal(estado.recolhida, true);
  assert.equal(estado.escolhida, true);
});

test("a escala do texto começa no padrão, que é um dos tamanhos oferecidos", () => {
  assert.equal(TAMANHO_PADRAO_DO_TEXTO, 1);
  assert.ok(TAMANHOS_DO_TEXTO.includes(TAMANHO_PADRAO_DO_TEXTO));
  assert.deepEqual([...TAMANHOS_DO_TEXTO].sort((a, b) => a - b), TAMANHOS_DO_TEXTO);
});

test("aumentar e diminuir andam um tamanho por vez", () => {
  assert.equal(proximoTamanhoDoTexto(1, 1), 1.15);
  assert.equal(proximoTamanhoDoTexto(1.15, 1), 1.3);
  assert.equal(proximoTamanhoDoTexto(1, -1), 0.9);
  assert.equal(proximoTamanhoDoTexto(1.3, -1), 1.15);
});

test("nas pontas da escala o tamanho para em vez de dar a volta", () => {
  const menor = TAMANHOS_DO_TEXTO[0];
  const maior = TAMANHOS_DO_TEXTO[TAMANHOS_DO_TEXTO.length - 1];
  assert.equal(proximoTamanhoDoTexto(maior, 1), maior);
  assert.equal(proximoTamanhoDoTexto(menor, -1), menor);
});

test("só o sinal do sentido conta, e sentido zero não muda nada", () => {
  assert.equal(proximoTamanhoDoTexto(1, 5), 1.15);
  assert.equal(proximoTamanhoDoTexto(1, -3), 0.9);
  assert.equal(proximoTamanhoDoTexto(1.15, 0), 1.15);
});

test("tamanho gravado fora da escala vale o padrão, e o passo parte dele", () => {
  assert.equal(tamanhoDoTextoValido(1.15), 1.15);
  assert.equal(tamanhoDoTextoValido(2), TAMANHO_PADRAO_DO_TEXTO);
  assert.equal(tamanhoDoTextoValido("1.15"), TAMANHO_PADRAO_DO_TEXTO);
  assert.equal(tamanhoDoTextoValido(null), TAMANHO_PADRAO_DO_TEXTO);
  assert.equal(proximoTamanhoDoTexto(7, 1), 1.15);
});

test("o tamanho aparece como porcentagem inteira", () => {
  assert.equal(formatarTamanhoDoTexto(1), "100%");
  assert.equal(formatarTamanhoDoTexto(1.15), "115%");
  assert.equal(formatarTamanhoDoTexto(0.9), "90%");
});

// A lateral direita: mínimo 260, máximo fixo 620; a faixa (44) e a esquerda (272) ficam fora do centro.
const DIREITA = { minimo: 260, maximo: 620 };
const naJanela = (pedida, larguraDaJanela, alheio = 44 + 272) => larguraNaJanela(pedida, { ...DIREITA, larguraDaJanela, alheio });

test("o teto é o máximo fixo até a janela passar do dobro dele, e metade dela depois", () => {
  assert.equal(tetoDaLargura(620, 1280), 640);
  assert.equal(tetoDaLargura(620, 1240), 620);
  assert.equal(tetoDaLargura(620, 1000), 620);
  assert.equal(tetoDaLargura(620, 2561), 1280);
});

test("numa janela larga a lateral cresce até metade dela", () => {
  assert.equal(naJanela(900, 1920), 900);
  assert.equal(naJanela(1200, 1920), 960);
  assert.equal(naJanela(700, 1280), 640);
});

test("a largura pedida vale inteira quando cabe, e o piso vale abaixo do mínimo", () => {
  assert.equal(naJanela(340, 1280), 340);
  assert.equal(naJanela(100, 1280), 260);
});

test("ao encolher a janela a lateral cede para o centro não passar do mínimo dele", () => {
  const larguraDaJanela = 1000;
  const alheio = 44 + 272;
  const largura = naJanela(620, larguraDaJanela, alheio);
  assert.equal(largura, larguraDaJanela - alheio - MINIMO_DO_CENTRO);
  assert.equal(larguraDaJanela - alheio - largura, MINIMO_DO_CENTRO);
});

test("sem espaço nem para o centro, a lateral fica no próprio mínimo", () => {
  assert.equal(naJanela(340, 901, 44 + 560), 260);
});

test("com a esquerda recolhida o centro deixa mais para a direita", () => {
  assert.equal(naJanela(620, 1000, 44), 620);
  assert.equal(naJanela(620, 1000, 44 + 272), 364);
});

// O Esc da lateral sobreposta: os elementos são objetos com o que o teste lê do DOM.
test("o Esc num campo com texto é de quem digita", () => {
  assert.equal(editandoTexto({ tagName: "TEXTAREA", value: "rascunho da resposta" }), true);
  assert.equal(editandoTexto({ tagName: "INPUT", type: "text", value: "abc" }), true);
  assert.equal(editandoTexto({ tagName: "INPUT", type: "search", value: "log" }), true);
  assert.equal(editandoTexto({ tagName: "DIV", isContentEditable: true, textContent: "nota" }), true);
});

test("num campo vazio não há rascunho, e o Esc fecha a lateral", () => {
  assert.equal(editandoTexto({ tagName: "TEXTAREA", value: "" }), false);
  assert.equal(editandoTexto({ tagName: "INPUT", type: "text", value: "" }), false);
  assert.equal(editandoTexto({ tagName: "DIV", isContentEditable: true, textContent: "" }), false);
});

test("fora de campo de texto o Esc fecha a lateral", () => {
  assert.equal(editandoTexto(null), false);
  assert.equal(editandoTexto({ tagName: "BODY" }), false);
  assert.equal(editandoTexto({ tagName: "BUTTON", value: "salvar" }), false);
  assert.equal(editandoTexto({ tagName: "SELECT", value: "aberta" }), false);
  assert.equal(editandoTexto({ tagName: "INPUT", type: "checkbox", value: "on" }), false);
});
