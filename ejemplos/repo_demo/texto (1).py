VOCALES = "aeiouáéíóú"

def invertir_palabras(frase):
    palabras = frase.split()
    palabras.reverse()
    return " ".join(palabras)


def es_palindromo(texto):
    limpio = "".join(c.lower() for c in texto if c.isalnum())
    return limpio == limpio[::-1]


def contar_vocales(texto):
    return sum(1 for c in texto.lower() if c in VOCALES)


def capitalizar_titulo(titulo, excepciones=("de", "la", "el", "y")):
    resultado = []
    for i, palabra in enumerate(titulo.lower().split()):
        if i > 0 and palabra in excepciones:
            resultado.append(palabra)
        else:
            resultado.append(palabra.capitalize())
    return " ".join(resultado)
