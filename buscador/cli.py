import argparse
import ast
import sys
from pathlib import Path
from .motor import METRICA_POR_DEFECTO, METRICAS, UMBRALES, ErrorBusqueda, Indice
from .normalizacion import normalizar_con_tabla
from .similitud import N_POR_DEFECTO

DESCRIPCION_METRICA = {
    "jaccard": "Jaccard sobre {n}-gramas",
    "levenshtein": "Levenshtein normalizada",
    "combinada": "promedio de Jaccard ({n}-gramas) y Levenshtein normalizada",
}


def crear_parser():
    p = argparse.ArgumentParser(
        prog="buscar_similares.py",
        description="Busca funciones estructuralmente similares comparando sus AST normalizados.",
        epilog="Ejemplo: python buscar_similares.py --dir ./mi_repo --funcion archivo.py:mi_funcion --top 5",
    )
    p.add_argument("--dir", required=True, type=Path, help="directorio (repositorio) donde buscar")

    objetivo = p.add_mutually_exclusive_group(required=True)
    objetivo.add_argument("--funcion", metavar="ARCHIVO:NOMBRE",
                          help="función objetivo, p. ej. utils.py:calcular o modelos.py:Clase.metodo")
    objetivo.add_argument("--codigo", metavar="CODIGO",
                          help="código de la función objetivo pegado como texto ('-' = leer de stdin)")
    objetivo.add_argument("--codigo-archivo", metavar="RUTA", type=Path,
                          help="archivo con el código de la función objetivo")
    objetivo.add_argument("--duplicados", action="store_true",
                          help="en lugar de buscar, listar todos los pares candidatos a duplicado")

    p.add_argument("--nombre", help="con --codigo/--codigo-archivo: qué función usar si hay varias")
    p.add_argument("--top", type=int, default=5, help="cantidad de resultados (default: 5)")
    p.add_argument("--metrica", choices=METRICAS, default=METRICA_POR_DEFECTO,
                   help=f"métrica de similitud (default: {METRICA_POR_DEFECTO})")
    p.add_argument("-n", "--ngramas", dest="n", type=int, default=N_POR_DEFECTO,
                   help=f"tamaño de los n-gramas para Jaccard (default: {N_POR_DEFECTO})")
    p.add_argument("--umbral", type=float,
                   help="score mínimo para considerar 'candidata a duplicado' (default según métrica: "
                        + ", ".join(f"{m}={u}" for m, u in UMBRALES.items()) + ")")
    p.add_argument("--min-tokens", type=int, default=20,
                   help="con --duplicados: ignorar funciones con menos tokens (default: 20)")
    p.add_argument("--mostrar-normalizado", action="store_true",
                   help="mostrar el AST normalizado (ast.unparse) y los tokens de la función objetivo")
    p.add_argument("--mostrar-codigo", action="store_true",
                   help="mostrar el código fuente de cada resultado")
    return p


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")   
    parser = crear_parser()
    args = parser.parse_args(argv)
    if args.top < 1:
        parser.error("--top debe ser >= 1")
    if args.n < 1:
        parser.error("-n/--ngramas debe ser >= 1")
    if args.umbral is not None and not 0 <= args.umbral <= 1:
        parser.error("--umbral debe estar entre 0 y 1")
    umbral = UMBRALES[args.metrica] if args.umbral is None else args.umbral

    errores = []
    try:
        indice = Indice.desde_directorio(args.dir, n=args.n, errores=errores)
    except NotADirectoryError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    for ruta, mensaje in errores:
        print(f"[aviso] se omite {ruta}: {mensaje}", file=sys.stderr)

    archivos = len({e.funcion.archivo for e in indice.entradas})
    print(f"Repositorio: {args.dir}  ({len(indice)} funciones en {archivos} archivos)")
    print(f"Métrica:     {DESCRIPCION_METRICA[args.metrica].format(n=args.n)}"
          f"  |  umbral de duplicado: {umbral:.2f}")

    if args.duplicados:
        imprimir_duplicados(indice.duplicados(args.metrica, umbral, args.min_tokens), umbral, args.min_tokens)
        return 0

    try:
        objetivo = resolver_objetivo(indice, args)
    except ErrorBusqueda as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    f = objetivo.funcion
    print(f"Objetivo:    {f.ubicacion}  {f.nombre_completo}  ({len(objetivo.tokens)} tokens)")
    if args.mostrar_normalizado:
        imprimir_normalizado(objetivo)
    resultados = indice.buscar(objetivo, top=args.top, metrica=args.metrica, umbral=umbral)
    imprimir_resultados(resultados, args.mostrar_codigo)
    return 0


def resolver_objetivo(indice, args):
    if args.funcion:
        return indice.buscar_funcion(args.funcion, args.dir)
    if args.codigo_archivo:
        try:
            codigo = args.codigo_archivo.read_text(encoding="utf-8")
        except OSError as e:
            raise ErrorBusqueda(f"no se pudo leer {args.codigo_archivo}: {e}") from e
    elif args.codigo == "-":
        codigo = sys.stdin.read()
    else:
        codigo = args.codigo
    return indice.desde_codigo(codigo, args.nombre)


def imprimir_normalizado(objetivo):
    arbol, tabla = normalizar_con_tabla(objetivo.funcion.nodo)
    print("\n--- Renombrado ---")
    print("  " + (", ".join(f"{orig} -> {var}" for orig, var in tabla.items()) or "(sin identificadores)"))
    print("--- AST normalizado (ast.unparse) ---")
    print(ast.unparse(arbol))
    print("--- Secuencia pre-order ---")
    print(" ".join(objetivo.tokens))


def imprimir_resultados(resultados, mostrar_codigo=False):
    print()
    if not resultados:
        print("El repositorio no tiene otras funciones para comparar.")
        return
    ancho = max(len("ubicación"), *(len(r.funcion.ubicacion) for r in resultados))
    print(f"  {'#':>2}  {'score':>5}  {'duplicado':9}  {'ubicación':{ancho}}  función")
    for i, r in enumerate(resultados, 1):
        marca = "SI" if r.es_duplicado else "-"
        print(f"  {i:>2}  {r.score:5.3f}  {marca:9}  {r.funcion.ubicacion:{ancho}}  {r.funcion.nombre_completo}")
        if mostrar_codigo:
            print("\n" + "\n".join("        " + linea for linea in r.funcion.codigo.splitlines()) + "\n")


def imprimir_duplicados(pares, umbral, min_tokens):
    print(f"\nPares candidatos a duplicado (score >= {umbral:.2f}, funciones de >= {min_tokens} tokens): {len(pares)}")
    if not pares:
        return
    columna_a = [f"{a.ubicacion} {a.nombre_completo}" for a, _, _ in pares]
    ancho = max(len("función A"), *(len(c) for c in columna_a))
    print(f"  {'score':>5}  {'función A':{ancho}}  función B")
    for (a, b, score), texto_a in zip(pares, columna_a):
        print(f"  {score:5.3f}  {texto_a:{ancho}}  {b.ubicacion} {b.nombre_completo}")
