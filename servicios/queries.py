"""Consultas de lectura del marketplace, separadas de comandos y vistas."""
from django.db.models import Avg, Count, Q, F, Case, When, Value, IntegerField
from django.db.models.functions import Coalesce
from servicios.models import Producto, Proveedor, Categoria, OpinionProducto, OpinionProveedor


def categorias_visibles():
    categorias = list(Categoria.objects.all())
    ocultas = {c.pk for c in categorias if not c.activa}
    while True:
        nuevas = {c.pk for c in categorias if c.padre_id in ocultas} - ocultas
        if not nuevas:
            break
        ocultas |= nuevas
    return [c.pk for c in categorias if c.pk not in ocultas]


def descendientes(pk):
    pares = list(Categoria.objects.values_list('pk', 'padre_id'))
    ids = {pk}
    while True:
        nuevos = {hijo for hijo, padre in pares if padre in ids} - ids
        if not nuevos:
            return ids
        ids |= nuevos


def productos_publicos():
    publicadas = Q(opiniones__estado='publicada', opiniones__orden__estado='COMPLETADA', opiniones__usuario_id=F('opiniones__orden__comprador_id'))
    return Producto.objects.filter(activo=True, proveedor__estado='activo', categoria_id__in=categorias_visibles()).select_related('proveedor', 'categoria', 'categoria__padre').prefetch_related('imagenes').annotate(valoracion=Coalesce(Avg('opiniones__estrellas', filter=publicadas), 0.0), numero_opiniones=Count('opiniones', filter=publicadas, distinct=True), precio_venta=Coalesce('precio_promocional', 'precio'))


def proveedores_publicos():
    return Proveedor.objects.filter(estado='activo').prefetch_related('giros').annotate(valoracion=Coalesce(Avg('opiniones__estrellas', filter=Q(opiniones__estado='publicada', opiniones__orden__estado='COMPLETADA', opiniones__usuario_id=F('opiniones__orden__comprador_id'))), 0.0), numero_opiniones=Count('opiniones', filter=Q(opiniones__estado='publicada'), distinct=True), completadas=Count('ordenes', filter=Q(ordenes__estado='COMPLETADA'), distinct=True))


def buscar_productos(datos):
    qs = productos_publicos()
    texto = datos.get('q', '')
    if texto:
        categorias = Categoria.objects.filter(nombre__icontains=texto).values_list('pk', flat=True)
        ids = set()
        for pk in categorias:
            ids |= descendientes(pk)
        qs = qs.filter(Q(nombre__icontains=texto) | Q(descripcion__icontains=texto) | Q(proveedor__nombre__icontains=texto) | Q(proveedor__giros__nombre__icontains=texto) | Q(categoria_id__in=ids)).distinct()
    for campo in ['proveedor', 'giro']:
        if datos.get(campo):
            qs = qs.filter(**{('proveedor__giros' if campo == 'giro' else campo): datos[campo]}).distinct()
    if datos.get('categoria'):
        qs = qs.filter(categoria_id__in=descendientes(datos['categoria'].pk))
    if datos.get('minimo') is not None:
        qs = qs.filter(precio_venta__gte=datos['minimo'])
    if datos.get('maximo') is not None:
        qs = qs.filter(precio_venta__lte=datos['maximo'])
    if datos.get('disponible'):
        qs = qs.filter(stock__gt=0)
    if datos.get('valoracion'):
        qs = qs.filter(valoracion__gte=datos['valoracion'])
    orden = datos.get('orden', 'relevancia')
    ordenes = {'nombre': ('nombre', 'pk'), 'recientes': ('-fecha_creacion', '-pk'), 'precio': ('precio_venta', 'pk'), '-precio': ('-precio_venta', 'pk'), 'valoracion': ('-valoracion', '-numero_opiniones', 'pk')}
    if orden == 'relevancia':
        qs = qs.annotate(relevancia=Case(When(nombre__icontains=texto, then=Value(2)), When(proveedor__nombre__icontains=texto, then=Value(1)), default=Value(0), output_field=IntegerField())).order_by('-relevancia', '-destacado', 'pk')
    else:
        qs = qs.order_by(*ordenes.get(orden, ('pk',)))
    return qs


def reputacion(opiniones):
    qs = opiniones.filter(estado='publicada', orden__estado='COMPLETADA', usuario_id=F('orden__comprador_id'))
    resumen = qs.aggregate(promedio=Avg('estrellas'), total=Count('pk'))
    conteos = dict(qs.order_by().values_list('estrellas').annotate(total=Count('pk')))
    resumen['distribucion'] = [(n, conteos.get(n, 0), round(conteos.get(n, 0)*100 / resumen['total']) if resumen['total'] else 0) for n in range(5, 0, -1)]
    return resumen
