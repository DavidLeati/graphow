/**
 * Registro de comandos e a paleta que os lista (Ctrl+P).
 *
 * Toda ação da moldura existe como comando com nome, ícone e atalho. A faixa de
 * ícones, os menus e a paleta chamam o mesmo comando, então uma ação nunca tem
 * dois comportamentos conforme o botão que a disparou — e a paleta é o lugar
 * onde se descobre que ela existe.
 */
import { escapeHtml, focoEmCampoDeTexto } from "./dom.js";
import { icone } from "./icones.js";
import { Sugestor } from "./sugestor.js";

export class RegistroDeComandos {
  constructor() {
    this.comandos = new Map();
    this.porAtalho = new Map();
    this.paleta = new Sugestor({
      placeholder: "Digite um comando…",
      instrucoes: [["↑↓", "navegar"], ["↵", "executar"], ["esc", "fechar"]],
      buscar: async (termo) => ({ itens: this.filtrar(termo) }),
      montarItem: (comando, termo) => this.montarItem(comando, termo),
      aoEscolher: (comando) => this.executar(comando.id),
    });
    window.addEventListener("keydown", (evento) => this.aoTeclar(evento));
  }

  /**
   * `atalho` usa a forma "Ctrl+K" ou uma tecla solta ("n"). Tecla solta só vale
   * fora de campos de texto, para não roubar a letra de quem está digitando.
   */
  registrar(comando) {
    this.comandos.set(comando.id, comando);
    for (const atalho of [].concat(comando.atalho || [])) this.porAtalho.set(atalho.toLowerCase(), comando.id);
  }

  executar(id, ...argumentos) {
    const comando = this.comandos.get(id);
    if (!comando || comando.disponivel?.() === false) return;
    comando.executar(...argumentos);
  }

  abrirPaleta() {
    if (this.paleta.aberto) this.paleta.fechar();
    else this.paleta.abrir();
  }

  filtrar(termo) {
    const alvo = termo.trim().toLowerCase();
    const disponiveis = [...this.comandos.values()].filter((comando) => !comando.oculto && comando.disponivel?.() !== false);
    if (!alvo) return disponiveis;
    return disponiveis
      .map((comando) => ({ comando, posicao: comando.nome.toLowerCase().indexOf(alvo) }))
      .filter(({ comando, posicao }) => posicao >= 0 || casaAsIniciais(comando.nome, alvo))
      .sort((a, b) => (a.posicao < 0) - (b.posicao < 0) || a.posicao - b.posicao)
      .map(({ comando }) => comando);
  }

  montarItem(comando, termo) {
    const atalho = comando.atalhoExibido || [].concat(comando.atalho || [])[0];
    return `
      <span class="prompt-item-icone">${icone(comando.icone || "command", { tamanho: 16 })}</span>
      <div class="prompt-item-conteudo"><div class="prompt-item-titulo">${realcar(comando.nome, termo)}</div></div>
      ${atalho ? `<span class="prompt-item-aux"><kbd>${escapeHtml(formatarAtalho(atalho))}</kbd></span>` : ""}`;
  }

  /**
   * Com um modal aberto o atalho não executa, mas o padrão do navegador é
   * barrado do mesmo jeito: Ctrl+P sobre um diálogo abriria a impressão. As
   * caixas de sugestão são a exceção — Ctrl+K e Ctrl+P alternam entre elas.
   */
  aoTeclar(evento) {
    // Shift só entra na combinação junto de outro modificador: "?" já é Shift+/.
    const comModificador = evento.ctrlKey || evento.metaKey || evento.altKey;
    const combinacao = [
      evento.ctrlKey || evento.metaKey ? "ctrl" : "",
      evento.altKey ? "alt" : "",
      evento.shiftKey && (comModificador || evento.key.length > 1) ? "shift" : "",
      evento.key.toLowerCase(),
    ].filter(Boolean).join("+");
    const id = this.porAtalho.get(combinacao);
    if (!id) return;
    const teclaSolta = !combinacao.includes("+");
    if (teclaSolta && focoEmCampoDeTexto()) return;
    evento.preventDefault();
    if (document.querySelector(".modal-recipiente:not(.mod-sugestor)")) return;
    this.executar(id);
  }
}

function casaAsIniciais(nome, alvo) {
  const iniciais = nome.toLowerCase().split(/\s+/).map((palavra) => palavra[0]).join("");
  return iniciais.includes(alvo);
}

function realcar(texto, termo) {
  const alvo = termo.trim();
  if (!alvo) return escapeHtml(texto);
  const posicao = texto.toLowerCase().indexOf(alvo.toLowerCase());
  if (posicao < 0) return escapeHtml(texto);
  return `${escapeHtml(texto.slice(0, posicao))}<mark class="realce-busca">${escapeHtml(texto.slice(posicao, posicao + alvo.length))}</mark>${escapeHtml(texto.slice(posicao + alvo.length))}`;
}

const TECLAS_LEGIVEIS = { arrowleft: "←", arrowright: "→", arrowup: "↑", arrowdown: "↓", enter: "↵", escape: "Esc" };

/** "ctrl+shift+f" vira "Ctrl + Shift + F" para exibição. */
export function formatarAtalho(atalho) {
  if (atalho === "+") return "+";
  return atalho
    .split("+")
    .map((parte) => TECLAS_LEGIVEIS[parte] || (parte.length === 1 ? parte.toUpperCase() : parte[0].toUpperCase() + parte.slice(1)))
    .join(" + ");
}
