import textwrap
from pathlib import Path
import pytest
from buscador.extraccion import extraer_de_codigo
from buscador.motor import Indice

RAIZ = Path(__file__).resolve().parent.parent
REPO_DEMO = RAIZ / "ejemplos" / "repo_demo"

def funcion(codigo, nombre=None):
    funciones = extraer_de_codigo(textwrap.dedent(codigo))
    if nombre is None:
        return funciones[0]
    return next(f for f in funciones if f.nombre_completo == nombre)


@pytest.fixture
def repo(tmp_path):
    def crear(archivos):
        for nombre, codigo in archivos.items():
            ruta = tmp_path / nombre
            ruta.parent.mkdir(parents=True, exist_ok=True)
            ruta.write_text(textwrap.dedent(codigo), encoding="utf-8")
        return tmp_path
    return crear


@pytest.fixture(scope="session")
def indice_demo():
    return Indice.desde_directorio(REPO_DEMO, errores=[])
