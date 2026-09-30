from django.contrib import admin
from django import forms
from servicios.models import (Categoria, Producto, ProductoImagen, Comentario, Proveedor, AdministradorProveedor, GiroComercial, Profile, Orden, OrdenDetalle, OpinionProducto, OpinionProveedor, Notificacion, PlanMembresia, MembresiaProveedor)
from servicios.application.memberships import validar_producto

admin.site.has_permission = lambda request: request.user.is_active and request.user.is_superuser
admin.site.site_header = 'OurEvents · Administración'
admin.site.site_title = 'OurEvents'

class ImagenInline(admin.TabularInline):
    model = ProductoImagen
    extra = 1

class AccesosFormSet(forms.models.BaseInlineFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return
        from servicios.application.memberships import plan_actual
        limite = plan_actual(self.instance).max_usuarios if self.instance.pk else 1
        activos = sum(bool(f.cleaned_data.get('activo')) for f in self.forms if f.cleaned_data and not f.cleaned_data.get('DELETE'))
        if limite is not None and activos > limite:
            raise forms.ValidationError(f'La membresía permite {limite} administradores activos.')


class AccesoInline(admin.TabularInline):
    model = AdministradorProveedor
    formset = AccesosFormSet
    extra = 0

@admin.register(Proveedor)
class ProveedorAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'estado', 'verificado', 'correo']
    list_filter = ['estado', 'verificado', 'giros']
    search_fields = ['nombre', 'razon_social', 'correo']
    readonly_fields = ['fecha_alta']
    inlines = [AccesoInline]

class ProductoAdminForm(forms.ModelForm):
    stock_anterior = forms.IntegerField(required=False, widget=forms.HiddenInput)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields['stock_anterior'].initial = self.instance.stock

    class Meta:
        model = Producto
        fields = '__all__'

    def clean(self):
        datos = super().clean()
        if self.instance.pk and datos.get('stock_anterior') != Producto.objects.get(pk=self.instance.pk).stock:
            raise forms.ValidationError('El stock cambió. Recarga antes de guardar.')
        if datos.get('proveedor'):
            self.instance.proveedor = datos['proveedor']
            self.instance.precio_promocional = datos.get('precio_promocional')
            validar_producto(self.instance)
        return datos

@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    form = ProductoAdminForm
    list_display = ['nombre', 'proveedor', 'stock', 'precio', 'activo']
    list_filter = ['proveedor', 'activo', 'categoria']
    search_fields = ['nombre', 'sku', 'proveedor__nombre']
    readonly_fields = ['fecha_creacion', 'fecha_modificacion']
    inlines = [ImagenInline]

class DetalleInline(admin.TabularInline):
    model = OrdenDetalle
    extra = 0
    can_delete = False
    readonly_fields = ['producto', 'nombre_producto_historico', 'cantidad', 'precio_unitario', 'subtotal']
    def has_add_permission(self, request, obj=None):
        return False

@admin.register(Orden)
class OrdenAdmin(admin.ModelAdmin):
    list_display = ['folio', 'comprador', 'proveedor', 'estado', 'subtotal', 'fecha_creacion']
    list_filter = ['estado', 'proveedor']
    search_fields = ['folio', 'comprador__username', 'proveedor__nombre']
    readonly_fields = [f.name for f in Orden._meta.fields]
    inlines = [DetalleInline]
    def has_add_permission(self, request):
        return False
    def has_delete_permission(self, request, obj=None):
        return False
    # Las transiciones se realizan desde /ordenes/<id>/, nunca con edición arbitraria.

class OpinionAdmin(admin.ModelAdmin):
    list_display = ['usuario', 'orden', 'estrellas', 'estado', 'fecha', 'compra_verificada']
    list_filter = ['estado', 'estrellas']
    search_fields = ['comentario', 'usuario__username', 'orden__folio']
    def get_readonly_fields(self, request, obj=None):
        return [f.name for f in self.model._meta.fields if f.name != 'estado']
    def has_add_permission(self, request):
        return False
    def has_delete_permission(self, request, obj=None):
        return False

admin.site.register(OpinionProducto, OpinionAdmin)
admin.site.register(OpinionProveedor, OpinionAdmin)

@admin.register(PlanMembresia)
class PlanAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'precio', 'max_productos', 'max_usuarios', 'promociones', 'activo']
    list_filter = ['activo', 'promociones']
    search_fields = ['nombre']

@admin.register(MembresiaProveedor)
class MembresiaAdmin(admin.ModelAdmin):
    list_display = ['proveedor', 'plan', 'inicio', 'fin', 'activa']
    list_filter = ['plan', 'activa']
    search_fields = ['proveedor__nombre']

@admin.register(Notificacion)
class NotificacionAdmin(admin.ModelAdmin):
    list_display = ['usuario', 'tipo', 'titulo', 'leida', 'fecha']
    list_filter = ['tipo', 'leida']
    search_fields = ['titulo', 'usuario__username']
    readonly_fields = [f.name for f in Notificacion._meta.fields]
    def has_add_permission(self, request):
        return False

@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'padre', 'activa', 'orden']
    list_filter = ['activa']
    search_fields = ['nombre']

admin.site.register([Comentario, GiroComercial, Profile])
