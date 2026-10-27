import ast
import builtins
import copy
import re

FUNC = "FUNC"
LIT = "LIT"    
PREFIJO_VAR = "VAR"

BUILTINS = frozenset(dir(builtins))

CAMPOS_BLOQUE = ("body", "orelse", "finalbody")
ABRE_BLOQUE, CIERRA_BLOQUE = "{", "}"


def _es_constante_conservada(valor):
    return valor is None or valor is Ellipsis or isinstance(valor, bool)


def nombres_ligados(funcion):
    ligados = set()
    for nodo in ast.walk(funcion):
        if isinstance(nodo, ast.Name) and isinstance(nodo.ctx, (ast.Store, ast.Del)):
            ligados.add(nodo.id)
        elif isinstance(nodo, ast.arg):
            ligados.add(nodo.arg)
        elif isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if nodo is not funcion:
                ligados.add(nodo.name)
        elif isinstance(nodo, (ast.Global, ast.Nonlocal)):
            ligados.update(nodo.names)
        elif isinstance(nodo, ast.alias):
            ligados.add(nodo.asname or nodo.name.split(".")[0])
        elif isinstance(nodo, ast.ExceptHandler) and nodo.name:
            ligados.add(nodo.name)
        elif type(nodo).__name__ in ("MatchAs", "MatchStar") and nodo.name:
            ligados.add(nodo.name)
        elif type(nodo).__name__ == "MatchMapping" and nodo.rest:
            ligados.add(nodo.rest)
    return ligados


class Normalizador(ast.NodeTransformer):
    def __init__(self, funcion):
        self.raiz = funcion
        self.nombre_funcion = funcion.name
        self.ligados = nombres_ligados(funcion)
        self.tabla = {}   
        posicionales = funcion.args.posonlyargs + funcion.args.args
        self.primer_parametro = posicionales[0].arg if posicionales else None   

    def _var(self, nombre):
        if nombre not in self.tabla:
            self.tabla[nombre] = f"{PREFIJO_VAR}{len(self.tabla) + 1}"
        return self.tabla[nombre]

    def _identificador(self, nombre):
        if nombre in self.ligados:
            return self._var(nombre)
        if nombre == self.nombre_funcion:
            return FUNC             
        if nombre in BUILTINS:
            return nombre            
        return self._var(nombre)     

    def visit_Name(self, nodo):
        nodo.id = self._identificador(nodo.id)
        return nodo

    def visit_arg(self, nodo):
        nodo.annotation = None       
        nodo.arg = self._var(nodo.arg)
        return nodo

    def visit_Attribute(self, nodo):
        if (nodo.attr == self.nombre_funcion and isinstance(nodo.value, ast.Name)
                and nodo.value.id == self.primer_parametro):
            nodo.attr = FUNC
        return self.generic_visit(nodo)

    def _visitar_funcion(self, nodo):
        if nodo is self.raiz:
            nodo.name = FUNC
            nodo.decorator_list = []     
        else:
            nodo.name = self._identificador(nodo.name)   
        nodo.returns = None
        if hasattr(nodo, "type_params"):                 
            nodo.type_params = []
        return self.generic_visit(nodo)

    visit_FunctionDef = _visitar_funcion
    visit_AsyncFunctionDef = _visitar_funcion

    def visit_ClassDef(self, nodo):
        nodo.name = self._identificador(nodo.name)
        return self.generic_visit(nodo)

    def visit_ExceptHandler(self, nodo):
        if nodo.name:
            nodo.name = self._var(nodo.name)
        return self.generic_visit(nodo)

    def visit_Global(self, nodo):
        nodo.names = [self._var(n) for n in nodo.names]
        return nodo

    visit_Nonlocal = visit_Global

    def visit_alias(self, nodo):
        if nodo.asname:
            nodo.asname = self._var(nodo.asname)
        return nodo

    def visit_MatchAs(self, nodo):
        if nodo.name:
            nodo.name = self._var(nodo.name)
        return self.generic_visit(nodo)

    visit_MatchStar = visit_MatchAs

    def visit_MatchMapping(self, nodo):
        if nodo.rest:
            nodo.rest = self._var(nodo.rest)
        return self.generic_visit(nodo)

    def visit_Constant(self, nodo):
        if not _es_constante_conservada(nodo.value):
            nodo.value = LIT
            nodo.kind = None
        return nodo

    def visit_Expr(self, nodo):
        if isinstance(nodo.value, ast.Constant) and isinstance(nodo.value.value, str):
            return None
        return self.generic_visit(nodo)

    def visit_AnnAssign(self, nodo):
        if nodo.value is None:
            return None
        asignacion = ast.copy_location(ast.Assign(targets=[nodo.target], value=nodo.value), nodo)
        return self.generic_visit(asignacion)


def _rellenar_cuerpos_vacios(arbol):
    for nodo in ast.walk(arbol):
        if isinstance(getattr(nodo, "body", None), list) and not nodo.body:
            nodo.body = [ast.Pass()]


def normalizar_con_tabla(funcion):
    copia = copy.deepcopy(funcion)
    normalizador = Normalizador(copia)
    arbol = normalizador.visit(copia)
    _rellenar_cuerpos_vacios(arbol)
    return ast.fix_missing_locations(arbol), normalizador.tabla


def normalizar(funcion):
    return normalizar_con_tabla(funcion)[0]

_CAMPO_NOMBRE = {
    ast.Name: "id",
    ast.arg: "arg",
    ast.Attribute: "attr",
    ast.keyword: "arg",
    ast.FunctionDef: "name",
    ast.AsyncFunctionDef: "name",
    ast.ClassDef: "name",
    ast.ExceptHandler: "name",
    ast.ImportFrom: "module",
}


def etiqueta(nodo):
    tipo = type(nodo).__name__
    if isinstance(nodo, ast.Constant):
        detalle = nodo.value if isinstance(nodo.value, str) else repr(nodo.value)
    elif isinstance(nodo, (ast.Global, ast.Nonlocal)):
        detalle = ",".join(nodo.names)
    elif isinstance(nodo, ast.alias):
        detalle = nodo.name if not nodo.asname else f"{nodo.name}>{nodo.asname}"
    elif tipo in ("MatchAs", "MatchStar"):
        detalle = nodo.name
    elif tipo == "MatchMapping":
        detalle = nodo.rest
    else:
        campo = _CAMPO_NOMBRE.get(type(nodo))
        detalle = getattr(nodo, campo) if campo else None
    return tipo if detalle is None else f"{tipo}:{detalle}"


def serializar(arbol):
    tokens = []
    _preorden(arbol, tokens)
    return tokens


def _preorden(nodo, tokens):
    tokens.append(etiqueta(nodo))
    for campo, valor in ast.iter_fields(nodo):
        if isinstance(valor, list):
            hijos = [v for v in valor if isinstance(v, ast.AST)]
            delimitar = campo in CAMPOS_BLOQUE and bool(hijos)
            if delimitar:
                tokens.append(ABRE_BLOQUE)
            for hijo in hijos:
                _preorden(hijo, tokens)
            if delimitar:
                tokens.append(CIERRA_BLOQUE)
        elif isinstance(valor, ast.AST) and not isinstance(valor, ast.expr_context):
            _preorden(valor, tokens)


def tokens_de_funcion(nodo_funcion):
    return serializar(normalizar(nodo_funcion))


_INDICE_VAR = re.compile(rf"\b{PREFIJO_VAR}\d+\b")


def sin_indices(tokens):
    return [_INDICE_VAR.sub(PREFIJO_VAR, t) for t in tokens]