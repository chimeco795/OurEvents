"""Pantallas de cuenta; las operaciones sensibles viven en application."""
from django.contrib import messages
from django.contrib.auth import login, logout, get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import render, redirect
from django.views.decorators.http import require_POST
from django.views.decorators.debug import sensitive_post_parameters
from servicios.account_forms import RegistroCuentaForm, DatosCuentaForm, PerfilCuentaForm, PreferenciasForm, RecuperarForm
from servicios.application import accounts, email_verification
from servicios.account_queries import tiendas_usuario, resumen_tienda
from servicios.marketplace_views import error, cuenta as cuenta_anterior

@sensitive_post_parameters('password1', 'password2')
def registro(request):
    if request.user.is_authenticated:
        return redirect('cuenta')
    form = RegistroCuentaForm(request.POST if request.method == 'POST' else None)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            usuario = form.save()
            email_verification.enviar_verificacion(usuario, request.build_absolute_uri('/'))
        login(request, usuario)
        messages.success(request, 'Cuenta creada. Revisa tu correo para verificarlo.')
        return redirect('cuenta')
    return render(request, 'accounts/form.html', {'form': form, 'titulo': 'Crear cuenta', 'boton': 'Crear mi cuenta'})

@login_required
def cuenta(request):
    return cuenta_anterior(request)

@login_required
def editar_perfil(request):
    p = email_verification.perfil(request.user)
    form = DatosCuentaForm(request.POST if request.method == 'POST' else None, instance=request.user)
    extra = PerfilCuentaForm(request.POST if request.method == 'POST' else None, request.FILES or None, instance=p)
    if request.method == 'POST':
        valido = form.is_valid()
        extra_valido = extra.is_valid()
        if valido and extra_valido:
            accounts.guardar_datos(request.user, form.cleaned_data, extra.cleaned_data)
            messages.success(request, 'Perfil actualizado. Si cambiaste el correo, verifica la nueva dirección.')
            return redirect('cuenta')
    return render(request, 'accounts/form.html', {'form': form, 'extra': extra, 'titulo': 'Editar perfil'})

@login_required
def seguridad(request):
    return render(request, 'accounts/seguridad.html')

@require_POST
def cerrar_sesion(request):
    logout(request)
    messages.success(request, 'Sesión cerrada correctamente.')
    return redirect('home')

@login_required
@require_POST
def reenviar(request):
    try:
        email_verification.enviar_verificacion(request.user, request.build_absolute_uri('/'))
        messages.success(request, 'Solicitamos el envío del correo de verificación. Revisa tu bandeja.')
    except ValidationError as exc:
        error(request, exc)
    return redirect('cuenta')

def verificar_email(request, token):
    if request.method == 'POST':
        try:
            email_verification.verificar(token)
            messages.success(request, 'Correo verificado correctamente.')
            return redirect('cuenta')
        except ValidationError as exc:
            error(request, exc)
    return render(request, 'accounts/verificar.html')

def recuperar(request):
    form = RecuperarForm(request.POST if request.method == 'POST' else None)
    if request.method == 'POST' and form.is_valid():
        for usuario in get_user_model().objects.filter(email__iexact=form.cleaned_data['email'], is_active=True):
            accounts.enviar_reset(usuario, request.build_absolute_uri('/'))
        return redirect('password_reset_done')
    return render(request, 'accounts/form.html', {'form': form, 'titulo': 'Recuperar contraseña', 'boton': 'Enviar enlace', 'descripcion': 'Si existe una cuenta activa con este correo, recibirás un enlace para establecer tu contraseña.'})

@login_required
def preferencias(request):
    form = PreferenciasForm(request.POST if request.method == 'POST' else None, instance=email_verification.perfil(request.user))
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Preferencias guardadas.')
        return redirect('preferencias')
    return render(request, 'accounts/form.html', {'form': form, 'titulo': 'Preferencias de notificaciones', 'descripcion': 'Los avisos esenciales de plataforma permanecen activos. Elige qué avisos recibir por email. Los mensajes de seguridad y recuperación siempre se envían cuando los solicitas.'})

@login_required
def mis_tiendas(request):
    tiendas = list(tiendas_usuario(request.user))
    for tienda in tiendas:
        tienda.resumen = resumen_tienda(tienda)
    return render(request, 'accounts/tiendas.html', {'tiendas': tiendas})
