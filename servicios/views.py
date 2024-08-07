# servicios/views.py

from django.shortcuts import render, redirect
from .models import Categoria, Producto, Comentario

def home(request):
    categorias = Categoria.objects.all()
    productos = Producto.objects.all()
    return render(request, 'home.html', {'categorias': categorias, 'productos': productos})

def catalogo(request):
    productos = Producto.objects.all()
    return render(request, 'catalogo.html', {'productos': productos})

def ver_comentarios(request):
    comentarios = Comentario.objects.all()
    return render(request, 'comentarios.html', {'comentarios': comentarios})

def capturar_comentarios(request):
    if request.method == 'POST':
        nombre = request.POST['nombre']
        comentario = request.POST['comentario']
        imagen = request.FILES.get('imagen')
        calificacion = request.POST['rating']
        Comentario.objects.create(nombre=nombre, comentario=comentario, imagen=imagen, calificacion=calificacion)
        return redirect('ver_comentarios')
    return render(request, 'comentarios.html')
