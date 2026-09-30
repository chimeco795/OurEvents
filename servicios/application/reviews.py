from django.core.exceptions import ValidationError, PermissionDenied
from django.db import transaction
from django.utils import timezone
from servicios.models import Orden, OpinionProducto, OpinionProveedor
from servicios.application.orders import exigir_usuario, es_gestor
from servicios.application.notifications import crear_notificacion, administradores


@transaction.atomic
def crear_opinion(usuario, orden_id, estrellas, comentario, producto_id=None):
    exigir_usuario(usuario)
    orden = Orden.objects.select_for_update().select_related('proveedor').get(pk=orden_id)
    if orden.comprador_id != usuario.pk:
        raise PermissionDenied
    if orden.estado != 'COMPLETADA':
        raise ValidationError('Puedes opinar cuando la orden esté completada.')
    valores = dict(usuario=usuario, orden=orden, estrellas=estrellas, comentario=comentario)
    opinion = OpinionProducto(producto_id=producto_id, **valores) if producto_id else OpinionProveedor(proveedor=orden.proveedor, **valores)
    opinion.full_clean()
    opinion.save()
    crear_notificacion(administradores(orden.proveedor), 'nueva_opinion', 'Nueva opinión verificada', comentario[:250], f'/gestion/{orden.proveedor_id}/opiniones/')
    return opinion


def crear_opinion_producto(usuario, orden_id, producto_id, estrellas, comentario):
    return crear_opinion(usuario, orden_id, estrellas, comentario, producto_id)


def crear_opinion_proveedor(usuario, orden_id, estrellas, comentario):
    return crear_opinion(usuario, orden_id, estrellas, comentario)


@transaction.atomic
def responder_opinion(usuario, tipo, opinion_id, respuesta):
    exigir_usuario(usuario)
    modelo = OpinionProducto if tipo == 'producto' else OpinionProveedor
    opinion = modelo.objects.select_for_update().select_related('orden').get(pk=opinion_id)
    if not es_gestor(usuario, opinion.orden.proveedor_id):
        raise PermissionDenied
    if opinion.respuesta:
        raise ValidationError('Esta opinión ya tiene respuesta.')
    if not respuesta.strip() or len(respuesta) > 3000:
        raise ValidationError('Escribe una respuesta entre 1 y 3000 caracteres.')
    opinion.respuesta = respuesta.strip()
    opinion.fecha_respuesta = timezone.now()
    opinion.save(update_fields=['respuesta', 'fecha_respuesta'])
    crear_notificacion([opinion.usuario_id], 'respuesta_opinion', 'El proveedor respondió tu opinión', opinion.respuesta[:250], f'/ordenes/{opinion.orden_id}/')
    return opinion
