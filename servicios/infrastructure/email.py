import logging
from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)


def enviar_email(destinatarios, titulo, mensaje):
    """Adaptador best-effort. Un fallo SMTP nunca revierte una orden confirmada."""
    try:
        if destinatarios:
            send_mail(titulo, mensaje, settings.DEFAULT_FROM_EMAIL, destinatarios, fail_silently=False)
    except Exception:
        logger.exception('No se pudo entregar el correo de notificación')
