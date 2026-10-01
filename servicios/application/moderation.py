"""Reportes de contenido y decisiones de moderación con auditoría."""
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.shortcuts import get_object_or_404
from servicios.models import ReporteContenido, OpinionProducto, OpinionProveedor
from servicios.queries import productos_publicos, proveedores_publicos
from servicios.application.providers import exigir_superusuario, auditar, administrar_proveedor
from servicios.application.orders import exigir_usuario
from servicios.application.notifications import crear_notificacion


def objeto_reportable(tipo, pk):
    consultas = {
        'producto': productos_publicos,
        'proveedor': proveedores_publicos,
        'opinion_producto': lambda: OpinionProducto.objects.filter(estado='publicada', orden__estado='COMPLETADA', producto__activo=True, producto__proveedor__estado='activo'),
        'opinion_proveedor': lambda: OpinionProveedor.objects.filter(estado='publicada', orden__estado='COMPLETADA', proveedor__estado='activo'),
    }
    if tipo not in consultas:
        raise ValidationError('Tipo de contenido inválido.')
    return get_object_or_404(consultas[tipo](), pk=pk)


@transaction.atomic
def reportar_contenido(usuario, tipo, objeto_id, motivo, comentario):
    exigir_usuario(usuario)
    get_user_model().objects.select_for_update().get(pk=usuario.pk)
    objeto = objeto_reportable(tipo, objeto_id)
    if ReporteContenido.objects.filter(usuario=usuario, tipo=tipo, **{tipo: objeto}, estado__in=['PENDIENTE', 'EN_REVISION']).exists():
        raise ValidationError('Ya tienes un reporte abierto sobre este contenido.')
    reporte = ReporteContenido(usuario=usuario, tipo=tipo, motivo=motivo, comentario=comentario, **{tipo: objeto})
    reporte.full_clean()
    reporte.save()
    auditar(usuario, 'reporte_creado', reporte)
    return reporte


@transaction.atomic
def moderar_reporte(usuario, reporte_id, accion, notas):
    exigir_superusuario(usuario)
    reporte = ReporteContenido.objects.select_for_update().get(pk=reporte_id)
    if reporte.estado not in {'PENDIENTE', 'EN_REVISION'}:
        raise ValidationError('Este reporte ya está cerrado.')
    if len(notas) > 3000 or (accion != 'revisar' and not notas.strip()):
        raise ValidationError('Explica la decisión en las notas (máximo 3000 caracteres).')
    if accion == 'revisar':
        if reporte.estado != 'PENDIENTE':
            raise ValidationError('El reporte ya está en revisión.')
        reporte.estado = 'EN_REVISION'
    elif accion == 'descartar':
        reporte.estado = 'DESCARTADO'
    else:
        acciones = {'producto': 'desactivar_producto', 'proveedor': 'suspender_proveedor', 'opinion_producto': 'ocultar_opinion', 'opinion_proveedor': 'ocultar_opinion'}
        if acciones.get(reporte.tipo) != accion:
            raise ValidationError('La acción no corresponde al contenido reportado.')
        objeto = reporte.objeto
        if reporte.tipo == 'producto':
            type(objeto).objects.filter(pk=objeto.pk).update(activo=False, fecha_modificacion=timezone.now())
            auditar(usuario, 'producto_desactivado', objeto, notas)
        elif reporte.tipo == 'proveedor':
            if objeto.estado in {'activo', 'inactivo'}:
                administrar_proveedor(usuario, objeto.pk, 'suspender', notas)
        else:
            type(objeto).objects.filter(pk=objeto.pk).update(estado='oculta')
            auditar(usuario, 'opinion_oculta', objeto, notas)
        reporte.estado = 'RESUELTO'
    reporte.notas_admin = notas.strip()
    reporte.fecha_revision = timezone.now()
    reporte.save(update_fields=['estado', 'notas_admin', 'fecha_revision'])
    auditar(usuario, 'reporte_'+accion, reporte, notas)
    if reporte.estado in {'RESUELTO', 'DESCARTADO'}:
        crear_notificacion([reporte.usuario_id], 'reporte_resuelto', 'Revisamos tu reporte', notas, '/mis-reportes/')
    return reporte
