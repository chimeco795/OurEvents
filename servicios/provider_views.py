from functools import wraps
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from servicios.models import (SolicitudProveedor, Proveedor, ReporteContenido, RegistroAdministrativo, MembresiaProveedor)
from servicios.provider_forms import (SolicitudProveedorForm, NuevoProveedorForm, AccionSolicitudForm, AccionProveedorForm, AsignarMembresiaForm, AgregarEquipoForm, AccionEquipoForm, ReporteForm, ModeracionForm)
from servicios.application import providers, moderation
from servicios.application.memberships import membresia_vigente
from servicios.marketplace_views import paginar, error
from servicios.permissions import obtener_proveedor
from servicios.administration_queries import dashboard_admin, solicitudes_filtradas, proveedores_filtrados


def solo_superusuario(vista):
    @login_required
    @wraps(vista)
    def protegida(request, *args, **kwargs):
        providers.exigir_superusuario(request.user)
        return vista(request, *args, **kwargs)
    return protegida


def params_pagina(request):
    parametros = request.GET.copy()
    parametros.pop('page', None)
    return parametros.urlencode()


@login_required
def quiero_vender(request):
    historial = request.user.solicitudes_proveedor.select_related('proveedor')
    abierta = historial.filter(estado__in=['PENDIENTE', 'EN_REVISION']).first()
    form = SolicitudProveedorForm(request.POST if request.method == 'POST' else None)
    if request.method == 'POST' and form.is_valid():
        try:
            providers.solicitar_proveedor(request.user, form.cleaned_data)
            messages.success(request, 'Solicitud recibida. Te avisaremos cuando sea revisada.')
            return redirect('quiero_vender')
        except ValidationError as exc:
            form.add_error(None, exc)
    return render(request, 'providers/quiero_vender.html', {'form': form, 'abierta': abierta, 'correo_verificado': request.user.profile.correo_verificado, 'page_obj': paginar(request, historial)})


@solo_superusuario
def administracion(request):
    return render(request, 'administracion/dashboard.html', dashboard_admin())


@solo_superusuario
def solicitudes(request):
    return render(request, 'administracion/solicitudes.html', {'page_obj': paginar(request, solicitudes_filtradas(request.GET)), 'estados': SolicitudProveedor.Estado.choices, 'querystring': params_pagina(request)})


@solo_superusuario
def solicitud_detalle(request, pk):
    obj = get_object_or_404(SolicitudProveedor.objects.select_related('usuario', 'proveedor').prefetch_related('giros'), pk=pk)
    return render(request, 'administracion/solicitud.html', {'solicitud': obj, 'abierta': obj.estado in ['PENDIENTE','EN_REVISION'], 'form': AccionSolicitudForm(), 'historial': RegistroAdministrativo.objects.filter(tipo_objeto='solicitudproveedor', objeto_id=pk).select_related('usuario')})


@solo_superusuario
@require_POST
def solicitud_accion(request, pk):
    get_object_or_404(SolicitudProveedor, pk=pk)
    form = AccionSolicitudForm(request.POST)
    if form.is_valid():
        try:
            providers.revisar_solicitud(request.user, pk, form.cleaned_data['estado'], form.cleaned_data['notas'])
            messages.success(request, 'Solicitud actualizada correctamente.')
        except ValidationError as exc:
            error(request, exc)
    else:
        messages.error(request, 'Revisa el estado y las notas de la solicitud.')
    return redirect('admin_solicitud', pk=pk)


@solo_superusuario
def proveedores(request):
    return render(request, 'administracion/proveedores.html', {'page_obj': paginar(request, proveedores_filtrados(request.GET)), 'estados': Proveedor.Estado.choices, 'querystring': params_pagina(request)})


@solo_superusuario
def proveedor_nuevo(request):
    form = NuevoProveedorForm(request.POST if request.method == 'POST' else None)
    if request.method == 'POST' and form.is_valid():
        try:
            datos = form.cleaned_data
            obj = providers.crear_proveedor_manual(request.user, datos, datos['administrador'].pk, datos['plan'].pk, datos['estado'])
            messages.success(request, 'Proveedor creado con administrador principal y membresía.')
            return redirect('admin_proveedor', pk=obj.pk)
        except ValidationError as exc:
            form.add_error(None, exc)
    return render(request, 'administracion/nuevo_proveedor.html', {'form': form})


@solo_superusuario
def proveedor_detalle(request, pk):
    obj = get_object_or_404(Proveedor, pk=pk)
    return render(request, 'administracion/proveedor.html', {'proveedor': obj, 'membresia': membresia_vigente(obj), 'form': AsignarMembresiaForm(), 'equipo': obj.accesos.select_related('usuario'), 'page_obj': paginar(request, RegistroAdministrativo.objects.filter(tipo_objeto='proveedor', objeto_id=pk).select_related('usuario'))})


