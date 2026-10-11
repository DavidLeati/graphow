import { createServer } from 'node:http';
import { lerTudo } from './storage.js';

const PORTA = Number(process.env.PORTA ?? 3000);

export function criarServidor() {
  return createServer((req, res) => {
    if (req.method === 'GET' && req.url === '/health') {
      res.writeHead(200, { 'content-type': 'application/json' });
      res.end(JSON.stringify({ ok: true, tarefas: lerTudo().length }));
      return;
    }
    res.writeHead(404, { 'content-type': 'application/json' });
    res.end(JSON.stringify({ erro: 'rota nao encontrada' }));
  });
}

if (import.meta.url === `file://${process.argv[1]}`) {
  criarServidor().listen(PORTA, () => console.log(`api-tarefas na porta ${PORTA}`));
}
