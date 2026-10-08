/**
 * O bloco "Escopo" do inspetor de um Goal, sem DOM: a leitura de `/api/escopo`
 * vira texto e HTML. O placar já vem escrito pelo servidor (`linhas`,
 * `linhas_de_desvio`), as mesmas linhas que o planejador lê na vista; aqui só
 * se decide o que destacar: o aviso de que o executor não assume Task de Goal
 * sem plano aprovado, os gatilhos disparados, as raízes que passaram de K e de
 * onde vem cada limiar. Testado por `node --test` em tests/web/js/escopo.test.mjs.
 */
import { escapeHtml } from "./dom.js";
import { icone } from "./icones.js";

export const AVISO_SEM_PLANO = "Plano não aprovado: o executor não assume Tasks deste Goal até um aprovar_plano (humano, ou árbitro se a política entregar).";

const LIMITE_DE_RAIZES = 5;

/** O rótulo de onde veio um limiar: a política global, o Projeto ou o preset que o fixou. */
export function rotuloDaOrigem(origem) {
  if (!origem) return "padrão";
  if (origem === "projeto") return "do Projeto";
  if (origem.startsWith("preset:")) return `preset ${origem.slice("preset:".length)}`;
  return origem;
}

/** "K 3 (global) · M 5 (do Projeto)": os dois limiares com a origem de cada um. */
export function textoDosLimiares(limiares) {
  if (!limiares) return "";
  return `K ${limiares.por_raiz} (${rotuloDaOrigem(limiares.origem_por_raiz)}) · M ${limiares.por_goal} (${rotuloDaOrigem(limiares.origem_por_goal)})`;
}

/** As raízes com emergentes, as que mais geraram primeiro, em no máximo cinco. */
export function raizesComDesvio(dados) {
  return (dados.raizes || [])
    .filter((raiz) => raiz.emergentes > 0)
    .sort((a, b) => b.emergentes - a.emergentes || a.raiz.localeCompare(b.raiz))
    .slice(0, LIMITE_DE_RAIZES);
}

/** Quantos gatilhos estão disparados. */
export function totalDeGatilhos(dados) {
  return (dados.gatilhos_disparados || []).length;
}

function htmlDoAviso(dados) {
  if (dados.plano_aprovado) return "";
  return `<div class="chamada mod-alerta" data-escopo="sem-plano">${icone("lock", { tamanho: 14 })}<span>${escapeHtml(AVISO_SEM_PLANO)}</span></div>`;
}

function htmlDosGatilhos(dados) {
  const linhas = dados.linhas_de_desvio || [];
  if (linhas.length === 0) return "";
  const disparou = totalDeGatilhos(dados) > 0;
  const modificador = disparou ? "mod-aviso" : "mod-info";
  const icon = disparou ? "alert-triangle" : "info";
  return `<div class="chamada ${modificador}" data-escopo="desvio">${icone(icon, { tamanho: 14 })}<span>${linhas.map(escapeHtml).join("<br>")}</span></div>`;
}

function htmlDaRaiz(raiz) {
  const marcas = [`${raiz.emergentes} emergentes`, `K ${raiz.contador_k}`];
  if (raiz.passou_de_k) marcas.push("passou de K");
  if (raiz.veredito_pendente) marcas.push("veredito de escopo pendente");
  return `<div class="bloco-nota"><button class="link-no" data-acao="ir-para" data-id="${escapeHtml(raiz.raiz)}">${escapeHtml(raiz.raiz)}</button> ${escapeHtml(marcas.join(" · "))}</div>`;
}

function htmlDasRaizes(dados) {
  const raizes = raizesComDesvio(dados);
  if (raizes.length === 0) return "";
  return `<div class="bloco-campo mod-coluna"><span class="bloco-campo-rotulo">${icone("route", { tamanho: 14 })} Decisões que mais geraram Tasks</span>${raizes.map(htmlDaRaiz).join("")}</div>`;
}

/** O bloco inteiro: aviso de travamento, as linhas do placar, os gatilhos, as raízes e os limiares. */
export function htmlDoEscopo(dados) {
  const linhas = (dados.linhas || []).map((linha) => `<li>${escapeHtml(linha)}</li>`).join("");
  return `
    <div class="bloco-campo mod-coluna" data-escopo="placar">
      <span class="bloco-campo-rotulo">${icone("target", { tamanho: 14 })} Escopo</span>
      ${htmlDoAviso(dados)}
      <ul class="escopo-linhas">${linhas}</ul>
      ${htmlDosGatilhos(dados)}
      ${htmlDasRaizes(dados)}
      <div class="bloco-nota">Limiares: ${escapeHtml(textoDosLimiares(dados.limiares))}</div>
    </div>`;
}

/** A frase do bloco quando a leitura falha. */
export function htmlDoEscopoIndisponivel(mensagem) {
  return `<div class="bloco-nota">${escapeHtml(mensagem || "Não foi possível ler o escopo deste Goal.")}</div>`;
}
