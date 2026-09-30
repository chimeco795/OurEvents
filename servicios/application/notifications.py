from django.db import transaction
from django.contrib.auth import get_user_model
from servicios.models import Notificacion
from servicios.infrastructure.email import enviar_email


def crear_notificacion(usuarios, tipo, titulo, mensaje, url, correo=False):
    ids = set(usuarios)
    Notificacion.objects.bulk_create([Notificacion(usuario_id=pk, tipo=tipo, titulo=titulo, mensaje=mensaje, url=url) for pk in ids])
    if correo:
        emails = list(get_user_model().objects.filter(pk__in=ids).exclude(email='').values_list('email', flat=True))
        transaction.on_commit(lambda: enviar_email(emails, titulo, mensaje))


def administradores(proveedor):
    return proveedor.accesos.filter(activo=True, usuario__is_active=True).values_list('usuario_id', flat=True)
