from collections import Counter

N_POR_DEFECTO = 3   

def ngramas(tokens, n=N_POR_DEFECTO):
    if n < 1:
        raise ValueError("n debe ser >= 1")
    if len(tokens) < n:
        return Counter([tuple(tokens)]) if tokens else Counter()
    return Counter(tuple(tokens[i:i + n]) for i in range(len(tokens) - n + 1))


def jaccard(a, b):
    if not a and not b:
        return 1.0
    interseccion = sum((a & b).values())
    union = sum((a | b).values())
    return interseccion / union


def similitud_jaccard(tokens1, tokens2, n=N_POR_DEFECTO):
    return jaccard(ngramas(tokens1, n), ngramas(tokens2, n))


def distancia_levenshtein(a, b):
    if len(a) < len(b):
        a, b = b, a
    anterior = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        actual = [i]
        for j, y in enumerate(b, 1):
            actual.append(min(
                anterior[j] + 1,              
                actual[j - 1] + 1,            
                anterior[j - 1] + (x != y),   
            ))
        anterior = actual
    return anterior[-1]


def similitud_levenshtein(tokens1, tokens2):
    largo = max(len(tokens1), len(tokens2))
    if largo == 0:
        return 1.0
    return 1.0 - distancia_levenshtein(tokens1, tokens2) / largo


def cota_levenshtein(largo1, largo2):
    largo = max(largo1, largo2)
    return 1.0 if largo == 0 else min(largo1, largo2) / largo
