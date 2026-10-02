// Testes da G9: liberar posse (inspetor, menu e API), o status do Goal e o selo "pelo árbitro"
// nas três telas que mostram uma Question respondida ou um Aprendizado promovido, rodados
// por `node --test`. tests/web/test_javascript.py os chama pela suíte do pytest. Sem DOM:
// as vistas recebem uma raiz de mentira, que só guarda o `innerHTML`.

import { test } from "node:test";
import assert from "node:assert/strict";

import { api } from "../../../src/graphow/web/static/js/api.js";
import { InspectorView } from "../../../src/graphow/web/static/js/inspector_view.js";
import { LeituraDaQuestaoView } from "../../../src/graphow/web/static/js/leitura_questao_view.js";
import { MemoriaView } from "../../../src/graphow/web/static/js/memoria_view.js";
import { itensDoMenuDoNo } from "../../../src/graphow/web/static/js/menus_do_grafo.js";
import { definirVocabulario, statusDoTipo } from "../../../src/graphow/web/static/js/ontologia_ui.js";
import { foiPeloArbitro, montarSeloDoArbitro } from "../../../src/graphow/web/static/js/selo_do_arbitro.js";

function raizDeMentira() {
  return { innerHTML: "", addEventListener() {}, querySelector: () => null, querySelectorAll: () => [] };
}

function estado(sobrescrever = {}) {
  return { nodes: new Map(), edges: new Map(), isTimeTraveling: false, currentBranch: "main", ...sobrescrever };
}

const INDICE = { conteineres: new Map(), no: () => null, ancestrais: () => [], info: new Map() };

test("o selo so aparece para o papel arbitro e leva o autor na dica", () => {
  assert.equal(foiPeloArbitro("arbitro"), true);
  assert.equal(foiPeloArbitro("humano"), false);
  assert.equal(montarSeloDoArbitro("humano", "david", "Respondida"), "");
  assert.equal(montarSeloDoArbitro(undefined, "", "Respondida"), "");
  const selo = montarSeloDoArbitro("arbitro", "arbitro-a1#x", "Respondida");
  assert.match(selo, /class="selo-arbitro"/);
  assert.match(selo, /pelo árbitro/);
  assert.match(selo, /title="Respondida pelo árbitro \(arbitro-a1#x\)"/);
  assert.match(montarSeloDoArbitro("arbitro", "", "Promovido"), /title="Promovido pelo árbitro"/);
});

test("o vocabulario de status do Goal vem de /api/ontologia e o menu o oferece", () => {
  definirVocabulario({
    arestas: { contem: [] },
    status: { Goal: ["pendente", "em_andamento", "concluido"], Task: ["pendente"] },
  });
  assert.deepEqual(statusDoTipo("Goal"), ["pendente", "em_andamento", "concluido"]);
  const goal = { id: "goal-1", tipo: "Goal", rotulo: "Meta", propriedades: { status: "pendente" } };
  const menu = itensDoMenuDoNo({ state: estado(), marcadores: { contem: () => false }, indice: { escopoDe: () => null } }, goal);
  const mudar = menu.find((item) => item?.rotulo === "Mudar status");
  assert.deepEqual(mudar.submenu.map((item) => item.rotulo), ["pendente", "em andamento", "concluido"]);
  assert.equal(mudar.submenu[0].marcado, true);
});

