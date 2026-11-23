# controlid-uhf-tags

Cadastro em massa de **tags UHF** (e cartões) em controladores de acesso **Control iD**
(testado numa iDUHF), ligando cada tag a uma unidade (quadra/casa), sem digitar uma a uma.

> **Feito com IA, de propósito.** Este repositório nasceu de uma sessão com o Claude Code
> (Anthropic) para resolver uma tarefa chata e repetitiva: cadastrar ~300 tags em um
> condomínio. Não é um software "de produto"; é um método + scripts pequenos que a IA montou,
> o humano revisou e usou. Publicado para que qualquer pessoa (ou IA) refaça sem passar
> pelo mesmo caminho de tentativa e erro. Leia a seção [Estado de validação](#estado-de-validação).

## O que você precisa saber (as descobertas)

1. **O número decimal da tag NÃO é o valor que vai em `cards.value`.**
   O decimal impresso/lido é `facility × 65536 + número` (8 bits + 16 bits).
   A Control iD guarda `facility × 2³² + número`:

   ```
   tag decimal 4000000  →  facility 61, número 2304  →  cards.value = 261993007360
   ```

   A [doc da API](https://controlid.com.br/docs/access-api-en/objects/list-of-objects) descreve
   a mesma conta para cartões "área,código" (`123,45678` → `528281023086`). Como conferir no seu
   aparelho: cadastre uma tag pela interface, exporte e confira se `value = (d>>16)<<32 | (d & 0xFFFF)`.
   Gravar o decimal cru em `cards` **importa sem erro, mas a tag não abre o portão**.

2. **Tags vão em `cards`**, não em `uhf_tags` (que ficou vazia no export de uma iDUHF em uso).
   `cards.value` é único: tag repetida derruba/ignora linhas.

3. **A importação por arquivo é rígida.** O `users.zip` exportado traz `users.csv` (seções
   `cid_metadata` e `cid_data`) e a pasta `user_images/`. A doc diz que não deve ser editado
   à mão e não documenta o formato. O que funcionou: **partir do export do próprio equipamento**
   e só acrescentar linhas em `users` e `cards`, mantendo CRLF, e **reproduzir o zip como o
   equipamento gera**: sem compressão (`stored`), "versão necessária" 1.0, origem DOS, sem
   atributos Unix no arquivo, entrada `user_images/` presente. Um zip comprimido (deflate) com
   atributos Unix, criado por padrão pelo `zipfile`, foi recusado como "arquivo inválido" no
   caso onde isso foi observado (a causa exata não foi isolada; o zip de teste com 1 usuário
   no formato do equipamento importou).

4. **Opções da importação** (tela do equipamento): tipos de usuário (manter atuais / usar do CSV),
   conflito de nome (atualizar mantém o id; ignorar; **sobrescrever** apaga e recria com id novo)
   e usuários ausentes do arquivo (manter / **apagar**, irreversível). Use *manter* nos ausentes.

5. **Não há chave de API.** A API é por sessão: `POST /login.fcgi` com `{"login","password"}`
   devolve `session`, usada como `?session=...` nas demais chamadas (`create_objects.fcgi`,
   `load_objects.fcgi`...). Crie um usuário temporário só para a automação e apague no fim.

## Fluxo recomendado (arquivo, sem rede, o mais seguro)

```bash
# 0. exporte "Somente usuários" no equipamento (gera users.zip) e guarde uma cópia (backup)

# 1. ranges de cartelas + lista de unidades  ->  CSV quadra,casa,tag
python3 expandir_ranges.py exemplos/ranges.txt exemplos/unidades.csv -o tags.csv \
        --pular F17 O13 --reservadas 4140481 3834995     # unidades/tags que já estão no aparelho

# 2. zip de TESTE com 1 usuário/1 tag; importe e passe a tag no leitor
python3 gerar_zip_importacao.py export/users.zip tags.csv -o teste/users.zip --limit 1

# 3. se abriu o portão, gere o zip completo e importe
python3 gerar_zip_importacao.py export/users.zip tags.csv -o completo/users.zip
```

`CSV tags`: cabeçalho `quadra,casa,tag` (veja [`exemplos/`](exemplos)). A matrícula vira `a01` e o
nome `QAC01` (altere em `unidade()` se quiser outro padrão). Linhas cujo usuário ou cartão já
existe no export são puladas, então dá para rodar de novo.

## Alternativa: pela API (sem arquivo)

```bash
export CID_USER=usuario_temporario            # senha só por ambiente, nunca em arquivo
read -rs CID_PASS && export CID_PASS
python3 cadastrar_tags.py tags.csv --host IP_DO_EQUIPAMENTO                 # dry-run
python3 cadastrar_tags.py tags.csv --host IP --apply --limit 5              # grava 5
python3 cadastrar_tags.py x --host IP --consultar existentes.csv            # só lê
```

Cria os usuários e depois os cartões em lotes de 50 (`create_objects.fcgi`), confere no fim e é
idempotente. **Atenção:** este caminho foi escrito a partir da documentação e **nunca foi
executado contra um equipamento real** (a IA que o escreveu não autentica em dispositivos). Rode
primeiro o dry-run e depois `--limit`.

## Estado de validação

| Parte | Situação |
|---|---|
| Conversão decimal → `cards.value` | Derivada e conferida contra 2 cartões já cadastrados num aparelho real; mesma fórmula da doc oficial |
| `gerar_zip_importacao.py` | Reproduz byte a byte o zip de 1 usuário que importou no aparelho do autor e o zip completo montado depois (304 usuários) |
| Tag abrindo o portão | **Teste final fica com você**: passe uma tag no leitor antes de entregar |
| `cadastrar_tags.py` (API) | **Não testado em equipamento**; formatos conferidos só na doc |
| Outros modelos/firmwares | Desconhecido. A doc avisa que o CSV difere entre linhas V5/V6 e que importar de firmware mais novo/antigo não é garantido |

## Segurança

- **Nunca versione** o `users.zip`/`users.csv` exportado: ele traz nomes, `salt` e hash de senha
  dos administradores (o `.gitignore` já bloqueia). Troque a senha de qualquer usuário que tenha
  passado por chat ou terminal.
- Faça backup (export completo) antes de importar com *Sobrescrever* ou *Apagar ausentes*.

## Licença

MIT. Sem garantia; use por sua conta e risco em equipamento de controle de acesso.
