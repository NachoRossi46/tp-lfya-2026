import pytest
from buscador.motor import METRICA_POR_DEFECTO, METRICAS, UMBRALES, ErrorBusqueda, Indice
from conftest import funcion

ORIGINAL_VARIANZA = """
def varianza(valores):
    media = sum(valores) / len(valores)
    acumulado = 0.0
    for v in valores:
        diferencia = v - media
        acumulado += diferencia * diferencia
    cantidad = len(valores)
    return acumulado / cantidad
"""

ORIGINAL_CONTAR = """
def contar_pares(numeros):
    cantidad = 0
    for n in numeros:
        if n % 2 == 0:
            cantidad += 1
    return cantidad
"""

ORIGINAL_BUSQUEDA = """
def buscar_indice(lista, objetivo):
    izquierda, derecha = 0, len(lista) - 1
    while izquierda <= derecha:
        medio = (izquierda + derecha) // 2
        if lista[medio] == objetivo:
            return medio
        if lista[medio] < objetivo:
            izquierda = medio + 1
        else:
            derecha = medio - 1
    return -1
"""


def score(codigo_a, codigo_b, metrica=METRICA_POR_DEFECTO):
    indice = Indice([])
    a = indice.indexar(funcion(codigo_a))
    b = indice.indexar(funcion(codigo_b))
    return indice.similitud(a, b, metrica)

@pytest.mark.parametrize("metrica", METRICAS)
def test_positivo_variables_renombradas(metrica):
    clon = """
    def busqueda_binaria(arr, x):
        lo, hi = 0, len(arr) - 1
        while lo <= hi:
            mid = (lo + hi) // 2
            if arr[mid] == x:
                return mid
            if arr[mid] < x:
                lo = mid + 1
            else:
                hi = mid - 1
        return -1
    """
    assert score(ORIGINAL_BUSQUEDA, clon, metrica) == 1.0


CLON_REORDENADO_VARIANZA = """
def calcular_varianza(xs):
    cantidad = len(xs)
    acumulado = 0.0
    media = sum(xs) / len(xs)
    for x in xs:
        diferencia = x - media
        acumulado += diferencia * diferencia
    return acumulado / cantidad
"""


@pytest.mark.parametrize("metrica", ["jaccard", "combinada"])
def test_positivo_lineas_reordenadas(metrica):
    # además de reordenar, renombra: `cantidad` ahora se calcula primero
    assert score(ORIGINAL_VARIANZA, CLON_REORDENADO_VARIANZA, metrica) >= UMBRALES[metrica]


def test_limitacion_conocida_levenshtein_sola_penaliza_reordenamientos():
    """Levenshtein respeta el orden: mover una sentencia cuesta borrarla e
    insertarla, y además renumera las VARn. Por eso no es la métrica por
    defecto (ver INFORME.md)."""
    lev = score(ORIGINAL_VARIANZA, CLON_REORDENADO_VARIANZA, "levenshtein")
    jac = score(ORIGINAL_VARIANZA, CLON_REORDENADO_VARIANZA, "jaccard")
    assert lev < UMBRALES["levenshtein"]
    assert jac >= UMBRALES["jaccard"]


@pytest.mark.parametrize("metrica", METRICAS)
def test_positivo_sentencia_agregada_y_literales_distintos(metrica):
    clon = """
    def cuantos_multiplos(lista):
        contador = 0
        for valor in lista:
            print("revisando", valor)
            if valor % 3 == 1:
                contador += 1
        return contador
    """
    assert score(ORIGINAL_CONTAR, clon, metrica) >= UMBRALES[metrica]


def test_limitacion_conocida_funcion_chica_con_varias_sentencias_agregadas():
    clon = """
    def cuantos_multiplos(lista):
        contador = 0
        vistos = []
        for valor in lista:
            if valor % 3 == 1:
                contador += 1
            vistos.append(valor)
        return contador
    """
    assert score(ORIGINAL_CONTAR, clon, "jaccard") < UMBRALES["jaccard"]
    assert score(ORIGINAL_CONTAR, clon, "levenshtein") >= UMBRALES["levenshtein"]


def test_positivo_el_clon_aparece_primero_en_la_busqueda(indice_demo):
    objetivo = indice_demo.buscar_funcion("estadisticas.py:varianza")
    resultados = indice_demo.buscar(objetivo, top=3)
    assert resultados[0].funcion.nombre == "calcular_varianza"
    assert resultados[0].es_duplicado


@pytest.mark.parametrize("metrica", METRICAS)
def test_negativo_calculo_numerico_vs_procesamiento_de_texto(metrica):
    texto = """
    def capitalizar_titulo(titulo, excepciones):
        resultado = []
        for i, palabra in enumerate(titulo.lower().split()):
            if i > 0 and palabra in excepciones:
                resultado.append(palabra)
            else:
                resultado.append(palabra.capitalize())
        return " ".join(resultado)
    """
    assert score(ORIGINAL_VARIANZA, texto, metrica) < UMBRALES[metrica]