test("o menu da Task so oferece liberar posse quando ha dono, e a acao chama o dialogo", async () => {
  const chamadas = [];
  const app = {
    state: estado(),
    marcadores: { contem: () => false },
    indice: { escopoDe: () => null },
    dialogos: { liberarPosse: async (no) => chamadas.push(no.id) },
  };
  const livre = { id: "task-1", tipo: "Task", rotulo: "T", propriedades: { status: "pendente" } };
  assert.equal(itensDoMenuDoNo(app, livre).some((item) => /Liberar posse/.test(item?.rotulo || "")), false);

  const presa = { ...livre, lock_ativo: "executor-sonnet#838b3d" };
  const item = itensDoMenuDoNo(app, presa).find((candidato) => /Liberar posse/.test(candidato?.rotulo || ""));
  assert.equal(item.rotulo, "Liberar posse de executor-sonnet#838b3d");
  assert.equal(item.desabilitado, false);
  await item.acao();
  assert.deepEqual(chamadas, ["task-1"]);

  const passado = { ...app, state: estado({ isTimeTraveling: true }) };
  const viajando = itensDoMenuDoNo(passado, presa).find((candidato) => /Liberar posse/.test(candidato?.rotulo || ""));
  assert.equal(viajando.desabilitado, true);
});

test("o inspetor mostra Liberar posse na Task em posse e o clique chama a acao", () => {
  const liberadas = [];
  const inspetor = new InspectorView(raizDeMentira(), { state: estado(), indice: INDICE, acoes: { liberarPosse: (no) => liberadas.push(no.id) } });
  const presa = { id: "task-1", tipo: "Task", rotulo: "T", lock_ativo: "agente-x", propriedades: {} };

  const html = inspetor.montarAlertas(presa);
  assert.match(html, /Em posse de <strong>agente-x<\/strong>/);
  assert.match(html, /data-acao="liberar-posse"/);
  assert.match(html, /Liberar posse/);

  inspetor.noRenderizado = presa;
  inspetor.aoClicar({ target: { closest: () => ({ dataset: { acao: "liberar-posse" } }) } });
  assert.deepEqual(liberadas, ["task-1"]);

  assert.doesNotMatch(inspetor.montarAlertas({ ...presa, lock_ativo: null }), /liberar-posse/);
  assert.doesNotMatch(inspetor.montarAlertas({ ...presa, tipo: "Goal" }), /liberar-posse/);
  inspetor.state.isTimeTraveling = true;
  assert.doesNotMatch(inspetor.montarAlertas(presa), /liberar-posse/);
});

test("o inspetor mostra o selo na Question respondida pelo arbitro e no Aprendizado promovido por ele", () => {
  const inspetor = new InspectorView(raizDeMentira(), { state: estado(), indice: INDICE, acoes: {} });
  const respondida = {
    id: "q-1", tipo: "Question", rotulo: "Q",
    propriedades: { status: "respondida", resposta: "sim", respondida_por: "arbitro-1", respondida_por_papel: "arbitro" },
  };
  assert.match(inspetor.montarBlocoDaQuestao(respondida, ""), /selo-arbitro[^>]*title="Respondida pelo árbitro \(arbitro-1\)"/);
  const humana = { ...respondida, propriedades: { ...respondida.propriedades, respondida_por_papel: "humano" } };
  assert.doesNotMatch(inspetor.montarBlocoDaQuestao(humana, ""), /selo-arbitro/);
  assert.match(inspetor.montarBlocoDaQuestao(respondida, ""), /Resposta do árbitro/);
  assert.doesNotMatch(inspetor.montarBlocoDaQuestao(respondida, ""), /Resposta humana/);
  assert.match(inspetor.montarBlocoDaQuestao(humana, ""), /Resposta humana/);
  assert.match(inspetor.montarBlocoDaQuestao({ ...respondida, propriedades: { status: "aberta", respondida_por_papel: "arbitro" } }, ""), /Resposta humana/);

  const promovido = { id: "apr-1", tipo: "Aprendizado", rotulo: "A", propriedades: { promovido_por: "arbitro-1", promovido_por_papel: "arbitro" } };
  assert.match(inspetor.montarBlocoDoAprendizado(promovido, ""), /selo-arbitro[^>]*title="Promovido pelo árbitro \(arbitro-1\)"/);
  const local = { ...promovido, propriedades: {} };
  assert.doesNotMatch(inspetor.montarBlocoDoAprendizado(local, ""), /selo-arbitro/);
});

