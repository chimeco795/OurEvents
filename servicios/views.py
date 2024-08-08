from django.shortcuts import render, redirect
from .models import Categoria, Producto, Comentario
from django.db.models import Avg, Count

def home(request):
    categorias = Categoria.objects.all()
    productos = Producto.objects.all()
    return render(request, 'home.html', {'categorias': categorias, 'productos': productos})

def catalogo(request):
    productos = Producto.objects.all()
    return render(request, 'catalogo.html', {'productos': productos})

def ver_comentarios(request):
    comentarios = Comentario.objects.all()
    promedio = comentarios.aggregate(Avg('calificacion'))['calificacion__avg'] or 0
    total_comentarios = comentarios.count()
    estrellas = comentarios.values('calificacion').annotate(count=Count('calificacion')).order_by('-calificacion')

    porcentaje_estrellas = {str(i): 0 for i in range(1, 6)}
    for estrella in estrellas:
        porcentaje_estrellas[str(estrella['calificacion'])] = (estrella['count'] / total_comentarios) * 100

    context = {
        'comentarios': comentarios,
        'promedio': promedio,
        'porcentaje_estrellas': porcentaje_estrellas
    }
    return render(request, 'comentarios.html', context)

def capturar_comentarios(request):
    if request.method == 'POST':
        nombre = request.POST['nombre']
        comentario = request.POST['comentario']
        imagen = request.FILES.get('imagen')
        calificacion = request.POST['rating']
        Comentario.objects.create(nombre=nombre, comentario=comentario, imagen=imagen, calificacion=calificacion)
        return redirect('ver_comentarios')
    return render(request, 'capturar_comentarios.html')
