
def promedio(numeros):
    total = 0
    for n in numeros:
        total += n
    return total / len(numeros)


def varianza(valores):
    media = sum(valores) / len(valores)
    acumulado = 0.0
    for v in valores:
        diferencia = v - media
        acumulado += diferencia * diferencia
    cantidad = len(valores)
    return acumulado / cantidad


def contar_pares(numeros):
    cantidad = 0
    for n in numeros:
        if n % 2 == 0:
            cantidad += 1
    return cantidad


def maximo(numeros):
    mayor = numeros[0]
    for n in numeros[1:]:
        if n > mayor:
            mayor = n
    return mayor


def factorial(n):
    if n <= 1:
        return 1
    return n * factorial(n - 1)
