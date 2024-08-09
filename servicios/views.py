from django.shortcuts import render, redirect
from .models import Categoria, Producto, Comentario
from django.db.models import Avg, Count
from django.core.mail import send_mail
from django.contrib import messages
from django.http import HttpResponse

def contacto(request):
    if request.method == 'POST':
        nombre = request.POST.get('nombre')
        correo = request.POST.get('correo')  # Cambiado a 'correo'
        telefono = request.POST.get('telefono')
        asunto = request.POST.get('asunto')
        mensaje = request.POST.get('mensaje')
        whatsapp = request.POST.get('whatsapp')

        # Aquí puedes agregar la lógica para enviar el correo, guardar en base de datos, etc.
        send_mail(
            asunto,
            mensaje,
            correo,
            ['destinatario@ourevents.com'],  # Cambia esto por la dirección de correo a la que deseas enviar el mensaje
        )

        return HttpResponse('Gracias por contactarnos. Te responderemos pronto.')

    return render(request, 'contacto.html')



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
    return render(request, 'comentarios/comentarios.html', context)

def capturar_comentarios(request):
    if request.method == 'POST':
        nombre = request.POST['nombre']
        comentario = request.POST['comentario']
        imagen = request.FILES.get('imagen')
        calificacion = request.POST['rating']
        Comentario.objects.create(nombre=nombre, comentario=comentario, imagen=imagen, calificacion=calificacion)
        return redirect('ver_comentarios')
    return render(request, 'capturar_comentarios.html')



def contacto(request):
    if request.method == 'POST':
        nombre = request.POST.get('nombre')
        correo = request.POST.get('correo')  # Cambiado a 'correo'
        telefono = request.POST.get('telefono')
        asunto = request.POST.get('asunto')
        mensaje = request.POST.get('mensaje')
        whatsapp = request.POST.get('whatsapp')

        # Aquí puedes agregar la lógica para enviar el correo, guardar en base de datos, etc.
        send_mail(
            asunto,
            mensaje,
            correo,
            ['destinatario@ourevents.com'],  # Cambia esto por la dirección de correo a la que deseas enviar el mensaje
        )

        return HttpResponse('Gracias por contactarnos. Te responderemos pronto.')

    return render(request, 'contacto.html')


def send_test_email(request):
    send_mail(
        'Prueba de correo electrónico',
        'Este es un correo de prueba enviado desde Django.',
        'chimecoo@gmail.com',  # De
        ['cars795@hotmail.com'],  # Para
        fail_silently=False,
    )
    return HttpResponse('Correo enviado con éxito.')
