"""Distinção entre o cliente HTTP ter ido embora e o servidor ter falhado."""


def eh_desconexao_do_cliente(erro: BaseException | None) -> bool:
    """Indica se a exceção é o cliente tendo ido embora, e não uma falha do servidor.

    As três variantes existem porque o sistema operacional escolhe qual levantar:
    Windows aborta (10053), Unix costuma resetar ou quebrar o cano. Tratar só as
    que aparecem na máquina de quem escreveu o código é como o traceback do SSE
    sobreviveu — o `except` já existia, faltava o irmão do Windows.
    """
    return isinstance(erro, ConnectionError)
