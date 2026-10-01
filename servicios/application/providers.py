"""Casos de uso de alta, administración y equipo de negocios."""
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone
from servicios.models import (Proveedor, AdministradorProveedor, SolicitudProveedor, PlanMembresia, MembresiaProveedor, GiroComercial, RegistroAdministrativo)
from servicios.permissions import obtener_proveedor
from servicios.application.notifications import crear_notificacion, administradores
from servicios.application.orders import exigir_usuario

CAMPOS_SOLICITUD = ('nombre_negocio', 'razon_social', 'descripcion', 'correo', 'telefono', 'whatsapp', 'ubicacion', 'sitio_web')
CAMPOS_TIENDA = ('nombre', 'razon_social', 'descripcion', 'correo', 'telefono', 'whatsapp', 'ubicacion', 'sitio_web', 'horario', 'zona_cobertura', 'pedido_minimo', 'tiempo_preparacion', 'formas_entrega', 'metodos_pago_informativos')


def exigir_superusuario(usuario):
    exigir_usuario(usuario)
    if not usuario.is_superuser:
        raise PermissionDenied


def auditar(usuario, accion, objeto, detalle=''):
    RegistroAdministrativo.objects.create(usuario=usuario, accion=accion, tipo_objeto=objeto._meta.model_name, objeto_id=objeto.pk, detalle=detalle)


def validar_continuidad_equipo(acceso):
    if acceso.es_principal and not acceso.activo:
        raise ValidationError('El administrador principal debe mantener su acceso activo.')
    if acceso.pk:
        anterior = AdministradorProveedor.objects.get(pk=acceso.pk)
        otros = acceso.proveedor.accesos.exclude(pk=acceso.pk).filter(activo=True, usuario__is_active=True)
        if anterior.activo and not acceso.activo and not otros.exists():
            raise ValidationError('No puedes desactivar al último administrador activo.')
        if anterior.es_principal and (not acceso.es_principal or not acceso.activo) and not otros.filter(es_principal=True).exists():
            raise ValidationError('Asigna primero otro administrador principal activo.')
        if anterior.proveedor_id != acceso.proveedor_id or anterior.usuario_id != acceso.usuario_id:
            raise ValidationError('No se puede trasladar un acceso a otra tienda o usuario.')


def giros_validos(giros):
    ids = {g.pk if isinstance(g, GiroComercial) else int(g) for g in giros}
    if not ids or GiroComercial.objects.filter(pk__in=ids, activo=True).count() != len(ids):
        raise ValidationError('Selecciona al menos un giro activo.')
    return ids


@transaction.atomic
def solicitar_proveedor(usuario, datos):
    exigir_usuario(usuario)
    get_user_model().objects.select_for_update().get(pk=usuario.pk)
    if SolicitudProveedor.objects.filter(usuario=usuario, estado__in=['PENDIENTE', 'EN_REVISION']).exists():
        raise ValidationError('Ya tienes una solicitud pendiente o en revisión.')
    giros = giros_validos(datos.get('giros', []))
    solicitud = SolicitudProveedor(usuario=usuario, **{k: datos.get(k, '') for k in CAMPOS_SOLICITUD})
    solicitud.full_clean()
    solicitud.save()
    solicitud.giros.set(giros)
    crear_notificacion([usuario.pk], 'solicitud_recibida', 'Recibimos tu solicitud de tienda', 'Nuestro equipo revisará los datos de tu negocio.', '/quiero-vender/')
    supers = get_user_model().objects.filter(is_superuser=True, is_active=True).values_list('pk', flat=True)
    crear_notificacion(supers, 'solicitud_nueva', 'Nueva solicitud de proveedor', solicitud.nombre_negocio, f'/administracion/solicitudes/{solicitud.pk}/')
    auditar(usuario, 'solicitud_creada', solicitud)
    return solicitud


def plan_gratis():
    plan, _ = PlanMembresia.objects.get_or_create(nombre='GRATIS', defaults={'precio': 0, 'max_productos': 5, 'max_usuarios': 1, 'duracion_dias': 30, 'promociones': False})
    if not plan.activo or plan.precio != 0 or plan.max_usuarios == 0:
        raise ValidationError('El plan GRATIS debe estar activo, ser gratuito y admitir al menos un administrador.')
    return plan


