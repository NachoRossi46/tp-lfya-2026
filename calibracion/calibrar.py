import argparse
import ast
import bisect
import copy
import random
import statistics
import sys
import sysconfig
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from buscador.extraccion import extraer_de_archivo, extraer_de_directorio   
from buscador.motor import Indice                                          
from buscador.normalizacion import nombres_ligados, sin_indices, tokens_de_funcion   
from buscador.similitud import jaccard, ngramas, similitud_levenshtein      

PAQUETES = ["json", "email", "http", "asyncio", "logging", "xml", "concurrent",
            "importlib", "unittest", "urllib"]
MODULOS = ["argparse.py", "csv.py", "difflib.py", "textwrap.py", "pathlib.py",
           "shutil.py", "tarfile.py", "zipfile.py", "statistics.py", "fractions.py"]


class _Renombrar(ast.NodeTransformer):
    def __init__(self, funcion, rng):
        self.rng = rng
        self.nombre_funcion = funcion.name
        self.renombrables = nombres_ligados(funcion)
        for n in ast.walk(funcion):      
            if isinstance(n, ast.alias) and not n.asname:
                self.renombrables.discard(n.name.split(".")[0])
        self.tabla = {}

    def _nuevo(self, x):
        if x == self.nombre_funcion and x not in self.renombrables:
            return "funcion_renombrada"
        if x not in self.renombrables:
            return x
        if x not in self.tabla:
            self.tabla[x] = "v_" + "".join(self.rng.choice("abcdefghij") for _ in range(6))
        return self.tabla[x]

    def visit_Name(self, n):
        n.id = self._nuevo(n.id)
        return n

    def visit_arg(self, n):
        n.arg = self._nuevo(n.arg)
        return n

    def visit_FunctionDef(self, n):
        n.name = self._nuevo(n.name)
        return self.generic_visit(n)

    visit_AsyncFunctionDef = visit_ClassDef = visit_FunctionDef

    def visit_ExceptHandler(self, n):
        if n.name:
            n.name = self._nuevo(n.name)
        return self.generic_visit(n)

    def visit_Global(self, n):
        n.names = [self._nuevo(x) for x in n.names]
        return n

    visit_Nonlocal = visit_Global

    def visit_alias(self, n):
        if n.asname:
            n.asname = self._nuevo(n.asname)
        return n

    def visit_Constant(self, n):
        if isinstance(n.value, bool) or n.value is None:
            return n
        if isinstance(n.value, (int, float)):
            n.value = self.rng.randint(0, 999)
        elif isinstance(n.value, str):
            n.value = "otro texto"
        return n


def renombrar(f, rng):
    f = copy.deepcopy(f)
    f = _Renombrar(f, rng).visit(f)
    f.name = "funcion_renombrada"
    return f


def reordenar(f, rng):
    f = copy.deepcopy(f)
    i = rng.randrange(len(f.body) - 1)
    f.body[i], f.body[i + 1] = f.body[i + 1], f.body[i]
    return f


def mover(f, rng):
    f = copy.deepcopy(f)
    i = rng.randrange(len(f.body))
    sentencia = f.body.pop(i)
    j = rng.choice([k for k in range(len(f.body) + 1) if k != i])
    f.body.insert(j, sentencia)
    return f


def insertar_var(f, rng):
    f = copy.deepcopy(f)
    f.body.insert(0, ast.parse("contador_extra = 0").body[0])
    return f


def insertar(f, rng):
    f = copy.deepcopy(f)
    nueva = ast.parse("print('debug', resultado)").body[0]
    f.body.insert(rng.randrange(len(f.body) + 1), nueva)
    return f


def borrar(f, rng):
    f = copy.deepcopy(f)
    del f.body[rng.randrange(len(f.body))]
    return f


def combinado(f, rng):
    return insertar(mover(renombrar(f, rng), rng), rng)


MUTACIONES = {"renombrar": renombrar, "reordenar": reordenar, "mover": mover,
              "insertar": insertar, "insertar_var": insertar_var, "borrar": borrar,
              "combinado": combinado}
TIPO3 = [m for m in MUTACIONES if m != "renombrar"]

def cargar_corpus(lib):
    funciones = []
    for paquete in PAQUETES:
        funciones += extraer_de_directorio(lib / paquete, errores=[])
    for modulo in MODULOS:
        funciones += extraer_de_archivo(lib / modulo, lib)
    return funciones


def scores(t1, t2, ns):
    lev = similitud_levenshtein(t1, t2)
    r = {"lev": lev}
    a1, a2 = sin_indices(t1), sin_indices(t2)
    for n in ns:
        r[f"jac{n}"] = jaccard(ngramas(a1, n), ngramas(a2, n))
    for n in (2, 3):
        r[f"comb{n}"] = (r[f"jac{n}"] + lev) / 2
    return r


def umbral_para_fpr(valores_neg, fpr_max):
    for u in [x / 100 for x in range(1, 101)]:
        if sum(v >= u for v in valores_neg) / len(valores_neg) <= fpr_max:
            return u
    return 1.0


