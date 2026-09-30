"""Carga opcional e idempotente de un catálogo de demostración inactivo."""
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'OurEvents.settings')
import django
django.setup()
from servicios.models import Categoria, Producto, Proveedor


def populate():
    proveedor, _ = Proveedor.objects.get_or_create(slug='negocio-demo', defaults={'nombre': 'Negocio demo'})
    for nombre, precio in [('Decoración de Globos', '150.00'), ('Centros de Mesa', '200.00'), ('Mesa de Dulces', '1000.00'), ('Estampado de Playeras', '250.00')]:
        categoria, _ = Categoria.objects.get_or_create(nombre=nombre)
        Producto.objects.get_or_create(proveedor=proveedor, nombre=nombre, defaults={'categoria': categoria, 'precio': precio, 'descripcion': 'Producto de demostración', 'stock': 0})

if __name__ == '__main__':
    populate()
