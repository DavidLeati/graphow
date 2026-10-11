import { readFileSync, writeFileSync, existsSync } from 'node:fs';

const ARQUIVO = process.env.ARQUIVO_TAREFAS ?? new URL('../dados/tarefas.json', import.meta.url).pathname;

export function lerTudo() {
  if (!existsSync(ARQUIVO)) return [];
  return JSON.parse(readFileSync(ARQUIVO, 'utf8'));
}

export function gravarTudo(tarefas) {
  writeFileSync(ARQUIVO, JSON.stringify(tarefas, null, 2));
}
