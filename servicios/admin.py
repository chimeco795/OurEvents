from django.contrib import admin
from .models import Categoria, Producto, ProductoImagen, Comentario, Proveedor, AdministradorProveedor, GiroComercial, Profile

# El panel global nunca se concede a administradores de negocios por is_staff.
admin.site.has_permission = lambda request: request.user.is_active and request.user.is_superuser

class ImagenInline(admin.TabularInline):
    model = ProductoImagen
    extra = 1

class AccesoInline(admin.TabularInline):
    model = AdministradorProveedor
    extra = 1

@admin.register(Proveedor)
class ProveedorAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'estado', 'verificado']
    list_filter = ['estado', 'verificado']
    inlines = [AccesoInline]

@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'proveedor', 'stock', 'activo']
    list_filter = ['proveedor', 'activo']
    inlines = [ImagenInline]

admin.site.register([Categoria, Comentario, GiroComercial, Profile])
