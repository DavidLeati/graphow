// Testes das contas de datas do calendário e da lista do histórico,
// rodados por `node --test`. tests/web/test_javascript.py os chama pela suíte do pytest.
// As datas são montadas por ano, mês e dia locais, como o histórico as vê:
// assim os testes dão o mesmo resultado em qualquer fuso.

import { test } from "node:test";
import assert from "node:assert/strict";

import {
  chaveDoDia, dataDaChave, diasDaGradeDoMes, diasDaSemana, inicioDaSemana, mesmoMes, passarMes, passarSemana,
  tituloDoPeriodo,
} from "../../../src/graphow/web/static/js/calendario.js";

const chaves = (datas) => datas.map(chaveDoDia);

test("a chave do dia usa o dia local, com mês e dia em dois dígitos", () => {
  assert.equal(chaveDoDia(new Date(2026, 0, 5)), "2026-01-05");
  assert.equal(chaveDoDia(new Date(2026, 8, 30, 23, 59)), "2026-09-30");
});

test("a chave volta à meia-noite local do mesmo dia", () => {
  const data = dataDaChave("2026-02-28");
  assert.equal(chaveDoDia(data), "2026-02-28");
  assert.equal(data.getHours(), 0);
});

test("a semana começa no domingo, como a primeira coluna do calendário", () => {
  assert.equal(chaveDoDia(inicioDaSemana(new Date(2026, 8, 30))), "2026-09-27");
  assert.equal(chaveDoDia(inicioDaSemana(new Date(2026, 8, 27))), "2026-09-27");
  assert.equal(chaveDoDia(inicioDaSemana(new Date(2026, 9, 3, 22, 0))), "2026-09-27");
});

test("a semana de uma data são sete dias, de domingo a sábado", () => {
  assert.deepEqual(chaves(diasDaSemana(new Date(2026, 8, 30))), [
    "2026-09-27", "2026-09-28", "2026-09-29", "2026-09-30", "2026-10-01", "2026-10-02", "2026-10-03",
  ]);
});

test("a semana atravessa a virada do ano sem se perder", () => {
  const dias = chaves(diasDaSemana(new Date(2026, 0, 1)));
  assert.equal(dias[0], "2025-12-28");
  assert.equal(dias[6], "2026-01-03");
});

test("a grade do mês tem seis semanas e começa no domingo antes do dia 1", () => {
  const dias = diasDaGradeDoMes(new Date(2026, 8, 17));
  assert.equal(dias.length, 42);
  assert.equal(chaveDoDia(dias[0]), "2026-08-30");
  assert.equal(chaveDoDia(dias[41]), "2026-10-10");
  assert.ok(dias.every((data) => data.getHours() === 0));
});

test("o passo de semana leva ao domingo da semana vizinha", () => {
  const quarta = new Date(2026, 8, 30);
  assert.equal(chaveDoDia(passarSemana(quarta, 1)), "2026-10-04");
  assert.equal(chaveDoDia(passarSemana(quarta, -1)), "2026-09-20");
  assert.equal(chaveDoDia(passarSemana(quarta, 0)), "2026-09-27");
});

test("o passo de semana atravessa meses e anos", () => {
  assert.equal(chaveDoDia(passarSemana(new Date(2026, 11, 30), 1)), "2027-01-03");
  assert.equal(chaveDoDia(passarSemana(new Date(2026, 2, 1), -1)), "2026-02-22");
});

test("o passo de mês cai no dia 1 e não pula o mês curto", () => {
  assert.equal(chaveDoDia(passarMes(new Date(2026, 0, 31), 1)), "2026-02-01");
  assert.equal(chaveDoDia(passarMes(new Date(2026, 0, 15), -1)), "2025-12-01");
  assert.equal(chaveDoDia(passarMes(new Date(2026, 11, 3), 1)), "2027-01-01");
});

test("mesmo mês pede mesmo ano", () => {
  assert.equal(mesmoMes(new Date(2026, 8, 1), new Date(2026, 8, 30)), true);
  assert.equal(mesmoMes(new Date(2026, 8, 1), new Date(2025, 8, 1)), false);
});

test("período num mês só leva o mês por extenso", () => {
  assert.deepEqual(tituloDoPeriodo(new Date(2026, 8, 1), new Date(2026, 8, 7)), { mes: "setembro", ano: "2026" });
});

test("semana que atravessa o mês leva os dois meses abreviados", () => {
  assert.deepEqual(tituloDoPeriodo(new Date(2026, 8, 27), new Date(2026, 9, 3)), { mes: "set. – out.", ano: "2026" });
  assert.deepEqual(tituloDoPeriodo(new Date(2025, 11, 28), new Date(2026, 0, 3)), { mes: "dez. – jan.", ano: "2025–2026" });
});
