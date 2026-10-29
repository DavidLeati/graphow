// Testes do Artifact que o canvas cria, sem DOM: a âncora preenchida e o `deriva_de` que vai no mesmo
// pedido do nó, rodados por `node --test`. tests/web/test_javascript.py os chama pela suíte do pytest.

import { test } from "node:test";
import assert from "node:assert/strict";

import {
  ancoraPreenchida, pedidoDoArtifact, tasksDeOrigem, tasksOferecidas,
} from "../../../src/graphow/web/static/js/artifact_do_canvas.js";

const SHA256 = "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08";

test("o documento fora de git leva o sha256 e o caminho, e o campo vazio não vai", () => {
  assert.deepEqual(ancoraPreenchida({ commit: "  ", sha256: ` ${SHA256} `, caminho: "relatorios/setembro.md" }),
    { sha256: SHA256, caminho: "relatorios/setembro.md" });
  assert.deepEqual(ancoraPreenchida({ commit: "abc" }), { commit: "abc" });
  assert.deepEqual(ancoraPreenchida({}), {});
});

test("o Artifact da ação externa vai sem âncora e com o deriva_de no mesmo pedido", () => {
  assert.deepEqual(pedidoDoArtifact({ commit: "", sha256: "", caminho: "", deriva_de: ["t-envio"] }),
    { propriedades: {}, deriva_de: ["t-envio"] });
});

test("as Tasks de origem saem sem vazio nem repetição, na ordem dada", () => {
  assert.deepEqual(tasksDeOrigem(["t-1", "", " t-2 ", "t-1", null]), ["t-1", "t-2"]);
  assert.deepEqual(tasksDeOrigem(undefined), []);
});

test("o diálogo oferece só as Tasks do canvas, pelo rótulo", () => {
  const nos = new Map([
    ["t-b", { id: "t-b", tipo: "Task", rotulo: "Somar" }],
    ["g-1", { id: "g-1", tipo: "Goal", rotulo: "Meta" }],
    ["t-a", { id: "t-a", tipo: "Task", rotulo: "Enviar" }],
  ]);
  assert.deepEqual(tasksOferecidas(nos.values()).map((no) => no.id), ["t-a", "t-b"]);
});
