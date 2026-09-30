/**
 * Painéis laterais da moldura: recolher, redimensionar e alternar entre vistas.
 *
 * Cada lateral tem um cabeçalho de ícones, um por
 * vista, e a lateral direita se divide em duas metades empilhadas, a de baixo
 * recolhível. Largura, vista ativa, altura da divisão, recolhimento e tamanho
 * do texto ficam gravados: a pessoa arruma a mesa uma vez.
 */
import { gravarPreferencia, lerPreferencia } from "./dom.js";

/** O que o centro guarda para si quando uma lateral que acompanha a janela divide a moldura com ele. */
export const MINIMO_DO_CENTRO = 320;

/** O teto do arraste: o máximo fixo, ou metade da janela quando ela é mais larga que o dobro dele. */
export function tetoDaLargura(maximo, larguraDaJanela) {
  return Math.max(maximo, Math.floor(larguraDaJanela / 2));
}

/**
 * A largura que a lateral ocupa na janela de agora. A pedida vale até o teto e
 * até onde o centro ainda fica com MINIMO_DO_CENTRO; `alheio` é o que o resto
 * da moldura (a faixa de ícones, a outra lateral) toma fora do centro. O piso
 * da lateral vence o do centro: abaixo dele o painel já não se lê.
 */
export function larguraNaJanela(pedida, { minimo, maximo, larguraDaJanela, alheio }) {
  const livre = larguraDaJanela - alheio - MINIMO_DO_CENTRO;
  return Math.max(minimo, Math.min(pedida, tetoDaLargura(maximo, larguraDaJanela), livre));
}

/**
 * Uma lateral inteira: pode recolher e tem a largura arrastável pela borda.
 * Com `espacoAlheio`, que diz quanto o resto da moldura toma fora do centro,
 * ela acompanha a janela: o teto cresce com ela e o centro não é esmagado.
 * A largura gravada é a que a pessoa escolheu; a da tela sai dela a cada
 * janela, e ao alargar a janela a lateral volta à escolhida.
 */
export class Lateral {
  constructor(elemento, { chave, alca, larguraPadrao, minimo = 200, maximo = 560, ladoDaAlca = "direita", aoMudar = null, espacoAlheio = null }) {
    this.elemento = elemento;
    this.chave = chave;
    this.minimo = minimo;
    this.maximo = maximo;
    this.ladoDaAlca = ladoDaAlca;
    this.aoMudar = aoMudar;
    this.espacoAlheio = espacoAlheio;
    const salvo = lerPreferencia(`lateral_${chave}`, {});
    this.largura = salvo.largura || larguraPadrao;
    this.recolhida = Boolean(salvo.recolhida);
    this.aplicar();
    if (alca) this.ligarAlca(alca);
    if (espacoAlheio) window.addEventListener("resize", () => this.reajustar());
  }

  /** A largura pedida dentro dos limites: os fixos e, se a lateral acompanha a janela, os dela. */
  limitar(largura) {
    if (!this.espacoAlheio) return Math.min(this.maximo, Math.max(this.minimo, largura));
    return larguraNaJanela(largura, { minimo: this.minimo, maximo: this.maximo, larguraDaJanela: window.innerWidth, alheio: this.espacoAlheio() });
  }

  aplicar() {
    this.elemento.style.width = this.recolhida ? "0px" : `${this.limitar(this.largura)}px`;
    this.elemento.classList.toggle("is-recolhida", this.recolhida);
    document.body.classList.toggle(`lateral-${this.chave}-recolhida`, this.recolhida);
  }

  /**
   * A janela ou o resto da moldura mudou. Reaplica e só avisa se a largura na
   * tela mudou: redimensionar a janela dispara muitos eventos, e quem escuta
   * redesenha painéis.
   */
  reajustar() {
    const antes = this.elemento.style.width;
    this.aplicar();
    if (this.elemento.style.width !== antes) this.aoMudar?.();
  }

  alternar() {
    this.recolhida = !this.recolhida;
    this.persistir();
  }

  expandir() {
    if (!this.recolhida) return;
    this.recolhida = false;
    this.persistir();
  }

