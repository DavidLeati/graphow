/**
 * O que a aba Configurações sabe dizer sem tocar o DOM: nomes legíveis, as
 * linhas da tabela de gestos, a origem de cada valor e os corpos de escrita.
 *
 * O catálogo (gestos, valores aceitos, presets) vem do servidor: o que mora
 * aqui é só apresentação, e por isso pode divergir sem a tela oferecer o que o
 * kernel recusa. Fica separado da vista para o `node --test` exercitá-lo.
 */

export const ESCOPO_GLOBAL = "global";
export const PRESET_PERSONALIZADA = "personalizada";
export const PRESET_HERDAR = "herdar";

const NOMES_DOS_PRESETS = {
  governanca_maxima: "Governança máxima",
  arbitragem_maxima: "Arbitragem máxima",
  personalizada: "Personalizada",
  herdar: "Herdar do global",
};

const NOMES_DOS_GESTOS = {
  responder_questao: "Responder dúvidas",
  promover_aprendizado: "Promover aprendizados",
  constraint: "Restrições (Constraint)",
  estrutura: "Estrutura do grafo",
  excluir: "Excluir",
  fechar_goal: "Fechar um Goal",
  encerrar_sessao: "Encerrar sessões",
  liberar_posse_alheia: "Liberar posse alheia",
  integracao: "Integração",
  max_correcoes: "Correções em cadeia",
};

const NOMES_DOS_VALORES = {
  humano: "Só o humano",
  arbitro: "Humano e árbitro",
  estrito: "Só o humano",
  ilimitado: "Todos os agentes",
};

/** Os gestos que a política nunca delega: sempre do humano, só para leitura. */
export const GESTOS_FIXOS = [
  { gesto: "promocao_global", nome: "Promoção global", descricao: "Dar a um Aprendizado alcance global, valendo em todo projeto" },
  { gesto: "alterar_governanca", nome: "Alterar a governança", descricao: "Mudar esta configuração: é o portão que protege todos os outros" },
];

export function nomeDoPreset(preset) {
  return NOMES_DOS_PRESETS[preset] || String(preset ?? "");
}

export function nomeDoGesto(gesto) {
  return NOMES_DOS_GESTOS[gesto] || String(gesto).replace(/_/g, " ");
}

export function nomeDoValor(gesto, valor) {
  if (gesto === "max_correcoes") return valor === 1 ? "1 correção" : `${valor} correções`;
  return NOMES_DOS_VALORES[valor] || String(valor);
}

/** A origem do valor em texto curto; o servidor a publica como `global`, `projeto`, `preset:<nome>` ou `legado:...`. */
export function rotuloDaOrigem(origem) {
  const texto = String(origem ?? "");
  if (texto === "global") return "global";
  if (texto === "projeto") return "projeto";
  if (texto.startsWith("legado")) return "legado";
  if (texto.startsWith("preset:")) return "preset";
  if (texto.startsWith("projeto:")) return `projeto ${texto.slice("projeto:".length)}`;
  return texto || "padrão";
}

/** Explica a origem para o tooltip: o texto curto sozinho não diz de onde o valor veio. */
export function explicarOrigem(origem) {
  const texto = String(origem ?? "");
  if (texto === "global") return "Vem da política global";
  if (texto === "projeto") return "Definido neste projeto";
  if (texto.startsWith("legado")) return "Vem de nivel_autonomia: ilimitado, de antes da governança configurável";
  if (texto.startsWith("preset:")) return `Valor fixo do preset ${nomeDoPreset(texto.slice("preset:".length))}`;
  if (texto.startsWith("projeto:")) return `O projeto ${texto.slice("projeto:".length)} restringe este gesto`;
  return "Valor padrão";
}

/** A configuração guardada do escopo, com o padrão de cada nível quando nada foi gravado. */
export function configuracaoDoEscopo(dados, ehProjeto) {
  const padrao = ehProjeto ? PRESET_HERDAR : "governanca_maxima";
  return {
    preset: dados?.configuracao?.preset || padrao,
    personalizada: dados?.configuracao?.personalizada || {},
  };
}

/** Os cartões do escopo, na ordem de leitura; `herdar` só existe no projeto. */
export function cartoesDoEscopo(catalogo, ehProjeto) {
  const lista = ehProjeto ? catalogo?.presets_do_projeto : catalogo?.presets;
  const porNome = new Map((lista || []).map((preset) => [preset.preset, preset]));
  const ordem = ehProjeto ? [PRESET_HERDAR, "governanca_maxima", "arbitragem_maxima", PRESET_PERSONALIZADA] : ["governanca_maxima", "arbitragem_maxima", PRESET_PERSONALIZADA];
  return ordem.filter((nome) => porNome.has(nome)).map((nome) => ({ preset: nome, nome: nomeDoPreset(nome), descricao: porNome.get(nome).descricao }));
}

