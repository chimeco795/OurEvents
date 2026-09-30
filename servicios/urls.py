from django.urls import path
from . import views

urlpatterns = [
    path('', views.negocios, name='gestion_negocios'),
    path('<int:proveedor_id>/productos/', views.productos, name='gestion_productos'),
    path('<int:proveedor_id>/datos/', views.editar_negocio, name='gestion_negocio'),
    path('<int:proveedor_id>/productos/nuevo/', views.editar_producto, name='gestion_producto_nuevo'),
    path('<int:proveedor_id>/productos/<int:producto_id>/', views.editar_producto, name='gestion_producto_editar'),
]
