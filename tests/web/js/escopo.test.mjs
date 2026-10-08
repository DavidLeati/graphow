// Testes do que o bloco "Escopo" do inspetor decide sem DOM: origem dos limiares, raízes com desvio,
// aviso de plano não aprovado, gatilhos e escape do HTML, rodados por `node --test`.
// tests/web/test_javascript.py os chama pela suíte do pytest.

import { test } from "node:test";
import assert from "node:assert/strict";

import {
  AVISO_SEM_PLANO, corpoDaResposta, corpoDoAprovar, htmlDoEscopo, htmlDoEscopoIndisponivel, precisaResponderDesvio,
  raizSugerida, raizesComDesvio, respostaValida, rotuloDaOrigem, textoDoAprovar, textoDosLimiares, totalDeGatilhos,
} from "../../../src/graphow/web/static/js/escopo_modelo.js";

const RAIZ = (raiz, emergentes, extra = {}) => ({ raiz, emergentes, contador_k: emergentes, passou_de_k: false, veredito_pendente: false, ...extra });

const COM_DESVIO = {
  id_goal: "g",
  plano_aprovado: true,
  linhas: ["Escopo: plano_v1 (humano, seq 10)", "Plano: 2 Tasks · 1 concluídas · 1 sem começar", "Cadeia mais longa: 1"],
  linhas_de_desvio: ["Gatilho K: d1 passou de 3 (4 emergentes desde a referência ou a resposta)", "Decisões sem veredito de escopo: d1"],
  gatilhos_disparados: [{ tipo: "raiz", raiz: "d1", contagem: 4, limiar: 3, disparou: true }],
  raizes: [RAIZ("d2", 1), RAIZ("d1", 4, { passou_de_k: true, veredito_pendente: true }), RAIZ("d0", 0)],
  limiares: { por_raiz: 3, por_goal: 5, origem_por_raiz: "global", origem_por_goal: "projeto" },
};

test("a origem do limiar é dita em palavras", () => {
  assert.equal(rotuloDaOrigem("global"), "global");
  assert.equal(rotuloDaOrigem("projeto"), "do Projeto");
  assert.equal(rotuloDaOrigem("preset:governanca_maxima"), "preset governanca_maxima");
  assert.equal(rotuloDaOrigem(""), "padrão");
});

test("os limiares saem com a origem de cada um", () => {
  assert.equal(textoDosLimiares(COM_DESVIO.limiares), "K 3 (global) · M 5 (do Projeto)");
  assert.equal(textoDosLimiares(null), "");
});

test("as raízes sem desvio ficam de fora e a que mais gerou vem primeiro", () => {
  assert.deepEqual(raizesComDesvio(COM_DESVIO).map((raiz) => raiz.raiz), ["d1", "d2"]);
  const muitas = { raizes: Array.from({ length: 9 }, (_, i) => RAIZ(`r${i}`, i + 1)) };
  assert.equal(raizesComDesvio(muitas).length, 5);
});

test("o gatilho disparado conta, e sem gatilho o total é zero", () => {
  assert.equal(totalDeGatilhos(COM_DESVIO), 1);
  assert.equal(totalDeGatilhos({}), 0);
});

test("com plano e desvio o bloco mostra as linhas, o gatilho, a raiz pendente e os limiares", () => {
  const html = htmlDoEscopo(COM_DESVIO);
  assert.match(html, /Escopo: plano_v1 \(humano, seq 10\)/);
  assert.match(html, /Gatilho K: d1 passou de 3/);
  assert.match(html, /veredito de escopo pendente/);
  assert.match(html, /data-id="d1"/);
  assert.match(html, /Limiares: K 3 \(global\) · M 5 \(do Projeto\)/);
  assert.doesNotMatch(html, /data-escopo="sem-plano"/);
  assert.match(html, /data-escopo="desvio"/);
});

test("sem plano aprovado o bloco abre pelo aviso de travamento", () => {
  const html = htmlDoEscopo({ ...COM_DESVIO, plano_aprovado: false, linhas_de_desvio: [], gatilhos_disparados: [], raizes: [] });
  assert.match(html, /data-escopo="sem-plano"/);
  assert.ok(html.includes("o executor não assume Tasks deste Goal até um aprovar_plano"));
  assert.ok(AVISO_SEM_PLANO.includes("aprovar_plano"));
  assert.doesNotMatch(html, /data-escopo="desvio"/);
});

