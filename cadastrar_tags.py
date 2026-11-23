#!/usr/bin/env python3
"""Cadastra moradores (quadra/casa) e tags UHF numa Control iD (iDUHF) via API REST.

CSV de entrada (cabecalho obrigatorio): quadra,casa,tag
  - tag = numero DECIMAL da tag; vira cards.value = facility*2^32 + numero (ver conv())
  - varias tags na mesma quadra/casa reutilizam o mesmo usuario

Credenciais so por variavel de ambiente (nada de senha em arquivo ou argumento):
  export CID_USER=...   export CID_PASS=...
  python3 cadastrar_tags.py tags.csv --host IP_DO_EQUIPAMENTO            # dry-run (padrao)
  python3 cadastrar_tags.py tags.csv --host IP_DO_EQUIPAMENTO --apply    # grava de verdade
  python3 cadastrar_tags.py tags.csv --host IP --apply --limit 5         # teste com 5 linhas
  python3 cadastrar_tags.py x --host IP --consultar existentes.csv       # so le, nao grava

Seguro para rodar de novo: pula usuarios (registration) e tags (value) que ja existem.
"""
import argparse, csv, json, os, sys, urllib.request

BATCH = 50


def conv(d):
    """decimal do leitor (facility*65536 + numero) -> cards.value (facility*2**32 + numero)"""
    return (d >> 16) << 32 | (d & 0xFFFF)


class Api:
    def __init__(self, host):
        self.base = f"http://{host}"
        self.session = None

    def post(self, path, body):
        url = self.base + path
        if self.session:
            url += f"?session={self.session}"
        req = urllib.request.Request(url, json.dumps(body).encode(),
                                     {"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read() or b"{}")

    def login(self, user, pw):
        self.session = None
        self.session = self.post("/login.fcgi", {"login": user, "password": pw})["session"]

    def load(self, obj):
        return self.post("/load_objects.fcgi", {"object": obj}).get(obj, [])

    def create(self, obj, values):
        return self.post("/create_objects.fcgi", {"object": obj, "values": values}).get("ids", [])


def chunks(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


def read_csv(path, limit):
    rows, erros, vistas = [], [], {}
    with open(path, newline="", encoding="utf-8-sig") as f:
        for n, r in enumerate(csv.DictReader(f), start=2):
            q, c, t = (r.get("quadra") or "").strip(), (r.get("casa") or "").strip(), (r.get("tag") or "").strip()
            if not (q and c and t):
                erros.append(f"linha {n}: campo vazio"); continue
            if not t.isdigit():
                erros.append(f"linha {n}: tag '{t}' nao e decimal"); continue
            if int(t) in vistas:
                erros.append(f"linha {n}: tag {t} duplicada (ja na linha {vistas[int(t)]})"); continue
            vistas[int(t)] = n
            rows.append((q, c, conv(int(t))))
            if limit and len(rows) >= limit:
                break
    return rows, erros


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("--host", required=True, help="IP do equipamento")
    ap.add_argument("--apply", action="store_true", help="grava no equipamento (sem isso e dry-run)")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--consultar", metavar="SAIDA.csv",
                    help="SOMENTE LEITURA: exporta usuarios e tags ja cadastrados e sai")
    a = ap.parse_args()

    user, pw = os.environ.get("CID_USER"), os.environ.get("CID_PASS")
    if not (user and pw):
        sys.exit("Defina CID_USER e CID_PASS no ambiente.")

    if a.consultar:
        api = Api(a.host)
        api.login(user, pw)
        us = {u["id"]: u for u in api.load("users")}
        with open(a.consultar, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["matricula", "nome", "tag_decimal"])
            for c in api.load("cards"):
                u = us.get(c["user_id"], {})
                w.writerow([u.get("registration", ""), u.get("name", ""), c["value"]])
        print(f"{len(us)} usuarios, exportado em {a.consultar}")
        return

    rows, erros = read_csv(a.csv, a.limit)
    reg = lambda q, c: q.lower() + c        # mesma convencao do gerar_zip_importacao.py
    moradores = {}
    for q, c, t in rows:
        moradores.setdefault(reg(q, c), []).append(t)

    api = Api(a.host)
    api.login(user, pw)
    users_exist = {u["registration"]: u["id"] for u in api.load("users")}
    cards_exist = {c["value"]: c["user_id"] for c in api.load("cards")}

    novos_users = [r for r in moradores if r not in users_exist]
    novas_tags = [(r, t) for r, ts in moradores.items() for t in ts if t not in cards_exist]
    print(f"CSV: {len(rows)} tags, {len(moradores)} moradores | ja no equipamento: "
          f"{len(users_exist)} usuarios, {len(cards_exist)} cartoes")
    print(f"A criar: {len(novos_users)} usuarios, {len(novas_tags)} tags "
          f"({'APLICANDO' if a.apply else 'DRY-RUN, nada sera gravado'})")

    falhas = []
    if a.apply:
        for lote in chunks(novos_users, BATCH):
            try:
                ids = api.create("users", [{"registration": r, "name": f"Q{r[0].upper()}C{r[1:]}"} for r in lote])
                users_exist.update(dict(zip(lote, ids)))
            except Exception as e:
                falhas += [f"usuario {r}: {e}" for r in lote]
        for lote in chunks([x for x in novas_tags if x[0] in users_exist], BATCH):
            try:
                api.create("cards", [{"value": t, "user_id": users_exist[r]} for r, t in lote])
            except Exception as e:
                falhas += [f"tag {t} ({r}): {e}" for r, t in lote]
        cards_final = {c["value"] for c in api.load("cards")}
        faltam = [t for _, ts in moradores.items() for t in ts if t not in cards_final]
        print(f"Conferencia: {len(faltam)} tags do CSV nao estao no equipamento {faltam[:10]}")

    for e in erros + falhas:
        print("ERRO:", e)
    sys.exit(1 if (erros or falhas) else 0)


if __name__ == "__main__":
    main()
