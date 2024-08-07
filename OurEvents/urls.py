from django.contrib import admin
from django.urls import path
from servicios import views  # Importar las vistas desde la aplicación 'servicios'

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.home, name='home'),
    path('catalogo/', views.catalogo, name='catalogo'),
    path('comentarios/', views.ver_comentarios, name='ver_comentarios'),
    path('comentarios/nuevo/', views.capturar_comentarios, name='capturar_comentarios'),
]
