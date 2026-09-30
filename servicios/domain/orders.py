"""Reglas puras del agregado Orden: sin HTTP ni infraestructura."""
TRANSICIONES_PROVEEDOR = {
    'NUEVA': ('VISTA', 'RECHAZADA', 'CANCELADA'),
    'VISTA': ('ACEPTADA', 'RECHAZADA', 'CANCELADA'),
    'ACEPTADA': ('EN_PROCESO', 'CANCELADA'),
    'EN_PROCESO': ('ATENDIDA', 'CANCELADA'),
    'ATENDIDA': ('COMPLETADA', 'CANCELADA'),
}
TRANSICIONES_COMPRADOR = {'NUEVA': ('CANCELADA',), 'VISTA': ('CANCELADA',)}
RESERVADOS = {'ACEPTADA', 'EN_PROCESO', 'ATENDIDA'}


def acciones(estado, es_proveedor):
    return (TRANSICIONES_PROVEEDOR if es_proveedor else TRANSICIONES_COMPRADOR).get(estado, ())
