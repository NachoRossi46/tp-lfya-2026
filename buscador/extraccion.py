import ast
import os
import sys
import tokenize
from dataclasses import dataclass, field
from pathlib import Path

DIRECTORIOS_EXCLUIDOS = {"__pycache__", "venv", "env", "site-packages", "node_modules"}

TIPOS_FUNCION = (ast.FunctionDef, ast.AsyncFunctionDef)

@dataclass
class Funcion:
    nombre: str                 
    nombre_completo: str        
    archivo: str                
    linea: int                  
    nodo: ast.AST = field(repr=False)   
    codigo: str = field(default="", repr=False)  

    @property
    def es_async(self):
        return isinstance(self.nodo, ast.AsyncFunctionDef)

    @property
    def ubicacion(self):
        return f"{self.archivo}:{self.linea}"


class _Recolector(ast.NodeVisitor):
    def __init__(self, archivo, fuente):
        self.archivo = archivo
        self.fuente = fuente
        self.pila = []
        self.funciones = []

    def _visitar_funcion(self, nodo):
        nombre_completo = ".".join(self.pila + [nodo.name])
        codigo = ast.get_source_segment(self.fuente, nodo) or ""
        self.funciones.append(
            Funcion(nodo.name, nombre_completo, self.archivo, nodo.lineno, nodo, codigo)
        )
        self.pila.append(nodo.name)
        self.generic_visit(nodo)
        self.pila.pop()

    visit_FunctionDef = _visitar_funcion
    visit_AsyncFunctionDef = _visitar_funcion

    def visit_ClassDef(self, nodo):
        self.pila.append(nodo.name)
        self.generic_visit(nodo)
        self.pila.pop()


def extraer_de_codigo(fuente, archivo="<codigo>"):
    arbol = ast.parse(fuente, filename=archivo)
    recolector = _Recolector(archivo, fuente)
    recolector.visit(arbol)
    return recolector.funciones


def leer_fuente(ruta):
    with tokenize.open(ruta) as f:
        return f.read()


def extraer_de_archivo(ruta, base=None):
    ruta = Path(ruta)
    nombre = ruta.relative_to(base).as_posix() if base else ruta.as_posix()
    return extraer_de_codigo(leer_fuente(ruta), nombre)


def listar_archivos_py(directorio):
    archivos = []
    for raiz, dirs, nombres in os.walk(directorio):
        dirs[:] = sorted(d for d in dirs
                         if not d.startswith(".") and d not in DIRECTORIOS_EXCLUIDOS)
        archivos.extend(Path(raiz) / n for n in sorted(nombres) if n.endswith(".py"))
    return archivos


def extraer_de_directorio(directorio, errores=None):
    directorio = Path(directorio)
    if not directorio.is_dir():
        raise NotADirectoryError(f"No es un directorio: {directorio}")
    funciones = []
    for ruta in listar_archivos_py(directorio):
        try:
            funciones.extend(extraer_de_archivo(ruta, directorio))
        except (SyntaxError, UnicodeDecodeError, ValueError, OSError) as e:
            mensaje = f"{type(e).__name__}: {e}"
            if errores is not None:
                errores.append((ruta, mensaje))
            else:
                print(f"[aviso] se omite {ruta} ({mensaje})", file=sys.stderr)
    return funciones
