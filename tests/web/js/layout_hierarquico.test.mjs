// Testes do arranjo automático do canvas, rodados por `node --test`.
// tests/web/test_javascript.py os chama pela suíte do pytest.

import { test } from "node:test";
import assert from "node:assert/strict";

import { calcularLayoutHierarquico } from "../../../src/graphow/web/static/js/layout_hierarquico.js";

/** Gerador determinístico: o mesmo grafo em toda execução. */
function sorteador(semente) {
  let estado = semente;
  return () => (estado = (estado * 1103515245 + 12345) % 2147483648) / 2147483648;
}

/** Projeto com setores e sessões; cada sessão tem Goal, Tasks, Decisions e Evidences ligadas. */
function montarGrafo({ setores, sessoesPorSetor, nosPorSessao }) {
  const sortear = sorteador(7);
  const nodes = [];
  const edges = [];
  const no = (id, tipo) => nodes.push({ id, tipo, rotulo: id, seq_criacao: nodes.length, propriedades: {} });
  const aresta = (de, para, tipo) => edges.push({ id: `e${edges.length}`, origem_id: de, destino_id: para, tipo });
  no("proj", "Projeto");
  for (let s = 0; s < setores; s++) {
    const setor = `setor${s}`;
    no(setor, "Setor");
    aresta("proj", setor, "contem");
    for (let k = 0; k < sessoesPorSetor; k++) montarSessao(`${setor}-sess${k}`, setor, { nosPorSessao, no, aresta, sortear });
  }
  return { nodes, edges };
}

function montarSessao(sessao, setor, { nosPorSessao, no, aresta, sortear }) {
  no(sessao, "Sessao");
  aresta(setor, sessao, "contem");
  const goal = `${sessao}-goal`;
  no(goal, "Goal");
  aresta(sessao, goal, "produz");
  const tarefas = [];
  for (let restantes = nosPorSessao - 1; restantes > 0; ) {
    const tarefa = `${sessao}-t${restantes--}`;
    no(tarefa, "Task");
    aresta(sessao, tarefa, "produz");
    aresta(goal, tarefa, "decompoe");
    if (tarefas.length > 0 && sortear() < 0.3) aresta(tarefa, tarefas[tarefas.length - 1], "depende_de");
    tarefas.push(tarefa);
    if (restantes <= 0) break;
    const decisao = `${sessao}-d${restantes--}`;
    no(decisao, "Decision");
    aresta(sessao, decisao, "produz");
    aresta(decisao, tarefa, "orienta");
    const evidencias = Math.min(restantes, sortear() < 0.15 ? 17 : Math.floor(sortear() * 3));
    for (let i = 0; i < evidencias; i++, restantes--) {
      const evidencia = `${decisao}-ev${i}`;
      no(evidencia, "Evidence");
      aresta(sessao, evidencia, "produz");
      aresta(evidencia, decisao, "justifica");
    }
  }
  // Dependências entre tarefas distantes: são as arestas longas, que viram corredores.
  for (let i = 0; i < tarefas.length / 20; i++) {
    const de = tarefas[Math.floor(sortear() * tarefas.length)];
    const para = tarefas[Math.floor(sortear() * tarefas.length)];
    if (de !== para) aresta(de, para, "depende_de");
  }
}

function arranjar(grafo) {
  const tamanhos = new Map(grafo.nodes.map((n) => [n.id, { largura: 220, altura: 150 }]));
  return calcularLayoutHierarquico(grafo.nodes, grafo.edges, { tamanhos, proporcao: 16 / 10 });
}

function sobreposicoes(posicoes) {
  const caixas = [...posicoes.values()];
  let total = 0;
  for (let i = 0; i < caixas.length; i++) {
    for (let j = i + 1; j < caixas.length; j++) {
      const a = caixas[i];
      const b = caixas[j];
      if (a.x < b.x + 220 && b.x < a.x + 220 && a.y < b.y + 150 && b.y < a.y + 150) total++;
    }
  }
  return total;
}

test("sessão de mil nós fica numa caixa do tamanho do desenho, sem coordenada astronômica", () => {
  const grafo = montarGrafo({ setores: 1, sessoesPorSetor: 1, nosPorSessao: 1000 });

  const posicoes = arranjar(grafo);

  assert.equal(posicoes.size, grafo.nodes.length);
  const coordenadas = [...posicoes.values()].flatMap(({ x, y }) => [x, y]);
  assert.ok(coordenadas.every(Number.isFinite));
  // A sessão tinha y na casa de 7e12: a altura do corredor se realimentava a cada relaxação.
  assert.ok(Math.max(...coordenadas) < 200_000, `maior coordenada: ${Math.max(...coordenadas)}`);
});

test("duzentos e vinte cartões sem sobreposição", () => {
  const posicoes = arranjar(montarGrafo({ setores: 3, sessoesPorSetor: 3, nosPorSessao: 24 }));

  assert.equal(sobreposicoes(posicoes), 0);
});

test("o mesmo grafo sai sempre no mesmo arranjo", () => {
  const grafo = montarGrafo({ setores: 2, sessoesPorSetor: 2, nosPorSessao: 30 });

  assert.deepEqual([...arranjar(grafo)], [...arranjar(grafo)]);
});
