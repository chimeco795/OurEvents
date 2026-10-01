"""Datos adicionales de fase 3. Sólo se invoca desde seed_demo en desarrollo."""
from servicios.models import SolicitudProveedor, Proveedor, GiroComercial, PlanMembresia, Producto, OpinionProducto, ReporteContenido
from servicios.application.providers import solicitar_proveedor, revisar_solicitud, crear_proveedor_manual, administrar_proveedor
from servicios.application.moderation import reportar_contenido


def seed_provider_lifecycle(usuarios):
    giro = GiroComercial.objects.get(nombre='Alimentos artesanales')
    for i, nombre in enumerate(['solicitante1', 'solicitante2', 'solicitante3'], 1):
        usuario = usuarios[nombre]
        if not SolicitudProveedor.objects.filter(usuario=usuario).exists():
            solicitud = solicitar_proveedor(usuario, {
                'nombre_negocio': f'Tienda candidata demo {i}',
                'descripcion': 'Negocio de demostración para revisar el flujo de alta.',
                'correo': f'{nombre}@example.test',
                'telefono': '5550000100', 'ubicacion': 'Ciudad de México', 'giros': [giro],
            })
            if i == 3:
                revisar_solicitud(usuarios['admin'], solicitud.pk, 'RECHAZADA', 'Demo: faltan datos de ubicación. Puedes enviar una nueva solicitud completa.')
    if not Proveedor.objects.filter(slug='demo-negocio-suspendido').exists():
        proveedor = crear_proveedor_manual(usuarios['admin'], {
            'nombre': 'Tienda pausada demo', 'descripcion': 'Negocio suspendido para pruebas administrativas.',
            'giros': [giro], 'ubicacion': 'Ciudad de México',
        }, usuarios['proveedor2'].pk, PlanMembresia.objects.get(nombre='PROFESIONAL').pk, 'activo')
        proveedor.slug = 'demo-negocio-suspendido'
        proveedor.save(update_fields=['slug'])
        administrar_proveedor(usuarios['admin'], proveedor.pk, 'suspender', 'Suspensión de demostración; conserva datos e historial.')
    objetivos = [('producto', Producto.objects.get(slug='demo-producto-3')),
                 ('proveedor', Proveedor.objects.get(slug='demo-negocio-2')),
                 ('opinion_producto', OpinionProducto.objects.filter(producto__slug__startswith='demo-', estado='publicada').first())]
    for tipo, objeto in objetivos:
        if objeto and not ReporteContenido.objects.filter(usuario=usuarios['solicitante1'], tipo=tipo, **{tipo:objeto}).exists():
            reportar_contenido(usuarios['solicitante1'], tipo, objeto.pk, 'otro', 'Reporte de demostración para practicar una revisión manual.')
