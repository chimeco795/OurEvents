from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from servicios.models import Producto, Proveedor
from servicios.permissions import obtener_proveedor
from servicios.application.memberships import validar_producto


@transaction.atomic
def guardar_producto(usuario, form, imagenes):
    proveedor = obtener_proveedor(usuario, form.instance.proveedor_id)
    Proveedor.objects.select_for_update().get(pk=proveedor.pk)
    if form.instance.pk:
        actual = Producto.objects.select_for_update().get(pk=form.instance.pk)
        if form.cleaned_data.get('stock_anterior') != actual.stock:
            raise ValidationError('El inventario cambió mientras editabas. Recarga el producto antes de guardar.')
    validar_producto(form.instance)
    producto = form.save()
    producto.imagenes.filter(principal=True).update(principal=False)
    for imagen_form in imagenes.forms:
        datos = imagen_form.cleaned_data
        if datos and not datos.get('DELETE'):
            imagen = imagen_form.save(commit=False)
            if imagen.imagen:
                imagen.producto = producto
                imagen.save()
        elif datos.get('DELETE') and imagen_form.instance.pk:
            imagen_form.instance.delete()
    return producto


@transaction.atomic
def actualizar_stock(usuario, proveedor_id, producto_id, stock, stock_minimo, stock_anterior):
    proveedor = obtener_proveedor(usuario, proveedor_id)
    if not Producto.objects.filter(pk=producto_id, proveedor=proveedor, stock=stock_anterior).update(stock=stock, stock_minimo=stock_minimo, fecha_modificacion=timezone.now()):
        raise ValidationError('El inventario cambió mientras editabas. Actualiza la página antes de guardar.')
