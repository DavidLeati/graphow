// Testes da leitura do fluxo que alimenta o quadro e o painel de impacto,
// rodados por `node --test`. tests/web/test_javascript.py os chama pela suíte do pytest.

import { test } from "node:test";
import assert from "node:assert/strict";

import { ladoDoVizinho, lerFluxo, statusDe } from "../../../src/graphow/web/static/js/leitura_de_fluxo.js";

/** Um objetivo com três tarefas, uma subtarefa e o contexto em volta delas. */
function montarFluxo() {
  const nos = [];
  const arestas = [];
  const no = (id, tipo, status) => nos.push({ id, tipo, rotulo: id, seq_criacao: nos.length, propriedades: status ? { status } : {} });
  const aresta = (origem, destino, tipo) => arestas.push({ id: `e${arestas.length}`, origem_id: origem, destino_id: destino, tipo });
  no("sess", "Sessao");
  no("goal", "Goal");
  no("t1", "Task", "concluido");
  no("t2", "Task", "bloqueado");
  no("t3", "Task");
  no("t2a", "Task", "em_andamento");
  no("q", "Question");
  no("q-fechada", "Question", "respondida");
  no("dec", "Decision");
  no("art", "Artifact");
  no("evid", "Evidence");
  no("orfa", "Task");
  no("run", "Run", "concluida");
  no("apr", "Aprendizado");
  for (const id of ["goal", "t1", "t2", "t3", "t2a", "q", "dec", "art", "evid", "orfa"]) aresta("sess", id, "produz");
  aresta("goal", "t1", "decompoe");
  aresta("goal", "t2", "decompoe");
  aresta("goal", "t3", "decompoe");
  aresta("t2", "t2a", "decompoe");
  aresta("t2", "t1", "depende_de");
  aresta("t3", "t2", "depende_de");
  aresta("q", "t2", "bloqueia");
  aresta("q-fechada", "t2", "bloqueia");
  aresta("dec", "t2a", "orienta");
  aresta("art", "t2a", "deriva_de");
  aresta("evid", "art", "deriva_de");
  aresta("evid", "dec", "justifica");
  aresta("run", "sess", "ocorreu_em");
  aresta("apr", "evid", "deriva_de");
  return lerFluxo(nos, arestas);
}

test("status ausente vira o padrão do tipo", () => {
  assert.equal(statusDe({ tipo: "Task", propriedades: {} }), "pendente");
  assert.equal(statusDe({ tipo: "Question" }), "aberta");
  assert.equal(statusDe({ tipo: "Decision", propriedades: {} }), null);
  assert.equal(statusDe({ tipo: "Task", propriedades: { status: "concluido" } }), "concluido");
});

test("quem depende tem o pré-requisito a montante; quem bloqueia fica a montante do bloqueado", () => {
  assert.equal(ladoDoVizinho("depende_de", true), "montante");
  assert.equal(ladoDoVizinho("depende_de", false), "jusante");
  assert.equal(ladoDoVizinho("bloqueia", false), "montante");
  assert.equal(ladoDoVizinho("bloqueia", true), "jusante");
});

test("todo nó de trabalho sobe até o objetivo pelas âncoras", () => {
  const fluxo = montarFluxo();
  for (const id of ["t1", "t2a", "q", "dec", "art", "evid"]) assert.equal(fluxo.objetivoDe(id), "goal", id);
  assert.equal(fluxo.objetivoDe("orfa"), null);
  assert.equal(fluxo.objetivoDe("apr"), null, "aprendizado não se pendura em objetivo");
});

test("a evidência de um artefato cerca a subtarefa, não a tarefa-mãe", () => {
  const fluxo = montarFluxo();
  assert.equal(fluxo.tarefaDe("evid"), "t2a");
  assert.deepEqual(fluxo.contextoDe("t2a"), ["dec", "art", "evid"]);
  assert.deepEqual(fluxo.contextoDe("t2"), ["q", "q-fechada"]);
});

test("só a pergunta aberta conta como bloqueio", () => {
  const fluxo = montarFluxo();
  assert.deepEqual(fluxo.perguntasAbertas("t2"), ["q"]);
  assert.deepEqual(fluxo.dependeDe("t3"), ["t2"]);
  assert.deepEqual(fluxo.liberaQuem("t2"), ["t3"]);
});

test("vizinhos separam o que afeta do que é afetado e escondem a sessão do trabalho", () => {
  const fluxo = montarFluxo();
  const { montante, jusante } = fluxo.vizinhos("t2");
  assert.deepEqual(montante.map((v) => v.id).sort(), ["goal", "q", "q-fechada", "t1"]);
  assert.deepEqual(jusante.map((v) => v.id).sort(), ["t2a", "t3"]);
  const comSessao = fluxo.vizinhos("t2", { estrutura: true });
  assert.ok(comSessao.montante.some((v) => v.id === "sess"));
  assert.ok(fluxo.vizinhos("sess").jusante.some((v) => v.id === "goal"), "contêiner mostra o que produziu");
});

test("raias seguem os objetivos e juntam as órfãs no fim", () => {
  const fluxo = montarFluxo();
  assert.deepEqual(fluxo.raias(), [
    { objetivo: "goal", tarefas: ["t1", "t2", "t3", "t2a"] },
    { objetivo: null, tarefas: ["orfa"] },
  ]);
});

test("o minimapa cobre cada nó exatamente uma vez", () => {
  const fluxo = montarFluxo();
  const grupos = fluxo.grupos();
  assert.deepEqual(grupos.map((g) => g.chave), ["goal", "solto", "estrutura", "memoria"]);
  const todos = grupos.flatMap((g) => g.nos);
  assert.equal(new Set(todos).size, todos.length);
  assert.equal(todos.length, fluxo.porId.size);
});

test("ciclo de âncoras não trava a subida", () => {
  const fluxo = lerFluxo(
    [{ id: "a", tipo: "Task" }, { id: "b", tipo: "Task" }],
    [{ id: "e1", origem_id: "a", destino_id: "b", tipo: "decompoe" }, { id: "e2", origem_id: "b", destino_id: "a", tipo: "decompoe" }],
  );
  assert.equal(fluxo.objetivoDe("a"), null);
});

test("aresta para nó fora do canvas é ignorada", () => {
  const fluxo = lerFluxo([{ id: "t", tipo: "Task" }], [{ id: "e", origem_id: "t", destino_id: "fora", tipo: "depende_de" }]);
  assert.deepEqual(fluxo.dependeDe("t"), []);
});
