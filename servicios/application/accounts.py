"""Casos de uso de cuentas propias y administración global de usuarios."""
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError
from django.db import transaction
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from servicios.models import Profile, Proveedor
from servicios.application.email_verification import perfil
from servicios.application.providers import exigir_superusuario, auditar
from servicios.infrastructure.email import enviar_email

@transaction.atomic
def guardar_datos(usuario, datos, perfil_datos=None):
    usuario = get_user_model().objects.select_for_update().get(pk=usuario.pk)
    previo = usuario.email
    for campo in ('first_name', 'last_name', 'email'):
        if campo in datos:
            setattr(usuario, campo, datos[campo])
    usuario.full_clean(exclude=['password'])
    usuario.save(update_fields=['first_name', 'last_name', 'email'])
    p = perfil(usuario)
    if previo != usuario.email:
        p.email_verificado = ''
        p.fecha_verificacion_email = None
        p.version_email += 1
    for campo in ('telefono', 'photo'):
        if perfil_datos is not None and campo in perfil_datos:
            setattr(p, campo, perfil_datos[campo] or '')
    p.save()
    return usuario

@transaction.atomic
def enviar_reset(usuario, base_url):
    usuario = get_user_model().objects.select_for_update().get(pk=usuario.pk)
    if not usuario.is_active or not usuario.email:
        return
    p = perfil(usuario)
    if p.ultimo_reset and timezone.now() - p.ultimo_reset < timedelta(minutes=2):
        return
    p.ultimo_reset = timezone.now()
    p.save(update_fields=['ultimo_reset'])
    uid = urlsafe_base64_encode(force_bytes(usuario.pk))
    token = default_token_generator.make_token(usuario)
    url = base_url.rstrip('/') + reverse('password_reset_confirm', args=[uid, token])
    transaction.on_commit(lambda: enviar_email([usuario.email], 'Establece tu contraseña de OurEvents', 'Abre este enlace para establecer tu contraseña:\n' + url + '\nSi no solicitaste este cambio, ignora el mensaje.'))

@transaction.atomic
def crear_usuario(actor, datos, base_url):
    exigir_superusuario(actor)
    user = get_user_model()(**{k: datos[k] for k in ('username', 'first_name', 'last_name', 'email', 'is_active')})
    user.set_unusable_password()
    user.full_clean()
    user.save()
    perfil(user)
    auditar(actor, 'usuario_creado', user, 'Alta mediante enlace para establecer contraseña.')
    enviar_reset(user, base_url)
    return user

@transaction.atomic
def editar_usuario(actor, usuario, datos):
    exigir_superusuario(actor)
    user = guardar_datos(usuario, datos)
    auditar(actor, 'usuario_editado', user, 'Datos básicos actualizados.')
    return user

@transaction.atomic
def estado_usuario(actor, usuario_id, activo):
    exigir_superusuario(actor)
    User = get_user_model()
    # Serializa cambios de superusuarios y conserva un responsable por tienda.
    list(User.objects.select_for_update().filter(is_superuser=True).order_by('pk'))
    user = User.objects.select_for_update().get(pk=usuario_id)
    if not activo:
        if user.is_superuser and user.is_active and not User.objects.filter(is_superuser=True, is_active=True).exclude(pk=user.pk).exists():
            raise ValidationError('No puedes desactivar al último superadministrador activo.')
        for tienda in Proveedor.objects.select_for_update().filter(accesos__usuario=user, accesos__activo=True):
            otros = tienda.accesos.filter(activo=True, usuario__is_active=True).exclude(usuario=user)
            if not otros.exists() or (tienda.accesos.filter(usuario=user, activo=True, es_principal=True).exists() and not otros.filter(es_principal=True).exists()):
                raise ValidationError(f'Asigna otro principal activo a {tienda.nombre} antes de desactivar esta cuenta.')
    user.is_active = activo
    user.save(update_fields=['is_active'])
    auditar(actor, 'usuario_activado' if activo else 'usuario_desactivado', user)
    return user
