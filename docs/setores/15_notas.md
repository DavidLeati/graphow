# Setor 15 — Acervo de Notas como Projeção

> Documento gerado a partir do código por `graphow docs-gerar`.
> Não edite à mão: a próxima geração sobrescreve. Para mudar o texto de missão
> da ala, edite `DEFINICOES_DE_SETOR` em `src/graphow/documentacao/setores.py`.

**Pacote:** `graphow.notas`

Renderiza um diretório de notas em Markdown a partir dos aprendizados promovidos, uma nota por aprendizado, com a origem derivada das arestas. O grafo é a fonte; o acervo é leitura, regenerável do zero, e a conferência acusa qualquer deriva.

## Inventário

5 módulos · 399 linhas · 9 classes

| Módulo | Linhas | Papel |
| :--- | ---: | :--- |
| [`notas/__init__.py`](#notasinit) | 57 | Acervo de notas como projeção do grafo: uma nota em Markdown por aprendizado promovido. |
| [`notas/extracao.py`](#notasextracao) | 50 | Extração das notas a partir da projeção: só o que o grafo diz, na ordem do log. |
| [`notas/modelo.py`](#notasmodelo) | 50 | Modelos imutáveis do acervo de notas: uma nota por aprendizado promovido. |
| [`notas/publicacao.py`](#notaspublicacao) | 149 | Publicação do acervo, com escrita atrás de interface injetável e conferência de deriva. |
| [`notas/renderizador.py`](#notasrenderizador) | 93 | Renderização das notas em Markdown, no formato "afirmação, como se sabe, como aplicar". |

## `notas/__init__.py`

Acervo de notas como projeção do grafo: uma nota em Markdown por aprendizado promovido.

### `MontadorAcervoDeNotas`

*serviço* — Compõe extração, renderização e publicação para um diretório em disco.

- `montar_documentos() -> tuple[DocumentoDeNota, ...]` — Consulta pura: o que o grafo produziria agora, sem gravar.
- `publicar() -> ResultadoDoAcervo` — Comando: grava o acervo inteiro e remove o que sobrou.
- `conferir() -> tuple[str, ...]` — Consulta pura: os arquivos que divergem do que o grafo produziria.

## `notas/extracao.py`

Extração das notas a partir da projeção: só o que o grafo diz, na ordem do log.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `SEM_LIMITE_DE_VALIDADE` | `str` | `''` |
| `TIPO_DE_NO_REMOVIDO` | `str` | `'removido'` |

### Funções do módulo

- `extrair_notas(view: GrafoView) -> tuple[NotaDeAprendizado, ...]` — Uma nota por aprendizado promovido, na ordem em que nasceram no log.

## `notas/modelo.py`

Modelos imutáveis do acervo de notas: uma nota por aprendizado promovido.

### `NotaDeAprendizado`

*DTO imutável* — O que uma nota do acervo diz sobre um aprendizado, tirado do grafo.

**Campos:** `id: str`, `afirmacao: str`, `como_aplicar: str`, `autor: str`, `papel: str`, `seq_criacao: int`, `alcances: tuple[str, ...]`, `origens: tuple[OrigemDaNota, ...]`, `substituto: str | None`, `contradicoes: tuple[OrigemDaNota, ...]`, `valido_ate: str`

- `nome_arquivo() -> str` `[property]` — Nome do arquivo da nota dentro do acervo.
- `esta_vigente() -> bool` `[property]` — Uma nota sem substituto segue valendo; a substituída fica, marcada.

### `OrigemDaNota`

*DTO imutável* — Um nó de onde o aprendizado saiu, ou que o contradiz, na forma que a nota cita.

**Campos:** `id: str`, `tipo: str`, `rotulo: str`, `seq: int`

- `descrever() -> str` — Citação em uma linha: tipo, rótulo, identificador e posição no log.

## `notas/publicacao.py`

Publicação do acervo, com escrita atrás de interface injetável e conferência de deriva.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `EXTENSAO_DAS_NOTAS` | `str` | `'*.md'` |

### `DocumentoDeNota`

*DTO imutável* — Par imutável de caminho relativo e conteúdo pronto para gravação.

**Campos:** `caminho_relativo: str`, `conteudo: str`

### `EscritorDeAcervo` (ABC)

*contrato* — Contrato de leitura e gravação do diretório do acervo.

- `escrever(documento: DocumentoDeNota) -> None` `[abstract]` — Grava um documento, criando o diretório se preciso.
- `ler(caminho_relativo: str) -> str | None` `[abstract]` — Conteúdo atual do documento, ou None quando ele não existe.
- `listar_existentes() -> tuple[str, ...]` `[abstract]` — Documentos Markdown presentes no acervo, em ordem estável.
- `remover(caminho_relativo: str) -> None` `[abstract]` — Apaga um documento que deixou de ser gerado.

### `EscritorDeAcervoEmDisco` (EscritorDeAcervo)

*serviço* — Adaptador concreto sobre um diretório do sistema de arquivos.

- `escrever(documento: DocumentoDeNota) -> None` — Grava em UTF-8 com quebras de linha normalizadas.
- `ler(caminho_relativo: str) -> str | None` — Lê o arquivo, se existir.
- `listar_existentes() -> tuple[str, ...]` — Os arquivos Markdown na raiz do acervo.
- `remover(caminho_relativo: str) -> None` — Apaga o arquivo, se ainda existir.

### `EscritorDeAcervoEmMemoria` (EscritorDeAcervo)

*serviço* — Escritor determinístico que guarda os documentos num dicionário, para testes.

- `escrever(documento: DocumentoDeNota) -> None` — Guarda o conteúdo em memória.
- `ler(caminho_relativo: str) -> str | None` — Conteúdo guardado, ou None.
- `listar_existentes() -> tuple[str, ...]` — Os caminhos guardados, em ordem estável.
- `remover(caminho_relativo: str) -> None` — Registra e aplica a remoção.

### `GeradorDeAcervo`

*serviço* — Renderiza as notas e publica ou confere o diretório do acervo.

- `montar_documentos(notas: Sequence[NotaDeAprendizado]) -> tuple[DocumentoDeNota, ...]` — Consulta pura: o índice e uma nota por aprendizado, sem gravar nada.
- `publicar(notas: Sequence[NotaDeAprendizado]) -> ResultadoDoAcervo` — Comando: grava os documentos e remove o que sobrou de gerações anteriores.
- `conferir(notas: Sequence[NotaDeAprendizado]) -> tuple[str, ...]` — Consulta pura: os documentos que divergem, faltam ou sobram no acervo.

### `ResultadoDoAcervo`

*DTO imutável* — Resumo do que a publicação produziu, para relato na linha de comando.

**Campos:** `documentos_escritos: int`, `documentos_removidos: tuple[str, ...]`

## `notas/renderizador.py`

Renderização das notas em Markdown, no formato "afirmação, como se sabe, como aplicar".

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `AVISO_DE_GERACAO` | `str` | `'> Nota gerada a partir do grafo por `graphow notas-gerar`. Não edite à…` |
| `NOME_DO_INDICE` | `str` | `'INDEX.md'` |
| `TITULO_DO_INDICE` | `str` | `'# Acervo de aprendizados'` |
| `ALCANCE_GLOBAL_NO_INDICE` | `str` | `'global'` |

### Funções do módulo

- `renderizar_nota(nota: NotaDeAprendizado) -> str` — Uma nota inteira: afirmação, como se sabe, como aplicar e os avisos.
- `renderizar_indice(notas: Sequence[NotaDeAprendizado]) -> str` — O índice do acervo: as notas por alcance, com as substituídas marcadas.

