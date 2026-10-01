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
    horario = models.CharField(max_length=250, blank=True)
    zona_cobertura = models.CharField(max_length=250, blank=True)
    pedido_minimo = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)])
    tiempo_preparacion = models.CharField(max_length=200, blank=True)
    formas_entrega = models.TextField(blank=True, max_length=1000)
    metodos_pago_informativos = models.TextField(blank=True, max_length=1000)
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
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    activo = models.BooleanField(default=True)
    es_principal = models.BooleanField(default=False)

    def clean(self):
        super().clean()
        from servicios.application.memberships import validar_administrador
        if self.proveedor_id:
            validar_administrador(self)
            from servicios.application.providers import validar_continuidad_equipo
            validar_continuidad_equipo(self)

    def save(self, *args, **kwargs):
        from django.db import transaction
        with transaction.atomic():
            Proveedor.objects.select_for_update().get(pk=self.proveedor_id)
            if not self.pk and self.activo and not self.proveedor.accesos.filter(activo=True, es_principal=True).exists():
                self.es_principal = True
            self.clean()
            super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError('Desactiva el acceso desde Equipo para conservar el historial.')

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
        from django.db import transaction
        from servicios.application.memberships import validar_producto
        with transaction.atomic():
            Proveedor.objects.select_for_update().get(pk=self.proveedor_id)
            validar_producto(self)
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


class PlanMembresia(models.Model):
    nombre = models.CharField(max_length=60, unique=True)
    precio = models.DecimalField(max_digits=10, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    duracion_dias = models.PositiveIntegerField(default=30, validators=[MinValueValidator(1)])
    max_productos = models.PositiveIntegerField(null=True, blank=True, help_text='Vacío: sin límite')
    max_usuarios = models.PositiveIntegerField(null=True, blank=True)
    promociones = models.BooleanField(default=False)
    estadisticas = models.BooleanField(default=False)
    activo = models.BooleanField(default=True)

    def __str__(self):
        return self.nombre


class MembresiaProveedor(models.Model):
    proveedor = models.ForeignKey(Proveedor, on_delete=models.CASCADE, related_name='membresias')
    plan = models.ForeignKey(PlanMembresia, on_delete=models.PROTECT)
    inicio = models.DateField(default=date.today)
    fin = models.DateField()
    activa = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['proveedor'], condition=Q(activa=True), name='una_membresia_activa'),
            models.CheckConstraint(condition=Q(fin__gte=F('inicio')), name='vigencia_valida'),
        ]


def generar_folio():
    return 'OE-' + uuid4().hex[:16].upper()


class Orden(models.Model):
    class Estado(models.TextChoices):
        NUEVA = 'NUEVA', 'Nueva'
        VISTA = 'VISTA', 'Vista'
        ACEPTADA = 'ACEPTADA', 'Aceptada'
        EN_PROCESO = 'EN_PROCESO', 'En proceso'
        ATENDIDA = 'ATENDIDA', 'Atendida'
        COMPLETADA = 'COMPLETADA', 'Completada'
        RECHAZADA = 'RECHAZADA', 'Rechazada'
        CANCELADA = 'CANCELADA', 'Cancelada'

    folio = models.CharField(max_length=24, unique=True, default=generar_folio, editable=False)
    comprador = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='ordenes')
    proveedor = models.ForeignKey(Proveedor, on_delete=models.PROTECT, related_name='ordenes')
    estado = models.CharField(max_length=12, choices=Estado.choices, default=Estado.NUEVA)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)
    subtotal = models.DecimalField(max_digits=14, decimal_places=2)
    notas_comprador = models.TextField(blank=True)
    notas_proveedor = models.TextField(blank=True)
    clave_solicitud = models.UUIDField(default=uuid4, unique=True, editable=False)

    class Meta:
        ordering = ['-fecha_creacion', '-pk']
        constraints = [models.CheckConstraint(condition=Q(subtotal__gte=0), name='orden_subtotal_positivo')]

    def __str__(self):
        return self.folio


