"""Verificación ligada al correo actual, con caducidad y límite persistente."""
from datetime import timedelta
from django.core import signing
from django.core.exceptions import ValidationError
from django.db import transaction
from django.urls import reverse
from django.utils import timezone
from servicios.models import Profile
from servicios.infrastructure.email import enviar_email

SALT = 'ourevents.email-verification.v1'

def perfil(usuario):
    return Profile.objects.get_or_create(user=usuario)[0]

@transaction.atomic
def enviar_verificacion(usuario, base_url):
    perfil(usuario)
    p = Profile.objects.select_for_update().select_related('user').get(user=usuario)
    if p.correo_verificado:
        raise ValidationError('Tu correo ya está verificado.')
    if not usuario.email:
        raise ValidationError('Agrega un correo en tu perfil antes de verificarlo.')
    if p.ultimo_envio_verificacion and timezone.now() - p.ultimo_envio_verificacion < timedelta(minutes=2):
        raise ValidationError('Espera dos minutos antes de solicitar otro correo.')
    p.ultimo_envio_verificacion = timezone.now()
    p.save(update_fields=['ultimo_envio_verificacion'])
    token = signing.dumps({'user': usuario.pk, 'email': usuario.email, 'version': p.version_email, 'envio': p.ultimo_envio_verificacion.isoformat()}, salt=SALT)
    url = base_url.rstrip('/') + reverse('verificar_email', args=[token])
    transaction.on_commit(lambda: enviar_email([usuario.email], 'Verifica tu correo en OurEvents', 'Confirma tu correo (enlace válido por 24 horas):\n' + url))

@transaction.atomic
def verificar(token):
    try:
        datos = signing.loads(token, salt=SALT, max_age=86400)
        p = Profile.objects.select_for_update().select_related('user').get(user_id=datos['user'])
        if not p.user.is_active or p.user.email != datos['email'] or p.version_email != datos['version'] or not p.ultimo_envio_verificacion or p.ultimo_envio_verificacion.isoformat() != datos['envio'] or p.correo_verificado:
            raise ValueError
    except (signing.BadSignature, Profile.DoesNotExist, KeyError, ValueError):
        raise ValidationError('El enlace no es válido, ya se utilizó o venció. Solicita otro desde Mi cuenta.')
    p.email_verificado = p.user.email
    p.fecha_verificacion_email = timezone.now()
    p.save(update_fields=['email_verificado', 'fecha_verificacion_email'])
    return p.user
