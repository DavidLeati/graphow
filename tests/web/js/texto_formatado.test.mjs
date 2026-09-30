// Testes do formatador que mostra a pergunta de uma dúvida como texto de leitura,
// rodados por `node --test`. tests/web/test_javascript.py os chama pela suíte do pytest.

import { test } from "node:test";
import assert from "node:assert/strict";

import { formatarTextoDeLeitura } from "../../../src/graphow/web/static/js/texto_formatado.js";

test("texto vazio, nulo ou só de espaços não produz nada", () => {
  assert.equal(formatarTextoDeLeitura(""), "");
  assert.equal(formatarTextoDeLeitura(null), "");
  assert.equal(formatarTextoDeLeitura(undefined), "");
  assert.equal(formatarTextoDeLeitura("  \n\n \t\n"), "");
});

test("linha em branco separa parágrafos e a quebra simples é preservada", () => {
  const html = formatarTextoDeLeitura("Primeira linha\nsegunda linha\n\nOutro parágrafo");
  assert.equal(html, "<p>Primeira linha<br>segunda linha</p><p>Outro parágrafo</p>");
});

test("quebras do Windows e várias linhas em branco seguidas contam como uma separação", () => {
  assert.equal(formatarTextoDeLeitura("a\r\n\r\n\r\nb"), "<p>a</p><p>b</p>");
});

test("linhas com hífen ou asterisco viram lista, e o texto em volta continua parágrafo", () => {
  const html = formatarTextoDeLeitura("Opções:\n- manter\n* trocar\nDecida.");
  assert.equal(html, "<p>Opções:</p><ul><li>manter</li><li>trocar</li></ul><p>Decida.</p>");
});

test("lista numerada vira ol e guarda o número de partida", () => {
  assert.equal(formatarTextoDeLeitura("1. um\n2) dois"), "<ol><li>um</li><li>dois</li></ol>");
  assert.equal(formatarTextoDeLeitura("3. três\n4. quatro"), '<ol start="3"><li>três</li><li>quatro</li></ol>');
});

test("linha recuada abaixo de um item continua o item", () => {
  const html = formatarTextoDeLeitura("- item longo\n  que continua aqui\n- outro");
  assert.equal(html, "<ul><li>item longo<br>que continua aqui</li><li>outro</li></ul>");
});

test("trecho entre crases vira code, e crase sem par fica como está", () => {
  assert.equal(formatarTextoDeLeitura("Veja `app.js` e `x`"), "<p>Veja <code>app.js</code> e <code>x</code></p>");
  assert.equal(formatarTextoDeLeitura("uma ` solta"), "<p>uma ` solta</p>");
});

test("HTML do dado sai escapado, dentro e fora de código e de lista", () => {
  const html = formatarTextoDeLeitura('<script>alert("x")</script>\n- <b>item</b>\n`<img src=x onerror=y>`');
  assert.ok(!html.includes("<script>"));
  assert.ok(!html.includes("<b>"));
  assert.ok(!html.includes("<img"));
  assert.ok(html.includes("&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt;"));
  assert.ok(html.includes("<li>&lt;b&gt;item&lt;/b&gt;</li>"));
  assert.ok(html.includes("<code>&lt;img src=x onerror=y&gt;</code>"));
});

test("asterisco sem espaço depois não é item de lista", () => {
  assert.equal(formatarTextoDeLeitura("**ênfase** no começo"), "<p>**ênfase** no começo</p>");
});