def _asignar_membresia(usuario, proveedor, plan):
    if not plan.activo or plan.duracion_dias < 1:
        raise ValidationError('El plan debe estar activo y tener duración válida.')
    if plan.max_productos is not None and proveedor.productos.count() > plan.max_productos:
        raise ValidationError('El negocio supera el límite de productos del nuevo plan.')
    if plan.max_usuarios is not None and proveedor.accesos.filter(activo=True).count() > plan.max_usuarios:
        raise ValidationError('Desactiva accesos excedentes antes de cambiar a este plan.')
    if plan.max_usuarios == 0:
        raise ValidationError('La tienda necesita al menos un administrador.')
    MembresiaProveedor.objects.filter(proveedor=proveedor, activa=True).update(activa=False)
    hoy = timezone.localdate()
    membresia = MembresiaProveedor.objects.create(proveedor=proveedor, plan=plan, inicio=hoy, fin=hoy+timedelta(days=plan.duracion_dias))
    auditar(usuario, 'membresia_asignada', proveedor, f'Plan {plan.nombre}; membresía {membresia.pk}')
    return membresia


@transaction.atomic
def asignar_membresia(usuario, proveedor_id, plan_id):
    exigir_superusuario(usuario)
    proveedor = Proveedor.objects.select_for_update().get(pk=proveedor_id)
    plan = PlanMembresia.objects.get(pk=plan_id)
    return _asignar_membresia(usuario, proveedor, plan)


def _crear_proveedor(usuario, datos, administrador, plan, estado):
    if not administrador.is_active:
        raise ValidationError('El administrador seleccionado debe ser un usuario activo.')
    if estado not in Proveedor.Estado.values:
        raise ValidationError('Estado de proveedor inválido.')
    proveedor = Proveedor(**{k: datos[k] for k in CAMPOS_TIENDA if k in datos}, estado=estado, verificado=False)
    proveedor.full_clean()
    proveedor.save()
    proveedor.giros.set(giros_validos(datos.get('giros', [])))
    _asignar_membresia(usuario, proveedor, plan)
    AdministradorProveedor.objects.create(proveedor=proveedor, usuario=administrador, activo=True, es_principal=True)
    auditar(usuario, 'proveedor_creado', proveedor, f'Administrador principal: {administrador.pk}')
    return proveedor


@transaction.atomic
def crear_proveedor_manual(usuario, datos, administrador_id, plan_id, estado):
    exigir_superusuario(usuario)
    administrador = get_user_model().objects.get(pk=administrador_id)
    proveedor = _crear_proveedor(usuario, datos, administrador, PlanMembresia.objects.get(pk=plan_id), estado)
    crear_notificacion([administrador.pk], 'equipo_agregado', 'Tu tienda está preparada', proveedor.nombre, '/gestion/')
    return proveedor


@transaction.atomic
def revisar_solicitud(usuario, solicitud_id, destino, notas=''):
    exigir_superusuario(usuario)
    solicitud = SolicitudProveedor.objects.select_for_update().select_related('usuario').get(pk=solicitud_id)
    permitidos = {'PENDIENTE': {'EN_REVISION', 'APROBADA', 'RECHAZADA'}, 'EN_REVISION': {'APROBADA', 'RECHAZADA'}}
    if destino not in permitidos.get(solicitud.estado, set()):
        raise ValidationError('La solicitud ya fue revisada o la transición no es válida.')
    if len(notas) > 3000:
        raise ValidationError('Las notas no pueden superar 3000 caracteres.')
    if destino == 'RECHAZADA' and not notas.strip():
        raise ValidationError('Indica el motivo del rechazo para orientar al solicitante.')
    if destino == 'APROBADA':
        datos = {k: getattr(solicitud, k) for k in CAMPOS_SOLICITUD if k != 'nombre_negocio'}
        datos.update(nombre=solicitud.nombre_negocio, giros=list(solicitud.giros.all()))
        solicitud.proveedor = _crear_proveedor(usuario, datos, solicitud.usuario, plan_gratis(), 'activo')
    solicitud.estado = destino
    solicitud.fecha_revision = timezone.now()
    solicitud.notas_admin = notas.strip()
    solicitud.save(update_fields=['estado', 'fecha_revision', 'notas_admin', 'proveedor'])
    crear_notificacion([solicitud.usuario_id], 'solicitud_'+destino.lower(), f'Solicitud {solicitud.get_estado_display().lower()}', notas or solicitud.nombre_negocio, '/quiero-vender/')
    auditar(usuario, 'solicitud_'+destino.lower(), solicitud, notas)
    return solicitud


