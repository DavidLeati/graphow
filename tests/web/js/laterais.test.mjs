// Testes do recolhimento da metade de baixo da lateral direita (o histórico),
// rodados por `node --test`. tests/web/test_javascript.py os chama pela suíte do pytest.

import { test } from "node:test";
import assert from "node:assert/strict";

import { ALTURA_PARA_RECOLHER, recolhidaDeInicio, RecolhimentoDaMetade } from "../../../src/graphow/web/static/js/laterais.js";

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