def auc(pos, neg):
    neg = sorted(neg)
    total = sum(bisect.bisect_left(neg, p) + 0.5 * (bisect.bisect_right(neg, p) - bisect.bisect_left(neg, p))
                for p in pos)
    return total / (len(pos) * len(neg))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lib", type=Path, default=Path(sysconfig.get_paths()["stdlib"]))
    ap.add_argument("--semilla", type=int, default=2026)
    ap.add_argument("--muestra", type=int, default=400, help="funciones a mutar")
    ap.add_argument("--consultas", type=int, default=15, help="consultas de búsqueda por tipo de clon")
    args = ap.parse_args()
    rng = random.Random(args.semilla)
    t0 = time.time()

    corpus = cargar_corpus(args.lib)
    datos = [(f, tokens_de_funcion(f.nodo)) for f in corpus]
    grandes = [(f, t) for f, t in datos if len(t) >= 30 and len(f.nodo.body) >= 3]
    print(f"Python {sys.version.split()[0]} - stdlib en {args.lib}")
    print(f"Corpus: {len(corpus)} funciones; con >= 30 tokens y >= 3 sentencias: {len(grandes)}")

    # 1) Positivos
    ns = [1, 2, 3, 4, 5, 6]
    muestra = rng.sample(grandes, min(args.muestra, len(grandes)))
    positivos = {m: [] for m in MUTACIONES}
    exactos = 0
    for f, t in muestra:
        for nombre, mutar in MUTACIONES.items():
            t2 = tokens_de_funcion(mutar(f.nodo, rng))
            positivos[nombre].append(scores(t, t2, ns))
            if nombre == "renombrar" and t2 == t:
                exactos += 1
    print(f"\nClones 'renombrar' con secuencia normalizada IDÉNTICA al original: {exactos}/{len(muestra)}")

    # 2) Negativos: pares distintos del mismo archivo
    por_archivo = {}
    for f, t in grandes:
        por_archivo.setdefault(f.archivo, []).append((f, t))
    negativos = []
    for lista in por_archivo.values():
        for i, (f1, t1) in enumerate(lista):
            for f2, t2 in lista[i + 1:]:
                if f1.nombre != f2.nombre and f1.codigo.strip() != f2.codigo.strip():
                    negativos.append(scores(t1, t2, ns))
    print(f"Negativos (pares de funciones distintas del mismo archivo): {len(negativos)}")

    metricas = [f"jac{n}" for n in ns] + ["lev", "comb2", "comb3"]
    print("\nTabla 1 - Mediana del score por tipo de clon y en negativos")
    print("métrica  " + "".join(f"{m:>13s}" for m in MUTACIONES) + "  negativos(p50/p99)")
    for m in metricas:
        fila = "".join(f"{statistics.median(s[m] for s in positivos[k]):13.2f}" for k in MUTACIONES)
        nv = sorted(s[m] for s in negativos)
        print(f"{m:8s} {fila}   {nv[len(nv) // 2]:.2f} / {nv[int(len(nv) * .99)]:.2f}")

    print("\nTabla 2 - Umbral con FPR <= 1% sobre negativos y recall de clones tipo 3 con ese umbral")
    print("métrica  umbral  recall  " + "".join(f"{m:>13s}" for m in TIPO3) + "    AUC")
    pos3 = [s for k in TIPO3 for s in positivos[k]]
    for m in metricas:
        nv = [s[m] for s in negativos]
        u = umbral_para_fpr(nv, 0.01)
        rec = sum(s[m] >= u for s in pos3) / len(pos3)
        por_tipo = "".join(f"{sum(s[m] >= u for s in positivos[k]) / len(positivos[k]):13.2f}" for k in TIPO3)
        print(f"{m:8s} {u:6.2f}  {rec:6.3f}  {por_tipo}  {auc([s[m] for s in pos3], nv):.3f}")

    # 3) Búsqueda: ¿el original aparece #1 al buscar su clon entre TODO el corpus?
    print(f"\nTabla 3 - Recuperación: se busca cada clon entre las {len(corpus)} funciones del corpus")
    consultas = []
    for f, t in rng.sample(muestra, min(args.consultas, len(muestra))):
        for nombre in TIPO3:
            consultas.append((nombre, f, mutar_y_envolver(f, MUTACIONES[nombre], rng)))
    print(f"{len(consultas)} consultas")
    print("config        top-1   top-5   " + "".join(f"{m:>13s}" for m in TIPO3) + "   seg/consulta")
    for metrica, n in [("jaccard", 2), ("jaccard", 3), ("jaccard", 4), ("levenshtein", 3),
                       ("combinada", 3)]:
        t1 = time.time()
        indice = Indice(corpus, n=n)
        top1 = {k: 0 for k in TIPO3}
        top5 = 0
        for nombre, original, clon in consultas:
            res = indice.buscar(indice.indexar(clon), top=5, metrica=metrica)
            claves = [(r.funcion.archivo, r.funcion.linea) for r in res]
            objetivo = (original.archivo, original.linea)
            top1[nombre] += claves[:1] == [objetivo]
            top5 += objetivo in claves
        por_tipo = "".join(f"{top1[k] / (len(consultas) / len(TIPO3)):13.2f}" for k in TIPO3)
        etiqueta = f"{metrica}" + (f" n={n}" if metrica != "levenshtein" else "")
        print(f"{etiqueta:13s} {sum(top1.values()) / len(consultas):5.3f}   {top5 / len(consultas):5.3f}  "
              f"{por_tipo}  {(time.time() - t1) / len(consultas):8.2f}")
    print(f"\nTiempo total: {time.time() - t0:.0f} s")


def mutar_y_envolver(funcion, mutar, rng):
    clon = copy.copy(funcion)
    clon.nodo = mutar(funcion.nodo, rng)
    clon.archivo, clon.linea = "<clon>", 0
    return clon


if __name__ == "__main__":
    main()
