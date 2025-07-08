from django.contrib import admin
from servicios import views  # Importar las vistas desde la aplicación 'servicios'
from django.urls import path, include
from django.contrib.auth import views as auth_views
from servicios.views import send_test_email  # Importa la vista desde la aplicación correcta


urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.home, name='home'),

    # Autenticación
    path('login/', auth_views.LoginView.as_view(template_name='login.html'), name='login'),
   
    path('logout/', auth_views.LogoutView.as_view(template_name='logged_out.html'), name='logout'),

    
    # Si usas perfil personalizado
    path('accounts/profile/', views.perfil_usuario, name='perfil'),

    path('accounts/password_change/', auth_views.PasswordChangeView.as_view(template_name='registration/password_change_form.html'), name='password_change'),
    path('accounts/password_change/done/', auth_views.PasswordChangeDoneView.as_view(template_name='registration/password_change_done.html'), name='password_change_done'),
 
   
    # Otras rutas
    path('catalogo/', views.catalogo, name='catalogo'),
    path('comentarios/', views.ver_comentarios, name='ver_comentarios'),
    path('comentarios/nuevo/', views.capturar_comentarios, name='capturar_comentarios'),
    path('contacto/', views.contacto, name='contacto'),
    path('enviar-correo/', send_test_email, name='send_test_email'),  # Ruta para enviar el correo
    
]
