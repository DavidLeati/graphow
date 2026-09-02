# Setor 14 — Geração deste Catálogo

> Documento gerado a partir do código por `graphow docs-gerar`.
> Não edite à mão: a próxima geração sobrescreve. Para mudar o texto de missão
> da ala, edite `DEFINICOES_DE_SETOR` em `src/graphow/documentacao/setores.py`.

**Pacote:** `graphow.documentacao`

Extrai o catálogo do próprio código e renderiza o índice e os dossiês. Existe para que a documentação não seja mantida à mão.

## Inventário

9 módulos · 1290 linhas · 27 classes

| Módulo | Linhas | Papel |
| :--- | ---: | :--- |
| [`documentacao/__init__.py`](#documentacaoinit) | 58 | Geração do catálogo de documentação a partir do próprio código-fonte. |
| [`documentacao/extrator.py`](#documentacaoextrator) | 155 | Extração do catálogo de código a partir da árvore sintática dos módulos. |
| [`documentacao/leitura_fonte.py`](#documentacaoleiturafonte) | 89 | Acesso ao código-fonte do repositório, atrás de interface injetável. |
| [`documentacao/modelo.py`](#documentacaomodelo) | 170 | Modelos imutáveis do catálogo de código extraído do repositório. |
| [`documentacao/publicacao.py`](#documentacaopublicacao) | 141 | Publicação dos documentos gerados, com escrita atrás de interface injetável. |
| [`documentacao/renderizador_indice.py`](#documentacaorenderizadorindice) | 141 | Renderização do índice de navegação da biblioteca de documentação. |
| [`documentacao/renderizador_setor.py`](#documentacaorenderizadorsetor) | 128 | Renderização do dossiê Markdown de uma ala temática. |
| [`documentacao/setores.py`](#documentacaosetores) | 155 | Definição das alas temáticas da biblioteca e montagem do catálogo. |
| [`documentacao/verificacao_guias.py`](#documentacaoverificacaoguias) | 253 | Confere os exemplos de linha de comando dos guias contra o parser real. |

## `documentacao/__init__.py`

Geração do catálogo de documentação a partir do próprio código-fonte.

### `MontadorDocumentacaoDoRepositorio`

*serviço* — Compõe leitura, extração e renderização para um repositório em disco.

- `montar_catalogo() -> CatalogoRepositorio` — Consulta o código e devolve o catálogo, sem escrever nada.
- `montar_documentos() -> tuple[DocumentoGerado, ...]` — Renderiza os documentos em memória, para comparação de deriva.
- `publicar() -> ResultadoPublicacao` — Comando: grava o índice e os dossiês em `docs/`.

## `documentacao/extrator.py`

Extração do catálogo de código a partir da árvore sintática dos módulos.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `PARAMETROS_IMPLICITOS` | `frozenset[str]` | `frozenset({'self', 'cls'})` |
| `ANOTACAO_AUSENTE` | `str` | `'sem anotacao'` |
| `BASE_ABSTRATA` | `str` | `'ABC'` |
| `LIMITE_DE_VALOR_EXIBIDO` | `int` | `72` |
| `TIPOS_DE_FUNCAO` | `tuple[type[ast.AST], ...]` | `(ast.FunctionDef, ast.AsyncFunctionDef)` |

### `ExtratorCatalogo`

*serviço* — Traduz arquivos-fonte em registros de catálogo, sem tocar em disco.

- `extrair_modulo(arquivo: ArquivoFonte) -> ModuloDocumentado` — Analisa um módulo e devolve tudo que ele expõe.

## `documentacao/leitura_fonte.py`

Acesso ao código-fonte do repositório, atrás de interface injetável.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `ARQUIVO_DE_PACOTE` | `str` | `'__init__.py'` |

### `ArquivoFonte`

*DTO imutável* — Conteúdo de um módulo Python junto do caminho pelo qual ele é referenciado.

**Campos:** `caminho_relativo: str`, `conteudo: str`

- `nome_modulo() -> str` `[property]` — Caminho de importação do módulo, derivado do caminho no disco.
- `total_linhas() -> int` `[property]` — Quantidade de linhas do arquivo.

### `LeitorCodigoFonte` (ABC)

*contrato* — Contrato de leitura dos módulos de um pacote do projeto.

- `listar_pacotes() -> tuple[str, ...]` `[abstract]` — Enumera os pacotes de primeiro nível sob a raiz do código.
- `ler_modulos(pacote: str) -> tuple[ArquivoFonte, ...]` `[abstract]` — Lê todos os módulos de um pacote, em ordem estável.

### `LeitorCodigoFonteEmDisco` (LeitorCodigoFonte)

*serviço* — Adaptador concreto sobre o sistema de arquivos do repositório.

- `listar_pacotes() -> tuple[str, ...]` — Enumera os diretórios que contêm um __init__.py.
- `ler_modulos(pacote: str) -> tuple[ArquivoFonte, ...]` — Lê os módulos do pacote ordenados por caminho, para saída determinística.

### `LeitorCodigoFonteEmMemoria` (LeitorCodigoFonte)

*serviço* — Leitor determinístico alimentado por um dicionário, para testes.

- `listar_pacotes() -> tuple[str, ...]` — Enumera os pacotes fornecidos na construção.
- `ler_modulos(pacote: str) -> tuple[ArquivoFonte, ...]` — Devolve os módulos do pacote informado.

## `documentacao/modelo.py`

Modelos imutáveis do catálogo de código extraído do repositório.

### `CatalogoRepositorio`

*DTO imutável* — Catálogo completo, pronto para renderização.

**Campos:** `setores: tuple[SetorDocumentado, ...]`

- `total_modulos() -> int` `[property]` — Quantidade de módulos Python catalogados.
- `total_linhas() -> int` `[property]` — Total de linhas de código catalogadas.
- `total_classes() -> int` `[property]` — Total de classes catalogadas.

### `ClasseDocumentada`

*DTO imutável* — Classe com suas bases, atributos de dados e métodos públicos.

**Campos:** `nome: str`, `bases: tuple[str, ...]`, `resumo: str`, `metodos: tuple[FuncaoDocumentada, ...]`, `campos: tuple[ParametroDocumentado, ...]`, `eh_imutavel: bool`, `eh_abstrata: bool`

- `metodos_publicos() -> tuple[FuncaoDocumentada, ...]` `[property]` — Métodos que compõem o contrato externo da classe.
- `natureza() -> str` `[property]` — Classificação curta da classe, para leitura de relance.

### `ConstanteDocumentada`

*DTO imutável* — Constante de módulo com tipo e valor declarados.

**Campos:** `nome: str`, `anotacao: str`, `valor: str`

### `FuncaoDocumentada`

*DTO imutável* — Função ou método com assinatura tipada e resumo da docstring.

**Campos:** `nome: str`, `parametros: tuple[ParametroDocumentado, ...]`, `retorno: str`, `resumo: str`, `linhas: int`, `eh_publica: bool`, `eh_propriedade: bool`, `eh_abstrata: bool`

- `formatar_assinatura() -> str` — Assinatura completa em uma linha, pronta para o catálogo.
- `marcadores() -> tuple[str, ...]` `[property]` — Rótulos curtos que qualificam a função no catálogo.

### `ModuloDocumentado`

*DTO imutável* — Um arquivo Python do pacote, com tudo que ele expõe.

**Campos:** `caminho_relativo: str`, `nome_modulo: str`, `resumo: str`, `linhas: int`, `classes: tuple[ClasseDocumentada, ...]`, `funcoes: tuple[FuncaoDocumentada, ...]`, `constantes: tuple[ConstanteDocumentada, ...]`

- `funcoes_publicas() -> tuple[FuncaoDocumentada, ...]` `[property]` — Funções de módulo que fazem parte da superfície pública.
- `esta_vazio() -> bool` `[property]` — Um módulo sem classes, funções ou constantes não rende dossiê.

### `ParametroDocumentado`

*DTO imutável* — Parâmetro de uma função, com o tipo declarado na assinatura.

**Campos:** `nome: str`, `anotacao: str`

- `formatar() -> str` — Representação textual do parâmetro na assinatura.

### `SetorDocumentado`

*DTO imutável* — Uma ala temática da biblioteca, correspondente a um pacote do código.

**Campos:** `numero: int`, `identificador: str`, `titulo: str`, `missao: str`, `modulos: tuple[ModuloDocumentado, ...]`

- `nome_arquivo() -> str` `[property]` — Nome do dossiê deste setor dentro de docs/setores/.
- `total_linhas() -> int` `[property]` — Soma das linhas de todos os módulos do setor.
- `total_classes() -> int` `[property]` — Quantidade de classes catalogadas no setor.
- `modulos_com_conteudo() -> tuple[ModuloDocumentado, ...]` `[property]` — Módulos que têm algo a documentar.

### Funções do módulo

- `resumir_docstring(docstring: str | None) -> str` — Extrai a primeira frase da docstring, que é o resumo canônico do elemento.
- `ordenar_por_nome(elementos: Sequence[ClasseDocumentada]) -> tuple[ClasseDocumentada, ...]` — Ordena classes por nome, para o catálogo sair estável entre execuções.

## `documentacao/publicacao.py`

Publicação dos documentos gerados, com escrita atrás de interface injetável.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `NOME_ARQUIVO_INDICE` | `str` | `'INDEX.md'` |
| `NOME_DIRETORIO_SETORES` | `str` | `'setores'` |

### `DocumentoGerado`

*DTO imutável* — Par imutável de caminho relativo e conteúdo pronto para gravação.

**Campos:** `caminho_relativo: str`, `conteudo: str`

### `EscritorDocumentacao` (ABC)

*contrato* — Contrato de gravação dos documentos gerados.

- `escrever(documento: DocumentoGerado) -> None` `[abstract]` — Grava um documento, criando os diretórios necessários.
- `listar_dossies_existentes() -> tuple[str, ...]` `[abstract]` — Enumera os dossiês já presentes no destino.
- `remover(caminho_relativo: str) -> None` `[abstract]` — Apaga um documento que deixou de ser gerado.

### `EscritorDocumentacaoEmDisco` (EscritorDocumentacao)

*serviço* — Adaptador concreto que grava sob o diretório `docs/`.

- `escrever(documento: DocumentoGerado) -> None` — Grava o documento em UTF-8 com quebras de linha normalizadas.
- `listar_dossies_existentes() -> tuple[str, ...]` — Lista os arquivos Markdown presentes no diretório de setores.
- `remover(caminho_relativo: str) -> None` — Apaga o arquivo, se ele ainda existir.

### `EscritorDocumentacaoEmMemoria` (EscritorDocumentacao)

*serviço* — Escritor determinístico que acumula os documentos, para testes.

- `escrever(documento: DocumentoGerado) -> None` — Acumula o conteúdo em memória.
- `listar_dossies_existentes() -> tuple[str, ...]` — Devolve os dossiês declarados na construção.
- `remover(caminho_relativo: str) -> None` — Registra a remoção solicitada.

### `GeradorDocumentacao`

*serviço* — Renderiza o catálogo e publica os documentos resultantes.

- `montar_documentos(catalogo: CatalogoRepositorio) -> tuple[DocumentoGerado, ...]` — Consulta pura: renderiza índice e dossiês sem gravar nada.
- `publicar(catalogo: CatalogoRepositorio) -> ResultadoPublicacao` — Comando: grava os documentos e remove dossiês de alas extintas.

### `ResultadoPublicacao`

*DTO imutável* — Resumo do que a geração produziu, para relato na linha de comando.

**Campos:** `documentos_escritos: int`, `documentos_removidos: tuple[str, ...]`, `bytes_totais: int`

## `documentacao/renderizador_indice.py`

Renderização do índice de navegação da biblioteca de documentação.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `PILARES` | `tuple[tuple[str, str], ...]` | `(('O Log é a Verdade', 'Event store append-only. O grafo é uma dobra de…` |
| `ROTEAMENTO_POR_INTENCAO` | `tuple[tuple[str, str], ...]` | `(('Entender o vocabulário do domínio', 'Setor 01 — `graphow.core`'), ('…` |
| `REGRAS_DE_ENGENHARIA` | `tuple[tuple[str, str], ...]` | `(('Linhas por arquivo', 'no máximo 400'), ('Linhas por função', 'no máx…` |

### `RenderizadorIndice`

*serviço* — Converte o catálogo no mapa de navegação da biblioteca.

- `renderizar(catalogo: CatalogoRepositorio) -> str` — Monta o índice completo em Markdown.

## `documentacao/renderizador_setor.py`

Renderização do dossiê Markdown de uma ala temática.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `AVISO_DE_GERACAO` | `str` | `'> Documento gerado a partir do código por `graphow docs-gerar`.\n> Não…` |

### `RenderizadorSetor`

*serviço* — Converte um setor catalogado no seu dossiê Markdown.

- `renderizar(setor: SetorDocumentado) -> str` — Monta o dossiê completo do setor.

## `documentacao/setores.py`

Definição das alas temáticas da biblioteca e montagem do catálogo.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `DEFINICOES_DE_SETOR` | `tuple[DefinicaoSetor, ...]` | `(DefinicaoSetor(1, 'core', 'Núcleo Ontológico', 'Vocabulário da ontolog…` |

### `DefinicaoSetor`

*DTO imutável* — Metadados curados de uma ala: o que ela é e por que existe.

**Campos:** `numero: int`, `pacote: str`, `titulo: str`, `missao: str`

### `MontadorCatalogo`

*serviço* — Monta o catálogo completo a partir do código-fonte lido.

- `montar() -> CatalogoRepositorio` — Consulta pura: percorre as definições e devolve o catálogo montado.

## `documentacao/verificacao_guias.py`

Confere os exemplos de linha de comando dos guias contra o parser real.

| Constante | Tipo | Valor |
| :--- | :--- | :--- |
| `PADRAO_INVOCACAO_CLI` | `re.Pattern[str]` | `re.compile('^\\s*(?:\\$\\s*)?graphow\\s+(?P<argumentos>\\S.*)$')` |
| `PADRAO_INVOCACAO_STDIO` | `re.Pattern[str]` | `re.compile('^\\s*(?:\\$\\s*)?(?:python|py)\\s+-m\\s+graphow\\.mcp\\.std…` |
| `PADRAO_ARGS_JSON` | `re.Pattern[str]` | `re.compile('"args"\\s*:\\s*(?P<lista>\\[[^\\]]*\\])', re.DOTALL)` |
| `PADRAO_COMANDO_JSON` | `re.Pattern[str]` | `re.compile('"command"\\s*:\\s*"(?P<comando>(?:[^"\\\\]|\\\\.)*)"')` |
| `PADRAO_VARIAVEL_DE_AMBIENTE` | `re.Pattern[str]` | `re.compile('\\$\\{?\\w+\\}?|%\\w+%')` |
| `MODULO_STDIO` | `str` | `'graphow.mcp.stdio_server'` |
| `EXTENSOES_DE_GUIA` | `tuple[str, ...]` | `('*.md', '*.json')` |

### `AlvoDeParser` (str, Enum)

*serviço* — Qual analisador de argumentos valida a invocação encontrada.

### `InvocacaoDocumentada`

*DTO imutável* — Uma chamada de linha de comando encontrada em um guia.

**Campos:** `arquivo: str`, `linha: int`, `alvo: AlvoDeParser`, `argumentos: tuple[str, ...]`

- `descrever() -> str` — Texto legível da invocação, para a mensagem de falha.

### `ProblemaEmGuia`

*DTO imutável* — Invocação documentada que o parser real recusaria.

**Campos:** `arquivo: str`, `linha: int`, `invocacao: str`, `motivo: str`

- `descrever() -> str` — Linha de relatório apontando arquivo, posição e causa.

### `VerificadorDeGuias`

*serviço* — Percorre os guias do repositório e valida cada exemplo executável.

- `listar_guias() -> tuple[Path, ...]` — Enumera os documentos que contêm exemplos de linha de comando.
- `verificar() -> tuple[ProblemaEmGuia, ...]` — Consulta pura: devolve todo exemplo que o parser real recusaria.

### Funções do módulo

- `validar_invocacao(invocacao: InvocacaoDocumentada) -> ProblemaEmGuia | None` — Passa a invocação pelo argparse real, capturando a recusa como problema.
- `extrair_invocacoes(caminho: Path, raiz: Path) -> tuple[InvocacaoDocumentada, ...]` — Reúne as invocações em texto e em blocos JSON de configuração do arquivo.
- `validar_ausencia_de_variaveis(invocacao: InvocacaoDocumentada) -> ProblemaEmGuia | None` — Recusa o exemplo que depende de variável que o ambiente não expande.

