from django import forms
from django.contrib.auth import get_user_model
from servicios.models import SolicitudProveedor, Proveedor, GiroComercial, PlanMembresia, ReporteContenido
from servicios.forms import ProveedorForm


class SolicitudProveedorForm(forms.ModelForm):
    class Meta:
        model = SolicitudProveedor
        fields = ['nombre_negocio', 'razon_social', 'descripcion', 'correo', 'telefono', 'whatsapp', 'ubicacion', 'sitio_web', 'giros']
        widgets = {'descripcion': forms.Textarea(attrs={'rows': 4}), 'giros': forms.CheckboxSelectMultiple}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['giros'].queryset = GiroComercial.objects.filter(activo=True)


class NuevoProveedorForm(ProveedorForm):
    administrador = forms.ModelChoiceField(queryset=get_user_model().objects.filter(is_active=True), label='Administrador principal')
    plan = forms.ModelChoiceField(queryset=PlanMembresia.objects.filter(activo=True))
    estado = forms.ChoiceField(choices=Proveedor.Estado.choices, initial='inactivo')

    class Meta(ProveedorForm.Meta):
        fields = ['nombre', 'razon_social', 'descripcion', 'correo', 'telefono', 'whatsapp', 'ubicacion', 'sitio_web', 'giros']


class AccionSolicitudForm(forms.Form):
    estado = forms.ChoiceField(choices=[('EN_REVISION', 'En revisión'), ('APROBADA', 'Aprobar'), ('RECHAZADA', 'Rechazar')])
    notas = forms.CharField(required=False, max_length=3000, widget=forms.Textarea(attrs={'rows': 3}))


class AccionProveedorForm(forms.Form):
    accion = forms.ChoiceField(choices=[(s,s) for s in ['activar','reactivar','suspender','verificar','quitar_verificacion']])
    notas = forms.CharField(required=False, max_length=3000)


class AsignarMembresiaForm(forms.Form):
    plan = forms.ModelChoiceField(queryset=PlanMembresia.objects.filter(activo=True))


class AgregarEquipoForm(forms.Form):
    username = forms.CharField(max_length=150, label='Nombre de usuario existente', help_text='Escribe el nombre exacto. El usuario debe tener una cuenta activa.')


class AccionEquipoForm(forms.Form):
    acceso_id = forms.IntegerField(min_value=1)
    accion = forms.ChoiceField(choices=[(s,s) for s in ['desactivar','reactivar','principal','colaborador']])


class ReporteForm(forms.ModelForm):
    class Meta:
        model = ReporteContenido
        fields = ['motivo', 'comentario']
        widgets = {'comentario': forms.Textarea(attrs={'rows': 4})}


class ModeracionForm(forms.Form):
    accion = forms.ChoiceField(choices=[(s,s) for s in ['revisar','descartar','desactivar_producto','suspender_proveedor','ocultar_opinion']])
    notas = forms.CharField(required=False, max_length=3000, widget=forms.Textarea(attrs={'rows': 3}))
