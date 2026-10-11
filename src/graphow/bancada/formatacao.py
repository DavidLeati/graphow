"""Números da bancada como o relatório do laboratório os escreve: vírgula decimal e ponto de milhar."""

TOKENS_POR_MILHAO: float = 1_000_000.0
SEM_VALOR: str = "-"


def formatar_dinheiro(valor: float | None) -> str:
    """`US$ 5,03`."""
    return SEM_VALOR if valor is None else f"US$ {_decimal(valor, 2)}"


def formatar_tokens(valor: int | None) -> str:
    """`6,2 M`, a forma do relatório."""
    return SEM_VALOR if valor is None else f"{_decimal(valor / TOKENS_POR_MILHAO, 1)} M"


def formatar_inteiro(valor: int | None) -> str:
    """`6.160.643`."""
    return SEM_VALOR if valor is None else f"{valor:,}".replace(",", ".")


def formatar_minutos(valor: float | None) -> str:
    """`20,0 min`."""
    return SEM_VALOR if valor is None else f"{_decimal(valor, 1)} min"


def formatar_variacao(valor: float | None, base: float | None) -> str:
    """A variação em relação à base: percentual, ou a diferença absoluta quando a base é zero."""
    if valor is None or base is None:
        return SEM_VALOR
    if base == 0:
        return f"{_com_sinal(valor - base, 0)} (base 0)"
    return f"{_com_sinal(100.0 * (valor - base) / base, 0)}%"


def _com_sinal(valor: float, casas: int) -> str:
    """O número com sinal explícito e vírgula decimal; o que arredonda para zero sai `+0`."""
    arredondado = round(valor, casas)
    texto = _decimal(abs(arredondado), casas)
    return f"+{texto}" if arredondado >= 0 else f"-{texto}"


def _decimal(valor: float, casas: int) -> str:
    """Vírgula decimal, ponto de milhar."""
    return f"{valor:,.{casas}f}".replace(",", "_").replace(".", ",").replace("_", ".")