test("sem desvio o bloco não promete alerta nem raízes", () => {
  const html = htmlDoEscopo({ ...COM_DESVIO, linhas_de_desvio: [], gatilhos_disparados: [], raizes: [RAIZ("d0", 0)] });
  assert.doesNotMatch(html, /Decisões que mais geraram/);
  assert.doesNotMatch(html, /data-escopo="desvio"/);
});

test("resposta do árbitro ou texto do agente não injeta HTML", () => {
  const html = htmlDoEscopo({ ...COM_DESVIO, linhas: ["<img src=x onerror=1>"], linhas_de_desvio: ["a <b>b</b>"], raizes: [RAIZ('"><script>', 2)] });
  assert.doesNotMatch(html, /<img|<script|<b>/);
  assert.match(html, /&lt;img src=x onerror=1&gt;/);
});

test("a leitura que falha mostra a mensagem escapada, ou a frase padrão", () => {
  assert.match(htmlDoEscopoIndisponivel("<falhou>"), /&lt;falhou&gt;/);
  assert.match(htmlDoEscopoIndisponivel(""), /Não foi possível ler o escopo/);
});

const CALMO = { ...COM_DESVIO, linhas_de_desvio: [], gatilhos_disparados: [], sem_veredito: [], raizes: [RAIZ("d2", 1)], para_aprovar: { versao: 3, tasks: 4 } };

test("o botão de aprovar o plano está sempre no bloco e diz o que congela e a versão", () => {
  for (const dados of [CALMO, { ...CALMO, plano_aprovado: false }]) {
    const html = htmlDoEscopo(dados);
    assert.match(html, /data-acao="aprovar-plano"/);
    assert.match(html, /Congela as 4 Tasks atuais como a versão 3 do plano/);
    assert.match(html, /vira a referência do desvio/);
  }
});

test("a frase do aprovar trata uma Task só e a ausência do dado", () => {
  assert.match(textoDoAprovar({ para_aprovar: { versao: 1, tasks: 1 } }), /a 1 Task atual como a versão 1/);
  assert.match(textoDoAprovar({}), /as 0 Tasks atuais como a versão 1/);
});

test("sem gatilho nem decisão sem veredito não há formulário de resposta", () => {
  assert.equal(precisaResponderDesvio(CALMO), false);
  assert.doesNotMatch(htmlDoEscopo(CALMO), /data-escopo="responder"/);
});

test("gatilho disparado, ou decisão sem veredito, abre o formulário com a raiz que mais gerou escolhida", () => {
  assert.equal(precisaResponderDesvio(COM_DESVIO), true);
  assert.equal(precisaResponderDesvio({ ...CALMO, sem_veredito: ["d9"] }), true);
  assert.equal(precisaResponderDesvio({ ...CALMO, raizes: [RAIZ("d1", 4, { veredito_pendente: true })] }), true);
  assert.equal(raizSugerida(COM_DESVIO), "d1");
  const html = htmlDoEscopo(COM_DESVIO);
  assert.match(html, /data-escopo="responder"/);
  assert.match(html, /data-escopo-resposta/);
  assert.match(html, /<option value="d1" selected>d1 \(4 emergentes\)<\/option>/);
  assert.match(html, /<option value="d2">/);
  assert.match(html, /data-acao="responder-desvio"/);
});

test("sem raiz com Task emergente o formulário abre com 'nenhuma decisão' escolhida", () => {
  const html = htmlDoEscopo({ ...COM_DESVIO, raizes: [], raiz_que_mais_gerou: null });
  assert.equal(raizSugerida({ raizes: [] }), "");
  assert.match(html, /<option value="" selected>Nenhuma decisão/);
});

test("os corpos dos pedidos levam goal e ramo; a raiz vazia some e a resposta perde os espaços das pontas", () => {
  assert.deepEqual(corpoDoAprovar("g1", "main"), { goal: "g1", ramo: "main" });
  assert.deepEqual(corpoDaResposta("g1", "main", "  segue  ", "d1"), { goal: "g1", ramo: "main", resposta: "segue", raiz: "d1" });
  assert.deepEqual(corpoDaResposta("g1", "main", "segue", ""), { goal: "g1", ramo: "main", resposta: "segue" });
});

test("a resposta ao desvio é obrigatória", () => {
  assert.equal(respostaValida("  "), false);
  assert.equal(respostaValida(undefined), false);
  assert.equal(respostaValida(" ok "), true);
});

test("o id da raiz e o texto dos botões não deixam HTML escapar", () => {
  const html = htmlDoEscopo({ ...COM_DESVIO, raizes: [RAIZ('<img src=x onerror=1>', 4, { passou_de_k: true })], raiz_que_mais_gerou: null });
  assert.doesNotMatch(html, /<img src=x/);
});