  persistir() {
    this.aplicar();
    gravarPreferencia(`lateral_${this.chave}`, { largura: this.largura, recolhida: this.recolhida });
    this.aoMudar?.();
  }

  ligarAlca(alca) {
    alca.addEventListener("mousedown", (evento) => {
      if (this.recolhida) return;
      evento.preventDefault();
      const inicioX = evento.clientX;
      // Parte da largura na tela: a gravada pode ser maior que a janela de agora comporta.
      const larguraInicial = this.limitar(this.largura);
      document.body.classList.add("is-redimensionando");
      const aoMover = (movimento) => {
        const delta = movimento.clientX - inicioX;
        const sinal = this.ladoDaAlca === "direita" ? 1 : -1;
        this.largura = this.limitar(larguraInicial + delta * sinal);
        this.aplicar();
        this.aoMudar?.();
      };
      const aoSoltar = () => {
        document.body.classList.remove("is-redimensionando");
        window.removeEventListener("mousemove", aoMover);
        window.removeEventListener("mouseup", aoSoltar);
        this.persistir();
      };
      window.addEventListener("mousemove", aoMover);
      window.addEventListener("mouseup", aoSoltar);
    });
  }
}

/**
 * Grupo de vistas com cabeçalho de ícones. Os botões levam `data-aba` e as
 * seções `data-painel` com o mesmo nome; só uma seção fica visível por vez.
 */
export class GrupoDeAbas {
  constructor(raiz, { chave, padrao, aoMudar = null }) {
    this.raiz = raiz;
    this.chave = chave;
    this.aoMudar = aoMudar;
    this.botoes = [...raiz.querySelectorAll(":scope > .grupo-cabecalho [data-aba]")];
    this.paineis = [...raiz.querySelectorAll(":scope > .grupo-conteudo > [data-painel]")];
    const salva = lerPreferencia(`aba_${chave}`, padrao);
    this.ativa = this.paineis.some((painel) => painel.dataset.painel === salva) ? salva : padrao;
    this.botoes.forEach((botao) => botao.addEventListener("click", () => this.ativar(botao.dataset.aba)));
    this.aplicar();
  }

  ativar(nome) {
    const mudou = this.ativa !== nome;
    this.ativa = nome;
    this.aplicar();
    gravarPreferencia(`aba_${this.chave}`, nome);
    if (mudou) this.aoMudar?.(nome);
  }

  aplicar() {
    this.botoes.forEach((botao) => botao.classList.toggle("is-ativa", botao.dataset.aba === this.ativa));
    this.paineis.forEach((painel) => {
      painel.hidden = painel.dataset.painel !== this.ativa;
    });
    // O nome da vista ativa ao lado dos ícones: ícone sozinho obriga a decorar.
    const titulo = this.raiz.querySelector(":scope > .grupo-cabecalho [data-titulo-grupo]");
    const ativo = this.botoes.find((botao) => botao.dataset.aba === this.ativa);
    if (titulo && ativo) titulo.textContent = ativo.title.replace(/\s*\(.*\)$/, "");
  }

  mostra(nome) {
    return this.ativa === nome;
  }
}

/** Os tamanhos do texto de uma lateral, como fração do tamanho padrão. */
export const TAMANHOS_DO_TEXTO = [0.9, 1, 1.15, 1.3];
export const TAMANHO_PADRAO_DO_TEXTO = 1;

/** O tamanho gravado, se é um dos oferecidos; preferência corrompida vale o padrão. */
export function tamanhoDoTextoValido(valor) {
  return TAMANHOS_DO_TEXTO.includes(valor) ? valor : TAMANHO_PADRAO_DO_TEXTO;
}

/** O tamanho vizinho no sentido pedido (negativo diminui), parado nas pontas da escala. */
export function proximoTamanhoDoTexto(atual, sentido) {
  const indice = TAMANHOS_DO_TEXTO.indexOf(tamanhoDoTextoValido(atual));
  const alvo = Math.min(TAMANHOS_DO_TEXTO.length - 1, Math.max(0, indice + Math.sign(sentido)));
  return TAMANHOS_DO_TEXTO[alvo];
}

