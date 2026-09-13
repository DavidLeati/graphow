/**
 * Modais e avisos da moldura.
 *
 * O modal antigo era um só elemento reaproveitado, com os botões religados a cada
 * abertura; dois modais seguidos herdavam o `onclick` um do outro. Aqui cada
 * abertura cria o próprio modal e o destrói ao fechar. `Enter` confirma, `Esc`
 * cancela, e o foco vai para o primeiro campo — o mínimo para usar sem mouse.
 */
import { escapeHtml } from "./dom.js";
import { icone } from "./icones.js";

// Modais empilham (a confirmação abre por cima do lote); só o do topo ouve o teclado.
const pilha = [];

/**
 * Abre um modal. `corpo` é HTML; `botoes` é uma lista de `{ rotulo, primario,
 * perigo, acao }`, onde `acao` pode devolver `false` para manter o modal aberto.
 */
export function abrirModal({ titulo, corpo = "", botoes = [], largura = 520, classe = "", aoAbrir = null, aoFechar = null }) {
  const recipiente = document.createElement("div");
  recipiente.className = `modal-recipiente ${classe}`;
  recipiente.innerHTML = `
    <div class="modal-fundo"></div>
    <div class="modal" role="dialog" aria-modal="true" style="width:${largura}px">
      <button class="modal-fechar clicavel-icone" aria-label="Fechar">${icone("x")}</button>
      <div class="modal-titulo">${escapeHtml(titulo)}</div>
      <div class="modal-conteudo">${corpo}</div>
      ${botoes.length ? '<div class="modal-botoes"></div>' : ""}
    </div>`;
  const modal = recipiente.querySelector(".modal");
  const controle = { elemento: modal, fechar: () => fechar() };
  const aoTeclar = (evento) => tratarTecla(evento, controle, botoes);

  function fechar() {
    if (!recipiente.isConnected) return;
    document.removeEventListener("keydown", aoTeclar, true);
    pilha.splice(pilha.indexOf(controle), 1);
    recipiente.remove();
    aoFechar?.();
  }
  pilha.push(controle);

  montarBotoes(modal.querySelector(".modal-botoes"), botoes, controle);
  recipiente.querySelector(".modal-fundo").addEventListener("click", fechar);
  recipiente.querySelector(".modal-fechar").addEventListener("click", fechar);
  document.addEventListener("keydown", aoTeclar, true);
  document.body.appendChild(recipiente);
  aoAbrir?.(modal, controle);
  focarPrimeiroCampo(modal);
  return controle;
}

function montarBotoes(recipiente, botoes, controle) {
  if (!recipiente) return;
  for (const botao of botoes) {
    const el = document.createElement("button");
    el.className = `botao ${botao.primario ? "mod-cta" : ""} ${botao.perigo ? "mod-perigo" : ""}`;
    el.textContent = botao.rotulo;
    el.addEventListener("click", () => executarBotao(botao, controle, el));
    recipiente.appendChild(el);
  }
}

async function executarBotao(botao, controle, elementoBotao) {
  if (!botao.acao) {
    controle.fechar();
    return;
  }
  elementoBotao.disabled = true;
  const manterAberto = (await botao.acao(controle.elemento)) === false;
  elementoBotao.disabled = false;
  if (!manterAberto) controle.fechar();
}

function tratarTecla(evento, controle, botoes) {
  if (pilha[pilha.length - 1] !== controle) return;
  if (evento.key === "Escape") {
    evento.stopPropagation();
    controle.fechar();
    return;
  }
  const emAreaDeTexto = evento.target.tagName === "TEXTAREA";
  if (evento.key !== "Enter" || emAreaDeTexto || evento.shiftKey) return;
  const primario = botoes.findIndex((botao) => botao.primario);
  if (primario < 0) return;
  evento.preventDefault();
  controle.elemento.querySelectorAll(".modal-botoes .botao")[primario]?.click();
}

function focarPrimeiroCampo(modal) {
  const campo = modal.querySelector("input:not([type=checkbox]):not([type=radio]):not([type=hidden]), textarea, select");
  setTimeout(() => {
    campo?.focus();
    if (campo?.select && campo.tagName === "INPUT") campo.select();
  }, 20);
}

/** Pergunta de sim ou não, com o botão destrutivo pintado como tal. */
export function confirmar({ titulo, mensagem, rotuloConfirmar = "Confirmar", perigo = false }) {
  return new Promise((resolver) => {
    let respondeu = false;
    abrirModal({
      titulo,
      corpo: `<p class="modal-texto">${mensagem}</p>`,
      largura: 440,
      botoes: [
        { rotulo: "Cancelar" },
        { rotulo: rotuloConfirmar, primario: true, perigo, acao: () => { respondeu = true; resolver(true); } },
      ],
      aoFechar: () => { if (!respondeu) resolver(false); },
    });
  });
}

/** Pede um texto curto, como um novo rótulo. Devolve `null` se a pessoa desistir. */
export function pedirTexto({ titulo, rotulo, valorInicial = "", placeholder = "", rotuloConfirmar = "Salvar" }) {
  return new Promise((resolver) => {
    let respondeu = false;
    abrirModal({
      titulo,
      largura: 460,
      corpo: `
        <label class="campo">
          <span class="campo-rotulo">${escapeHtml(rotulo)}</span>
          <input type="text" class="entrada" data-campo="texto" value="${escapeHtml(valorInicial)}" placeholder="${escapeHtml(placeholder)}">
        </label>`,
      botoes: [
        { rotulo: "Cancelar" },
        {
          rotulo: rotuloConfirmar,
          primario: true,
          acao: (modal) => {
            const valor = modal.querySelector("[data-campo=texto]").value.trim();
            if (!valor) return false;
            respondeu = true;
            resolver(valor);
            return true;
          },
        },
      ],
      aoFechar: () => { if (!respondeu) resolver(null); },
    });
  });
}

const DURACAO_DO_AVISO_MS = 4000;

/**
 * Aviso passageiro no canto superior direito.
 * `acao` opcional vira um botão dentro do aviso — "Mostrar tudo", "Desfazer".
 */
export function avisar(mensagem, tipo = "info", acao = null) {
  let recipiente = document.getElementById("avisos");
  if (!recipiente) {
    recipiente = document.createElement("div");
    recipiente.id = "avisos";
    recipiente.className = "avisos";
    document.body.appendChild(recipiente);
  }
  const aviso = document.createElement("div");
  aviso.className = `aviso aviso-${tipo}`;
  aviso.innerHTML = `<span class="aviso-texto">${escapeHtml(mensagem)}</span>`;
  if (acao) {
    const botao = document.createElement("button");
    botao.className = "aviso-acao";
    botao.textContent = acao.rotulo;
    botao.addEventListener("click", () => { acao.executar(); aviso.remove(); });
    aviso.appendChild(botao);
  }
  aviso.addEventListener("click", (evento) => { if (evento.target === aviso) aviso.remove(); });
  recipiente.appendChild(aviso);
  setTimeout(() => aviso.remove(), acao ? DURACAO_DO_AVISO_MS * 2 : DURACAO_DO_AVISO_MS);
}
