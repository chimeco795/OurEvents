from uuid import uuid4
from decimal import Decimal
from django.core.exceptions import ValidationError
from servicios.queries import productos_publicos
from servicios.application.orders import precio_actual


class CarritoSesion:
    """Adaptador de persistencia sustituible. Sólo guarda IDs/cantidades, nunca precios."""
    def __init__(self, session):
        self.session = session
        self.items = dict(session.get('solicitud', {}))

    def actualizar(self, producto_id, cantidad):
        if not 0 <= cantidad <= 999:
            raise ValidationError('Cantidad fuera del rango permitido.')
        if cantidad:
            if len(self.items) >= 100 and str(producto_id) not in self.items:
                raise ValidationError('La solicitud admite hasta 100 productos.')
            self.items[str(producto_id)] = cantidad
        else:
            self.items.pop(str(producto_id), None)
        self.session['solicitud'] = self.items
        self.session['claves_solicitud'] = {}

    def grupos(self):
        grupos = {}
        claves = self.session.get('claves_solicitud', {})
        for producto in productos_publicos().filter(pk__in=self.items).order_by('proveedor_id', 'pk'):
            grupo = grupos.setdefault(producto.proveedor_id, {'proveedor': producto.proveedor, 'lineas': [], 'subtotal': Decimal('0')})
            cantidad = self.items[str(producto.pk)]
            subtotal = precio_actual(producto)*cantidad
            grupo['lineas'].append({'producto': producto, 'cantidad': cantidad, 'subtotal': subtotal})
            grupo['subtotal'] += subtotal
            grupo['clave'] = claves.setdefault(str(producto.proveedor_id), str(uuid4()))
        self.session['claves_solicitud'] = claves
        return list(grupos.values())

    def cantidades(self, proveedor_id):
        for grupo in self.grupos():
            if grupo['proveedor'].pk == proveedor_id:
                return {linea['producto'].pk: linea['cantidad'] for linea in grupo['lineas']}
        return {}

    def retirar(self, ids):
        for pk in ids:
            self.items.pop(str(pk), None)
        self.session['solicitud'] = self.items
