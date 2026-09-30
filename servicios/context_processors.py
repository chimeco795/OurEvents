def marketplace(request):
    return {'notificaciones_pendientes': request.user.notificaciones.filter(leida=False).count() if request.user.is_authenticated else 0, 'cantidad_solicitud': sum(request.session.get('solicitud', {}).values())}
