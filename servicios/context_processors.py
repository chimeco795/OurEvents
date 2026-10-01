def marketplace(request):
    from servicios.permissions import proveedores_administrables
    tiendas = proveedores_administrables(request.user).only('pk', 'nombre') if request.user.is_authenticated and request.path.startswith('/gestion/') else []
    return {'tiendas_contexto': tiendas, 'notificaciones_pendientes': request.user.notificaciones.filter(leida=False).count() if request.user.is_authenticated else 0, 'cantidad_solicitud': sum(request.session.get('solicitud', {}).values())}
