from django.db import transaction
from django.contrib.auth import get_user_model
from servicios.models import Notificacion, Profile
from servicios.infrastructure.email import enviar_email


def crear_notificacion(usuarios, tipo, titulo, mensaje, url, correo=None):
    ids = set(usuarios)
    Notificacion.objects.bulk_create([Notificacion(usuario_id=pk, tipo=tipo, titulo=titulo, mensaje=mensaje, url=url) for pk in ids])
    campo = 'email_nueva_orden' if tipo == 'nueva_orden' else 'email_cambio_orden' if tipo.startswith('orden_') else 'email_nueva_opinion' if 'opinion' in tipo else 'email_administracion'
    if correo is not False:
        bloqueados = Profile.objects.filter(user_id__in=ids, **{campo: False}).values_list('user_id', flat=True)
        emails = list(get_user_model().objects.filter(pk__in=ids, is_active=True).exclude(pk__in=bloqueados).exclude(email='').values_list('email', flat=True))
        def entregar():
            for email in emails:
                enviar_email([email], titulo, mensaje)
        transaction.on_commit(entregar)



def administradores(proveedor):
    return proveedor.accesos.filter(activo=True, usuario__is_active=True).values_list('usuario_id', flat=True)
