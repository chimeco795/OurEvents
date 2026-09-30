from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404
from .models import Proveedor


def proveedores_administrables(usuario):
    if usuario.is_superuser:
        return Proveedor.objects.all()
    return Proveedor.objects.filter(accesos__usuario=usuario, accesos__activo=True, estado=Proveedor.Estado.ACTIVO)


def obtener_proveedor(usuario, pk):
    if not usuario.is_authenticated or not usuario.is_active:
        raise PermissionDenied
    return get_object_or_404(proveedores_administrables(usuario), pk=pk)