/**
 * Uma linha por gesto do catálogo. `editavel` só vale na Personalizada; no
 * projeto a linha ainda diz se o gesto está sobrescrito ou herdando, e o valor
 * que herdaria, para a opção "Herdar" mostrar o que ela traria.
 */
export function linhasDaTabela(catalogo, dados, ehProjeto) {
  const { preset, personalizada } = configuracaoDoEscopo(dados, ehProjeto);
  const editavel = preset === PRESET_PERSONALIZADA;
  const herdado = dados?.politica_global || {};
  return (catalogo?.gestos || []).map((gesto) => {
    const chave = gesto.gesto;
    const sobrescrito = ehProjeto && Object.hasOwn(personalizada, chave);
    return {
      gesto: chave,
      nome: nomeDoGesto(chave),
      descricao: gesto.descricao,
      valores: gesto.valores,
      valor: dados?.politica_efetiva?.[chave],
      origem: dados?.origens?.[chave],
      editavel,
      ehProjeto,
      sobrescrito,
      herdaria: herdado[chave],
    };
  });
}

/** O valor que o catálogo aceita a partir do texto de um `<option>`: o inteiro de `max_correcoes` volta como número. */
export function valorDoCatalogo(valores, texto) {
  return (valores || []).find((valor) => String(valor) === String(texto));
}

/** O corpo do PUT que troca de preset sem tocar a personalizada guardada. */
export function corpoDoPreset(preset) {
  return { preset };
}

/** O corpo do PUT que muda um gesto: só ele viaja, o servidor mescla na personalizada guardada. */
export function corpoDoGesto(gesto, valor) {
  return { personalizada: { [gesto]: valor } };
}

const TEXTO_VAZIO = "";

function textoOuNulo(valor) {
  const texto = String(valor ?? TEXTO_VAZIO).trim();
  return texto === TEXTO_VAZIO ? null : texto;
}

function inteiroOuNulo(valor) {
  const texto = textoOuNulo(valor);
  if (texto === null) return { valor: null };
  const numero = Number(texto);
  return Number.isInteger(numero) && numero >= 1 ? { valor: numero } : { erro: "O teto de rodadas é um inteiro a partir de 1." };
}

/** As linhas de um textarea viram a lista de globs; sem nenhuma linha, nulo apaga a propriedade. */
export function listaDeCaminhos(texto) {
  const linhas = String(texto ?? TEXTO_VAZIO).split(/\r?\n/).map((linha) => linha.trim()).filter(Boolean);
  return linhas.length ? linhas : null;
}

/** O corpo `{operacao}` a partir do formulário; vazio apaga a propriedade (valor nulo), como o backend aceita. */
export function operacaoDoFormulario(campos) {
  const teto = inteiroOuNulo(campos.teto_rodadas);
  if (teto.erro) return { erro: teto.erro };
  return {
    corpo: {
      operacao: {
        cadencia: textoOuNulo(campos.cadencia),
        teto_rodadas: teto.valor,
        ramo_base: textoOuNulo(campos.ramo_base),
        caminhos_de_colisao: listaDeCaminhos(campos.caminhos_de_colisao),
      },
    },
  };
}

/** Os valores do projeto como o formulário os mostra: o que não foi gravado volta vazio. */
export function camposDaOperacao(operacao) {
  return {
    cadencia: operacao?.cadencia ?? TEXTO_VAZIO,
    teto_rodadas: operacao?.teto_rodadas ?? TEXTO_VAZIO,
    ramo_base: operacao?.ramo_base ?? TEXTO_VAZIO,
    caminhos_de_colisao: (operacao?.caminhos_de_colisao || []).join("\n"),
  };
}

/** O tipo do evento em texto legível: `no_atualizado` vira "no atualizado". */
export function descreverTipoDeEvento(tipo) {
  return String(tipo ?? "").replace(/_/g, " ");
}

/** A mensagem de uma recusa, com cada problema que o servidor apontou. */
export function mensagemDeRecusa(resposta) {
  const problemas = Array.isArray(resposta?.problemas) ? resposta.problemas : [];
  const base = resposta?.mensagem || "O servidor recusou a configuração.";
  return problemas.length && !base.includes(problemas[0]) ? `${base} (${problemas.join("; ")})` : base;
}
