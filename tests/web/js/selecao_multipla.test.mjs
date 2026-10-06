// Testes da seleção múltipla do estado do canvas (Shift ou Ctrl + clique e o
// laço do Shift + arrastar), rodados por `node --test`. tests/web/test_javascript.py
// os chama pela suíte do pytest.

import { test } from "node:test";
import assert from "node:assert/strict";

import { faixaDeIds, GraphowState } from "../../../src/graphow/web/static/js/state.js";

function estadoCom(...ids) {
  const estado = new GraphowState();
  for (const id of ids) estado.nodes.set(id, { id, tipo: "Task", rotulo: id });
  estado.edges.set("e1", { id: "e1", tipo: "depende_de", origem_id: ids[0], destino_id: ids[1] });
  return estado;
}

test("o clique simples deixa só aquele nó na seleção", () => {
  const estado = estadoCom("a", "b");
  estado.alternarNoNaSelecao("a");
  estado.alternarNoNaSelecao("b");
  estado.selectElement("node", "a");
  assert.deepEqual(estado.idsDosNosSelecionados(), ["a"]);
  assert.equal(estado.emSelecaoMultipla(), false);
});

test("Shift + clique soma o nó e o faz principal; de novo, tira e devolve o principal ao último", () => {
  const estado = estadoCom("a", "b", "c");
  estado.selectElement("node", "a");
  estado.alternarNoNaSelecao("b");
  estado.alternarNoNaSelecao("c");
  assert.deepEqual(estado.idsDosNosSelecionados(), ["a", "b", "c"]);
  assert.equal(estado.selectedElement.id, "c");
  estado.alternarNoNaSelecao("c");
  assert.deepEqual(estado.idsDosNosSelecionados(), ["a", "b"]);
  assert.equal(estado.selectedElement.id, "b");
});

test("tirar o último nó esvazia a seleção", () => {
  const estado = estadoCom("a", "b");
  estado.alternarNoNaSelecao("a");
  estado.alternarNoNaSelecao("a");
  assert.equal(estado.selectedElement, null);
  assert.equal(estado.nosSelecionados.size, 0);
});

test("a aresta selecionada não entra na seleção de nós, e o primeiro nó somado a substitui", () => {
  const estado = estadoCom("a", "b");
  estado.selectElement("edge", "e1");
  assert.equal(estado.nosSelecionados.size, 0);
  estado.alternarNoNaSelecao("a");
  assert.equal(estado.selectedElement.type, "node");
  assert.deepEqual(estado.idsDosNosSelecionados(), ["a"]);
});

test("o laço soma ao que já estava selecionado e ignora ids fora do canvas", () => {
  const estado = estadoCom("a", "b", "c");
  estado.selectElement("node", "a");
  estado.selecionarNos(["b", "fantasma", "c"], { somar: true });
  assert.deepEqual(estado.idsDosNosSelecionados(), ["a", "b", "c"]);
  assert.equal(estado.selectedElement.id, "c");
});

test("cada troca de seleção avisa os ouvintes", () => {
  const estado = estadoCom("a", "b");
  const avisos = [];
  estado.subscribe((tipo) => avisos.push(tipo));
  estado.selectElement("node", "a");
  estado.alternarNoNaSelecao("b");
  estado.selecionarNos(["a"]);
  assert.deepEqual(avisos, ["SELECTION_CHANGED", "SELECTION_CHANGED", "SELECTION_CHANGED"]);
});

test("a faixa vai da âncora ao alvo, inclusive, nos dois sentidos, e sem âncora é só o alvo", () => {
  const ordem = ["a", "b", "c", "d"];
  assert.deepEqual(faixaDeIds(ordem, "a", "c"), ["a", "b", "c"]);
  assert.deepEqual(faixaDeIds(ordem, "d", "b"), ["d", "c", "b"]);
  assert.deepEqual(faixaDeIds(ordem, null, "b"), ["b"]);
  assert.deepEqual(faixaDeIds(ordem, "fora", "b"), ["b"]);
});

test("Shift + clique no explorador seleciona o item do meio e faz do alvo o principal", () => {
  const estado = estadoCom("a", "b", "c");
  estado.selectElement("node", "a");
  estado.selecionarFaixa(["a", "b", "c"], "a", "c");
  assert.deepEqual(estado.idsDosNosSelecionados(), ["a", "b", "c"]);
  assert.equal(estado.selectedElement.id, "c");
});

test("a faixa substitui a seleção, soma com Ctrl + Shift e pula o que não está no canvas", () => {
  const estado = estadoCom("a", "b", "c", "d");
  estado.selectElement("node", "d");
  estado.selecionarFaixa(["a", "x", "b"], "a", "b");
  assert.deepEqual(estado.idsDosNosSelecionados(), ["a", "b"]);
  estado.selectElement("node", "d");
  estado.selecionarFaixa(["a", "b"], "a", "b", { somar: true });
  assert.deepEqual(estado.idsDosNosSelecionados(), ["d", "a", "b"]);
});
