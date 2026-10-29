import asyncio
import json

class Producto:
    def __init__(self, nombre, precio, stock=0):
        self.nombre = nombre
        self.precio = precio
        self.stock = stock

    def valor_total(self):
        return self.precio * self.stock


class Inventario:
    def __init__(self):
        self.productos = {}

    def agregar(self, producto):
        if producto.nombre in self.productos:
            raise ValueError(f"ya existe {producto.nombre}")
        self.productos[producto.nombre] = producto

    def valor_total(self):
        total = 0
        for producto in self.productos.values():
            total += producto.valor_total()
        return total

    def sin_stock(self):
        faltantes = []
        for nombre, producto in self.productos.items():
            if producto.stock == 0:
                faltantes.append(nombre)
        return faltantes

    def guardar(self, ruta):
        datos = {n: {"precio": p.precio, "stock": p.stock} for n, p in self.productos.items()}
        with open(ruta, "w", encoding="utf-8") as archivo:
            json.dump(datos, archivo, indent=2)


async def cargar_precios(proveedores):
    precios = {}
    for proveedor in proveedores:
        await asyncio.sleep(0)
        precios[proveedor] = len(proveedor) * 10
    return precios
