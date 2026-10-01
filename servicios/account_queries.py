from django.db.models import Count, Q
from servicios.models import Proveedor
from servicios.application.memberships import plan_actual

def tiendas_usuario(usuario):
    return Proveedor.objects.filter(accesos__usuario=usuario, accesos__activo=True).distinct().annotate(total_productos=Count('productos', distinct=True), ordenes_pendientes=Count('ordenes', filter=Q(ordenes__estado__in=['NUEVA','VISTA','ACEPTADA','EN_PROCESO','ATENDIDA']), distinct=True))

def resumen_tienda(tienda):
    pasos = [('Información básica', bool(tienda.nombre and tienda.descripcion and tienda.ubicacion)), ('Logo', bool(tienda.logotipo)), ('Portada', bool(tienda.portada)), ('Datos de contacto', bool(tienda.telefono or tienda.correo or tienda.whatsapp)), ('Primer producto', tienda.productos.exists()), ('Inventario configurado', tienda.productos.filter(stock__gt=0).exists())]
    publicada = tienda.estado == 'activo'
    motivo = 'Tienda publicada' if publicada else 'Tienda no visible públicamente: ' + tienda.get_estado_display().lower()
    avisos = []
    if not pasos[0][1]: avisos.append('Completa la información básica para que los compradores conozcan tu negocio.')
    if not pasos[4][1]: avisos.append('Sin productos: tu ficha está disponible si la tienda está activa, pero aún no tiene catálogo.')
    return {'pasos': pasos, 'porcentaje': round(100 * sum(ok for _, ok in pasos) / len(pasos)), 'publicada': publicada, 'estado_publicacion': motivo, 'avisos': avisos, 'plan': plan_actual(tienda)}
