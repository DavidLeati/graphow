/**
 * O Artifact que o humano cria pelo canvas, sem DOM: a âncora e as Tasks de que ele deriva.
 *
 * O kernel recusa o Artifact novo sem âncora (artifact_sem_ancora). A âncora é
 * o `commit` do git (40 ou 64 caracteres) ou, no documento fora de git, o
 * `sha256` do conteúdo com o `caminho` dele. Sem nenhuma, só passa o Artifact
 * cujos `deriva_de` vão todos a Tasks de ação externa, e o kernel julga isso
 * pelo lote que cria o nó: por isso as Tasks de origem vão no mesmo pedido
 * (`deriva_de`), e o servidor grava o nó e as arestas juntos. Com a aresta
 * criada depois, o Artifact da ação externa não tinha como nascer.
 */

export const CAMPOS_DA_ANCORA = Object.freeze(["commit", "sha256", "caminho"]);

/** As propriedades da âncora que vieram preenchidas, sem os espaços em volta. */
export function ancoraPreenchida(campos) {
  const pares = CAMPOS_DA_ANCORA.map((chave) => [chave, String(campos?.[chave] ?? "").trim()]);
  return Object.fromEntries(pares.filter(([, valor]) => valor));
}

/** Os ids das Tasks de que o Artifact deriva, sem vazios nem repetidos, na ordem dada. */
export function tasksDeOrigem(ids) {
  return [...new Set((ids || []).map((id) => String(id ?? "").trim()).filter(Boolean))];
}

/** As Tasks que o diálogo oferece como origem: as do canvas, pelo rótulo. */
export function tasksOferecidas(nos) {
  return [...(nos || [])].filter((no) => no?.tipo === "Task").sort((a, b) => String(a.rotulo).localeCompare(String(b.rotulo)));
}

/** O que o pedido de criação do Artifact acrescenta: as propriedades da âncora e o `deriva_de`. */
export function pedidoDoArtifact(campos) {
  return { propriedades: ancoraPreenchida(campos), deriva_de: tasksDeOrigem(campos?.deriva_de) };
}
