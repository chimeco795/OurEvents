from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.mail import EmailMessage
from django.db import transaction
from django.db.models import Avg, Count
from django.shortcuts import render, redirect, get_object_or_404
from .models import Categoria, Producto, Comentario, Proveedor
from .forms import ProductoForm, ProveedorForm, ImagenFormSet, ComentarioForm, ContactoForm
from .permissions import obtener_proveedor, proveedores_administrables


def ver_comentarios(request):
    comentarios = Comentario.objects.all()
    total = comentarios.count()
    porcentajes = {str(i): 0 for i in range(1, 6)}
    for item in comentarios.values('calificacion').annotate(count=Count('pk')):
        porcentajes[str(item['calificacion'])] = item['count'] / total * 100
    return render(request, 'comentarios/comentarios.html', {'comentarios': comentarios, 'promedio': comentarios.aggregate(Avg('calificacion'))['calificacion__avg'] or 0, 'porcentaje_estrellas': porcentajes})


@login_required
def capturar_comentarios(request):
    form = ComentarioForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        comentario = form.save(commit=False)
        comentario.nombre = request.user.get_username()
        comentario.save()
        return redirect('ver_comentarios')
    return render(request, 'gestion/formulario.html', {'form': form, 'titulo': 'Comentario general (no verificado)'})


@login_required
def contacto(request):
    form = ContactoForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        if settings.CONTACT_EMAIL:
            EmailMessage(form.cleaned_data['asunto'], form.cleaned_data['mensaje'], settings.DEFAULT_FROM_EMAIL, [settings.CONTACT_EMAIL], reply_to=[form.cleaned_data['correo']]).send()
            messages.success(request, 'Mensaje enviado.')
            return redirect('contacto')
        form.add_error(None, 'El canal de contacto no está configurado todavía.')
    return render(request, 'gestion/formulario.html', {'form': form, 'titulo': 'Contacto'})


@login_required
def perfil_usuario(request):
    return redirect('cuenta')


@login_required
def negocios(request):
    return render(request, 'gestion/negocios.html', {'proveedores': proveedores_administrables(request.user)})


@login_required
def productos(request, proveedor_id):
    proveedor = obtener_proveedor(request.user, proveedor_id)
    from .marketplace_views import paginar
    return render(request, 'gestion/productos.html', {'proveedor': proveedor, 'page_obj': paginar(request, proveedor.productos.select_related('proveedor', 'categoria').order_by('nombre'))})


@login_required
def editar_negocio(request, proveedor_id):
    proveedor = obtener_proveedor(request.user, proveedor_id)
    form = ProveedorForm(request.POST or None, request.FILES or None, instance=proveedor)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Datos actualizados.')
        return redirect('gestion_productos', proveedor_id=proveedor.pk)
    return render(request, 'gestion/formulario.html', {'form': form, 'titulo': 'Datos del negocio'})


@login_required
def editar_producto(request, proveedor_id, producto_id=None):
    proveedor = obtener_proveedor(request.user, proveedor_id)
    producto = get_object_or_404(proveedor.productos, pk=producto_id) if producto_id else Producto(proveedor=proveedor)
    form = ProductoForm(request.POST or None, request.FILES or None, instance=producto)
    imagenes = ImagenFormSet(request.POST or None, request.FILES or None, instance=producto)
    if request.method == 'POST':
        valido = form.is_valid()
        imagenes_validas = imagenes.is_valid()
        if valido and imagenes_validas:
            from .application.catalog import guardar_producto
            from django.core.exceptions import ValidationError
            try:
                guardar_producto(request.user, form, imagenes)
            except ValidationError as exc:
                form.add_error(None, exc)
                return render(request, 'gestion/formulario.html', {'form': form, 'imagenes': imagenes, 'titulo': 'Producto'})
            messages.success(request, 'Producto guardado.')
            return redirect('gestion_productos', proveedor_id=proveedor.pk)
    return render(request, 'gestion/formulario.html', {'form': form, 'imagenes': imagenes, 'titulo': 'Producto'})
