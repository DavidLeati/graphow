/**
 * O HTML da aba Configurações, por seção. Cada função recebe o que desenha e
 * devolve um trecho; quem decide quando desenhar, e o que fazer com os cliques,
 * é `configuracoes_view.js`.
 */
import { escapeHtml } from "./dom.js";
import { formatarDataCompleta, formatarIdadeRelativa } from "./idade.js";
import { icone } from "./icones.js";
import {
  cartoesDoEscopo, configuracaoDoEscopo, descreverTipoDeEvento, explicarOrigem, GESTOS_FIXOS, nomeDoPreset, nomeDoValor,
  PRESET_HERDAR, PRESET_PERSONALIZADA, rotuloDaOrigem,
} from "./configuracoes_modelo.js";

const ICONES_DOS_PRESETS = {
  governanca_maxima: "shield",
  arbitragem_maxima: "bot",
  personalizada: "sliders",
  herdar: "corner-down-right",
};

const CAMPOS_DA_OPERACAO = [
  ["cadencia", "Cadência"],
  ["teto_rodadas", "Teto de rodadas"],
  ["ramo_base", "Ramo base"],
  ["caminhos_de_colisao", "Caminhos de colisão"],
];

export function htmlDoSeletorDeEscopo(projetos, escopo) {
  const opcoes = projetos.map((projeto) => `<option value="${escapeHtml(projeto.id)}" ${projeto.id === escopo ? "selected" : ""}>${escapeHtml(projeto.rotulo)}</option>`);
  return `<option value="global" ${escopo === "global" ? "selected" : ""}>Global</option>${opcoes.length ? `<optgroup label="Projetos">${opcoes.join("")}</optgroup>` : ""}`;
}

/** Os cartões de preset: um grupo de rádio, em que escolher um já grava. */
export function htmlDosCartoes({ catalogo, dados, global, ehProjeto, gravando }) {
  const { preset: ativo } = configuracaoDoEscopo(dados, ehProjeto);
  const presetGlobal = configuracaoDoEscopo(global, false).preset;
  const cartoes = cartoesDoEscopo(catalogo, ehProjeto).map((cartao) => {
    const selecionado = cartao.preset === ativo;
    const nota = cartao.preset === PRESET_HERDAR ? `<span class="cfg-cartao-nota">Hoje a global é <strong>${escapeHtml(nomeDoPreset(presetGlobal))}</strong></span>` : "";
    return `
      <button type="button" class="cfg-cartao ${selecionado ? "is-ativo" : ""}" role="radio" aria-checked="${selecionado}" data-preset="${escapeHtml(cartao.preset)}" ${gravando ? "disabled" : ""}>
        <span class="cfg-cartao-topo">${icone(ICONES_DOS_PRESETS[cartao.preset] || "circle", { tamanho: 16 })}<span class="cfg-cartao-nome">${escapeHtml(cartao.nome)}</span><span class="cfg-cartao-marca">${selecionado ? icone("circle-check", { tamanho: 16 }) : ""}</span></span>
        <span class="cfg-cartao-texto">${escapeHtml(cartao.descricao)}</span>${nota}
      </button>`;
  });
  return `<div class="cfg-cartoes" role="radiogroup" aria-label="Preset de governança">${cartoes.join("")}</div>`;
}

function htmlDoValorEditavel(linha, gravando) {
  const herdaria = linha.herdaria === undefined ? "" : ` (global: ${nomeDoValor(linha.gesto, linha.herdaria)})`;
  const escolhido = (valor) => (linha.ehProjeto ? linha.sobrescrito : true) && linha.valor === valor;
  const opcoes = linha.valores.map((valor) => `<option value="${escapeHtml(valor)}" ${escolhido(valor) ? "selected" : ""}>${escapeHtml(nomeDoValor(linha.gesto, valor))}</option>`);
  const heranca = linha.ehProjeto ? `<option value="herdar" ${linha.sobrescrito ? "" : "selected"}>Herdar${escapeHtml(herdaria)}</option>` : "";
  return `<select class="seletor mod-pequeno" data-gesto="${escapeHtml(linha.gesto)}" aria-label="${escapeHtml(linha.nome)}" ${gravando ? "disabled" : ""}>${heranca}${opcoes.join("")}</select>`;
}

