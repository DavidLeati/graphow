// Testes do que a aba Configurações decide sem DOM: as linhas da tabela, a origem de cada
// valor, os cartões por escopo, os corpos de escrita e o HTML dos trechos principais,
// rodados por `node --test`. tests/web/test_javascript.py os chama pela suíte do pytest.

import { test } from "node:test";
import assert from "node:assert/strict";

import {
  cartoesDoEscopo, corpoDoGesto, corpoDoPreset, listaDeCaminhos, linhasDaTabela, mensagemDeRecusa, nomeDoValor, operacaoDoFormulario,
  ehGestoInteiro, pedeNumero, rotuloDaOrigem, valorDoCampoNumerico, valorDoCatalogo,
} from "../../../src/graphow/web/static/js/configuracoes_modelo.js";
import {
  htmlDaAuditoria, htmlDaNotaDaTabela, htmlDaOperacao, htmlDaTabela, htmlDosCartoes,
} from "../../../src/graphow/web/static/js/configuracoes_html.js";

const CATALOGO = {
  gestos: [
    { gesto: "responder_questao", descricao: "Responder", valores: ["arbitro", "humano"] },
    { gesto: "max_correcoes", descricao: "Correções", valores: [0, 1, 2, 3, 4, 5], minimo: 0, maximo: 5, padrao: 2 },
    { gesto: "teto_expansao", descricao: "Teto", valores: [], minimo: 0, maximo: 500, padrao: 0 },
  ],
  presets: [
    { preset: "governanca_maxima", descricao: "Tudo humano" },
    { preset: "arbitragem_maxima", descricao: "Árbitro decide" },
    { preset: "personalizada", descricao: "Você escolhe" },
  ],
  presets_do_projeto: [
    { preset: "herdar", descricao: "Segue a global" },
    { preset: "governanca_maxima", descricao: "Tudo humano" },
    { preset: "arbitragem_maxima", descricao: "Árbitro decide" },
    { preset: "personalizada", descricao: "Você escolhe" },
  ],
  operacao: {
    cadencia: { descricao: "Quando para", valores: ["tarefa", "goal", "setor"] },
    teto_rodadas: { descricao: "Rodadas", minimo: 1 },
    ramo_base: { descricao: "Ramo" },
    caminhos_de_colisao: { descricao: "Globs" },
    gravacao_do_gerente: { descricao: "Quando o gerente grava", valores: ["apos_aprovacao", "durante_alinhamento"], padrao: "apos_aprovacao" },
  },
};

const GLOBAL = {
  catalogo: CATALOGO,
  configuracao: { preset: "arbitragem_maxima", personalizada: { excluir: "arbitro" } },
  politica_efetiva: { responder_questao: "arbitro", max_correcoes: 2 },
  origens: { responder_questao: "preset:arbitragem_maxima", max_correcoes: "preset:arbitragem_maxima" },
};

const PROJETO_PERSONALIZADO = {
  configuracao: { preset: "personalizada", personalizada: { responder_questao: "humano" } },
  politica_global: { responder_questao: "arbitro", max_correcoes: 2 },
  politica_efetiva: { responder_questao: "humano", max_correcoes: 2 },
  origens: { responder_questao: "projeto", max_correcoes: "global" },
  operacao: { cadencia: "goal", teto_rodadas: null, ramo_base: null, caminhos_de_colisao: ["src/**", "tests/**"] },
};

test("a origem do valor vira texto curto e o legado continua legível", () => {
  assert.equal(rotuloDaOrigem("global"), "global");
  assert.equal(rotuloDaOrigem("projeto"), "projeto");
  assert.equal(rotuloDaOrigem("legado:nivel_autonomia"), "legado");
  assert.equal(rotuloDaOrigem("preset:arbitragem_maxima"), "preset");
  assert.equal(rotuloDaOrigem("projeto:proj-x"), "projeto proj-x");
});

test("o projeto ganha o cartão Herdar do global, na frente; o global não o tem", () => {
  assert.deepEqual(cartoesDoEscopo(CATALOGO, true).map((cartao) => cartao.preset), ["herdar", "governanca_maxima", "arbitragem_maxima", "personalizada"]);
  assert.deepEqual(cartoesDoEscopo(CATALOGO, false).map((cartao) => cartao.preset), ["governanca_maxima", "arbitragem_maxima", "personalizada"]);
});

