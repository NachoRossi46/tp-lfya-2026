import heapq
from dataclasses import dataclass, field
from pathlib import Path
from .extraccion import extraer_de_archivo, extraer_de_codigo, extraer_de_directorio
from .normalizacion import sin_indices, tokens_de_funcion
from .similitud import N_POR_DEFECTO, cota_levenshtein, jaccard, ngramas, similitud_levenshtein

METRICAS = ("jaccard", "levenshtein", "combinada")
METRICA_POR_DEFECTO = "jaccard"

UMBRALES = {"jaccard": 0.60, "levenshtein": 0.66, "combinada": 0.63}


class ErrorBusqueda(Exception):
    """La función objetivo no se pudo determinar (no existe, es ambigua, ...)."""

@dataclass
class FuncionIndexada:
    funcion: object                 
    tokens: list
    ngramas: object = field(repr=False)   
    total_ngramas: int = 0

    @property
    def clave(self):
        return (self.funcion.archivo, self.funcion.linea, self.funcion.nombre_completo)


@dataclass
class Resultado:
    funcion: object                 
    score: float
    es_duplicado: bool


class Indice:
    def __init__(self, funciones, n=N_POR_DEFECTO):
        self.n = n
        self.entradas = [self.indexar(f) for f in funciones]

    @classmethod
    def desde_directorio(cls, directorio, n=N_POR_DEFECTO, errores=None):
        return cls(extraer_de_directorio(directorio, errores), n)

    def indexar(self, funcion):
        tokens = tokens_de_funcion(funcion.nodo)
        grams = ngramas(sin_indices(tokens), self.n)   
        return FuncionIndexada(funcion, tokens, grams, sum(grams.values()))

    def __len__(self):
        return len(self.entradas)

    def similitud(self, a, b, metrica=METRICA_POR_DEFECTO):
        if metrica == "jaccard":
            return jaccard(a.ngramas, b.ngramas)
        if metrica == "levenshtein":
            return similitud_levenshtein(a.tokens, b.tokens)
        if metrica == "combinada":
            return (jaccard(a.ngramas, b.ngramas) + similitud_levenshtein(a.tokens, b.tokens)) / 2
        raise ValueError(f"métrica desconocida: {metrica!r} (opciones: {', '.join(METRICAS)})")

    @staticmethod
    def cota(a, b, metrica):
        cota_j = cota_levenshtein(a.total_ngramas, b.total_ngramas)
        cota_l = cota_levenshtein(len(a.tokens), len(b.tokens))
        return {"jaccard": cota_j, "levenshtein": cota_l, "combinada": (cota_j + cota_l) / 2}[metrica]

    def buscar(self, objetivo, top=5, metrica=METRICA_POR_DEFECTO, umbral=None):
        if top < 1:
            raise ValueError("top debe ser >= 1")
        umbral = UMBRALES[metrica] if umbral is None else umbral
        candidatos = [e for e in self.entradas if e.clave != objetivo.clave]
        candidatos.sort(key=lambda e: self.cota(objetivo, e, metrica), reverse=True)
        mejores_scores = []  
        calculados = []       
        for e in candidatos:
            if len(mejores_scores) == top and self.cota(objetivo, e, metrica) < mejores_scores[0]:
                break       
            score = self.similitud(objetivo, e, metrica)
            calculados.append((score, e))
            if len(mejores_scores) < top:
                heapq.heappush(mejores_scores, score)
            elif score > mejores_scores[0]:
                heapq.heapreplace(mejores_scores, score)
        calculados.sort(key=lambda x: (-x[0], _clave_orden(x[1])))
        return [Resultado(e.funcion, s, s >= umbral) for s, e in calculados[:top]]

    def duplicados(self, metrica=METRICA_POR_DEFECTO, umbral=None, min_tokens=20):
        umbral = UMBRALES[metrica] if umbral is None else umbral
        entradas = [e for e in self.entradas if len(e.tokens) >= min_tokens]
        pares = []
        for i, a in enumerate(entradas):
            for b in entradas[i + 1:]:
                if self.cota(a, b, metrica) < umbral:
                    continue
                score = self.similitud(a, b, metrica)
                if score >= umbral:
                    pares.append((a.funcion, b.funcion, score))
        pares.sort(key=lambda p: (-p[2], p[0].archivo, p[0].linea, p[1].archivo, p[1].linea))
        return pares

    def buscar_funcion(self, especificacion, directorio=None):
        if ":" not in especificacion:
            raise ErrorBusqueda("La función debe indicarse como ARCHIVO:NOMBRE, "
                                "p. ej. utils.py:calcular o modelos.py:Clase.metodo")
        archivo, nombre = especificacion.rsplit(":", 1)
        archivo_norm = archivo.replace("\\", "/").removeprefix("./")
        if directorio:
            try:  
                archivo_norm = Path(archivo).resolve().relative_to(Path(directorio).resolve()).as_posix()
            except ValueError:
                pass

        archivos = sorted({e.funcion.archivo for e in self.entradas})
        coincidentes = [a for a in archivos if a == archivo_norm] or \
                       [a for a in archivos if a.endswith("/" + archivo_norm)]
        if len(coincidentes) > 1:
            raise ErrorBusqueda(f"'{archivo}' es ambiguo, coincide con: " + ", ".join(coincidentes))
        if coincidentes:
            candidatas = [e for e in self.entradas if e.funcion.archivo == coincidentes[0]]
        elif Path(archivo).is_file():
            try:
                candidatas = [self.indexar(f) for f in extraer_de_archivo(archivo)]
            except (SyntaxError, UnicodeDecodeError, ValueError) as e:
                raise ErrorBusqueda(f"No se pudo parsear '{archivo}': {type(e).__name__}: {e}") from e
        else:
            raise ErrorBusqueda(f"No se encontró el archivo '{archivo}' en el repositorio")
        return _elegir_por_nombre(candidatas, nombre, archivo)

    def desde_codigo(self, codigo, nombre=None):
        try:
            funciones = extraer_de_codigo(codigo, "<codigo pegado>")
        except SyntaxError as e:
            raise ErrorBusqueda(f"El código pegado no es Python válido: {e}") from e
        if not funciones:
            raise ErrorBusqueda("El código pegado no contiene ninguna definición de función (def)")
        candidatas = [self.indexar(f) for f in funciones]
        if nombre:
            return _elegir_por_nombre(candidatas, nombre, "<codigo pegado>")
        return candidatas[0]


def _elegir_por_nombre(candidatas, nombre, origen):
    elegidas = [e for e in candidatas if e.funcion.nombre_completo == nombre] or \
               [e for e in candidatas if e.funcion.nombre == nombre]
    if not elegidas:
        disponibles = ", ".join(e.funcion.nombre_completo for e in candidatas) or "(ninguna)"
        raise ErrorBusqueda(f"No hay una función '{nombre}' en {origen}. Disponibles: {disponibles}")
    if len(elegidas) > 1:
        opciones = ", ".join(f"{e.funcion.nombre_completo} (línea {e.funcion.linea})" for e in elegidas)
        raise ErrorBusqueda(f"'{nombre}' es ambiguo en {origen}: {opciones}. "
                            "Usá el nombre completo, p. ej. Clase.metodo")
    return elegidas[0]


def _clave_orden(entrada):
    f = entrada.funcion
    return (f.archivo, f.linea, f.nombre_completo)