@transaction.atomic
def administrar_proveedor(usuario, proveedor_id, accion, notas=''):
    exigir_superusuario(usuario)
    proveedor = Proveedor.objects.select_for_update().get(pk=proveedor_id)
    anterior = proveedor.estado
    if accion in {'activar', 'reactivar', 'suspender'}:
        reglas = {'activar': ({'inactivo'}, 'activo'), 'reactivar': ({'suspendido'}, 'activo'), 'suspender': ({'activo', 'inactivo'}, 'suspendido')}
        origen, destino = reglas[accion]
        if anterior not in origen:
            raise ValidationError('La acción no corresponde al estado actual del proveedor.')
        if destino == 'activo' and not proveedor.accesos.filter(es_principal=True, activo=True, usuario__is_active=True).exists():
            raise ValidationError('Asigna un administrador principal activo antes de publicar la tienda.')
        proveedor.estado = destino
    elif accion in {'verificar', 'quitar_verificacion'}:
        verificar = accion == 'verificar'
        if proveedor.verificado == verificar:
            raise ValidationError('El estado de verificación ya coincide con la acción.')
        proveedor.verificado = verificar
        proveedor.fecha_verificacion = timezone.now() if verificar else None
    else:
        raise ValidationError('Acción administrativa inválida.')
    proveedor.save(update_fields=['estado', 'verificado', 'fecha_verificacion'])
    auditar(usuario, 'proveedor_'+accion, proveedor, f'{anterior} → {proveedor.estado}. {notas}')
    if accion in {'activar', 'reactivar', 'suspender'}:
        crear_notificacion(administradores(proveedor), 'proveedor_'+accion, f'Tu tienda está {proveedor.get_estado_display().lower()}', notas or proveedor.nombre, '/gestion/')
    return proveedor


def puede_gestionar_equipo(usuario, proveedor):
    return usuario.is_authenticated and usuario.is_active and (usuario.is_superuser or (proveedor.estado == 'activo' and proveedor.accesos.filter(usuario=usuario, activo=True, es_principal=True).exists()))


def exigir_equipo(usuario, proveedor):
    if not puede_gestionar_equipo(usuario, proveedor):
        raise PermissionDenied


@transaction.atomic
def agregar_equipo(usuario, proveedor_id, username):
    proveedor = Proveedor.objects.select_for_update().get(pk=proveedor_id)
    exigir_equipo(usuario, proveedor)
    destino = get_user_model().objects.filter(username=username, is_active=True).first()
    if destino is None:
        raise ValidationError('No se encontró un usuario activo con ese nombre exacto.')
    if proveedor.accesos.filter(usuario=destino).exists():
        raise ValidationError('El usuario ya tiene un acceso. Reactívalo si corresponde.')
    acceso = AdministradorProveedor(proveedor=proveedor, usuario=destino, activo=True)
    acceso.save()
    auditar(usuario, 'equipo_agregado', proveedor, f'Usuario {destino.pk}')
    crear_notificacion([destino.pk], 'equipo_agregado', 'Te agregaron a un equipo', proveedor.nombre, '/gestion/')
    return acceso


@transaction.atomic
def cambiar_acceso(usuario, proveedor_id, acceso_id, accion):
    proveedor = Proveedor.objects.select_for_update().get(pk=proveedor_id)
    exigir_equipo(usuario, proveedor)
    acceso = proveedor.accesos.select_for_update().select_related('usuario').filter(pk=acceso_id).first()
    if acceso is None:
        raise PermissionDenied
    if accion == 'desactivar':
        acceso.activo = False
        acceso.es_principal = False
    elif accion == 'reactivar':
        if not acceso.usuario.is_active:
            raise ValidationError('Primero debe activarse la cuenta de usuario.')
        acceso.activo = True
    elif accion == 'principal':
        if not acceso.activo or not acceso.usuario.is_active:
            raise ValidationError('El principal debe ser un usuario con acceso activo.')
        acceso.es_principal = True
    elif accion == 'colaborador':
        acceso.es_principal = False
    else:
        raise ValidationError('Acción de equipo inválida.')
    acceso.save()
    auditar(usuario, 'equipo_'+accion, proveedor, f'Usuario {acceso.usuario_id}')
    if accion == 'reactivar':
        crear_notificacion([acceso.usuario_id], 'equipo_reactivado', 'Tu acceso fue reactivado', proveedor.nombre, '/gestion/')
    return acceso