@pytest.mark.parametrize("metrica", METRICAS)
def test_negativo_recursion_vs_ordenamiento(metrica):
    factorial = """
    def factorial(n):
        if n <= 1:
            return 1
        return n * factorial(n - 1)
    """
    burbuja = """
    def ordenar_burbuja(lista):
        datos = list(lista)
        for i in range(len(datos)):
            for j in range(len(datos) - 1 - i):
                if datos[j] > datos[j + 1]:
                    datos[j], datos[j + 1] = datos[j + 1], datos[j]
        return datos
    """
    assert score(factorial, burbuja, metrica) < UMBRALES[metrica]


@pytest.mark.parametrize("metrica", METRICAS)
def test_negativo_busqueda_binaria_vs_contar(metrica):
    assert score(ORIGINAL_BUSQUEDA, ORIGINAL_CONTAR, metrica) < UMBRALES[metrica]


def test_limitacion_conocida_clon_semantico_no_se_detecta():
    iterativo = """
    def promedio(numeros):
        total = 0
        for n in numeros:
            total += n
        return total / len(numeros)
    """
    funcional = "def promedio(numeros):\n    return sum(numeros) / len(numeros)"
    assert score(iterativo, funcional) < UMBRALES[METRICA_POR_DEFECTO]


def test_buscar_devuelve_top_k_ordenado_y_excluye_al_objetivo(indice_demo):
    objetivo = indice_demo.buscar_funcion("estadisticas.py:promedio")
    resultados = indice_demo.buscar(objetivo, top=4)
    assert len(resultados) == 4
    assert all(r.funcion.ubicacion != objetivo.funcion.ubicacion for r in resultados)
    scores = [r.score for r in resultados]
    assert scores == sorted(scores, reverse=True)
    assert resultados[0].funcion.nombre == "media_aritmetica" and resultados[0].score == 1.0


@pytest.mark.parametrize("metrica", METRICAS)
def test_la_poda_da_el_mismo_resultado_que_comparar_contra_todos(indice_demo, metrica):
    for objetivo in indice_demo.entradas:
        resultados = indice_demo.buscar(objetivo, top=3, metrica=metrica)
        todos = sorted(
            ((indice_demo.similitud(objetivo, e, metrica), e.funcion.archivo, e.funcion.linea)
             for e in indice_demo.entradas if e is not objetivo),
            key=lambda x: (-x[0], x[1], x[2]))[:3]
        assert [(r.score, r.funcion.archivo, r.funcion.linea) for r in resultados] == todos


def test_resolver_funcion_por_archivo_y_nombre(indice_demo):
    assert indice_demo.buscar_funcion("inventario.py:Inventario.valor_total").funcion.linea == 26
    assert indice_demo.buscar_funcion("copiado/estadisticas_v2.py:fact").funcion.nombre == "fact"
    # sufijo único de la ruta
    assert indice_demo.buscar_funcion("estadisticas_v2.py:fact").funcion.archivo == "copiado/estadisticas_v2.py"


@pytest.mark.parametrize("especificacion, mensaje", [
    ("inventario.py:valor_total", "ambiguo"),        # Producto.valor_total e Inventario.valor_total
    ("estadisticas.py:no_existe", "No hay una función"),
    ("no_existe.py:f", "No se encontró el archivo"),
    ("sin_dos_puntos", "ARCHIVO:NOMBRE"),
])
def test_errores_al_resolver_la_funcion(indice_demo, especificacion, mensaje):
    with pytest.raises(ErrorBusqueda, match=mensaje):
        indice_demo.buscar_funcion(especificacion)


def test_funcion_objetivo_desde_codigo_pegado(indice_demo):
    objetivo = indice_demo.desde_codigo("def mi_suma(xs):\n    s = 0\n    for e in xs:\n        s += e\n"
                                        "    return s / len(xs)")
    assert indice_demo.buscar(objetivo, top=1)[0].funcion.nombre in ("promedio", "media_aritmetica")
    with pytest.raises(ErrorBusqueda, match="no es Python válido"):
        indice_demo.desde_codigo("def roto(:")
    with pytest.raises(ErrorBusqueda, match="ninguna definición"):
        indice_demo.desde_codigo("x = 1")


def test_reporte_de_duplicados(indice_demo):
    pares = {frozenset((a.nombre, b.nombre)) for a, b, _ in indice_demo.duplicados()}
    assert frozenset(("promedio", "media_aritmetica")) in pares
    assert frozenset(("varianza", "calcular_varianza")) in pares
    assert frozenset(("contar_pares", "cuantos_pares")) in pares
    assert frozenset(("promedio", "promedio_funcional")) not in pares
