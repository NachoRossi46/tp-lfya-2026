# Clon tipo 2 de promedio(): nombres y docstring cambiados.
def media_aritmetica(datos):
    acumulador = 0
    for elemento in datos:
        acumulador += elemento
    return acumulador / len(datos)


# Clon tipo 3 de varianza(): variables renombradas y sentencias reordenadas.
def calcular_varianza(xs):
    cantidad = len(xs)
    acumulado = 0.0
    media = sum(xs) / len(xs)
    for x in xs:
        diferencia = x - media
        acumulado += diferencia * diferencia
    return acumulado / cantidad


# Clon tipo 3 de contar_pares(): una sentencia agregada (el print).
def cuantos_pares(lista):
    contador = 0
    for valor in lista:
        print("revisando", valor)
        if valor % 2 == 0:
            contador += 1
    return contador


# Clon tipo 2 de factorial(): la recursión usa el nuevo nombre.
def fact(k):
    if k <= 1:
        return 1
    return k * fact(k - 1)


# Clon tipo 4 (semántico) de promedio(): mismo resultado, otra estructura.
# La herramienta NO lo detecta como duplicado (ver limitaciones en el informe).
def promedio_funcional(numeros):
    return sum(numeros) / len(numeros)