class OrdenDetalle(models.Model):
    orden = models.ForeignKey(Orden, on_delete=models.CASCADE, related_name='detalles')
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT)
    nombre_producto_historico = models.CharField(max_length=100)
    cantidad = models.PositiveIntegerField(validators=[MinValueValidator(1), MaxValueValidator(999)])
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2)
    subtotal = models.DecimalField(max_digits=14, decimal_places=2)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['orden', 'producto'], name='producto_unico_en_orden'),
            models.CheckConstraint(condition=Q(cantidad__gte=1, cantidad__lte=999), name='cantidad_orden_valida'),
            models.CheckConstraint(condition=Q(precio_unitario__gte=0), name='detalle_precio_positivo'),
            models.CheckConstraint(condition=Q(subtotal__gte=0), name='detalle_subtotal_positivo'),
        ]


class OpinionBase(models.Model):
    class Moderacion(models.TextChoices):
        PUBLICADA = 'publicada', 'Publicada'
        OCULTA = 'oculta', 'Oculta'
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    orden = models.ForeignKey(Orden, on_delete=models.PROTECT)
    estrellas = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    comentario = models.TextField(max_length=3000)
    fecha = models.DateTimeField(auto_now_add=True)
    estado = models.CharField(max_length=10, choices=Moderacion.choices, default=Moderacion.PUBLICADA)
    respuesta = models.TextField(max_length=3000, blank=True)
    fecha_respuesta = models.DateTimeField(null=True, blank=True)

    class Meta:
        abstract = True
        ordering = ['-fecha', '-pk']

    @property
    def tipo_reporte(self):
        return 'opinion_producto' if self._meta.model_name == 'opinionproducto' else 'opinion_proveedor'

    @property
    def compra_verificada(self):
        return self.orden.estado == Orden.Estado.COMPLETADA and self.usuario_id == self.orden.comprador_id

    def clean(self):
        super().clean()
        if self.orden_id and not self.compra_verificada:
            raise ValidationError('Solo el comprador de una orden completada puede opinar.')


class OpinionProducto(OpinionBase):
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT, related_name='opiniones')

    class Meta(OpinionBase.Meta):
        constraints = [models.UniqueConstraint(fields=['usuario', 'orden', 'producto'], name='opinion_producto_unica'), models.CheckConstraint(condition=Q(estrellas__gte=1, estrellas__lte=5), name='estrellas_producto_validas')]

    def clean(self):
        super().clean()
        if self.orden_id and self.producto_id and not self.orden.detalles.filter(producto_id=self.producto_id).exists():
            raise ValidationError('El producto no pertenece a la orden.')


class OpinionProveedor(OpinionBase):
    proveedor = models.ForeignKey(Proveedor, on_delete=models.PROTECT, related_name='opiniones')

    class Meta(OpinionBase.Meta):
        constraints = [models.UniqueConstraint(fields=['usuario', 'orden', 'proveedor'], name='opinion_proveedor_unica'), models.CheckConstraint(condition=Q(estrellas__gte=1, estrellas__lte=5), name='estrellas_proveedor_validas')]

    def clean(self):
        super().clean()
        if self.orden_id and self.proveedor_id != self.orden.proveedor_id:
            raise ValidationError('El proveedor no pertenece a la orden.')


class Notificacion(models.Model):
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notificaciones')
    tipo = models.CharField(max_length=40)
    titulo = models.CharField(max_length=150)
    mensaje = models.TextField()
    url = models.CharField(max_length=250)
    leida = models.BooleanField(default=False)
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-fecha', '-pk']
        indexes = [models.Index(fields=['usuario', 'leida'])]