test("o Goal ganha o seletor de status no topo do inspetor e a linha some da tabela de propriedades", () => {
  const inspetor = new InspectorView(raizDeMentira(), { state: estado(), indice: INDICE, acoes: { ehMarcador: () => false } });
  const goal = { id: "goal-1", tipo: "Goal", rotulo: "Meta", propriedades: { status: "em_andamento", descricao: "x" } };
  inspetor.renderNo(goal);
  const html = inspetor.raiz.innerHTML;
  assert.match(html, /<select class="seletor mod-status[^>]*data-prop="status"/);
  assert.match(html, /<option value="concluido"/);
  assert.equal((html.match(/data-chave="status"/g) || []).length, 0);
});

test("a leitura da Question mostra o selo so quando respondida pelo arbitro", () => {
  const leitura = new LeituraDaQuestaoView(raizDeMentira(), { state: estado(), indice: INDICE, acoes: {}, aoCarregar: null });
  const base = { id: "q-1", tipo: "Question", rotulo: "Q", propriedades: { status: "respondida", resposta: "sim", respondida_por: "arbitro-1" } };
  leitura.montar({ ...base, propriedades: { ...base.propriedades, respondida_por_papel: "arbitro" } });
  assert.match(leitura.raiz.innerHTML, /selo-arbitro[^>]*title="Respondida pelo árbitro \(arbitro-1\)"/);
  assert.match(leitura.raiz.innerHTML, /Resposta do árbitro/);
  assert.doesNotMatch(leitura.raiz.innerHTML, /Resposta humana/);
  leitura.montar({ ...base, propriedades: { ...base.propriedades, respondida_por_papel: "humano" } });
  assert.doesNotMatch(leitura.raiz.innerHTML, /selo-arbitro/);
  assert.match(leitura.raiz.innerHTML, /Resposta humana/);
  leitura.montar({ ...base, propriedades: { status: "aberta", respondida_por_papel: "arbitro" } });
  assert.doesNotMatch(leitura.raiz.innerHTML, /selo-arbitro/);
});

test("a memoria marca o aprendizado promovido pelo arbitro", () => {
  const memoria = new MemoriaView(raizDeMentira(), { state: estado(), indice: INDICE, acoes: {} });
  const item = {
    id: "apr-1", afirmacao: "A", como_aplicar: "", alcances: ["proj-1"], origens: [], contradicoes: [], substituto: null,
    valido_ate: "", promovido: true, vigente: true, autor: "executor", papel: "executor", seq_criacao: 3,
    promovido_por: "arbitro-1", promovido_por_papel: "arbitro",
  };
  assert.match(memoria.montarAprendizado(item), /selo-arbitro[^>]*title="Promovido pelo árbitro \(arbitro-1\)"/);
  assert.doesNotMatch(memoria.montarAprendizado({ ...item, promovido_por_papel: "humano" }), /selo-arbitro/);
  assert.doesNotMatch(memoria.montarAprendizado({ ...item, promovido_por: undefined, promovido_por_papel: undefined }), /selo-arbitro/);
});

test("api.liberarPosse faz POST com o token e o ramo na rota da Task", async () => {
  const pedidos = [];
  const original = globalThis.fetch;
  globalThis.fetch = async (url, opcoes = {}) => {
    pedidos.push({ url, opcoes });
    const corpo = url === "/api/identity" ? { token: "tok" } : { sucesso: true, dono_anterior: "agente-x" };
    return { ok: true, json: async () => corpo };
  };
  try {
    const recibo = await api.liberarPosse("task 1", "main");
    assert.equal(recibo.sucesso, true);
  } finally {
    globalThis.fetch = original;
  }
  const post = pedidos.find((pedido) => pedido.url !== "/api/identity");
  assert.equal(post.url, "/api/tarefas/task%201/liberar-posse");
  assert.equal(post.opcoes.method, "POST");
  assert.equal(post.opcoes.headers["X-Graphow-Token"], "tok");
  assert.deepEqual(JSON.parse(post.opcoes.body), { ramo_id: "main" });
});
