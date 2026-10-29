import ast
import re
import sys
import pytest
from buscador.normalizacion import normalizar, normalizar_con_tabla, serializar, sin_indices, tokens_de_funcion
from conftest import funcion


def tokens(codigo, nombre=None):
    return tokens_de_funcion(funcion(codigo, nombre).nodo)


def test_variables_y_parametros_se_reemplazan_por_var_n():
    arbol, tabla = normalizar_con_tabla(funcion("""
        def f(lista, factor):
            total = 0
            for x in lista:
                total += x * factor
            return total
    """).nodo)
    assert tabla == {"lista": "VAR1", "factor": "VAR2", "total": "VAR3", "x": "VAR4"}
    assert "for VAR4 in VAR1:" in ast.unparse(arbol)


def test_renombrar_variables_no_cambia_la_secuencia():
    a = tokens("def f(a, b):\n    c = a + b\n    return c * a")
    b = tokens("def g(x, y):\n    z = x + y\n    return z * x")
    assert a == b


def test_se_preserva_la_correspondencia_entre_variables():
    # a + a  no es lo mismo que  a + b
    assert tokens("def f(a, b): return a + a") != tokens("def f(a, b): return a + b")


def test_literales_se_reemplazan_por_lit():
    assert tokens("def f(x): return x * 2 + 'hola'") == tokens("def f(x): return x * 3.5 + 'chau'")
    assert "Constant:LIT" in tokens("def f(): return 42")


def test_none_true_false_se_conservan():
    assert tokens("def f(): return None") != tokens("def f(): return False")
    assert "Constant:None" in tokens("def f(): return None")


def test_el_nombre_de_la_funcion_no_influye_ni_en_la_recursion():
    a = tokens("def factorial(n):\n    return 1 if n <= 1 else n * factorial(n - 1)")
    b = tokens("def fact(k):\n    return 1 if k <= 1 else k * fact(k - 1)")
    assert a == b
    assert "Name:FUNC" in a and "Name:factorial" not in a


def test_recursion_de_metodo_vs_delegacion():
    rec = tokens("def visitar(self, n):\n    return self.visitar(n.hijo)")
    assert "Attribute:FUNC" in rec
    # self.archivo.close() dentro de close() es otro objeto: se conserva el nombre
    deleg = tokens("def close(self):\n    self.archivo.close()")
    assert "Attribute:close" in deleg


def test_docstrings_anotaciones_y_decoradores_se_ignoran():
    con = tokens('''
        @cache
        def f(x: int, y: "str" = None) -> list:
            """Documentación."""
            r: int = x
            return [r, y]
    ''')
    sin = tokens('''
        def g(a, b=None):
            r = a
            return [r, b]
    ''')
    assert con == sin


def test_builtins_se_conservan_salvo_que_se_redefinan():
    assert "Name:len" in tokens("def f(x): return len(x)")
    # `len` es aquí una variable local, no la builtin
    assert "Name:len" not in tokens("def f(x):\n    len = 3\n    return len")


def test_funciones_globales_y_modulos_se_anonimizan():
    assert tokens("def f(x): return math.sqrt(helper(x))") == tokens("def f(x): return m.sqrt(otra(x))")


def test_recorrido_preorder_raiz_primero():
    t = tokens("def f(a):\n    return a + 1")
    assert t == ["FunctionDef:FUNC", "arguments", "arg:VAR1", "{",
                 "Return", "BinOp", "Name:VAR1", "Add", "Constant:LIT", "}"]


def test_los_bloques_reflejan_el_anidamiento():
    dentro = tokens("def f(xs):\n    for x in xs:\n        a(x)\n        b(x)")
    fuera = tokens("def f(xs):\n    for x in xs:\n        a(x)\n    b(x)")
    assert dentro != fuera


def test_var_n_se_numeran_en_orden_de_primera_aparicion_en_la_secuencia(indice_demo):
    for entrada in indice_demo.entradas:
        vistos = []
        for token in entrada.tokens:
            for numero in re.findall(r"VAR(\d+)", token):
                if int(numero) not in vistos:
                    vistos.append(int(numero))
        assert vistos == list(range(1, len(vistos) + 1)), entrada.funcion.nombre_completo


def test_el_arbol_original_no_se_modifica():
    f = funcion("def original(x):\n    '''doc'''\n    return x + 1")
    antes = ast.dump(f.nodo)
    normalizar(f.nodo)
    assert ast.dump(f.nodo) == antes


def test_cuerpo_vacio_tras_quitar_docstring_sigue_siendo_valido():
    arbol = normalizar(funcion('def f():\n    """sólo docstring"""').nodo)
    assert ast.unparse(arbol) == "def FUNC():\n    pass"


@pytest.mark.parametrize("codigo", [
    "def f(x):\n    try:\n        pass\n    except ValueError as e:\n        raise e",
    "def f():\n    global G\n    G = 1",
    pytest.param(
        "def f(p):\n    match p:\n        case [a, *resto]:\n            return a\n        case {'k': v, **otros}:\n            return v",
        marks=pytest.mark.skipif(sys.version_info < (3, 10), reason="match requiere Python 3.10")),
    "def f():\n    import os.path as op\n    return op",
    "async def f(xs):\n    async for x in xs:\n        await x",
    "def f(xs):\n    return {k: v for k, v in xs if (n := k)}",
])
def test_construcciones_variadas_quedan_sin_nombres_originales(codigo):
    t = tokens(codigo)
    originales = {"x", "e", "G", "p", "a", "resto", "v", "otros", "op", "xs", "k", "n"}
    detalles = {parte for token in t for parte in re.split(r"[:,>]", token)[1:]}
    assert not (detalles & originales), t


def test_sin_indices():
    assert sin_indices(["Name:VAR12", "arg:VAR3", "Global:VAR1,VAR2", "Name:len"]) == \
        ["Name:VAR", "arg:VAR", "Global:VAR,VAR", "Name:len"]


def test_serializar_omite_contextos_load_store():
    t = serializar(ast.parse("x = y").body[0])
    assert t == ["Assign", "Name:x", "Name:y"]
