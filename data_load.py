#data_load.py

import os
import django
from faker import Faker
import random

# Configura el entorno Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "OurEvents.settings")
django.setup()

from servicios.models import Categoria, Producto, Comentario

# Inicializar Faker
fake = Faker('es_ES')

def populate():
    # Define las categorías
    categorias = [
        "Decoración de Globos",
        "Centros de Mesa",
        "Mesa de Dulces",
        "Estampado de Playeras"
    ]

    # Crea las categorías en la base de datos
    for nombre in categorias:
        Categoria.objects.get_or_create(nombre=nombre)

    # Define los productos para cada categoría
    productos = [
        {"nombre": "Globo Arco Iris", "categoria": "Decoración de Globos", "precio": 150.00},
        {"nombre": "Centro de Mesa Floral", "categoria": "Centros de Mesa", "precio": 200.00},
        {"nombre": "Mesa Dulce para 50 personas", "categoria": "Mesa de Dulces", "precio": 1000.00},
        {"nombre": "Playera Estampada Personalizada", "categoria": "Estampado de Playeras", "precio": 250.00}
    ]

    # Crea los productos en la base de datos
    for producto_data in productos:
        categoria = Categoria.objects.get(nombre=producto_data["categoria"])
        Producto.objects.get_or_create(
            nombre=producto_data["nombre"],
            categoria=categoria,
            precio=producto_data["precio"]
        )


def create_sample_comments():
    for _ in range(5):
        nombre = fake.name()
        comentario = fake.text(max_nb_chars=200)
        imagen = None
        rating = random.randint(1, 5)
        fecha = fake.date_between(start_date='-1y', end_date='today')  # Fecha aleatoria en el último año

        Comentario.objects.create(
            nombre=nombre,
            comentario=comentario,
            imagen=imagen,
            calificacion=rating,
            fecha=fecha
        )

if __name__ == "__main__":
    create_sample_comments()