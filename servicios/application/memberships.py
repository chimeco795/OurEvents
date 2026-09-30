from types import SimpleNamespace
from django.core.exceptions import ValidationError
from django.utils import timezone
from servicios.models import MembresiaProveedor


def membresia_vigente(proveedor):
    hoy = timezone.localdate()
    return MembresiaProveedor.objects.select_related('plan').filter(proveedor=proveedor, activa=True, plan__activo=True, inicio__lte=hoy, fin__gte=hoy).first()


def plan_actual(proveedor):
    membresia = membresia_vigente(proveedor)
    return membresia.plan if membresia else SimpleNamespace(nombre='GRATIS', max_productos=5, max_usuarios=1, promociones=False, estadisticas=False)


def validar_producto(producto):
    plan = plan_actual(producto.proveedor)
    if not producto.pk and plan.max_productos is not None and producto.proveedor.productos.count() >= plan.max_productos:
        raise ValidationError(f'El plan {plan.nombre} permite {plan.max_productos} productos. Contacta al administrador.')
    if producto.precio_promocional is not None and not plan.promociones:
        raise ValidationError('El plan actual no permite promociones.')


def validar_administrador(acceso):
    plan = plan_actual(acceso.proveedor)
    if acceso.activo and plan.max_usuarios is not None and acceso.proveedor.accesos.filter(activo=True).exclude(pk=acceso.pk).exclude(usuario_id=acceso.usuario_id).count() >= plan.max_usuarios:
        raise ValidationError(f'El plan {plan.nombre} permite {plan.max_usuarios} administradores.')
