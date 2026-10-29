import random
from collections import Counter
import pytest
from buscador.similitud import (cota_levenshtein, distancia_levenshtein, jaccard, ngramas,
                                similitud_jaccard, similitud_levenshtein)


def test_ngramas():
    assert ngramas(list("abcab"), 2) == Counter({("a", "b"): 2, ("b", "c"): 1, ("c", "a"): 1})
    assert ngramas(list("ab"), 3) == Counter({("a", "b"): 1})   # secuencia más corta que n
    assert ngramas([], 3) == Counter()
    with pytest.raises(ValueError):
        ngramas(list("abc"), 0)


def test_jaccard_de_multiconjuntos():
    a = Counter({"x": 2, "y": 1})
    b = Counter({"x": 1, "z": 1})
    # intersección = min -> {x:1} (1);  unión = max -> {x:2, y:1, z:1} (4)
    assert jaccard(a, b) == pytest.approx(1 / 4)
    assert jaccard(a, a) == 1.0
    assert jaccard(a, Counter({"w": 1})) == 0.0
    assert jaccard(Counter(), Counter()) == 1.0


def test_similitud_jaccard_extremos():
    assert similitud_jaccard(list("abcdef"), list("abcdef"), 3) == 1.0
    assert similitud_jaccard(list("abcdef"), list("uvwxyz"), 3) == 0.0


@pytest.mark.parametrize("a, b, d", [
    ("kitten", "sitting", 3),
    ("", "abc", 3),
    ("abc", "abc", 0),
    ("flaw", "lawn", 2),
])
def test_distancia_levenshtein(a, b, d):
    assert distancia_levenshtein(a, b) == d
    assert distancia_levenshtein(b, a) == d


def test_similitud_levenshtein_normalizada():
    assert similitud_levenshtein(list("kitten"), list("sitting")) == pytest.approx(1 - 3 / 7)
    assert similitud_levenshtein([], []) == 1.0
    assert similitud_levenshtein(["a"], ["b"]) == 0.0


def test_cota_levenshtein_es_cota_superior():
    rng = random.Random(0)
    for _ in range(300):
        a = [rng.choice("abc") for _ in range(rng.randint(0, 12))]
        b = [rng.choice("abc") for _ in range(rng.randint(0, 12))]
        assert similitud_levenshtein(a, b) <= cota_levenshtein(len(a), len(b)) + 1e-12
