from django import forms
from django.forms import inlineformset_factory, BaseInlineFormSet
from .models import Producto, ProductoImagen, Proveedor, Categoria, Comentario

class ProductoForm(forms.ModelForm):
    class Meta:
        model = Producto
        fields = ['categoria', 'nombre', 'descripcion_corta', 'descripcion', 'precio', 'precio_promocional', 'stock', 'stock_minimo', 'sku', 'activo']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['categoria'].queryset = Categoria.objects.filter(activa=True)

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
