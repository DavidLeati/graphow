/**
 * Contas de datas do calendário e da lista do histórico.
 *
 * O histórico pensa em dias do relógio de quem olha: um evento das 23h de
 * terça é de terça aqui, mesmo que em UTC já seja quarta. Por isso tudo sai
 * dos getters locais do `Date`, nunca de `toISOString`, e os passos de semana
 * e de mês montam datas novas por ano, mês e dia, o que atravessa o horário
 * de verão sem somar milissegundos. Nada aqui toca DOM: roda igual no Node.
 */

/** Chave `AAAA-MM-DD` do dia local de uma data; é como o histórico indexa o log. */
export function chaveDoDia(data) {
  const mes = String(data.getMonth() + 1).padStart(2, "0");
  const dia = String(data.getDate()).padStart(2, "0");
  return `${data.getFullYear()}-${mes}-${dia}`;
}

/** Meia-noite local do dia de uma chave `AAAA-MM-DD`. */
export function dataDaChave(chave) {
  const [ano, mes, dia] = chave.split("-").map(Number);
  return new Date(ano, mes - 1, dia);
}

/** Domingo da semana da data, como a primeira coluna do calendário. */
export function inicioDaSemana(data) {
  return new Date(data.getFullYear(), data.getMonth(), data.getDate() - data.getDay());
}

function diasAPartirDe(inicio, quantos) {
  return Array.from({ length: quantos }, (_, deslocamento) => new Date(inicio.getFullYear(), inicio.getMonth(), inicio.getDate() + deslocamento));
}

/** Os sete dias, de domingo a sábado, da semana que contém a data. */
export function diasDaSemana(data) {
  return diasAPartirDe(inicioDaSemana(data), 7);
}

/** As seis semanas da grade do mês da data, com as pontas dos meses vizinhos. */
export function diasDaGradeDoMes(data) {
  return diasAPartirDe(inicioDaSemana(new Date(data.getFullYear(), data.getMonth(), 1)), 42);
}

/** Domingo da semana `passo` semanas adiante (ou atrás, com passo negativo). */
export function passarSemana(data, passo) {
  const inicio = inicioDaSemana(data);
  return new Date(inicio.getFullYear(), inicio.getMonth(), inicio.getDate() + 7 * passo);
}

/** Dia 1 do mês `passo` meses adiante; do dia 31 não se pula um mês curto. */
export function passarMes(data, passo) {
  return new Date(data.getFullYear(), data.getMonth() + passo, 1);
}

export function mesmoMes(a, b) {
  return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth();
}

const nomeDoMes = (data, formato) => data.toLocaleDateString("pt-BR", { month: formato });

/**
 * Título do período entre duas datas: o mês por extenso quando cabe num mês só,
 * os dois meses abreviados quando a semana atravessa a virada. Volta separado
 * em mês e ano porque o calendário os desenha com pesos diferentes.
 */
export function tituloDoPeriodo(primeiro, ultimo) {
  if (mesmoMes(primeiro, ultimo)) return { mes: nomeDoMes(primeiro, "long"), ano: String(primeiro.getFullYear()) };
  const anos = primeiro.getFullYear() === ultimo.getFullYear() ? String(primeiro.getFullYear()) : `${primeiro.getFullYear()}–${ultimo.getFullYear()}`;
  return { mes: `${nomeDoMes(primeiro, "short")} – ${nomeDoMes(ultimo, "short")}`, ano: anos };
}

/**
 * Nome curto de um dia para o cabeçalho da lista: "Hoje", "Ontem" ou
 * "qua., 24 set.", com o ano só quando não é o de hoje. O `Intl` junta dia e
 * mês com "de"; montado por partes, o rótulo cabe numa lateral estreita.
 */
export function rotuloDoDia(chave, hoje) {
  if (chave === chaveDoDia(hoje)) return "Hoje";
  if (chave === chaveDoDia(new Date(hoje.getFullYear(), hoje.getMonth(), hoje.getDate() - 1))) return "Ontem";
  const data = dataDaChave(chave);
  const semana = data.toLocaleDateString("pt-BR", { weekday: "short" });
  const ano = data.getFullYear() === hoje.getFullYear() ? "" : ` ${data.getFullYear()}`;
  return `${semana}, ${data.getDate()} ${nomeDoMes(data, "short")}${ano}`;
}

/**
 * Parte uma lista já ordenada em blocos de eventos seguidos do mesmo dia, numa
 * passada só. O log vem em ordem, então um dia não se repete; se o relógio de
 * quem gravou voltar atrás, o dia aparece de novo em outro bloco, sem sumir.
 */
export function agruparPorDia(eventos, diaDe) {
  const grupos = [];
  for (const evento of eventos) {
    const dia = diaDe(evento);
    const ultimo = grupos[grupos.length - 1];
    if (ultimo && ultimo.dia === dia) ultimo.eventos.push(evento);
    else grupos.push({ dia, eventos: [evento] });
  }
  return grupos;
}
