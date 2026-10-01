"""Administración propia de cuentas, planes e historial de membresías."""
from datetime import timedelta
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST
from servicios.account_forms import NuevoUsuarioForm, DatosCuentaForm, PlanForm
from servicios.application import accounts, plans
from servicios.application.email_verification import perfil
from servicios.application.providers import auditar
from servicios.models import PlanMembresia, MembresiaProveedor, RegistroAdministrativo
from servicios.account_queries import tiendas_usuario
from servicios.provider_views import solo_superusuario, params_pagina
from servicios.marketplace_views import paginar, error

@solo_superusuario
def usuarios(request):
    qs = get_user_model().objects.select_related('profile').order_by('username')
    q = request.GET.get('q', '')[:150]
    if q: qs = qs.filter(Q(username__icontains=q)|Q(email__icontains=q)|Q(first_name__icontains=q)|Q(last_name__icontains=q))
    if request.GET.get('estado') in ['activo','inactivo']: qs = qs.filter(is_active=request.GET['estado']=='activo')
    if request.GET.get('rol') == 'superusuario': qs = qs.filter(is_superuser=True)
    return render(request, 'administracion/usuarios.html', {'page_obj': paginar(request, qs), 'querystring': params_pagina(request)})

@solo_superusuario
def nuevo_usuario(request):
    form = NuevoUsuarioForm(request.POST if request.method == 'POST' else None)
    if request.method == 'POST' and form.is_valid():
        try:
            usuario = accounts.crear_usuario(request.user, form.cleaned_data, request.build_absolute_uri('/'))
            messages.success(request, 'Usuario creado. Si está activo, se solicitó el envío del enlace para establecer contraseña. En desarrollo consulta el correo en la consola del servidor.')
            return redirect('admin_usuario', pk=usuario.pk)
        except ValidationError as exc: form.add_error(None, exc)
    return render(request, 'accounts/form.html', {'form': form, 'titulo': 'Crear usuario', 'administrativo': True, 'descripcion': 'El usuario recibirá un enlace para establecer su contraseña. No se otorgan privilegios de superusuario.'})

@solo_superusuario
def usuario(request, pk):
    obj = get_object_or_404(get_user_model(), pk=pk)
    form = DatosCuentaForm(request.POST if request.method == 'POST' else None, instance=obj)
    if request.method == 'POST' and form.is_valid():
        try:
            accounts.editar_usuario(request.user, obj, form.cleaned_data)
            messages.success(request, 'Datos actualizados.')
            return redirect('admin_usuario', pk=pk)
        except ValidationError as exc: form.add_error(None, exc)
    historial = RegistroAdministrativo.objects.filter(tipo_objeto='user', objeto_id=pk).select_related('usuario')[:30]
    return render(request, 'administracion/usuario.html', {'objeto': obj, 'perfil': perfil(obj), 'form': form, 'tiendas': tiendas_usuario(obj), 'ordenes': obj.ordenes.select_related('proveedor')[:8], 'historial': historial})

@solo_superusuario
@require_POST
def usuario_accion(request, pk):
    obj = get_object_or_404(get_user_model(), pk=pk)
    try:
        accion = request.POST.get('accion')
        if accion in {'activar','desactivar'}:
            accounts.estado_usuario(request.user, pk, accion=='activar')
        elif accion == 'recuperar':
            accounts.enviar_reset(obj, request.build_absolute_uri('/'))
            auditar(request.user, 'recuperacion_solicitada', obj)
        else: raise ValidationError('Acción inválida.')
        messages.success(request, 'Acción procesada. Los envíos requieren una cuenta activa con correo y tienen un intervalo mínimo de dos minutos.')
    except ValidationError as exc: error(request, exc)
    return redirect('admin_usuario', pk=pk)

@solo_superusuario
def lista_planes(request):
    qs = PlanMembresia.objects.order_by('precio','nombre')
    if request.GET.get('q'): qs = qs.filter(nombre__icontains=request.GET['q'][:60])
    return render(request, 'administracion/planes.html', {'page_obj': paginar(request, qs), 'querystring': params_pagina(request)})

@solo_superusuario
def plan(request, pk=None):
    obj = get_object_or_404(PlanMembresia, pk=pk) if pk else None
    form = PlanForm(request.POST if request.method == 'POST' else None, instance=obj)
    if request.method == 'POST' and form.is_valid():
        try:
            plans.guardar_plan(request.user, form.cleaned_data, pk, form.cleaned_data['confirmar_impacto'])
            messages.success(request, 'Plan guardado. Se conservan membresías, productos y accesos existentes.')
            return redirect('admin_planes')
        except ValidationError as exc: form.add_error(None, exc)
    afectados = plans.excedidos(form.instance) if pk else []
    return render(request, 'accounts/form.html', {'form': form, 'titulo': 'Editar plan' if pk else 'Crear plan', 'administrativo': True, 'descripcion': 'Desactivar impide nuevas asignaciones; las membresías vigentes mantienen acceso hasta su vencimiento. Las condiciones guardadas al asignar se conservan como historial.', 'afectados': afectados})

@solo_superusuario
def membresias(request):
    hoy = timezone.localdate()
    qs = MembresiaProveedor.objects.select_related('proveedor','plan').order_by('-inicio','-pk')
    if request.GET.get('q'): qs = qs.filter(proveedor__nombre__icontains=request.GET['q'][:150])
    if request.GET.get('plan','').isdigit(): qs = qs.filter(plan_id=request.GET['plan'])
    estado = request.GET.get('estado')
    if estado == 'activa': qs = qs.filter(activa=True, inicio__lte=hoy, fin__gte=hoy)
    elif estado == 'proxima': qs = qs.filter(activa=True, inicio__lte=hoy, fin__gte=hoy, fin__lte=hoy+timedelta(days=30))
    elif estado == 'vencida': qs = qs.filter(fin__lt=hoy)
    elif estado == 'historica': qs = qs.filter(activa=False)
    return render(request, 'administracion/membresias.html', {'page_obj': paginar(request, qs), 'planes': PlanMembresia.objects.all(), 'hoy': hoy, 'querystring': params_pagina(request)})