export function formatarTamanhoDoTexto(tamanho) {
  return `${Math.round(tamanho * 100)}%`;
}

/**
 * O tamanho do texto de uma lateral, pelos botões A− e A+ (`data-tamanho-texto`
 * com o sentido). Ele entra como `--escala-lateral`, que os tokens de fonte da
 * lateral multiplicam. Na ponta da escala o botão fica `aria-disabled`, não
 * `disabled`: desabilitado, ele perderia o foco de quem aperta pelo teclado.
 */
export class TamanhoDoTexto {
  constructor(alvo, controles, { chave, aoMudar = null }) {
    this.alvo = alvo;
    this.chave = chave;
    this.aoMudar = aoMudar;
    this.botoes = [...controles.querySelectorAll("[data-tamanho-texto]")];
    this.tamanho = tamanhoDoTextoValido(lerPreferencia(`tamanho_texto_${chave}`, TAMANHO_PADRAO_DO_TEXTO));
    this.botoes.forEach((botao) => botao.addEventListener("click", () => this.mudar(Number(botao.dataset.tamanhoTexto))));
    this.aplicar();
  }

  mudar(sentido) {
    const novo = proximoTamanhoDoTexto(this.tamanho, sentido);
    if (novo === this.tamanho) return;
    this.tamanho = novo;
    this.aplicar();
    gravarPreferencia(`tamanho_texto_${this.chave}`, novo);
    this.aoMudar?.(novo);
  }

  aplicar() {
    this.alvo.style.setProperty("--escala-lateral", String(this.tamanho));
    const atual = formatarTamanhoDoTexto(this.tamanho);
    this.botoes.forEach((botao) => {
      const sentido = Number(botao.dataset.tamanhoTexto);
      const rotulo = `${sentido < 0 ? "Diminuir" : "Aumentar"} o texto da lateral (agora ${atual})`;
      botao.title = rotulo;
      botao.setAttribute("aria-label", rotulo);
      botao.setAttribute("aria-disabled", String(proximoTamanhoDoTexto(this.tamanho, sentido) === this.tamanho));
    });
  }
}

/** Altura de janela abaixo da qual a metade de baixo nasce recolhida. */
export const ALTURA_PARA_RECOLHER = 800;

/**
 * Se a metade de baixo começa recolhida. A escolha gravada vence sempre; sem
 * ela, decide a altura da janela: numa janela baixa o histórico levava dois
 * quintos da lateral e a dúvida aberta em cima ficava numa fresta.
 */
export function recolhidaDeInicio(salva, alturaDaJanela) {
  if (typeof salva === "boolean") return salva;
  return alturaDaJanela < ALTURA_PARA_RECOLHER;
}

/**
 * O recolhimento da metade de baixo, sem DOM, para caber num teste. `escolhida`
 * é o último gesto da pessoa ou, sem gesto nenhum, o padrão da janela;
 * `temporaria` é o recolhimento que a seleção pediu, e que nunca vira escolha.
 */
export class RecolhimentoDaMetade {
  constructor(salva, alturaDaJanela) {
    this.escolhida = recolhidaDeInicio(salva, alturaDaJanela);
    this.temporaria = false;
    this.acompanhada = null;
  }

  get recolhida() {
    return this.escolhida || this.temporaria;
  }

  /** Um gesto da pessoa: vale mais que o padrão da janela e desfaz o temporário. */
  definir(recolhida) {
    this.escolhida = Boolean(recolhida);
    this.temporaria = false;
  }

  /**
   * Acompanha a seleção. Uma seleção nova que pede espaço recolhe a metade só
   * enquanto dura; qualquer outra devolve o estado escolhido. A mesma seleção
   * de novo não muda nada: a releitura do tempo real, ou a dúvida respondida
   * ali mesmo, não recolhe o que a pessoa expandiu nem expande debaixo dela.
   * Devolve se o estado mudou.
   */
  acompanhar(id, pedeEspaco) {
    if (id === this.acompanhada) return false;
    const antes = this.recolhida;
    this.acompanhada = id;
    this.temporaria = Boolean(pedeEspaco);
    return this.recolhida !== antes;
  }
}

