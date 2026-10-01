from django.urls import path
from servicios import provider_views as v

urlpatterns = [
    path('quiero-vender/', v.quiero_vender, name='quiero_vender'),
    path('gestion/<int:proveedor_id>/equipo/', v.equipo, name='gestion_equipo'),
    path('gestion/<int:proveedor_id>/equipo/accion/', v.equipo_accion, name='equipo_accion'),
    path('reportar/<str:tipo>/<int:pk>/', v.reportar, name='reportar_contenido'),
    path('mis-reportes/', v.mis_reportes, name='mis_reportes'),
    path('administracion/', v.administracion, name='administracion'),
    path('administracion/solicitudes/', v.solicitudes, name='admin_solicitudes'),
    path('administracion/solicitudes/<int:pk>/', v.solicitud_detalle, name='admin_solicitud'),
    path('administracion/solicitudes/<int:pk>/accion/', v.solicitud_accion, name='admin_solicitud_accion'),
    path('administracion/proveedores/', v.proveedores, name='admin_proveedores'),
    path('administracion/proveedores/nuevo/', v.proveedor_nuevo, name='admin_proveedor_nuevo'),
    path('administracion/proveedores/<int:pk>/', v.proveedor_detalle, name='admin_proveedor'),
    path('administracion/proveedores/<int:pk>/accion/', v.proveedor_accion, name='admin_proveedor_accion'),
    path('administracion/proveedores/<int:pk>/membresia/', v.asignar_plan, name='admin_asignar_plan'),
    path('administracion/moderacion/', v.moderacion, name='admin_moderacion'),
    path('administracion/moderacion/<int:pk>/', v.reporte_detalle, name='admin_reporte'),
    path('administracion/moderacion/<int:pk>/accion/', v.moderar, name='admin_moderar'),
]
