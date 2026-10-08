// Testes do que a caixa de propostas decide sem DOM: o corpo da decisão, o agrupamento por
// Projeto, a ordem, o resumo e o HTML, rodados por `node --test`. tests/web/test_javascript.py
// os chama pela suíte do pytest.

import { test } from "node:test";
import assert from "node:assert/strict";

import {
  agruparPorProjeto, autoria, corpoDaDecisao, DECISOES, htmlDaCaixa, htmlDaProposta, ordenarPropostas, resumoDaCaixa,
} from "../../../src/graphow/web/static/js/propostas_modelo.js";

const PROPOSTAS = [
  { id: "p3", rotulo: "Cache de leitura", status: "aberta", projeto_id: "proj-b", projeto_rotulo: "Beta", origens: [], sessao_id: "sess-b", seq_criacao: 30, autor: "agente", papel: "planejador" },
  { id: "p1", rotulo: "Migrar o log antigo", status: "aberta", projeto_id: "proj-a", projeto_rotulo: "Alfa", origens: [{ id: "task-1", tipo: "Task", rotulo: "Ler o log", seq: 5 }], sessao_id: "sess-a", seq_criacao: 10, autor: "agente", papel: "executor" },
  { id: "p2", rotulo: "Outra ideia", status: "aberta", projeto_id: "proj-a", projeto_rotulo: "Alfa", origens: [], sessao_id: null, seq_criacao: 20, autor: "", papel: "" },
  { id: "p4", rotulo: "Solta", status: "aberta", projeto_id: null, projeto_rotulo: "", origens: [], sessao_id: null, seq_criacao: 1, autor: "", papel: "" },
];

test("a decisão só leva o id, o status e o ramo: a identidade é do servidor", () => {
  assert.deepEqual(corpoDaDecisao("p1", "aceita", "main"), { id_proposta: "p1", status: "aceita", ramo_id: "main" });
});

test("a caixa oferece só aceitar e descartar", () => {
  assert.deepEqual(DECISOES.map((decisao) => decisao.status), ["aceita", "descartada"]);
});

test("as propostas saem do mais antigo ao mais novo, e o empate pelo id", () => {
  const empate = [{ ...PROPOSTAS[0], id: "b", seq_criacao: 1 }, { ...PROPOSTAS[0], id: "a", seq_criacao: 1 }];
  assert.deepEqual(ordenarPropostas(PROPOSTAS).map((p) => p.id), ["p4", "p1", "p2", "p3"]);
  assert.deepEqual(ordenarPropostas(empate).map((p) => p.id), ["a", "b"]);
});

test("os grupos vão por Projeto em ordem alfabética e o 'Sem Projeto' fica por último", () => {
  const grupos = agruparPorProjeto(PROPOSTAS);
  assert.deepEqual(grupos.map((g) => g.rotulo), ["Alfa", "Beta", "Sem Projeto"]);
  assert.deepEqual(grupos[0].itens.map((p) => p.id), ["p1", "p2"]);
});

test("o resumo conta no singular e no plural, e diz quando está vazia", () => {
  assert.equal(resumoDaCaixa([]), "Nenhuma proposta aberta.");
  assert.equal(resumoDaCaixa([PROPOSTAS[0]]), "1 proposta aberta.");
  assert.equal(resumoDaCaixa(PROPOSTAS), "4 propostas abertas.");
});

test("a autoria junta autor e papel, e some quando o servidor não os trouxe", () => {
  assert.equal(autoria(PROPOSTAS[1]), "agente (executor)");
  assert.equal(autoria(PROPOSTAS[2]), "");
});

test("o HTML da proposta leva os botões de decisão, a origem e a sessão", () => {
  const html = htmlDaProposta(PROPOSTAS[1]);
  assert.match(html, /data-decidir="aceita" data-proposta="p1"/);
  assert.match(html, /data-decidir="descartada" data-proposta="p1"/);
  assert.match(html, /data-ir="task-1"/);
  assert.match(html, /data-ir="sess-a"/);
});

test("viajando no tempo a proposta não oferece decisão", () => {
  assert.doesNotMatch(htmlDaProposta(PROPOSTAS[1], { viajando: true }), /data-decidir/);
});

test("o texto do agente é escapado no HTML", () => {
  const html = htmlDaProposta({ ...PROPOSTAS[2], rotulo: "<img src=x onerror=alert(1)>", id: 'a"b' });
  assert.doesNotMatch(html, /<img/);
  assert.match(html, /&lt;img/);
  assert.match(html, /data-ir="a&quot;b"/);
});

test("a caixa vazia explica o que ela é, e a cheia traz uma seção por Projeto", () => {
  assert.match(htmlDaCaixa([]), /Nenhuma proposta aberta/);
  const cheia = htmlDaCaixa(PROPOSTAS);
  assert.equal((cheia.match(/<details/g) || []).length, 3);
  assert.match(cheia, /<details class="secao" data-secao="proj-a" open>/);
});

test("a seção recolhida pela pessoa não volta aberta", () => {
  const html = htmlDaCaixa(PROPOSTAS, { fechados: new Set(["proj-a"]) });
  assert.doesNotMatch(html, /data-secao="proj-a" open/);
  assert.match(html, /data-secao="proj-b" open/);
});
