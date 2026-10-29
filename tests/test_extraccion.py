import ast
from buscador.extraccion import extraer_de_codigo, extraer_de_directorio, listar_archivos_py

CODIGO = '''
def libre(x):
    return x

class Clase:
    def metodo(self):
        def interna():
            return 1
        return interna()

async def asincronica():
    pass
'''


def test_extrae_funciones_metodos_anidadas_y_async():
    funciones = extraer_de_codigo(CODIGO, "mod.py")
    assert [f.nombre_completo for f in funciones] == [
        "libre", "Clase.metodo", "Clase.metodo.interna", "asincronica"]
    assert [f.es_async for f in funciones] == [False, False, False, True]


def test_registra_nombre_archivo_linea_y_subarbol():
    libre, metodo, *_ = extraer_de_codigo(CODIGO, "mod.py")
    assert (libre.nombre, libre.archivo, libre.linea) == ("libre", "mod.py", 2)
    assert (metodo.nombre, metodo.linea) == ("metodo", 6)
    assert isinstance(libre.nodo, ast.FunctionDef) and libre.nodo.name == "libre"
    assert libre.codigo == "def libre(x):\n    return x"
    assert libre.ubicacion == "mod.py:2"


def test_recorre_directorio_recursivamente(repo):
    raiz = repo({
        "a.py": "def f(): pass",
        "sub/b.py": "def g(): pass",
        "sub/profundo/c.py": "def h(): pass",
        "notas.txt": "def no_es_python(): pass",
        ".venv/lib.py": "def de_entorno_virtual(): pass",
        "__pycache__/x.py": "def cache(): pass",
    })
    funciones = extraer_de_directorio(raiz)
    assert {(f.archivo, f.nombre) for f in funciones} == {
        ("a.py", "f"), ("sub/b.py", "g"), ("sub/profundo/c.py", "h")}
    assert len(listar_archivos_py(raiz)) == 3


def test_archivo_invalido_se_omite_y_se_informa(repo):
    raiz = repo({"bueno.py": "def f(): pass", "py2.py": 'print "hola"'})
    errores = []
    funciones = extraer_de_directorio(raiz, errores)
    assert [f.nombre for f in funciones] == ["f"]
    assert len(errores) == 1 and errores[0][0].name == "py2.py"
    assert "SyntaxError" in errores[0][1]


def test_respeta_declaracion_de_codificacion(tmp_path):
    (tmp_path / "latin.py").write_bytes(
        "# -*- coding: latin-1 -*-\ndef año():\n    return 'ñandú'\n".encode("latin-1"))
    assert [f.nombre for f in extraer_de_directorio(tmp_path)] == ["año"]
