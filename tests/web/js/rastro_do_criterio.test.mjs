// Testes da T3f: o bloco "Rastro" do inspetor de um Criterio, a partir da resposta de `/api/rastro`,
// rodados por `node --test`. tests/web/test_javascript.py os chama pela suíte do pytest.

import { test } from "node:test";
import assert from "node:assert/strict";

import { htmlDoRastro, htmlDoRastroIndisponivel } from "../../../src/graphow/web/static/js/rastro_do_criterio.js";

const C2 = {
  codigo: "C2", no: "crit-soma-c2", texto: "o README explica", testes: [], checagem: ["abrir o <README>"], ja_atendido: "",
  commit_do_aceite: "0accad508b39aaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  fatias: [{ codigo: "F2", titulo: "Uso", status: "concluido", commit: "9ea3e0d09a16bbbb", corrige: "" },
    { codigo: "M1.K1.1", titulo: "Corrige", status: "concluido", commit: "a00d5cb0bde8cccc", corrige: "ver-goal-soma-1" }],
  atestado: { verificacao: "ver-goal-soma-2", tipo: "conferencia", marco: "M1", veredito: "atende", commit: "a00d5cb0bde8cccc",
    conferencia: { estado: "vigente", arquivos: [], motivo: "", rotulo: "vigente" } },
  achados: [{ id: "achado-goal-soma-v1-1", titulo: "README sem exemplo", gravidade: "bloqueante", estado: "resolvido", origem: "ver-goal-soma-1" }],
  retirada: null,
};

test("os quatro blocos do criterio: testes com o commit do aceite, fatias, verificacao conferida e achados", () => {
  const html = htmlDoRastro({ goal: "goal-soma", criterios: [C2] });
  assert.match(html, /Testes \(aceite em <code>0accad508b39<\/code>\)/);
  assert.match(html, /Checagem: abrir o &lt;README&gt;/);
  assert.match(html, /M1\.K1\.1 em <code>a00d5cb0bde8<\/code> \(concluido, corrige ver-goal-soma-1\)/);
  assert.match(html, /ver-goal-soma-2 \(conferencia, M1\): atende em <code>a00d5cb0bde8<\/code> <span data-conferencia="vigente">\[vigente\]<\/span>/);
  assert.match(html, /README sem exemplo \(bloqueante, resolvido\)/);
  assert.doesNotMatch(html, /data-rastro="retirado"/);
});

test("o retirado traz a chamada com a Decision, quem e o motivo; sem verificacao nem achado, as frases vazias", () => {
  const retirado = { ...C2, atestado: null, achados: [], fatias: [], retirada: { decisao: "pedido-1", por: "david", motivo: "fica para depois" } };
  const html = htmlDoRastro({ goal: "goal-soma", criterios: [retirado] });
  assert.match(html, /data-rastro="retirado"[^]*Retirado pelo humano \(pedido-1, por david\): fica para depois/);
  assert.match(html, /Nenhuma o julgou\./);
  assert.match(html, /Nenhum\./);
});

test("sem criterio na resposta ou com a leitura falha, uma frase", () => {
  assert.match(htmlDoRastro({ goal: "g", criterios: [] }), /Sem rastro/);
  assert.match(htmlDoRastroIndisponivel("'x' nao leva a um Goal"), /&#39;x&#39; nao leva|'x' nao leva/);
});
