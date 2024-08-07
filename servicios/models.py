#models.py

from django.db import models
from datetime import date


class Categoria(models.Model):
    nombre = models.CharField(max_length=100)

    def __str__(self):
        return self.nombre

class Producto(models.Model):
    categoria = models.ForeignKey(Categoria, on_delete=models.CASCADE)
    nombre = models.CharField(max_length=100)
    descripcion = models.TextField()
    precio = models.DecimalField(max_digits=10, decimal_places=2)
    imagen = models.ImageField(upload_to='productos/')

    def __str__(self):
        return self.nombre

class Comentario(models.Model):
    nombre = models.CharField(max_length=100)
    comentario = models.TextField()
    imagen = models.ImageField(upload_to='comentarios/', blank=True, null=True)
    calificacion = models.PositiveIntegerField()
    fecha = models.DateField()