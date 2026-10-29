"""Framework leve para CRUD eficiente de coleções estruturadas."""
from __future__ import annotations

import json
import threading
from bisect import bisect_left, bisect_right, insort
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping


class CollectionError(Exception):
    """Erro base do framework."""


class ValidationError(CollectionError):
    pass


class NotFoundError(CollectionError):
    pass


class DuplicateIdError(CollectionError):
    pass


@dataclass(frozen=True)
class Field:
    """Regra de campo. `type` pode ser um tipo Python ou tupla de tipos."""
    type: type | tuple[type, ...] | None = None
    required: bool = False
    default: Any = None
    validator: Callable[[Any], bool] | None = None


@dataclass(frozen=True)
class Index:
    """Definição de índice: hash (igualdade) ou ordered (intervalos/ordenação)."""
    field: str
    kind: str = "hash"


class Collection:
    """Coleção thread-safe com índices em memória e persistência JSON opcional.

    IDs são únicos. Valores armazenados e retornados são cópias para impedir
    alterações externas que corrompam os índices.
    """
    def __init__(self, schema: Mapping[str, Field | type], *, id_field: str = "id",
                 indexes: Iterable[Index] = (), relations: bool = True,
                 storage_path: str | Path | None = None):
        self.schema = {k: (v if isinstance(v, Field) else Field(type=v)) for k, v in schema.items()}
        self.id_field = id_field
        if id_field not in self.schema:
            self.schema[id_field] = Field(required=True)
        self.indexes = tuple(indexes)
        for idx in self.indexes:
            if idx.field not in self.schema or idx.kind not in {"hash", "ordered"}:
                raise ValueError(f"Índice inválido: {idx}")
        self._records: dict[Any, dict[str, Any]] = {}
        self._hash: dict[str, dict[Any, set[Any]]] = {}
        self._ordered: dict[str, list[tuple[Any, str, Any]]] = {}
        for idx in self.indexes:
            if idx.kind == "hash": self._hash.setdefault(idx.field, {})
            else: self._ordered.setdefault(idx.field, [])
        self._graph: dict[Any, set[Any]] = {}
        self._relations = relations
        self._path = Path(storage_path) if storage_path else None
        self._lock = threading.RLock()
        if self._path and self._path.exists():
            self._load()

    def _validate(self, record: Mapping[str, Any], *, partial: bool = False) -> dict[str, Any]:
        if not isinstance(record, Mapping): raise ValidationError("O registro deve ser um objeto/mapeamento")
        extra = set(record) - set(self.schema)
        if extra: raise ValidationError(f"Campos não definidos no esquema: {sorted(extra)}")
        out = dict(record)
        for name, rule in self.schema.items():
            if name not in out:
                if partial: continue
                if rule.required: raise ValidationError(f"Campo obrigatório ausente: {name}")
                if rule.default is not None: out[name] = rule.default
                continue
            value = out[name]
            if rule.type is not None and not isinstance(value, rule.type):
                raise ValidationError(f"Tipo inválido em '{name}': esperado {rule.type}, recebido {type(value).__name__}")
            if rule.validator and not rule.validator(value): raise ValidationError(f"Valor inválido para '{name}'")
        if not partial and (self.id_field not in out or out[self.id_field] is None):
            raise ValidationError(f"'{self.id_field}' é obrigatório e não pode ser nulo")
        return out

    @staticmethod
    def _sort_key(value: Any) -> tuple[str, str]:
        # Ordem natural para números e ordem determinística entre tipos distintos.
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return ("number", value)
        if isinstance(value, str):
            return ("str", value)
        if isinstance(value, bool):
            return ("bool", int(value))
        return (type(value).__name__, repr(value))

    def _index_add(self, record: Mapping[str, Any]) -> None:
        rid = record[self.id_field]
        for field, table in self._hash.items():
            if field in record:
                try: table.setdefault(record[field], set()).add(rid)
                except TypeError as e: raise ValidationError(f"Campo indexado '{field}' deve ser hashable") from e
        for field, items in self._ordered.items():
                if field in record: insort(items, (self._sort_key(record[field]), repr(rid), rid))

    def _index_remove(self, record: Mapping[str, Any]) -> None:
        rid = record[self.id_field]
        for field, table in self._hash.items():
            if field in record:
                ids = table.get(record[field])
                if ids:
                    ids.discard(rid)
                    if not ids: del table[record[field]]
        for field, items in self._ordered.items():
            if field in record:
                key = (self._sort_key(record[field]), repr(rid), rid)
                pos = bisect_left(items, key)
                if pos < len(items) and items[pos] == key: items.pop(pos)

    def _save(self) -> None:
        if not self._path: return
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(self._path.suffix + ".tmp")
        tmp.write_text(json.dumps(list(self._records.values()), ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self._path)

    def _load(self) -> None:
        try: rows = json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e: raise CollectionError(f"Não foi possível carregar {self._path}: {e}") from e
        if not isinstance(rows, list): raise CollectionError("Arquivo de coleção deve conter uma lista JSON")
        for row in rows:
            clean = self._validate(row)
            rid = clean[self.id_field]
            if rid in self._records: raise DuplicateIdError(f"ID duplicado no arquivo: {rid}")
            self._records[rid] = clean
            self._index_add(clean)
            self._graph.setdefault(rid, set())

    def insert(self, record: Mapping[str, Any]) -> dict[str, Any]:
        clean = self._validate(record)
        rid = clean[self.id_field]
        with self._lock:
            if rid in self._records: raise DuplicateIdError(f"ID já existe: {rid}")
            self._records[rid] = clean
            try: self._index_add(clean)
            except Exception:
                self._records.pop(rid, None); raise
            if self._relations: self._graph.setdefault(rid, set())
            self._save()
            return dict(clean)

    def get(self, record_id: Any) -> dict[str, Any]:
        with self._lock:
            if record_id not in self._records: raise NotFoundError(f"Registro não encontrado: {record_id}")
            return dict(self._records[record_id])

    def update(self, record_id: Any, changes: Mapping[str, Any]) -> dict[str, Any]:
        with self._lock:
            if record_id not in self._records: raise NotFoundError(f"Registro não encontrado: {record_id}")
            if self.id_field in changes and changes[self.id_field] != record_id:
                raise ValidationError("Não é permitido alterar o ID")
            merged = dict(self._records[record_id]); merged.update(changes)
            clean = self._validate(merged)
            old = self._records[record_id]
            self._index_remove(old)
            try: self._index_add(clean)
            except Exception:
                self._index_add(old); raise
            self._records[record_id] = clean
            self._save()
            return dict(clean)

    def delete(self, record_id: Any) -> dict[str, Any]:
        with self._lock:
            if record_id not in self._records: raise NotFoundError(f"Registro não encontrado: {record_id}")
            removed = self._records.pop(record_id)
            self._index_remove(removed)
            self._graph.pop(record_id, None)
            for neighbors in self._graph.values(): neighbors.discard(record_id)
            self._save()
            return dict(removed)

    def find(self, field: str, value: Any) -> list[dict[str, Any]]:
        """Busca exata; usa índice hash quando disponível, caso contrário varre registros."""
        if field not in self.schema: raise ValidationError(f"Campo desconhecido: {field}")
        with self._lock:
            ids = self._hash.get(field, {}).get(value) if field in self._hash else None
            rows = (self._records[i] for i in ids) if ids is not None else (r for r in self._records.values() if r.get(field) == value)
            return [dict(r) for r in rows]

    def where(self, field: str, *, gt: Any = None, gte: Any = None, lt: Any = None,
              lte: Any = None) -> list[dict[str, Any]]:
        """Consulta por intervalo. Usa índice ordenado se configurado; resultado em ordem crescente."""
        if field not in self.schema: raise ValidationError(f"Campo desconhecido: {field}")
        with self._lock:
            if field in self._ordered:
                ids = [rid for _, _, rid in self._ordered[field]]
                rows = [self._records[i] for i in ids]
            else:
                rows = [r for r in self._records.values() if field in r]
                try: rows.sort(key=lambda r: r[field])
                except TypeError as e: raise ValidationError(f"Campo '{field}' não é ordenável") from e
            def ok(v: Any) -> bool:
                try:
                    return ((gt is None or v > gt) and (gte is None or v >= gte)
                            and (lt is None or v < lt) and (lte is None or v <= lte))
                except TypeError as e: raise ValidationError(f"Limites incompatíveis com campo '{field}'") from e
            return [dict(r) for r in rows if field in r and ok(r[field])]

    def list(self, *, order_by: str | None = None, descending: bool = False,
             offset: int = 0, limit: int | None = None) -> list[dict[str, Any]]:
        if offset < 0 or (limit is not None and limit < 0): raise ValueError("offset/limit não podem ser negativos")
        with self._lock:
            if order_by is None: rows = list(self._records.values())
            elif order_by not in self.schema: raise ValidationError(f"Campo desconhecido: {order_by}")
            elif order_by in self._ordered:
                ids = [rid for _, _, rid in self._ordered[order_by]]
                rows = [self._records[i] for i in ids]
            else:
                rows = sorted((r for r in self._records.values() if order_by in r), key=lambda r: r[order_by])
            if descending: rows.reverse()
            rows = rows[offset: offset + limit if limit is not None else None]
            return [dict(r) for r in rows]

    def connect(self, source_id: Any, target_id: Any, *, bidirectional: bool = True) -> None:
        """Cria uma aresta no grafo de relações entre registros existentes."""
        if not self._relations: raise CollectionError("Grafo de relações desativado")
        with self._lock:
            if source_id not in self._records or target_id not in self._records: raise NotFoundError("Os dois registros precisam existir")
            self._graph.setdefault(source_id, set()).add(target_id)
            if bidirectional: self._graph.setdefault(target_id, set()).add(source_id)

    def neighbors(self, record_id: Any) -> list[dict[str, Any]]:
        with self._lock:
            if record_id not in self._records: raise NotFoundError(f"Registro não encontrado: {record_id}")
            return [dict(self._records[i]) for i in self._graph.get(record_id, ())]

    def count(self) -> int:
        return len(self._records)

    def check_integrity(self) -> bool:
        """Recalcula e compara índices internos; útil em testes/diagnóstico."""
        with self._lock:
            for field, table in self._hash.items():
                expected: dict[Any, set[Any]] = {}
                for rid, row in self._records.items():
                    if field in row: expected.setdefault(row[field], set()).add(rid)
                if expected != table: return False
            for field, entries in self._ordered.items():
                expected = sorted((self._sort_key(r[field]), repr(rid), rid) for rid, r in self._records.items() if field in r)
                if entries != expected: return False
            return True

    def graph(self) -> dict[Any, tuple[Any, ...]]:
        with self._lock: return {k: tuple(sorted(v, key=repr)) for k, v in self._graph.items()}