test("a tabela só é editável na Personalizada, e o projeto sabe o que herdaria", () => {
  assert.ok(linhasDaTabela(CATALOGO, GLOBAL, false).every((linha) => !linha.editavel));
  const linhas = linhasDaTabela(CATALOGO, PROJETO_PERSONALIZADO, true);
  assert.ok(linhas.every((linha) => linha.editavel));
  const [responder, correcoes] = linhas;
  assert.equal(responder.sobrescrito, true);
  assert.equal(responder.herdaria, "arbitro");
  assert.equal(correcoes.sobrescrito, false);
  assert.equal(correcoes.origem, "global");
});

test("o corpo de um gesto leva só ele; o de um preset não leva a personalizada", () => {
  assert.deepEqual(corpoDoGesto("excluir", "arbitro"), { personalizada: { excluir: "arbitro" } });
  assert.deepEqual(corpoDoPreset("governanca_maxima"), { preset: "governanca_maxima" });
});

test("o valor escolhido volta como o catálogo o declara: o inteiro de max_correcoes não vira texto", () => {
  assert.equal(valorDoCatalogo([0, 1, 2], "2"), 2);
  assert.equal(valorDoCatalogo(["arbitro", "humano"], "humano"), "humano");
  assert.equal(valorDoCatalogo(["arbitro"], "inexistente"), undefined);
  assert.equal(nomeDoValor("max_correcoes", 1), "1 reprovação");
  assert.equal(nomeDoValor("max_correcoes", 3), "3 reprovações");
});

test("a operação em branco apaga as propriedades, e o teto inválido não chega ao servidor", () => {
  const vazia = operacaoDoFormulario({ cadencia: "", teto_rodadas: "", ramo_base: "  ", caminhos_de_colisao: "" });
  assert.deepEqual(vazia.corpo.operacao, { cadencia: null, teto_rodadas: null, ramo_base: null, caminhos_de_colisao: null, gravacao_do_gerente: null });
  const cheia = operacaoDoFormulario({ cadencia: "setor", teto_rodadas: "4", ramo_base: "main", caminhos_de_colisao: "src/**\n\n tests/** ", gravacao_do_gerente: "durante_alinhamento" });
  assert.deepEqual(cheia.corpo.operacao, { cadencia: "setor", teto_rodadas: 4, ramo_base: "main", caminhos_de_colisao: ["src/**", "tests/**"], gravacao_do_gerente: "durante_alinhamento" });
  assert.ok(operacaoDoFormulario({ teto_rodadas: "0" }).erro);
  assert.ok(operacaoDoFormulario({ teto_rodadas: "2,5" }).erro);
  assert.equal(listaDeCaminhos("   \n"), null);
});

test("a recusa do servidor leva os problemas, sem repeti-los quando a mensagem já os traz", () => {
  assert.match(mensagemDeRecusa({ mensagem: "Invalida", problemas: ["gesto x"] }), /gesto x/);
  assert.equal(mensagemDeRecusa({ mensagem: "Invalida: gesto x", problemas: ["gesto x"] }), "Invalida: gesto x");
});

test("os cartões marcam o preset ativo e o Herdar diz qual global vale", () => {
  const html = htmlDosCartoes({ catalogo: CATALOGO, dados: { configuracao: { preset: "herdar" } }, global: GLOBAL, ehProjeto: true, gravando: false });
  assert.match(html, /aria-checked="true" data-preset="herdar"/);
  assert.match(html, /Arbitragem máxima<\/strong>/);
  assert.equal((html.match(/aria-checked="true"/g) || []).length, 1);
});

test("nos presets fixos a tabela é leitura e a nota diz que só a Personalizada muda", () => {
  const dados = { ...GLOBAL };
  const linhas = linhasDaTabela(CATALOGO, dados, false);
  const tabela = htmlDaTabela(linhas, false);
  assert.doesNotMatch(tabela, /<select/);
  assert.match(tabela, /Promoção global/);
  assert.match(tabela, /Alterar a governança/);
  const nota = htmlDaNotaDaTabela({ dados, global: GLOBAL, ehProjeto: false });
  assert.match(nota, /Só a Personalizada muda/);
  assert.match(nota, /1 gesto/);
});

