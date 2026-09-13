/**
 * Idade e ordem de um no: ha quanto tempo ele existe e onde ele entrou no log.
 *
 * Sao duas perguntas distintas. O carimbo de tempo diz a idade; a sequencia do
 * log diz quem veio antes de quem, e e a unica resposta confiavel para isso,
 * porque processos diferentes escrevem com relogios proprios.
 */

const MINUTO_MS = 60000;
const HORA_MS = 60 * MINUTO_MS;
const DIA_MS = 24 * HORA_MS;

const SEM_DATA = "";
const DATA_DESCONHECIDA = "desconhecido";

function instanteDe(iso) {
  return Date.parse(iso ?? "");
}

/**
 * Distancia em texto curto, do tamanho que cabe no rodape de um card.
 * Devolve vazio para um no sem carimbo de tempo, em vez de inventar uma idade.
 */
export function formatarIdadeCurta(iso, agora = Date.now()) {
  const instante = instanteDe(iso);
  if (Number.isNaN(instante)) return SEM_DATA;
  const decorrido = Math.max(0, agora - instante);
  if (decorrido < MINUTO_MS) return "agora";
  if (decorrido < HORA_MS) return `${Math.floor(decorrido / MINUTO_MS)} min`;
  if (decorrido < DIA_MS) return `${Math.floor(decorrido / HORA_MS)} h`;
  return `${Math.floor(decorrido / DIA_MS)} d`;
}

/**
 * Mesma idade em frase corrente. Existe separado da forma curta porque "ha" nao
 * cabe em toda idade: "ha agora" nao e portugues.
 */
export function formatarIdadeRelativa(iso, agora = Date.now()) {
  const curta = formatarIdadeCurta(iso, agora);
  if (curta === SEM_DATA || curta === "agora") return curta;
  return `há ${curta}`;
}

/** Data absoluta no fuso de quem esta olhando, para o tooltip e o inspetor. */
export function formatarDataCompleta(iso) {
  const instante = instanteDe(iso);
  if (Number.isNaN(instante)) return DATA_DESCONHECIDA;
  return new Date(instante).toLocaleString();
}

/** Indica que o no recebeu alguma escrita depois da que o criou. */
export function foiAlterado(node) {
  return (node?.seq_atualizacao ?? 0) > (node?.seq_criacao ?? 0);
}

/** Texto do tooltip do card: nascimento, ultima alteracao e posicao no log. */
export function descreverHistoricoDoNo(node) {
  const partes = [
    `Criado em ${formatarDataCompleta(node?.criado_em)} (log #${node?.seq_criacao ?? 0})`,
  ];
  if (foiAlterado(node)) {
    partes.push(
      `Alterado em ${formatarDataCompleta(node?.atualizado_em)} (log #${node.seq_atualizacao})`
    );
  }
  return partes.join("\n");
}
