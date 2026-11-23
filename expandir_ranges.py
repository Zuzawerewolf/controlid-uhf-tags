#!/usr/bin/env python3
"""Expande ranges de tags (cartelas) e atribui as tags as unidades, na ordem, gerando o CSV
quadra,casa,tag usado pelos outros scripts.

ranges.txt : uma cartela por linha, "inicio fim" (decimal; pode estar crescente ou decrescente).
             A tag e atribuida na ordem em que aparece (inicio -> fim). Linhas com # sao ignoradas.
unidades   : CSV quadra,casa na ordem de entrega (uma linha por unidade).
--pular    : unidades que ja tem tag (ex.: --pular F17 O13); nao recebem tag do range.
             --reservadas : tags que ja existem no equipamento; falha se aparecerem nos ranges.

  python3 expandir_ranges.py ranges.txt unidades.csv -o tags.csv --pular F17 O13
"""
import argparse, csv, sys


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("ranges"); ap.add_argument("unidades")
    ap.add_argument("-o", "--saida", required=True)
    ap.add_argument("--pular", nargs="*", default=[], help="unidades ja atendidas, ex.: F17 O13")
    ap.add_argument("--reservadas", nargs="*", type=int, default=[])
    a = ap.parse_args()

    tags, n = [], 0
    for l in open(a.ranges, encoding="utf-8"):
        l = l.split("#")[0].split()
        if not l:
            continue
        n += 1
        i, f = int(l[0]), int(l[1])
        passo = -1 if f < i else 1
        faixa = list(range(i, f + passo, passo))
        print(f"cartela {n}: {i} -> {f}  ({len(faixa)} tags)")
        tags += faixa
    if len(tags) != len(set(tags)):
        sys.exit("ERRO: tag repetida entre os ranges")
    if set(tags) & set(a.reservadas):
        sys.exit(f"ERRO: ranges contem tags ja cadastradas: {sorted(set(tags) & set(a.reservadas))}")

    pular = {p.upper() for p in a.pular}
    un = [(r["quadra"].strip(), r["casa"].strip()) for r in csv.DictReader(open(a.unidades, encoding="utf-8-sig"))]
    alvo = [u for u in un if (u[0] + u[1]).upper() not in pular]
    print(f"\n{len(tags)} tags, {len(alvo)} unidades a atender ({len(un)} no total, {len(un)-len(alvo)} puladas)")
    if len(tags) < len(alvo):
        print(f"FALTAM {len(alvo)-len(tags)} tags; sem tag: {[''.join(u) for u in alvo[len(tags):]]}")
    if len(tags) > len(alvo):
        print(f"SOBRAM {len(tags)-len(alvo)} tags")
    with open(a.saida, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["quadra", "casa", "tag"])
        for (q, c), t in zip(alvo, tags):
            w.writerow([q, c, t])
    print("->", a.saida)


if __name__ == "__main__":
    main()
