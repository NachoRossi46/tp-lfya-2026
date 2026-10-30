# Motor de búsqueda de funciones similares vía AST

Trabajo práctico de **Lenguajes Formales y Autómatas (UCSE, 2026)**.

Dado un directorio con archivos Python, la herramienta extrae todas las funciones,
representa cada una mediante su **árbol de sintaxis abstracta (AST) normalizado**
y busca cuáles son estructuralmente similares a una función dada: el mismo principio
que usan los detectores de código duplicado (PMD/CPD, SonarQube) o de similitud entre
entregas (MOSS, JPlag), a escala reducida.

Las decisiones de diseño, la métrica elegida, la calibración del umbral y las
limitaciones están en el [informe](INFORME.md) ([PDF](INFORME.pdf)).

## Requisitos

- Python ≥ 3.9 (usa sólo la biblioteca estándar; probado con 3.11).
- `pytest` para correr los tests: `pip install -r requirements.txt`.

## Uso

```bash
# Top-5 de funciones más parecidas a una función del repositorio
python buscar_similares.py --dir ./mi_repo --funcion archivo.py:mi_funcion --top 5

# Métodos: usar el nombre completo
python buscar_similares.py --dir ./mi_repo --funcion modelos.py:Clase.metodo

# Pegando el código de la función objetivo (o '-' para leerlo de stdin)
python buscar_similares.py --dir ./mi_repo --codigo "def f(xs): return sum(xs) / len(xs)"
python buscar_similares.py --dir ./mi_repo --codigo-archivo fragmento.py

# Reporte de todos los pares candidatos a duplicado del repositorio
python buscar_similares.py --dir ./mi_repo --duplicados
```

Opciones principales:

| Opción | Descripción |
|---|---|
| `--top K` | cantidad de resultados (default 5) |
| `--metrica` | `jaccard` (default), `levenshtein` o `combinada` |
| `-n N` | tamaño de los n-gramas de Jaccard (default 3) |
| `--umbral U` | score desde el cual se marca "candidata a duplicado" (default según métrica) |
| `--mostrar-normalizado` | muestra el renombrado, el AST normalizado (`ast.unparse`) y la secuencia de tokens |
| `--mostrar-codigo` | muestra el código de cada resultado |
| `--min-tokens T` | con `--duplicados`, ignora funciones triviales de menos de T tokens (default 20) |

### Ejemplo

El directorio [`ejemplos/repo_demo`](ejemplos/repo_demo) contiene funciones originales,
copias disfrazadas de ellas (`copiado/estadisticas_v2.py`), funciones no relacionadas y
un archivo en Python 2 que no parsea (se informa y se omite):

```text
$ python buscar_similares.py --dir ejemplos/repo_demo --funcion estadisticas.py:varianza --top 3
[aviso] se omite ejemplos/repo_demo/legacy_py2.py: SyntaxError: Missing parentheses in call to 'print'. ...
Repositorio: ejemplos/repo_demo  (22 funciones en 4 archivos)
Métrica:     Jaccard sobre 3-gramas  |  umbral de duplicado: 0.60
Objetivo:    estadisticas.py:12  varianza  (46 tokens)

   #  score  duplicado  ubicación                      función
   1  0.760  SI         copiado/estadisticas_v2.py:13  calcular_varianza
   2  0.294  -          copiado/estadisticas_v2.py:5   media_aritmetica
   3  0.294  -          estadisticas.py:4              promedio
```

Con `--mostrar-normalizado` se ve cada etapa aplicada a la función objetivo:

```text
$ python buscar_similares.py --dir ejemplos/repo_demo --funcion estadisticas.py:promedio --mostrar-normalizado
--- Renombrado ---
  numeros -> VAR1, total -> VAR2, n -> VAR3
--- AST normalizado (ast.unparse) ---
def FUNC(VAR1):
    VAR2 = 'LIT'
    for VAR3 in VAR1:
        VAR2 += VAR3
    return VAR2 / len(VAR1)
--- Secuencia pre-order ---
FunctionDef:FUNC arguments arg:VAR1 { Assign Name:VAR2 Constant:LIT For Name:VAR3 Name:VAR1 { AugAssign Name:VAR2 Add Name:VAR3 } Return BinOp Name:VAR2 Div Call Name:len Name:VAR1 }
```

## Estructura

```text
buscar_similares.py      punto de entrada (CLI)
buscador/
  extraccion.py          recorre el directorio, ast.parse, extrae FunctionDef/AsyncFunctionDef
  normalizacion.py       NodeTransformer (VARn, LIT, FUNC) y serialización pre-order
  similitud.py           n-gramas, Jaccard, Levenshtein normalizada
  motor.py               índice del repositorio, búsqueda top-K, reporte de duplicados
  cli.py                 argumentos y salida por consola
tests/                   suite de pytest (casos positivos y negativos en test_motor.py)
calibracion/             experimento reproducible que fija n, métrica y umbral
ejemplos/repo_demo/      repositorio de ejemplo
INFORME.md / .pdf        informe
```

## Tests

```bash
pip install -r requirements.txt
python -m pytest
```

Los casos pedidos por el enunciado están en [`tests/test_motor.py`](tests/test_motor.py):
`test_positivo_*` (clones con variables renombradas, líneas reordenadas y sentencias
agregadas) y `test_negativo_*` (funciones claramente distintas).

## Calibración

```bash
python calibracion/calibrar.py > calibracion/resultados.txt
```

Genera clones sintéticos de ~400 funciones de la biblioteca estándar y los compara con
pares de funciones distintas; de ahí salen el `n`, la métrica por defecto y el umbral
(resultados en [`calibracion/resultados.txt`](calibracion/resultados.txt))
