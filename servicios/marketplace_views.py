"""Presentación HTTP. Las mutaciones de negocio delegan en servicios de aplicación."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError, PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q, F, Count
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from servicios.models import Orden, Producto, Proveedor, Categoria, OpinionProducto, OpinionProveedor, Notificacion
from servicios.forms import BusquedaForm, CantidadForm, SolicitudForm, TransicionForm, OpinionForm, RespuestaForm, InventarioForm
from servicios.queries import productos_publicos, proveedores_publicos, buscar_productos, reputacion
from servicios.permissions import obtener_proveedor, proveedores_administrables
from servicios.domain.orders import acciones
from servicios.application import orders, reviews, memberships, catalog
from servicios.infrastructure.cart import CarritoSesion


def paginar(request, queryset, cantidad=12):
    return Paginator(queryset, cantidad).get_page(request.GET.get('page'))


def error(request, exc):
    messages.error(request, ' '.join(exc.messages))


def home(request):
    productos = productos_publicos()
    return render(request, 'home.html', {'categorias': Categoria.objects.filter(activa=True, padre=None), 'destacados': productos.filter(destacado=True)[:8], 'mejores': productos.filter(numero_opiniones__gt=0).order_by('-valoracion')[:4], 'proveedores': proveedores_publicos().order_by('-verificado', '-valoracion')[:4]})


def catalogo(request):
    form = BusquedaForm(request.GET)
    productos = buscar_productos(form.cleaned_data) if form.is_valid() else productos_publicos().none()
    proveedores = proveedores_publicos()
    texto = form.cleaned_data.get('q', '')
    if texto:
        proveedores = proveedores.filter(Q(nombre__icontains=texto) | Q(descripcion__icontains=texto) | Q(giros__nombre__icontains=texto)).distinct()
    else:
        proveedores = proveedores.none()
    parametros = request.GET.copy()
    parametros.pop('page', None)
    return render(request, 'catalogo.html', {'form': form, 'page_obj': paginar(request, productos), 'proveedores': Paginator(proveedores.order_by('nombre'), 8).get_page(request.GET.get('proveedores_page')), 'querystring': parametros.urlencode()})


def producto(request, slug):
    obj = get_object_or_404(productos_publicos(), slug=slug)
    opiniones = obj.opiniones.filter(estado='publicada').select_related('usuario', 'orden')
    return render(request, 'marketplace/producto.html', {'producto': obj, 'reputacion': reputacion(obj.opiniones), 'page_obj': paginar(request, opiniones), 'cantidad_form': CantidadForm()})


def proveedor(request, slug):
    obj = get_object_or_404(proveedores_publicos(), slug=slug)
    return render(request, 'marketplace/proveedor.html', {'proveedor': obj, 'reputacion': reputacion(obj.opiniones), 'page_obj': paginar(request, productos_publicos().filter(proveedor=obj).order_by('-destacado', 'nombre')), 'opiniones': paginar_opiniones_proveedor(request, obj), 'categorias': Categoria.objects.filter(productos__proveedor=obj, productos__activo=True).distinct()})


def paginar_opiniones_proveedor(request, obj):
    return Paginator(obj.opiniones.filter(estado='publicada').select_related('usuario', 'orden'), 10).get_page(request.GET.get('opiniones_page'))


@require_POST
def carrito_actualizar(request, producto_id):
    obj = get_object_or_404(Producto, pk=producto_id)
    form = CantidadForm(request.POST)
    if form.is_valid():
        try:
            cantidad = form.cleaned_data['cantidad']
            if cantidad and not productos_publicos().filter(pk=obj.pk).exists():
                raise ValidationError('Este producto ya no está disponible.')
            carrito = CarritoSesion(request.session)
            if request.POST.get('agregar'):
                cantidad += carrito.items.get(str(obj.pk), 0)
            carrito.actualizar(obj.pk, cantidad)
            messages.success(request, 'Producto agregado a la orden.' if cantidad else 'Producto retirado de la solicitud.')
        except ValidationError as exc:
            error(request, exc)
    else:
        messages.error(request, 'Indica una cantidad válida entre 0 y 999.')
    return redirect('solicitud')


def solicitud(request):
    carrito = CarritoSesion(request.session)
    grupos = carrito.grupos()
    ids_visibles = {str(l['producto'].pk) for g in grupos for l in g['lineas']}
    no_disponibles = Producto.objects.filter(pk__in=set(carrito.items)-ids_visibles)
    return render(request, 'marketplace/solicitud.html', {'grupos': grupos, 'no_disponibles': no_disponibles})


@login_required
@require_POST
def generar_orden(request, proveedor_id):
    form = SolicitudForm(request.POST)
    if form.is_valid():
        carrito = CarritoSesion(request.session)
        try:
            clave = form.cleaned_data['clave']
            existente = Orden.objects.filter(clave_solicitud=clave, comprador=request.user, proveedor_id=proveedor_id).first()
            if existente:
                return redirect('orden_detalle', pk=existente.pk)
            if str(clave) != request.session.get('claves_solicitud', {}).get(str(proveedor_id)):
                raise ValidationError('La solicitud cambió. Revisa los productos e intenta de nuevo.')
            cantidades = carrito.cantidades(proveedor_id)
            orden = orders.crear_orden(request.user, proveedor_id, cantidades, clave, form.cleaned_data['notas'])
            carrito.retirar(cantidades)
            messages.success(request, 'Orden creada correctamente. Acuerda pago y entrega directamente con el proveedor.')
            return redirect('orden_detalle', pk=orden.pk)
        except ValidationError as exc:
            error(request, exc)
    else:
        messages.error(request, 'No se pudo generar la orden. Revisa tus notas y vuelve a intentarlo.')
    return redirect('solicitud')


@login_required
def cuenta(request):
    pendientes = request.user.ordenes.filter(estado='COMPLETADA').annotate(total_detalles=Count('detalles', distinct=True), valorados=Count('opinionproducto', filter=Q(opinionproducto__usuario=request.user), distinct=True)).filter(Q(opinionproveedor__isnull=True) | Q(valorados__lt=F('total_detalles'))).select_related('proveedor')[:8]
    from servicios.application.email_verification import perfil
    from servicios.account_queries import tiendas_usuario
    return render(request, 'marketplace/cuenta.html', {'pendientes': pendientes, 'perfil': perfil(request.user), 'recientes': request.user.ordenes.select_related('proveedor')[:5], 'tiendas': tiendas_usuario(request.user), 'avisos': request.user.notificaciones.all()[:5]})


@login_required
def ordenes(request, proveedor_id=None):
    negocio = obtener_proveedor(request.user, proveedor_id) if proveedor_id else None
    qs = Orden.objects.filter(proveedor=negocio) if negocio else request.user.ordenes.all()
    return render(request, 'marketplace/ordenes.html', {'proveedor': negocio, 'page_obj': paginar(request, qs.select_related('proveedor', 'comprador'))})


@login_required
def orden_detalle(request, pk):
    obj = get_object_or_404(Orden.objects.select_related('proveedor', 'comprador').prefetch_related('detalles__producto'), pk=pk)
    if not orders.puede_ver(request.user, obj):
        raise PermissionDenied
    gestor = orders.es_gestor(request.user, obj.proveedor_id)
    valorados = set(OpinionProducto.objects.filter(orden=obj, usuario=request.user).values_list('producto_id', flat=True))
    pendientes = [d for d in obj.detalles.all() if d.producto_id not in valorados]
    return render(request, 'marketplace/orden.html', {'orden': obj, 'detalles_pendientes': pendientes, 'proveedor_pendiente': not OpinionProveedor.objects.filter(orden=obj, usuario=request.user).exists(), 'acciones': acciones(obj.estado, gestor), 'gestor': gestor, 'es_comprador': obj.comprador_id == request.user.pk, 'opinion_form': OpinionForm(), 'opiniones_producto': OpinionProducto.objects.filter(orden=obj).select_related('usuario', 'orden', 'producto'), 'opiniones_proveedor': OpinionProveedor.objects.filter(orden=obj).select_related('usuario', 'orden')})


@login_required
@require_POST
def transicion(request, pk):
    get_object_or_404(Orden, pk=pk)
    form = TransicionForm(request.POST)
    if form.is_valid():
        try:
            orders.cambiar_estado(request.user, pk, form.cleaned_data['estado'], form.cleaned_data['notas'])
            messages.success(request, 'Estado de la orden actualizado.')
        except ValidationError as exc:
            error(request, exc)
    else:
        messages.error(request, 'Estado o notas inválidos.')
    return redirect('orden_detalle', pk=pk)


@login_required
@require_POST
def opinar(request, pk, producto_id=None):
    get_object_or_404(Orden, pk=pk)
    form = OpinionForm(request.POST)
    if form.is_valid():
        try:
            reviews.crear_opinion(request.user, pk, form.cleaned_data['estrellas'], form.cleaned_data['comentario'], producto_id)
            messages.success(request, 'Opinión publicada.')
        except ValidationError as exc:
            error(request, exc)
    else:
        messages.error(request, 'Selecciona de 1 a 5 estrellas y escribe tu opinión (máximo 3000 caracteres).')
    return redirect('orden_detalle', pk=pk)


@login_required
@require_POST
def responder(request, tipo, pk):
    if tipo not in ('producto', 'proveedor'):
        raise PermissionDenied
    get_object_or_404(OpinionProducto if tipo == 'producto' else OpinionProveedor, pk=pk)
    form = RespuestaForm(request.POST)
    if form.is_valid():
        try:
            opinion = reviews.responder_opinion(request.user, tipo, pk, form.cleaned_data['respuesta'])
            messages.success(request, 'Respuesta publicada.')
            return redirect('gestion_opiniones', proveedor_id=opinion.orden.proveedor_id)
        except ValidationError as exc:
            error(request, exc)
    else:
        messages.error(request, 'Escribe una respuesta válida.')
    return redirect('gestion_negocios')


@login_required
def notificaciones(request):
    return render(request, 'marketplace/notificaciones.html', {'page_obj': paginar(request, request.user.notificaciones.all())})


@login_required
@require_POST
def leer_notificacion(request, pk):
    obj = get_object_or_404(Notificacion, pk=pk, usuario=request.user)
    obj.leida = True
    obj.save(update_fields=['leida'])
    return redirect('notificaciones')


@login_required
def dashboard(request, proveedor_id):
    obj = obtener_proveedor(request.user, proveedor_id)
    productos = obj.productos.aggregate(activos=Count('pk', filter=Q(activo=True)), agotados=Count('pk', filter=Q(stock=0)), bajos=Count('pk', filter=Q(stock__gt=0, stock__lte=F('stock_minimo'))))
    ordenes_kpi = obj.ordenes.aggregate(nuevas=Count('pk', filter=Q(estado='NUEVA')), proceso=Count('pk', filter=Q(estado__in=['VISTA', 'ACEPTADA', 'EN_PROCESO', 'ATENDIDA'])), completadas=Count('pk', filter=Q(estado='COMPLETADA')))
    from servicios.account_queries import resumen_tienda
    return render(request, 'marketplace/dashboard.html', {'proveedor': obj, 'configuracion': resumen_tienda(obj), 'kpis': {**productos, **ordenes_kpi}, 'reputacion': reputacion(obj.opiniones), 'opiniones': obj.opiniones.select_related('usuario', 'orden')[:5]})


@login_required
def inventario(request, proveedor_id):
    obj = obtener_proveedor(request.user, proveedor_id)
    if request.method == 'POST':
        form = InventarioForm(request.POST)
        if form.is_valid():
            get_object_or_404(obj.productos, pk=form.cleaned_data['producto_id'])
            try:
                catalog.actualizar_stock(request.user, obj.pk, **form.cleaned_data)
                messages.success(request, 'Inventario actualizado.')
            except ValidationError as exc:
                error(request, exc)
        else:
            messages.error(request, 'El stock y el mínimo deben ser enteros no negativos.')
        return redirect('gestion_inventario', proveedor_id=obj.pk)
    return render(request, 'marketplace/inventario.html', {'proveedor': obj, 'page_obj': paginar(request, obj.productos.select_related('proveedor').order_by('nombre'))})


@login_required
def opiniones_gestion(request, proveedor_id):
    obj = obtener_proveedor(request.user, proveedor_id)
    tipo = 'producto' if request.GET.get('tipo') == 'producto' else 'proveedor'
    qs = OpinionProducto.objects.filter(orden__proveedor=obj).select_related('producto') if tipo == 'producto' else obj.opiniones.all()
    return render(request, 'marketplace/opiniones_gestion.html', {'proveedor': obj, 'tipo': tipo, 'page_obj': paginar(request, qs.select_related('usuario', 'orden')), 'querystring': 'tipo=' + tipo})


@login_required
def membresia(request, proveedor_id):
    obj = obtener_proveedor(request.user, proveedor_id)
    return render(request, 'marketplace/membresia.html', {'proveedor': obj, 'plan': memberships.plan_actual(obj), 'membresia': memberships.membresia_vigente(obj)})
