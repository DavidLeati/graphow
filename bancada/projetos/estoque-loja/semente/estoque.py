"""Controle de estoque da Ferragem Silva (versao do Joao, 2023).

Uso:
    python estoque.py cadastrar <codigo> <nome> <preco> [minimo]
    python estoque.py entrada <codigo> <qtd>
    python estoque.py pedido <codigo>:<qtd> [<codigo>:<qtd> ...]
    python estoque.py listar
    python estoque.py total
"""
import os
import sys
from datetime import datetime

PASTA = os.path.dirname(os.path.abspath(__file__))
ARQUIVO = os.environ.get("ESTOQUE_CSV", os.path.join(PASTA, "estoque.csv"))
LOG = os.environ.get("ESTOQUE_LOG", os.path.join(PASTA, "movimentos.log"))

estoque = {}


def carregar():
    estoque.clear()
    if not os.path.exists(ARQUIVO):
        return
    with open(ARQUIVO, encoding="utf-8") as f:
        for linha in f.readlines()[1:]:
            partes = linha.strip().split(",")
            if len(partes) < 4:
                continue
            codigo, nome, qtd, preco = partes[0], partes[1], partes[2], partes[3]
            minimo = partes[4] if len(partes) > 4 else "0"
            estoque[codigo] = {
                "nome": nome,
                "qtd": int(qtd),
                "preco": float(preco),
                "minimo": int(minimo),
            }


def salvar():
    with open(ARQUIVO, "w", encoding="utf-8") as f:
        f.write("codigo,nome,qtd,preco,minimo\n")
        for codigo, p in estoque.items():
            f.write(f"{codigo},{p['nome']},{p['qtd']},{p['preco']},{p['minimo']}\n")


def registrar(tipo, codigo, qtd):
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(f"{datetime.now().isoformat()};{tipo};{codigo};{qtd}\n")


def cadastrar(codigo, nome, preco, minimo=0):
    if codigo in estoque:
        print("Produto ja existe")
        return False
    estoque[codigo] = {"nome": nome, "qtd": 0, "preco": float(preco), "minimo": int(minimo)}
    registrar("cadastro", codigo, 0)
    return True


def entrada(codigo, qtd):
    if codigo not in estoque:
        print("Produto nao encontrado:", codigo)
        return False
    estoque[codigo]["qtd"] += int(qtd)
    registrar("entrada", codigo, qtd)
    return True


def pedido(itens):
    """Baixa um pedido de venda. itens = lista de (codigo, qtd)."""
    # confere se tem tudo antes de baixar
    for codigo, qtd in itens:
        if codigo not in estoque:
            print("Produto nao encontrado:", codigo)
            return False
        if estoque[codigo]["qtd"] < int(qtd):
            print("Estoque insuficiente para", codigo)
            return False
    for codigo, qtd in itens:
        estoque[codigo]["qtd"] -= int(qtd)
        registrar("saida", codigo, qtd)
    return True


def valor_total():
    total = 0
    for p in estoque.values():
        total += p["qtd"] * p["preco"]
    return total


def listar():
    for codigo, p in sorted(estoque.items()):
        print(codigo, "-", p["nome"], "-", p["qtd"], "un - R$", p["preco"])


def main(args):
    carregar()
    if not args:
        print(__doc__)
        return
    cmd = args[0]
    if cmd == "cadastrar":
        minimo = args[4] if len(args) > 4 else 0
        if cadastrar(args[1], args[2], args[3], minimo):
            salvar()
    elif cmd == "entrada":
        if entrada(args[1], args[2]):
            salvar()
    elif cmd == "pedido":
        itens = [tuple(a.split(":")) for a in args[1:]]
        if pedido(itens):
            salvar()
            print("Pedido baixado")
    elif cmd == "listar":
        listar()
    elif cmd == "total":
        print("Valor total do estoque: R$", valor_total())
    else:
        print("Comando desconhecido:", cmd)


if __name__ == "__main__":
    main(sys.argv[1:])
