#!/usr/bin/env python3
"""Gera um users.zip de IMPORTACAO para equipamentos Control iD (linha iDUHF/iDAccess)
a partir de um users.zip EXPORTADO do proprio equipamento + um CSV quadra,casa,tag.

Por que partir do export: o formato interno (secoes cid_metadata/cid_data) e a validacao
do equipamento nao sao documentados; o export do SEU aparelho (mesmo firmware) e o unico
molde confiavel. O script so acrescenta linhas nas secoes `users` e `cards`.

Uso:
  python3 gerar_zip_importacao.py export/users.zip tags.csv -o saida/users.zip
  python3 gerar_zip_importacao.py export/users.zip tags.csv -o saida/users.zip --limit 1   # zip de teste

CSV (cabecalho obrigatorio): quadra,casa,tag     (tag = decimal impresso/lido da tag)
Convencao: matricula = quadra+casa em minusculas (a01), nome = QAC01. Ajuste em unidade().
"""
import argparse, csv, sys, zipfile


def conv(d):
    """decimal do leitor (facility*65536 + numero) -> cards.value (facility*2**32 + numero)"""
    return (d >> 16) << 32 | (d & 0xFFFF)


def unidade(q, c):
    return q.lower() + c, f"Q{q.upper()}C{c}"          # (matricula, nome)


def secao(txt, nome):
    """(inicio, fim) das linhas de dados da secao dentro de cid_data"""
    base = txt.index("\ncid_data\n")
    i = txt.index(f"\n{nome}\n", base) + len(nome) + 2
    j = txt.find("\n\n", i)
    return i, (len(txt) if j < 0 else j)


def linhas(txt, nome):
    i, j = secao(txt, nome)
    return txt[i:j].split("\n")[1:]                     # sem o cabecalho de colunas


def inserir(txt, nome, novas):
    i, j = secao(txt, nome)
    return txt[:j] + "".join("\n" + n for n in novas) + txt[j:]


def ler_csv(path, limit):
    rows, vistas = [], set()
    with open(path, newline="", encoding="utf-8-sig") as f:
        for n, r in enumerate(csv.DictReader(f), start=2):
            q, c, t = [(r.get(k) or "").strip() for k in ("quadra", "casa", "tag")]
            if not (q and c and t.isdigit()):
                sys.exit(f"linha {n}: precisa de quadra, casa e tag decimal")
            if t in vistas:
                sys.exit(f"linha {n}: tag {t} duplicada no CSV")
            vistas.add(t); rows.append((q, c, int(t)))
            if limit and len(rows) >= limit:
                break
    return rows


def escrever_zip(path, csv_bytes, ref):
    """zip identico ao do equipamento: sem compressao, versao 1.0, origem DOS, sem atributos"""
    dt = ref.infolist()[0].date_time
    with zipfile.ZipFile(path, "w", zipfile.ZIP_STORED) as z:
        for nome, dados, attr in (("users.csv", csv_bytes, 0), ("user_images/", b"", 0x10)):
            zi = zipfile.ZipInfo(nome, dt)
            zi.compress_type, zi.create_system, zi.external_attr = zipfile.ZIP_STORED, 0, attr
            z.writestr(zi, dados)
    d = bytearray(open(path, "rb").read())              # o Python grava versao 2.0 e perms Unix
    q = 0
    while (q := d.find(b"PK\x03\x04", q)) >= 0:
        d[q + 4] = 0x0A; q += 4
    q = n = 0
    while (q := d.find(b"PK\x01\x02", q)) >= 0:
        d[q + 6] = 0x0A
        if n == 0:
            d[q + 38:q + 42] = b"\0\0\0\0"
        n += 1; q += 4
    open(path, "wb").write(d)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("export_zip"); ap.add_argument("csv")
    ap.add_argument("-o", "--saida", required=True)
    ap.add_argument("--limit", type=int, default=0, help="so as N primeiras linhas (zip de teste)")
    ap.add_argument("--valor-direto", action="store_true",
                    help="grava a tag como esta no CSV, sem a conversao facility*2^32+numero")
    a = ap.parse_args()

    ref = zipfile.ZipFile(a.export_zip)
    txt = ref.read("users.csv").decode("utf-8").replace("\r\n", "\n")
    regs = {l.split(",")[1] for l in linhas(txt, "users") if l}
    cards = {int(l.split(",")[1]) for l in linhas(txt, "cards") if l}
    uid = max(int(l.split(",")[0]) for l in linhas(txt, "users") if l) + 1
    cid = max([int(l.split(",")[0]) for l in linhas(txt, "cards") if l] or [0]) + 1

    novos, novos_cards, pulados = [], [], []
    ids = {}
    for q, c, t in ler_csv(a.csv, a.limit):
        reg, nome = unidade(q, c)
        if reg not in regs and reg not in ids:
            ids[reg] = uid
            novos.append(f"{uid},{reg},{nome},,,,,,,0,0,"); uid += 1
        v = t if a.valor_direto else conv(t)
        if v in cards or reg in regs:                   # ja existe: nao duplica
            pulados.append((reg, t)); continue
        cards.add(v)
        novos_cards.append(f"{cid},{v},{ids[reg]},"); cid += 1

    saida = inserir(inserir(txt, "users", novos), "cards", novos_cards)
    escrever_zip(a.saida, saida.replace("\n", "\r\n").encode("utf-8"), ref)
    print(f"{len(novos)} usuarios e {len(novos_cards)} cartoes novos -> {a.saida}")
    if pulados:
        print(f"{len(pulados)} linhas puladas (matricula ou cartao ja no equipamento): {pulados[:5]}")


if __name__ == "__main__":
    main()
