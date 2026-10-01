"""Planes editables sin borrar contratos ni retirar accesos automáticamente."""
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from servicios.models import PlanMembresia, MembresiaProveedor
from servicios.application.providers import exigir_superusuario, auditar

CAMPOS = ('nombre', 'precio', 'duracion_dias', 'max_productos', 'max_usuarios', 'promociones', 'estadisticas', 'activo')

def condiciones(plan):
    return {k: str(getattr(plan, k)) if k == 'precio' else getattr(plan, k) for k in CAMPOS}

def excedidos(plan):
    hoy = timezone.localdate()
    contratos = MembresiaProveedor.objects.filter(plan_id=plan.pk, activa=True, inicio__lte=hoy, fin__gte=hoy).select_related('proveedor')
    return [m.proveedor for m in contratos if (plan.max_productos is not None and m.proveedor.productos.count() > plan.max_productos) or (plan.max_usuarios is not None and m.proveedor.accesos.filter(activo=True).count() > plan.max_usuarios)]

@transaction.atomic
def guardar_plan(actor, datos, plan_id=None, confirmar=False):
    exigir_superusuario(actor)
    plan = PlanMembresia.objects.select_for_update().get(pk=plan_id) if plan_id else PlanMembresia()
    anterior = condiciones(plan) if plan_id else None
    for k in CAMPOS:
        setattr(plan, k, datos[k])
    plan.full_clean()
    if plan.max_usuarios == 0:
        raise ValidationError('El plan debe permitir al menos un administrador.')
    if anterior and anterior['nombre'] == 'GRATIS' and (plan.nombre != 'GRATIS' or plan.precio != 0 or not plan.activo):
        raise ValidationError('GRATIS debe conservar su nombre, precio cero y estado activo para el alta de tiendas.')
    afectados = excedidos(plan) if plan_id else []
    if afectados and not confirmar:
        raise ValidationError(f'{len(afectados)} proveedores quedarían excedidos. Confirma el impacto para guardar; no se eliminarán productos ni accesos.')
    plan.save()
    auditar(actor, 'plan_editado' if plan_id else 'plan_creado', plan, f'Antes: {anterior}. Ahora: {condiciones(plan)}. Proveedores excedidos: {len(afectados)}.')
    return plan