/**
 * Divisão entre as duas metades empilhadas da lateral direita. A de baixo pode
 * recolher até sobrar só o cabeçalho, e a de cima leva a altura inteira.
 * Recolher não mexe na fração gravada: ao expandir, a divisão volta onde estava.
 */
export class DivisorVertical {
  constructor(divisor, superior, inferior, { chave, fracaoPadrao = 0.58, botaoRecolher = null }) {
    this.divisor = divisor;
    this.superior = superior;
    this.inferior = inferior;
    this.chave = chave;
    this.botaoRecolher = botaoRecolher;
    this.dicaDoDivisor = divisor.title;
    this.fracao = lerPreferencia(`divisao_${chave}`, fracaoPadrao);
    this.recolhimento = new RecolhimentoDaMetade(lerPreferencia(`divisao_${chave}_recolhida`, null), window.innerHeight);
    this.aplicar();
    // Recolhida, não há o que dividir: o divisor fica só como linha.
    divisor.addEventListener("mousedown", (evento) => { if (!this.recolhida) this.arrastar(evento); });
    divisor.addEventListener("dblclick", () => { if (!this.recolhida) this.definir(fracaoPadrao); });
    botaoRecolher?.addEventListener("click", () => this.alternar());
    // O ícone da vista de baixo pede a vista: com a metade recolhida, expande.
    inferior.querySelectorAll(":scope > .grupo-cabecalho [data-aba]").forEach((botao) => botao.addEventListener("click", () => this.expandir()));
  }

  get recolhida() {
    return this.recolhimento.recolhida;
  }

  aplicar() {
    const recolhida = this.recolhida;
    this.superior.style.flex = recolhida ? "1 1 0" : `${this.fracao} 1 0`;
    this.inferior.style.flex = recolhida ? "0 0 auto" : `${1 - this.fracao} 1 0`;
    this.inferior.classList.toggle("is-recolhida", recolhida);
    this.divisor.classList.toggle("is-inerte", recolhida);
    this.divisor.title = recolhida ? "" : this.dicaDoDivisor;
    if (this.botaoRecolher) {
      this.botaoRecolher.setAttribute("aria-expanded", String(!recolhida));
      this.botaoRecolher.title = recolhida ? "Expandir o histórico" : "Recolher o histórico e dar a altura ao painel de cima";
    }
  }

  alternar() {
    this.escolher(!this.recolhida);
  }

  expandir() {
    if (this.recolhida) this.escolher(false);
  }

  escolher(recolhida) {
    this.recolhimento.definir(recolhida);
    this.aplicar();
    gravarPreferencia(`divisao_${this.chave}_recolhida`, this.recolhimento.escolhida);
  }

  /**
   * Recolhe a metade de baixo enquanto a seleção pede espaço, sem gravar nada.
   * Com o ponteiro ou o foco nela, a pessoa está usando o histórico, talvez
   * clicando no evento que levou à seleção: recolher ali tiraria a lista de
   * debaixo do cursor.
   */
  acompanharSelecao(id, pedeEspaco) {
    const emUso = this.inferior.matches(":hover, :focus-within");
    if (this.recolhimento.acompanhar(id, pedeEspaco && !emUso)) this.aplicar();
  }

  definir(fracao) {
    this.fracao = Math.min(0.85, Math.max(0.15, fracao));
    this.aplicar();
    gravarPreferencia(`divisao_${this.chave}`, this.fracao);
  }

  arrastar(evento) {
    evento.preventDefault();
    const pai = this.superior.parentElement.getBoundingClientRect();
    document.body.classList.add("is-redimensionando-vertical");
    const aoMover = (movimento) => this.definir((movimento.clientY - pai.top) / pai.height);
    const aoSoltar = () => {
      document.body.classList.remove("is-redimensionando-vertical");
      window.removeEventListener("mousemove", aoMover);
      window.removeEventListener("mouseup", aoSoltar);
    };
    window.addEventListener("mousemove", aoMover);
    window.addEventListener("mouseup", aoSoltar);
  }
}
