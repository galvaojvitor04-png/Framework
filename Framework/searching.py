"""
Algoritmos de Busca.

Implementações genéricas, parametrizadas por função-chave,
compatíveis com qualquer tipo de dado.

Algoritmos:
    - Busca Linear         — O(n)
    - Busca Binária        — O(log n) — requer lista ordenada
    - Busca por Predicado  — O(n) — filtragem por função booleana
    - Busca Fuzzy (texto)  — O(n·m) — similaridade por Levenshtein
"""

from typing import Any, Callable, List, Optional, Tuple


# --------------------------------------------------------------------------- #
#  Busca Linear                                                                #
# --------------------------------------------------------------------------- #

def linear_search(
    data: List[Any],
    target: Any,
    key: Optional[Callable[[Any], Any]] = None,
) -> Optional[int]:
    """
    Busca linear por valor-alvo.

    Args:
        data:   Lista de elementos.
        target: Valor a buscar.
        key:    Função extratora de chave (opcional).

    Returns:
        Índice do primeiro elemento encontrado ou None.
    """
    _key = key or (lambda x: x)
    for i, item in enumerate(data):
        if _key(item) == target:
            return i
    return None


def linear_search_all(
    data: List[Any],
    target: Any,
    key: Optional[Callable[[Any], Any]] = None,
) -> List[int]:
    """
    Retorna os índices de todos os elementos que correspondem ao alvo.
    """
    _key = key or (lambda x: x)
    return [i for i, item in enumerate(data) if _key(item) == target]


# --------------------------------------------------------------------------- #
#  Busca Binária                                                               #
# --------------------------------------------------------------------------- #

def binary_search(
    data: List[Any],
    target: Any,
    key: Optional[Callable[[Any], Any]] = None,
) -> Optional[int]:
    """
    Busca binária em lista ORDENADA.

    Args:
        data:   Lista ordenada de elementos.
        target: Valor a buscar.
        key:    Função extratora de chave (deve ser a mesma usada na ordenação).

    Returns:
        Índice do elemento encontrado ou None.
    """
    _key = key or (lambda x: x)
    low, high = 0, len(data) - 1

    while low <= high:
        mid = (low + high) // 2
        mid_key = _key(data[mid])

        if mid_key == target:
            return mid
        if mid_key < target:
            low = mid + 1
        else:
            high = mid - 1

    return None


def binary_search_leftmost(
    data: List[Any],
    target: Any,
    key: Optional[Callable[[Any], Any]] = None,
) -> Optional[int]:
    """
    Retorna o índice do PRIMEIRO elemento >= target (limite esquerdo).
    """
    _key = key or (lambda x: x)
    low, high = 0, len(data)

    while low < high:
        mid = (low + high) // 2
        if _key(data[mid]) < target:
            low = mid + 1
        else:
            high = mid

    return low if low < len(data) and _key(data[low]) == target else None


# --------------------------------------------------------------------------- #
#  Busca por Predicado                                                         #
# --------------------------------------------------------------------------- #

def filter_search(
    data: List[Any],
    predicate: Callable[[Any], bool],
) -> List[Any]:
    """
    Filtra elementos que satisfazem o predicado.

    Args:
        data:      Lista de elementos.
        predicate: Função que retorna True para os elementos desejados.

    Returns:
        Lista de elementos correspondentes.
    """
    return [item for item in data if predicate(item)]


def find_first(
    data: List[Any],
    predicate: Callable[[Any], bool],
) -> Optional[Any]:
    """Retorna o primeiro elemento que satisfaz o predicado."""
    for item in data:
        if predicate(item):
            return item
    return None


# --------------------------------------------------------------------------- #
#  Busca Fuzzy por Similaridade (Distância de Levenshtein)                    #
# --------------------------------------------------------------------------- #

def _levenshtein(s1: str, s2: str) -> int:
    """Calcula a Distância de Edição (Levenshtein) entre duas strings."""
    m, n = len(s1), len(s2)
    dp = list(range(n + 1))

    for i in range(1, m + 1):
        prev = dp[0]
        dp[0] = i
        for j in range(1, n + 1):
            temp = dp[j]
            if s1[i - 1] == s2[j - 1]:
                dp[j] = prev
            else:
                dp[j] = 1 + min(prev, dp[j], dp[j - 1])
            prev = temp

    return dp[n]


def fuzzy_search(
    data: List[Any],
    query: str,
    key: Callable[[Any], str],
    max_distance: int = 2,
    top_k: int = 5,
) -> List[Tuple[Any, int]]:
    """
    Busca fuzzy por similaridade textual (distância de Levenshtein).

    Args:
        data:         Lista de elementos.
        query:        Texto de consulta.
        key:          Função que extrai a string comparável do elemento.
        max_distance: Distância máxima aceita.
        top_k:        Número máximo de resultados retornados.

    Returns:
        Lista de (elemento, distância) ordenada por proximidade.
    """
    results: List[Tuple[Any, int]] = []

    for item in data:
        dist = _levenshtein(query.lower(), key(item).lower())
        if dist <= max_distance:
            results.append((item, dist))

    results.sort(key=lambda x: x[1])
    return results[:top_k]


def substring_search(
    data: List[Any],
    query: str,
    key: Callable[[Any], str],
    case_sensitive: bool = False,
) -> List[Any]:
    """
    Busca por substring em campo textual.

    Args:
        data:           Lista de elementos.
        query:          Texto a buscar.
        key:            Função que extrai o campo textual do elemento.
        case_sensitive: Diferencia maiúsculas/minúsculas se True.

    Returns:
        Lista de elementos cujo campo contém a substring.
    """
    if not case_sensitive:
        q = query.lower()
        return [item for item in data if q in key(item).lower()]
    return [item for item in data if query in key(item)]