test("na Personalizada do projeto cada gesto é um seletor com a opção Herdar", () => {
  const linhas = linhasDaTabela(CATALOGO, PROJETO_PERSONALIZADO, true);
  const tabela = htmlDaTabela(linhas, false);
  assert.equal((tabela.match(/<select/g) || []).length, 2);
  assert.match(tabela, /Herdar \(global: Humano e árbitro\)/);
  assert.match(tabela, /value="humano" selected/);
});

test("a operação mostra o que está gravado e a lista de caminhos uma por linha", () => {
  const valores = { cadencia: "goal", teto_rodadas: "", ramo_base: "", caminhos_de_colisao: "src/**\ntests/**" };
  const html = htmlDaOperacao(CATALOGO, valores, false);
  assert.match(html, /<option value="goal" selected>/);
  assert.match(html, /src\/\*\*\ntests\/\*\*<\/textarea>/);
});

test("a gravação do gerente é um seletor que mostra o padrão quando o projeto não a definiu", () => {
  const vazio = htmlDaOperacao(CATALOGO, { gravacao_do_gerente: "" }, false);
  assert.match(vazio, /<option value="" selected>Padrão \(Após a aprovação\)<\/option>/);
  const definido = htmlDaOperacao(CATALOGO, { gravacao_do_gerente: "durante_alinhamento" }, false);
  assert.match(definido, /<option value="durante_alinhamento" selected>Durante o alinhamento<\/option>/);
});

test("a auditoria lista seq, autor e ids tocados, sem campo de justificativa", () => {
  const html = htmlDaAuditoria({
    sucesso: true,
    total: 3,
    eventos: [{ seq: 41, instante: "2026-10-02T10:00:00+00:00", autor: "arbitro-1", papel: "arbitro", tipo: "no_atualizado", justificativa: null, ids_tocados: ["q1"] }],
  });
  assert.match(html, /#41/);
  assert.match(html, /arbitro-1/);
  assert.match(html, /data-ir="q1"/);
  assert.doesNotMatch(html, /justificativa/i);
  assert.match(htmlDaAuditoria({ sucesso: true, total: 0, eventos: [] }), /ainda não fez nenhum gesto/);
});

test("o catálogo distingue o gesto inteiro de lista curta do que pede um campo numérico", () => {
  const [, correcoes, teto] = CATALOGO.gestos;
  assert.equal(ehGestoInteiro(teto), true);
  assert.equal(ehGestoInteiro(CATALOGO.gestos[0]), false);
  assert.equal(pedeNumero(correcoes), false);
  assert.equal(pedeNumero(teto), true);
  assert.equal(pedeNumero(undefined), false);
});

test("o campo numérico respeita o domínio, e vazio só herda no projeto", () => {
  const [, , teto] = CATALOGO.gestos;
  assert.equal(valorDoCampoNumerico(teto, "40", false), 40);
  assert.equal(valorDoCampoNumerico(teto, "0", true), 0);
  assert.equal(valorDoCampoNumerico(teto, "501", false), undefined);
  assert.equal(valorDoCampoNumerico(teto, "-1", false), undefined);
  assert.equal(valorDoCampoNumerico(teto, "2,5", false), undefined);
  assert.equal(valorDoCampoNumerico(teto, "  ", true), "herdar");
  assert.equal(valorDoCampoNumerico(teto, "", false), undefined);
});

test("os gestos do escopo têm nome legível e o teto zero diz que está desligado", () => {
  assert.equal(nomeDoValor("teto_expansao", 0), "Desligado");
  assert.equal(nomeDoValor("teto_expansao", 12), "12 Tasks");
  assert.equal(nomeDoValor("limiar_desvio_por_raiz", 1), "1 Task");
  assert.equal(nomeDoValor("limiar_desvio_por_goal", 5), "5 Tasks");
  const [, , teto] = linhasDaTabela(CATALOGO, PROJETO_PERSONALIZADO, true);
  assert.equal(teto.numerico, true);
  assert.equal(teto.minimo, 0);
  assert.equal(teto.maximo, 500);
});

test("na tabela editável o gesto numérico vira campo com limites e o de lista segue select", () => {
  const html = htmlDaTabela(linhasDaTabela(CATALOGO, PROJETO_PERSONALIZADO, true), false);
  assert.match(html, /<input[^>]*type="number"[^>]*min="0"[^>]*max="500"[^>]*data-gesto="teto_expansao"/);
  assert.match(html, /<select[^>]*data-gesto="max_correcoes"/);
  assert.match(html, /placeholder="herdar/);
});