@solo_superusuario
@require_POST
def proveedor_accion(request, pk):
    get_object_or_404(Proveedor, pk=pk)
    form = AccionProveedorForm(request.POST)
    if form.is_valid():
        try:
            providers.administrar_proveedor(request.user, pk, form.cleaned_data['accion'], form.cleaned_data['notas'])
            messages.success(request, 'Proveedor actualizado.')
        except ValidationError as exc:
            error(request, exc)
    else:
        messages.error(request, 'Acción administrativa inválida.')
    return redirect('admin_proveedor', pk=pk)


@solo_superusuario
@require_POST
def asignar_plan(request, pk):
    get_object_or_404(Proveedor, pk=pk)
    form = AsignarMembresiaForm(request.POST)
    if form.is_valid():
        try:
            providers.asignar_membresia(request.user, pk, form.cleaned_data['plan'].pk)
            messages.success(request, 'Membresía asignada. La anterior queda en el historial.')
        except ValidationError as exc:
            error(request, exc)
    else:
        messages.error(request, 'Selecciona un plan activo.')
    return redirect('admin_proveedor', pk=pk)


@login_required
def equipo(request, proveedor_id):
    obj = obtener_proveedor(request.user, proveedor_id)
    form = AgregarEquipoForm(request.POST if request.method == 'POST' else None)
    gestionable = providers.puede_gestionar_equipo(request.user, obj)
    if request.method == 'POST':
        providers.exigir_equipo(request.user, obj)
        if form.is_valid():
            try:
                providers.agregar_equipo(request.user, obj.pk, form.cleaned_data['username'])
                messages.success(request, 'Usuario agregado al equipo.')
                return redirect('gestion_equipo', proveedor_id=obj.pk)
            except ValidationError as exc:
                form.add_error(None, exc)
    return render(request, 'providers/equipo.html', {'proveedor': obj, 'equipo': obj.accesos.select_related('usuario').order_by('-es_principal', 'pk'), 'form': form, 'gestionable': gestionable})


@login_required
@require_POST
def equipo_accion(request, proveedor_id):
    obj = obtener_proveedor(request.user, proveedor_id)
    providers.exigir_equipo(request.user, obj)
    form = AccionEquipoForm(request.POST)
    if form.is_valid():
        try:
            providers.cambiar_acceso(request.user, obj.pk, form.cleaned_data['acceso_id'], form.cleaned_data['accion'])
            messages.success(request, 'Acceso actualizado.')
        except ValidationError as exc:
            error(request, exc)
    else:
        messages.error(request, 'Acción de equipo inválida.')
    return redirect('gestion_equipo', proveedor_id=obj.pk)


@login_required
def reportar(request, tipo, pk):
    try:
        obj = moderation.objeto_reportable(tipo, pk)
    except ValidationError:
        from django.http import Http404
        raise Http404
    form = ReporteForm(request.POST if request.method == 'POST' else None)
    if request.method == 'POST' and form.is_valid():
        try:
            moderation.reportar_contenido(request.user, tipo, pk, form.cleaned_data['motivo'], form.cleaned_data['comentario'])
            messages.success(request, 'Reporte recibido. El equipo revisará el contenido.')
            return redirect('mis_reportes')
        except ValidationError as exc:
            form.add_error(None, exc)
    return render(request, 'providers/reportar.html', {'form': form, 'objeto': obj, 'tipo': tipo})


@login_required
def mis_reportes(request):
    return render(request, 'providers/reportes.html', {'page_obj': paginar(request, ReporteContenido.objects.filter(usuario=request.user))})


@solo_superusuario
def moderacion(request):
    qs = ReporteContenido.objects.select_related('usuario')
    estado = request.GET.get('estado', 'PENDIENTE')
    if estado in ReporteContenido.Estado.values:
        qs = qs.filter(estado=estado)
    return render(request, 'administracion/moderacion.html', {'page_obj': paginar(request, qs), 'estados': ReporteContenido.Estado.choices, 'estado': estado, 'querystring': params_pagina(request)})


@solo_superusuario
def reporte_detalle(request, pk):
    obj = get_object_or_404(ReporteContenido.objects.select_related('usuario', 'producto', 'proveedor', 'opinion_producto', 'opinion_proveedor'), pk=pk)
    accion = {'producto':'desactivar_producto','proveedor':'suspender_proveedor','opinion_producto':'ocultar_opinion','opinion_proveedor':'ocultar_opinion'}[obj.tipo]
    return render(request, 'administracion/reporte.html', {'reporte': obj, 'abierto': obj.estado in ['PENDIENTE','EN_REVISION'], 'accion_contenido': accion, 'historial': RegistroAdministrativo.objects.filter(tipo_objeto='reportecontenido', objeto_id=pk).select_related('usuario')})


@solo_superusuario
@require_POST
def moderar(request, pk):
    get_object_or_404(ReporteContenido, pk=pk)
    form = ModeracionForm(request.POST)
    if form.is_valid():
        try:
            moderation.moderar_reporte(request.user, pk, form.cleaned_data['accion'], form.cleaned_data['notas'])
            messages.success(request, 'Decisión de moderación registrada.')
        except ValidationError as exc:
            error(request, exc)
    else:
        messages.error(request, 'Revisa la acción y las notas.')
    return redirect('admin_reporte', pk=pk)
