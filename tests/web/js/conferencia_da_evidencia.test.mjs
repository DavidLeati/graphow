// Testes da T3d2: o inspetor mostra a conferência da Evidence sobre código que o canvas manda
// (`no.conferencia`), rodados por `node --test`. tests/web/test_javascript.py os chama pela suíte do
// pytest. Sem DOM: a vista recebe uma raiz de mentira, que só guarda o `innerHTML`.

import { test } from "node:test";
import assert from "node:assert/strict";

import { htmlDaConferencia } from "../../../src/graphow/web/static/js/conferencia_da_evidencia.js";
import { InspectorView } from "../../../src/graphow/web/static/js/inspector_view.js";

function raizDeMentira() {
  return { innerHTML: "", addEventListener() {}, querySelector: () => null, querySelectorAll: () => [] };
}

const ESTADO = { nodes: new Map(), edges: new Map(), isTimeTraveling: false, currentBranch: "main" };
const INDICE = { conteineres: new Map(), no: () => null, ancestrais: () => [], info: new Map() };

test("a desatualizada vem em alerta com os arquivos que mudaram, escapados", () => {
  const html = htmlDaConferencia({ estado: "desatualizada", arquivos: ["soma.py", "<x>.py"], motivo: "" });
  assert.match(html, /class="chamada mod-alerta" data-conferencia="desatualizada"/);
  assert.match(html, /Mudaram: <code>soma\.py<\/code>, <code>&lt;x&gt;\.py<\/code>\./);
});

test("sem ancora e nao conferida trazem o rotulo e o motivo; sem conferencia, nada", () => {
  assert.match(htmlDaConferencia({ estado: "sem_ancora", arquivos: [], motivo: "a Evidence nao tem o commit em que foi vista" }),
    /<span>Sem âncora: a Evidence nao tem o commit em que foi vista\.<\/span>/);
  assert.match(htmlDaConferencia({ estado: "nao_conferida", arquivos: [], motivo: "" }), /data-conferencia="nao_conferida"/);
  assert.equal(htmlDaConferencia(null), "");
  assert.equal(htmlDaConferencia({ estado: "outro" }), "");
});

test("T3d3.2: o objeto que sumiu e o clone removido dizem o motivo, sem o texto fixo da gravada sem commit", () => {
  const sumiu = htmlDaConferencia({ estado: "sem_ancora", arquivos: [], motivo: "o commit ffffffffffff nao existe mais no repositorio" });
  const semClone = htmlDaConferencia({ estado: "nao_conferida", arquivos: [], motivo: "a arvore revisada abc so ficou no clone do Goal" });
  assert.match(sumiu, /<span>Sem âncora: o commit ffffffffffff nao existe mais no repositorio\.<\/span>/);
  assert.match(semClone, /<span>Não conferida: a arvore revisada abc so ficou no clone do Goal\.<\/span>/);
  assert.doesNotMatch(sumiu + semClone, /gravada sem o commit|sem repositório git à mão/);
});

test("o inspetor da Evidence desatualizada mostra a chamada da conferencia", () => {
  const inspetor = new InspectorView(raizDeMentira(), { state: ESTADO, indice: INDICE, acoes: { ehMarcador: () => false } });
  const evidencia = { id: "ver-goal-1", tipo: "Evidence", rotulo: "Verificacao", propriedades: {},
    conferencia: { estado: "desatualizada", arquivos: ["soma.py"], motivo: "", rotulo: "desatualizada (mudaram: soma.py)" } };
  inspetor.renderNo(evidencia);
  assert.match(inspetor.raiz.innerHTML, /data-conferencia="desatualizada"/);
  assert.match(inspetor.raiz.innerHTML, /<code>soma\.py<\/code>/);
});
