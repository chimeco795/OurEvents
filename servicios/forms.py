from django import forms
from django.forms import inlineformset_factory, BaseInlineFormSet
from .models import Producto, ProductoImagen, Proveedor, Categoria, Comentario

class ProductoForm(forms.ModelForm):
    stock_anterior = forms.IntegerField(required=False, widget=forms.HiddenInput)
    class Meta:
        model = Producto
        fields = ['categoria', 'nombre', 'descripcion_corta', 'descripcion', 'precio', 'precio_promocional', 'stock', 'stock_minimo', 'sku', 'activo']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['categoria'].queryset = Categoria.objects.filter(activa=True)
        if self.instance.pk:
            self.fields['stock_anterior'].initial = self.instance.stock

    def clean(self):
        datos = super().clean()
        from servicios.application.memberships import plan_actual
        plan = plan_actual(self.instance.proveedor)
        if not self.instance.pk and plan.max_productos is not None and self.instance.proveedor.productos.count() >= plan.max_productos:
            raise forms.ValidationError('Alcanzaste el límite de productos de tu membresía.')
        if datos.get('precio_promocional') is not None and not plan.promociones:
            self.add_error('precio_promocional', 'Tu membresía no permite promociones.')
        return datos

    def clean_sku(self):
        sku = self.cleaned_data.get('sku', '')
        if sku and Producto.objects.filter(proveedor_id=self.instance.proveedor_id, sku=sku).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError('Este SKU ya existe en el negocio.')
        return sku

class ProveedorForm(forms.ModelForm):
    class Meta:
        model = Proveedor
        fields = ['nombre', 'razon_social', 'descripcion', 'logotipo', 'portada', 'telefono', 'correo', 'whatsapp', 'sitio_web', 'ubicacion', 'giros']

class ComentarioForm(forms.ModelForm):
    class Meta:
        model = Comentario
        fields = ['comentario', 'imagen', 'calificacion']

class ContactoForm(forms.Form):
    correo = forms.EmailField()
    asunto = forms.CharField(max_length=150)
    mensaje = forms.CharField(max_length=5000, widget=forms.Textarea)

class ImagenesFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return
        principales = 0
        for form in self.forms:
            datos = form.cleaned_data
            imagen = datos.get('id')
            if imagen and imagen.producto_id != self.instance.pk:
                raise forms.ValidationError('La imagen no pertenece a este producto.')
            if datos and not datos.get('DELETE') and datos.get('principal'):
                principales += 1
        if principales > 1:
            raise forms.ValidationError('Selecciona una sola imagen principal.')

ImagenFormSet = inlineformset_factory(Producto, ProductoImagen, fields=['imagen', 'orden', 'principal', 'texto_alternativo'], formset=ImagenesFormSet, extra=1, max_num=10, validate_max=True)

from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from .models import GiroComercial


class BusquedaForm(forms.Form):
    q = forms.CharField(required=False, max_length=150, label='Buscar')
    categoria = forms.ModelChoiceField(queryset=Categoria.objects.filter(activa=True), required=False, label='Categoría')
    giro = forms.ModelChoiceField(queryset=GiroComercial.objects.filter(activo=True), required=False)
    proveedor = forms.ModelChoiceField(queryset=Proveedor.objects.filter(estado='activo'), required=False)
    minimo = forms.DecimalField(required=False, min_value=0, max_digits=10, decimal_places=2, label='Precio mínimo')
    maximo = forms.DecimalField(required=False, min_value=0, max_digits=10, decimal_places=2, label='Precio máximo')
    disponible = forms.BooleanField(required=False, label='Sólo con stock')
    valoracion = forms.IntegerField(required=False, min_value=1, max_value=5, label='Valoración mínima')
    orden = forms.ChoiceField(required=False, choices=[('relevancia', 'Relevancia'), ('nombre', 'Nombre A–Z'), ('recientes', 'Más recientes'), ('precio', 'Precio menor'), ('-precio', 'Precio mayor'), ('valoracion', 'Mejor valoración')])

    def clean(self):
        datos = super().clean()
        if datos.get('minimo') is not None and datos.get('maximo') is not None and datos['minimo'] > datos['maximo']:
            raise forms.ValidationError('El precio mínimo no puede superar el máximo.')
        return datos


class CantidadForm(forms.Form):
    cantidad = forms.IntegerField(min_value=0, max_value=999, initial=1)


class SolicitudForm(forms.Form):
    clave = forms.UUIDField(widget=forms.HiddenInput)
    notas = forms.CharField(required=False, max_length=3000, widget=forms.Textarea(attrs={'rows': 2}), label='Notas para el proveedor')


class TransicionForm(forms.Form):
    estado = forms.CharField(max_length=12)
    notas = forms.CharField(required=False, max_length=3000)


class OpinionForm(forms.Form):
    estrellas = forms.TypedChoiceField(choices=[(n, f'{n} ★') for n in range(5, 0, -1)], coerce=int)
    comentario = forms.CharField(max_length=3000, widget=forms.Textarea(attrs={'rows': 3}))


class RespuestaForm(forms.Form):
    respuesta = forms.CharField(max_length=3000, widget=forms.Textarea(attrs={'rows': 3}))


class InventarioForm(forms.Form):
    producto_id = forms.IntegerField(widget=forms.HiddenInput)
    stock_anterior = forms.IntegerField(min_value=0, widget=forms.HiddenInput)
    stock = forms.IntegerField(min_value=0, max_value=2147483647)
    stock_minimo = forms.IntegerField(min_value=0, max_value=2147483647)


class PerfilForm(forms.ModelForm):
    class Meta:
        model = get_user_model()
        fields = ['first_name', 'last_name', 'email']


class RegistroForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        fields = ['username', 'email']