function htmlDaLinha(linha, gravando) {
  const valor = linha.editavel
    ? htmlDoValorEditavel(linha, gravando)
    : `<span class="cfg-valor-texto">${escapeHtml(nomeDoValor(linha.gesto, linha.valor))}</span>`;
  return `
    <div class="cfg-linha" role="row">
      <div class="cfg-gesto" role="cell"><strong>${escapeHtml(linha.nome)}</strong><span class="cfg-descricao">${escapeHtml(linha.descricao)}</span></div>
      <div class="cfg-valor" role="cell">${valor}</div>
      <div class="cfg-origem" role="cell"><span class="cfg-selo" title="${escapeHtml(explicarOrigem(linha.origem))}">${escapeHtml(rotuloDaOrigem(linha.origem))}</span></div>
    </div>`;
}

function htmlDaLinhaFixa(fixa) {
  return `
    <div class="cfg-linha mod-fixa" role="row">
      <div class="cfg-gesto" role="cell"><strong>${escapeHtml(fixa.nome)}</strong><span class="cfg-descricao">${escapeHtml(fixa.descricao)}</span></div>
      <div class="cfg-valor" role="cell"><span class="cfg-valor-texto">${icone("lock", { tamanho: 13 })} Só o humano</span></div>
      <div class="cfg-origem" role="cell"><span class="cfg-selo" title="Nenhuma política delega este gesto">fixo</span></div>
    </div>`;
}

/** A nota que diz por que a tabela está só para leitura, ou o que a Personalizada guardada tem. */
export function htmlDaNotaDaTabela({ dados, global, ehProjeto }) {
  const { preset, personalizada } = configuracaoDoEscopo(dados, ehProjeto);
  if (preset === PRESET_PERSONALIZADA) {
    return ehProjeto
      ? '<div class="chamada mod-info">' + icone("info", { tamanho: 14 }) + "<span>Cada gesto pode herdar da política global ou ser sobrescrito aqui. O que você muda grava na hora.</span></div>"
      : '<div class="chamada mod-info">' + icone("info", { tamanho: 14 }) + "<span>Cada mudança grava na hora. Os gestos que você ainda não definiu valem como na Governança máxima.</span></div>";
  }
  const guardados = Object.keys(personalizada).length;
  const guardada = guardados ? ` A Personalizada guardada (${guardados} gesto${guardados === 1 ? "" : "s"}) fica intacta e volta quando você a escolher.` : "";
  const herdando = preset === PRESET_HERDAR ? ` Este projeto segue a política global: ${nomeDoPreset(configuracaoDoEscopo(global, false).preset)}.` : "";
  return `<div class="chamada mod-aviso">${icone("lock", { tamanho: 14 })}<span>Só a Personalizada muda estes valores; aqui eles são de leitura.${escapeHtml(herdando)}${escapeHtml(guardada)}</span></div>`;
}

export function htmlDaTabela(linhas, gravando) {
  const cabecalho = `
    <div class="cfg-linha mod-cabecalho" role="row">
      <div role="columnheader">Gesto</div><div role="columnheader">Quem decide</div><div role="columnheader">Origem</div>
    </div>`;
  const corpo = linhas.map((linha) => htmlDaLinha(linha, gravando)).join("");
  return `<div class="cfg-tabela" role="table" aria-label="Gestos governáveis">${cabecalho}${corpo}${GESTOS_FIXOS.map(htmlDaLinhaFixa).join("")}</div>`;
}

