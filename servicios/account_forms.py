from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from servicios.models import Profile, PlanMembresia

class RegistroCuentaForm(UserCreationForm):
    email = forms.EmailField(label='Correo')
    first_name = forms.CharField(label='Nombre', max_length=150)
    last_name = forms.CharField(label='Apellido', max_length=150)
    class Meta(UserCreationForm.Meta):
        fields = ['username', 'first_name', 'last_name', 'email']

class DatosCuentaForm(forms.ModelForm):
    email = forms.EmailField(label='Correo')
    class Meta:
        model = get_user_model()
        fields = ['first_name', 'last_name', 'email']

class PerfilCuentaForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['telefono', 'photo']
        labels = {'photo': 'Foto', 'telefono': 'Teléfono'}

class PreferenciasForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['email_nueva_orden', 'email_cambio_orden', 'email_nueva_opinion', 'email_administracion']
        labels = {'email_nueva_orden': 'Nueva orden por email', 'email_cambio_orden': 'Cambios de orden por email', 'email_nueva_opinion': 'Opiniones por email', 'email_administracion': 'Administración de tienda por email'}

class NuevoUsuarioForm(DatosCuentaForm):
    class Meta(DatosCuentaForm.Meta):
        fields = ['username', 'first_name', 'last_name', 'email', 'is_active']

class RecuperarForm(forms.Form):
    email = forms.EmailField(label='Correo electrónico')

class PlanForm(forms.ModelForm):
    confirmar_impacto = forms.BooleanField(required=False, label='Confirmo el impacto sobre proveedores excedidos')
    class Meta:
        model = PlanMembresia
        fields = ['nombre', 'precio', 'duracion_dias', 'max_productos', 'max_usuarios', 'promociones', 'estadisticas', 'activo']
        labels = {'duracion_dias': 'Duración en días', 'max_productos': 'Máximo de productos', 'max_usuarios': 'Máximo de usuarios'}
        help_texts = {'max_usuarios': 'Vacío significa ilimitado.', 'max_productos': 'Vacío significa ilimitado.'}
