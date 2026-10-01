from datetime import timedelta
from django.contrib.auth import get_user_model
from django.db.models import Q, Count
from django.utils import timezone
from servicios.models import SolicitudProveedor, Proveedor, Producto, Orden, ReporteContenido, MembresiaProveedor


def solicitudes_filtradas(parametros):
    qs = SolicitudProveedor.objects.select_related('usuario', 'proveedor')
    if parametros.get('q'):
        qs = qs.filter(Q(nombre_negocio__icontains=parametros['q'][:150]) | Q(usuario__username__icontains=parametros['q'][:150]))
    if parametros.get('estado') in SolicitudProveedor.Estado.values:
        qs = qs.filter(estado=parametros['estado'])
    return qs


def proveedores_filtrados(parametros):
    qs = Proveedor.objects.order_by('nombre')
    if parametros.get('q'):
        qs = qs.filter(Q(nombre__icontains=parametros['q'][:150]) | Q(correo__icontains=parametros['q'][:150]))
    if parametros.get('estado') in Proveedor.Estado.values:
        qs = qs.filter(estado=parametros['estado'])
    return qs


def membresias_proximas():
    hoy = timezone.localdate()
    return MembresiaProveedor.objects.filter(activa=True, fin__range=(hoy, hoy+timedelta(days=30))).select_related('proveedor', 'plan').order_by('fin')


def dashboard_admin():
    abiertos = ReporteContenido.objects.filter(estado__in=['PENDIENTE', 'EN_REVISION'])
    return {
        'kpis': [
            ('Solicitudes pendientes', SolicitudProveedor.objects.filter(estado__in=['PENDIENTE','EN_REVISION']).count()),
            ('Proveedores activos', Proveedor.objects.filter(estado='activo').count()),
            ('Proveedores suspendidos', Proveedor.objects.filter(estado='suspendido').count()),
            ('Productos activos', Producto.objects.filter(activo=True, proveedor__estado='activo').count()),
            ('Opiniones reportadas', abiertos.filter(tipo__startswith='opinion_').count()),
            ('Membresías por vencer', membresias_proximas().count()),
        ],
        'ordenes': Orden.objects.select_related('proveedor', 'comprador')[:8],
        'proximas': membresias_proximas()[:8],
    }
