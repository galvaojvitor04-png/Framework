# Framework de Coleções CRUD

Biblioteca Python pequena e reutilizável para gerenciar coleções de registros estruturados em memória, com validação, índices, ordenação, relações em grafo e persistência JSON opcional. Não requer dependências externas e usa Python 3.10+.

## Recursos

- **CRUD:** inserir, obter, atualizar parcialmente e excluir registros com ID único.
- **Esquema:** tipos, campos obrigatórios, valores padrão e validadores customizados.
- **Busca exata:** índice hash opcional para localizar registros por campos de igualdade.
- **Ordenação/intervalos:** índice ordenado opcional para listagem ordenada e consulta `gt/gte/lt/lte`.
- **Relações:** grafo de adjacência para conectar registros e consultar vizinhos.
- **Persistência:** JSON atômico opcional, com reconstrução dos índices ao iniciar.
- **Proteção dos dados:** cópias são devolvidas nas operações para evitar que mutações externas desalinhem os índices; métodos são protegidos por lock.

## Exemplo

```python
from collection_framework import Collection, Field, Index

clientes = Collection(
    schema={
        "id": Field(str, required=True),
        "nome": Field(str, required=True),
        "idade": Field(int, required=True),
        "perfil": Field(dict),  # campos complexos/nested são aceitos
    },
    indexes=[Index("nome", "hash"), Index("idade", "ordered")],
    storage_path="dados/clientes.json",  # opcional
)

clientes.insert({"id": "c-1", "nome": "Ana", "idade": 29,
                 "perfil": {"cidade": "Recife", "preferencias": ["email"]}})
print(clientes.find("nome", "Ana"))
print(clientes.where("idade", gte=18, lt=40))
print(clientes.list(order_by="idade", descending=True, limit=20))
clientes.update("c-1", {"idade": 30})
clientes.delete("c-1")
```

### Relações como grafo

```python
clientes.insert({"id": "c-2", "nome": "Beto", "idade": 31})
clientes.connect("c-1", "c-2")  # bidirecional por padrão
print(clientes.neighbors("c-1"))
```

Use `bidirectional=False` para criar uma aresta direcionada. Ao excluir um registro, suas arestas incidentes são removidas.

## Esquema e validação

Cada campo pode ser declarado com `Field(tipo, required=False, default=None, validator=None)`. Também é possível usar diretamente um tipo, por exemplo `{"nome": str}`. `validator` recebe o valor e deve retornar `True` quando válido. Campos não declarados são rejeitados. Os tipos `dict` e `list` permitem armazenar objetos e coleções aninhadas em JSON.

## Índices e custos esperados

| Operação | Estrutura | Custo típico |
|---|---|---:|
| Inserir/remover | tabela de registros + atualização dos índices | O(1) médio sem índices; O(log n) por índice ordenado |
| Busca exata | hash indexado | O(1) médio + resultados |
| Busca exata sem índice | varredura | O(n) |
| Consulta de intervalo/listagem ordenada indexada | lista ordenada com busca binária na manutenção | O(n) para materializar/filtrar resultados; inserção O(n) devido a deslocamento em lista Python |
| Listagem geral | dicionário | O(n) |
| Vizinhos no grafo | lista de adjacência | O(grau do vértice) |

A ordenação é natural para valores numéricos e strings. É recomendável que cada campo ordenado tenha valores comparáveis entre si. Índices aceleram consultas, mas consomem memória e tornam escrita mais custosa.

## Execução dos testes

Na pasta do projeto:

```bash
python3 -m unittest -v
```

## Limites de uso

Esta implementação é voltada a aplicações locais, protótipos e coleções moderadas. Persistência JSON não substitui banco transacional multi-processo: não há transações entre processos, consultas concorrentes distribuídas ou recuperação avançada contra falhas. Para grandes volumes ou múltiplos escritores, use um banco de dados como SQLite/PostgreSQL e mantenha esta API como camada adaptadora.
