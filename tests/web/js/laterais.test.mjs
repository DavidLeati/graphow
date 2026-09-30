// Testes do recolhimento da metade de baixo da lateral direita (o histórico)
// e do tamanho do texto das laterais,
// rodados por `node --test`. tests/web/test_javascript.py os chama pela suíte do pytest.

import { test } from "node:test";
import assert from "node:assert/strict";

import {
  ALTURA_PARA_RECOLHER, formatarTamanhoDoTexto, proximoTamanhoDoTexto, recolhidaDeInicio, RecolhimentoDaMetade,
  TAMANHO_PADRAO_DO_TEXTO, TAMANHOS_DO_TEXTO, tamanhoDoTextoValido,
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
