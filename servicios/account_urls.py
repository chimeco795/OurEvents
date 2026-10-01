from django.urls import path, reverse_lazy
from django.contrib.auth import views as auth
from django.views.generic import TemplateView
from servicios import account_views as v, account_admin_views as a

urlpatterns = [
    path('registro/', v.registro, name='registro'),
    path('logout/', v.cerrar_sesion, name='logout'),
    path('mi-cuenta/', v.cuenta, name='cuenta'),
    path('mi-cuenta/perfil/', v.editar_perfil, name='editar_perfil'),
    path('mi-cuenta/seguridad/', v.seguridad, name='seguridad'),
    path('mi-cuenta/preferencias/', v.preferencias, name='preferencias'),
    path('mi-cuenta/verificacion/enviar/', v.reenviar, name='reenviar_verificacion'),
    path('verificar-correo/<str:token>/', v.verificar_email, name='verificar_email'),
    path('mi-cuenta/seguridad/contrasena/', auth.PasswordChangeView.as_view(template_name='accounts/password_change.html', success_url=reverse_lazy('password_change_done')), name='password_change'),
    path('mi-cuenta/seguridad/contrasena/listo/', auth.PasswordChangeDoneView.as_view(template_name='accounts/password_changed.html'), name='password_change_done'),
    path('recuperar-contrasena/', v.recuperar, name='password_reset'),
    path('recuperar-contrasena/enviado/', TemplateView.as_view(template_name='accounts/reset_sent.html'), name='password_reset_done'),
    path('restablecer/<uidb64>/<token>/', auth.PasswordResetConfirmView.as_view(template_name='accounts/reset_confirm.html', success_url=reverse_lazy('password_reset_complete')), name='password_reset_confirm'),
    path('restablecer/listo/', auth.PasswordResetCompleteView.as_view(template_name='accounts/reset_complete.html'), name='password_reset_complete'),
    path('mis-tiendas/', v.mis_tiendas, name='mis_tiendas'),
    path('administracion/usuarios/', a.usuarios, name='admin_usuarios'),
    path('administracion/usuarios/nuevo/', a.nuevo_usuario, name='admin_usuario_nuevo'),
    path('administracion/usuarios/<int:pk>/', a.usuario, name='admin_usuario'),
    path('administracion/usuarios/<int:pk>/accion/', a.usuario_accion, name='admin_usuario_accion'),
    path('administracion/planes/', a.lista_planes, name='admin_planes'),
    path('administracion/planes/nuevo/', a.plan, name='admin_plan_nuevo'),
    path('administracion/planes/<int:pk>/', a.plan, name='admin_plan'),
    path('administracion/membresias/', a.membresias, name='admin_membresias'),
]