class SolicitudProveedor(models.Model):
    class Estado(models.TextChoices):
        PENDIENTE = 'PENDIENTE', 'Pendiente'
        EN_REVISION = 'EN_REVISION', 'En revisión'
        APROBADA = 'APROBADA', 'Aprobada'
        RECHAZADA = 'RECHAZADA', 'Rechazada'

    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='solicitudes_proveedor')
    nombre_negocio = models.CharField(max_length=150)
    razon_social = models.CharField(max_length=200, blank=True)
    descripcion = models.TextField(max_length=3000)
    correo = models.EmailField()
    telefono = models.CharField(max_length=30)
    whatsapp = models.CharField(max_length=30, blank=True)
    ubicacion = models.CharField(max_length=250)
    sitio_web = models.URLField(blank=True)
    giros = models.ManyToManyField(GiroComercial)
    estado = models.CharField(max_length=12, choices=Estado.choices, default=Estado.PENDIENTE)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_revision = models.DateTimeField(null=True, blank=True)
    notas_admin = models.TextField(blank=True, max_length=3000)
    proveedor = models.OneToOneField(Proveedor, null=True, blank=True, on_delete=models.PROTECT, related_name='solicitud_alta')

    class Meta:
        ordering = ['-fecha_creacion', '-pk']
        constraints = [models.UniqueConstraint(fields=['usuario'], condition=Q(estado__in=['PENDIENTE', 'EN_REVISION']), name='una_solicitud_proveedor_activa')]

    def __str__(self):
        return self.nombre_negocio


class ReporteContenido(models.Model):
    class Estado(models.TextChoices):
        PENDIENTE = 'PENDIENTE', 'Pendiente'
        EN_REVISION = 'EN_REVISION', 'En revisión'
        RESUELTO = 'RESUELTO', 'Resuelto'
        DESCARTADO = 'DESCARTADO', 'Descartado'

    class Tipo(models.TextChoices):
        PRODUCTO = 'producto', 'Producto'
        PROVEEDOR = 'proveedor', 'Proveedor'
        OPINION_PRODUCTO = 'opinion_producto', 'Opinión de producto'
        OPINION_PROVEEDOR = 'opinion_proveedor', 'Opinión de proveedor'

    class Motivo(models.TextChoices):
        FALSA = 'falsa', 'Información falsa'
        INAPROPIADO = 'inapropiado', 'Contenido inapropiado'
        FRAUDE = 'fraude', 'Fraude'
        PROHIBIDO = 'prohibido', 'Producto prohibido'
        SPAM = 'spam', 'Spam'
        OTRO = 'otro', 'Otro'

    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    tipo = models.CharField(max_length=20, choices=Tipo.choices)
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT, null=True, blank=True)
    proveedor = models.ForeignKey(Proveedor, on_delete=models.PROTECT, null=True, blank=True)
    opinion_producto = models.ForeignKey(OpinionProducto, on_delete=models.PROTECT, null=True, blank=True)
    opinion_proveedor = models.ForeignKey(OpinionProveedor, on_delete=models.PROTECT, null=True, blank=True)
    motivo = models.CharField(max_length=15, choices=Motivo.choices)
    comentario = models.TextField(max_length=3000)
    estado = models.CharField(max_length=12, choices=Estado.choices, default=Estado.PENDIENTE)
    fecha = models.DateTimeField(auto_now_add=True)
    fecha_revision = models.DateTimeField(null=True, blank=True)
    notas_admin = models.TextField(blank=True, max_length=3000)

    class Meta:
        ordering = ['-fecha', '-pk']
        constraints = [models.CheckConstraint(condition=(
            Q(tipo='producto', producto__isnull=False, proveedor__isnull=True, opinion_producto__isnull=True, opinion_proveedor__isnull=True) |
            Q(tipo='proveedor', producto__isnull=True, proveedor__isnull=False, opinion_producto__isnull=True, opinion_proveedor__isnull=True) |
            Q(tipo='opinion_producto', producto__isnull=True, proveedor__isnull=True, opinion_producto__isnull=False, opinion_proveedor__isnull=True) |
            Q(tipo='opinion_proveedor', producto__isnull=True, proveedor__isnull=True, opinion_producto__isnull=True, opinion_proveedor__isnull=False)
        ), name='reporte_objeto_coherente')]

    @property
    def objeto(self):
        return getattr(self, self.tipo)


class RegistroAdministrativo(models.Model):
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    accion = models.CharField(max_length=80)
    tipo_objeto = models.CharField(max_length=40)
    objeto_id = models.PositiveBigIntegerField()
    detalle = models.TextField(blank=True)
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-fecha', '-pk']