function htmlDoCampoDaOperacao(chave, rotulo, catalogo, valores) {
  const meta = catalogo?.operacao?.[chave] || {};
  const nota = `<span class="campo-nota">${escapeHtml(meta.descricao || "")}</span>`;
  const valor = valores[chave];
  const atributos = `data-campo-operacao="${chave}" id="cfg-operacao-${chave}"`;
  let controle = `<input class="entrada" type="text" ${atributos} value="${escapeHtml(valor)}">`;
  if (chave === "cadencia") {
    const opcoes = (meta.valores || []).map((opcao) => `<option value="${escapeHtml(opcao)}" ${opcao === valor ? "selected" : ""}>${escapeHtml(opcao)}</option>`);
    controle = `<select class="seletor" ${atributos}><option value="" ${valor ? "" : "selected"}>Não definida</option>${opcoes.join("")}</select>`;
  } else if (chave === "teto_rodadas") {
    controle = `<input class="entrada mod-numero" type="number" min="${meta.minimo ?? 1}" step="1" ${atributos} value="${escapeHtml(valor)}">`;
  } else if (chave === "caminhos_de_colisao") {
    controle = `<textarea class="entrada mod-area" rows="3" ${atributos} placeholder="Um glob por linha">${escapeHtml(valor)}</textarea>`;
  }
  return `<div class="campo"><label class="campo-rotulo" for="cfg-operacao-${chave}">${escapeHtml(rotulo)}</label>${controle}${nota}</div>`;
}

export function htmlDaOperacao(catalogo, valores, gravando) {
  const campos = CAMPOS_DA_OPERACAO.map(([chave, rotulo]) => htmlDoCampoDaOperacao(chave, rotulo, catalogo, valores));
  return `
    <form class="cfg-operacao" data-operacao autocomplete="off">
      <div class="cfg-operacao-grade">${campos.join("")}</div>
      <div class="cfg-operacao-acoes">
        <button type="submit" class="botao mod-cta" ${gravando ? "disabled" : ""}>Gravar no projeto</button>
        <span class="texto-fraco">Campo vazio apaga a propriedade do projeto.</span>
      </div>
    </form>`;
}

function htmlDoEventoDeAuditoria(evento) {
  const ids = (evento.ids_tocados || []).map((id) => `<button type="button" class="link-no cfg-aud-id" data-ir="${escapeHtml(id)}" title="Focar no canvas"><code>${escapeHtml(id)}</code></button>`);
  return `
    <li class="cfg-aud-item">
      <span class="cfg-aud-seq">#${escapeHtml(evento.seq)}</span>
      <time datetime="${escapeHtml(evento.instante)}" title="${escapeHtml(formatarDataCompleta(evento.instante))}">${escapeHtml(formatarIdadeRelativa(evento.instante) || "sem data")}</time>
      <span class="cfg-aud-autor">${escapeHtml(evento.autor)}</span>
      <span class="cfg-aud-tipo">${escapeHtml(descreverTipoDeEvento(evento.tipo))}</span>
      <span class="cfg-aud-ids">${ids.join("")}</span>
    </li>`;
}

export function htmlDaAuditoria(auditoria) {
  if (!auditoria) return `<div class="painel-vazio"><span>Lendo a auditoria…</span></div>`;
  if (auditoria.sucesso === false) return `<div class="chamada mod-alerta">${icone("alert-triangle", { tamanho: 14 })}<span>${escapeHtml(auditoria.mensagem || "Não foi possível ler a auditoria.")}</span></div>`;
  const eventos = auditoria.eventos || [];
  if (!eventos.length) return `<div class="painel-vazio">${icone("bot", { tamanho: 22 })}<span>O árbitro ainda não fez nenhum gesto neste ramo.</span></div>`;
  const resumo = `Os ${eventos.length} mais recentes de ${auditoria.total} gesto${auditoria.total === 1 ? "" : "s"} do árbitro.`;
  return `<ol class="cfg-auditoria">${eventos.map(htmlDoEventoDeAuditoria).join("")}</ol><p class="campo-nota">${escapeHtml(resumo)}</p>`;
}
