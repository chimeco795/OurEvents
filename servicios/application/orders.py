from decimal import Decimal
from uuid import UUID
from django.core.exceptions import ValidationError, PermissionDenied
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from servicios.models import Orden, OrdenDetalle, Producto, Proveedor
from servicios.permissions import proveedores_administrables
from servicios.domain.orders import acciones, RESERVADOS
from servicios.queries import categorias_visibles
from servicios.application.notifications import crear_notificacion, administradores


def exigir_usuario(usuario):
    if not usuario.is_authenticated or not usuario.is_active:
        raise PermissionDenied


def es_gestor(usuario, proveedor_id):
    return proveedores_administrables(usuario).filter(pk=proveedor_id).exists()


def puede_ver(usuario, orden):
    return usuario.is_authenticated and usuario.is_active and (orden.comprador_id == usuario.pk or es_gestor(usuario, orden.proveedor_id))


def precio_actual(producto):
    return producto.precio_promocional if producto.precio_promocional is not None else producto.precio


@transaction.atomic
def crear_orden(usuario, proveedor_id, cantidades, clave, notas=''):
    exigir_usuario(usuario)
    try:
        clave = UUID(str(clave))
    except (ValueError, TypeError, AttributeError):
        raise ValidationError('Solicitud inválida. Actualiza la página.')
    existente = Orden.objects.filter(clave_solicitud=clave).first()
    if existente:
        if existente.comprador_id != usuario.pk or existente.proveedor_id != proveedor_id:
            raise PermissionDenied
        return existente
    if not cantidades or len(cantidades) > 100:
        raise ValidationError('Agrega entre 1 y 100 productos a tu solicitud.')
    if any(type(pk) is not int or pk < 1 for pk in cantidades):
        raise ValidationError('Los productos de la solicitud no son válidos.')
    if any(type(cantidad) is not int or not 1 <= cantidad <= 999 for cantidad in cantidades.values()):
        raise ValidationError('La cantidad debe estar entre 1 y 999.')
    proveedor = Proveedor.objects.select_for_update().get(pk=proveedor_id)
    existente = Orden.objects.filter(clave_solicitud=clave).first()
    if existente:
        if existente.comprador_id != usuario.pk or existente.proveedor_id != proveedor_id:
            raise PermissionDenied
        return existente
    if proveedor.estado != Proveedor.Estado.ACTIVO:
        raise ValidationError('El proveedor no está disponible.')
    visibles = set(categorias_visibles())
    productos = list(Producto.objects.select_for_update().filter(pk__in=cantidades, proveedor=proveedor).select_related('categoria').order_by('pk'))
    if len(productos) != len(cantidades) or any(not p.activo or p.categoria_id not in visibles for p in productos):
        raise ValidationError('Uno de los productos ya no está disponible en este negocio.')
    subtotal = sum((precio_actual(p) * cantidades[p.pk] for p in productos), Decimal('0'))
    if subtotal > Decimal('999999999999.99'):
        raise ValidationError('El subtotal excede el límite de una orden. Divide la solicitud.')
    orden = Orden.objects.create(comprador=usuario, proveedor=proveedor, subtotal=subtotal, clave_solicitud=clave, notas_comprador=notas[:3000])
    OrdenDetalle.objects.bulk_create([OrdenDetalle(orden=orden, producto=p, nombre_producto_historico=p.nombre, cantidad=cantidades[p.pk], precio_unitario=precio_actual(p), subtotal=precio_actual(p)*cantidades[p.pk]) for p in productos])
    crear_notificacion(administradores(proveedor), 'nueva_orden', 'Nueva orden recibida', f'{orden.folio}: revisa los productos solicitados.', f'/ordenes/{orden.pk}/', correo=True)
    return orden


@transaction.atomic
def cambiar_estado(usuario, orden_id, destino, notas=''):
    exigir_usuario(usuario)
    orden = Orden.objects.select_for_update().select_related('proveedor').get(pk=orden_id)
    gestor = es_gestor(usuario, orden.proveedor_id)
    if not gestor and orden.comprador_id != usuario.pk:
        raise PermissionDenied
    if destino not in acciones(orden.estado, gestor):
        raise ValidationError('Esta transición ya no está disponible. Actualiza la orden.')
    previo = orden.estado
    # CAS complementa el bloqueo: una transición no se aplica dos veces.
    if not Orden.objects.filter(pk=orden.pk, estado=previo).update(estado=destino, fecha_modificacion=timezone.now()):
        raise ValidationError('Otra persona actualizó esta orden.')
    detalles = list(orden.detalles.order_by('producto_id'))
    if destino == Orden.Estado.ACEPTADA:
        for detalle in detalles:
            cambiado = Producto.objects.filter(pk=detalle.producto_id, proveedor=orden.proveedor, proveedor__estado='activo', activo=True, categoria_id__in=categorias_visibles(), stock__gte=detalle.cantidad).update(stock=F('stock')-detalle.cantidad, fecha_modificacion=timezone.now())
            if not cambiado:
                raise ValidationError(f'Stock insuficiente o producto inactivo: {detalle.nombre_producto_historico}.')
    elif destino == Orden.Estado.CANCELADA and previo in RESERVADOS:
        for detalle in detalles:
            Producto.objects.filter(pk=detalle.producto_id).update(stock=F('stock')+detalle.cantidad, fecha_modificacion=timezone.now())
    orden.estado = destino
    if gestor and notas:
        orden.notas_proveedor = notas[:3000]
        orden.save(update_fields=['notas_proveedor'])
    destinatarios = [orden.comprador_id] if gestor else administradores(orden.proveedor)
    crear_notificacion(destinatarios, 'orden_' + destino.lower(), f'Orden {orden.get_estado_display().lower()}', f'{orden.folio} cambió a {orden.get_estado_display()}.', f'/ordenes/{orden.pk}/')
    return orden


def aceptar_orden(usuario, orden_id):
    return cambiar_estado(usuario, orden_id, 'ACEPTADA')


def rechazar_orden(usuario, orden_id):
    return cambiar_estado(usuario, orden_id, 'RECHAZADA')


def cancelar_orden(usuario, orden_id):
    return cambiar_estado(usuario, orden_id, 'CANCELADA')


def completar_orden(usuario, orden_id):
    return cambiar_estado(usuario, orden_id, 'COMPLETADA')
