from datetime import date
from uuid import uuid4
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.db.models import Q, F
from django.utils.text import slugify
from django.utils import timezone


def asignar_slug(obj):
    if not obj.slug:
        obj.slug = f'{slugify(obj.nombre)[:70] or "registro"}-{uuid4().hex[:12]}'


class GiroComercial(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True, blank=True)
    activo = models.BooleanField(default=True)

    def save(self, *args, **kwargs):
        asignar_slug(self)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.nombre


class Proveedor(models.Model):
    class Estado(models.TextChoices):
        ACTIVO = 'activo', 'Activo'
        INACTIVO = 'inactivo', 'Inactivo'
        SUSPENDIDO = 'suspendido', 'Suspendido'

    nombre = models.CharField(max_length=150)
    slug = models.SlugField(max_length=100, unique=True, blank=True)
    razon_social = models.CharField(max_length=200, blank=True)
    descripcion = models.TextField(blank=True)
    logotipo = models.ImageField(upload_to='proveedores/logos/', blank=True)
    portada = models.ImageField(upload_to='proveedores/portadas/', blank=True)
    telefono = models.CharField(max_length=30, blank=True)
    correo = models.EmailField(blank=True)
    whatsapp = models.CharField(max_length=30, blank=True)
    sitio_web = models.URLField(blank=True)
    ubicacion = models.CharField(max_length=250, blank=True)
    estado = models.CharField(max_length=12, choices=Estado.choices, default=Estado.INACTIVO)
    fecha_alta = models.DateTimeField(auto_now_add=True)
    verificado = models.BooleanField(default=False)
    fecha_verificacion = models.DateTimeField(null=True, blank=True)
    giros = models.ManyToManyField(GiroComercial, blank=True, related_name='proveedores')
    administradores = models.ManyToManyField(settings.AUTH_USER_MODEL, through='AdministradorProveedor', related_name='proveedores')

    def save(self, *args, **kwargs):
        asignar_slug(self)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.nombre


class AdministradorProveedor(models.Model):
    proveedor = models.ForeignKey(Proveedor, on_delete=models.CASCADE, related_name='accesos')
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    activo = models.BooleanField(default=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['proveedor', 'usuario'], name='administrador_proveedor_unico')]


class Categoria(models.Model):
    nombre = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100, unique=True, blank=True)
    padre = models.ForeignKey('self', on_delete=models.PROTECT, null=True, blank=True, related_name='subcategorias')
    activa = models.BooleanField(default=True)
    orden = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['orden', 'nombre']

    def clean(self):
        super().clean()
        visitados = {self.pk} if self.pk else set()
        padre = self.padre
        while padre:
            if padre.pk in visitados:
                raise ValidationError({'padre': 'La jerarquía no puede contener ciclos.'})
            visitados.add(padre.pk)
            padre = padre.padre

    def save(self, *args, **kwargs):
        self.clean()
        asignar_slug(self)
        super().save(*args, **kwargs)

    @property
    def nivel(self):
        nivel, padre = 0, self.padre
        while padre:
            nivel, padre = nivel + 1, padre.padre
        return nivel

    def __str__(self):
        return self.nombre


class Producto(models.Model):
    proveedor = models.ForeignKey(Proveedor, on_delete=models.PROTECT, related_name='productos')
    categoria = models.ForeignKey(Categoria, on_delete=models.PROTECT, related_name='productos')
    nombre = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100, unique=True, blank=True)
    descripcion_corta = models.CharField(max_length=250, blank=True)
    descripcion = models.TextField()
    precio = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    precio_promocional = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)])
    # Compatibilidad con archivos y templates existentes; la galería es la fuente nueva.
    imagen = models.ImageField(upload_to='productos/', blank=True)
    stock = models.PositiveIntegerField(default=0)
    stock_minimo = models.PositiveIntegerField(default=0)
    sku = models.CharField(max_length=80, blank=True)
    activo = models.BooleanField(default=True)
    destacado = models.BooleanField(default=False)
    fecha_creacion = models.DateTimeField(default=timezone.now)
    fecha_modificacion = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(precio__gte=0), name='precio_no_negativo'),
            models.CheckConstraint(condition=Q(precio_promocional__isnull=True) | (Q(precio_promocional__gte=0) & Q(precio_promocional__lte=F('precio'))), name='promocion_valida'),
            models.UniqueConstraint(fields=['proveedor', 'sku'], condition=~Q(sku=''), name='sku_unico_por_proveedor'),
        ]

    def clean(self):
        super().clean()
        if self.precio_promocional is not None and self.precio is not None and self.precio_promocional > self.precio:
            raise ValidationError({'precio_promocional': 'La promoción no puede superar el precio.'})

    def save(self, *args, **kwargs):
        asignar_slug(self)
        super().save(*args, **kwargs)

    @property
    def disponibilidad(self):
        if not self.activo or self.proveedor.estado != Proveedor.Estado.ACTIVO:
            return 'Inactivo'
        if self.stock == 0:
            return 'Agotado'
        return 'Stock bajo' if self.stock <= self.stock_minimo else 'Disponible'

    @property
    def imagen_portada(self):
        primera = next(iter(self.imagenes.all()), None)
        return primera.imagen if primera else self.imagen

    def __str__(self):
        return self.nombre


class ProductoImagen(models.Model):
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE, related_name='imagenes')
    imagen = models.ImageField(upload_to='productos/galeria/')
    orden = models.PositiveIntegerField(default=0)
    principal = models.BooleanField(default=False)
    texto_alternativo = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ['-principal', 'orden', 'pk']
        constraints = [models.UniqueConstraint(fields=['producto'], condition=Q(principal=True), name='imagen_principal_unica')]


class Comentario(models.Model):
    nombre = models.CharField(max_length=100)
    comentario = models.TextField()
    imagen = models.ImageField(upload_to='comentarios/', blank=True, null=True)
    calificacion = models.PositiveIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    fecha = models.DateField(default=date.today)


class Profile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    photo = models.ImageField(upload_to='profiles/', blank=True, null=True)

    def __str__(self):
        return f'Perfil de {self.user.username}'
