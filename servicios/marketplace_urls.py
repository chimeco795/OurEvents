from django.urls import path
from servicios import marketplace_views as v

urlpatterns = [
    path('buscar/', v.catalogo, name='buscar'),
    path('producto/<slug:slug>/', v.producto, name='producto_detalle'),
    path('proveedor/<slug:slug>/', v.proveedor, name='proveedor_detalle'),
    path('solicitud/', v.solicitud, name='solicitud'),
    path('solicitud/producto/<int:producto_id>/', v.carrito_actualizar, name='carrito_actualizar'),
    path('solicitud/<int:proveedor_id>/generar/', v.generar_orden, name='generar_orden'),
    path('mis-ordenes/', v.ordenes, name='mis_ordenes'),
    path('ordenes/<int:pk>/', v.orden_detalle, name='orden_detalle'),
    path('ordenes/<int:pk>/estado/', v.transicion, name='orden_estado'),
    path('ordenes/<int:pk>/opinion/', v.opinar, name='opinar_proveedor'),
    path('ordenes/<int:pk>/opinion/<int:producto_id>/', v.opinar, name='opinar_producto'),
    path('opiniones/<str:tipo>/<int:pk>/respuesta/', v.responder, name='responder_opinion'),
    path('notificaciones/', v.notificaciones, name='notificaciones'),
    path('notificaciones/<int:pk>/leida/', v.leer_notificacion, name='leer_notificacion'),
    path('gestion/<int:proveedor_id>/', v.dashboard, name='gestion_dashboard'),
    path('gestion/<int:proveedor_id>/inventario/', v.inventario, name='gestion_inventario'),
    path('gestion/<int:proveedor_id>/ordenes/', v.ordenes, name='gestion_ordenes'),
    path('gestion/<int:proveedor_id>/opiniones/', v.opiniones_gestion, name='gestion_opiniones'),
    path('gestion/<int:proveedor_id>/membresia/', v.membresia, name='gestion_membresia'),
]
