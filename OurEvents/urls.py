from django.contrib import admin
from django.urls import path
from servicios import views  # Importar las vistas desde la aplicación 'servicios'

from servicios.views import send_test_email  # Importa la vista desde la aplicación correcta


urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.home, name='home'),
    path('catalogo/', views.catalogo, name='catalogo'),
    path('comentarios/', views.ver_comentarios, name='ver_comentarios'),
    path('comentarios/nuevo/', views.capturar_comentarios, name='capturar_comentarios'),
    path('contacto/', views.contacto, name='contacto'),
    path('enviar-correo/', send_test_email, name='send_test_email'),  # Ruta para enviar el correo
]
