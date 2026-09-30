from decimal import Decimal
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.db.migrations.executor import MigrationExecutor
from django.db import connection
from .models import Proveedor, AdministradorProveedor, Categoria, Producto, ProductoImagen
from .forms import ImagenFormSet

@override_settings(SECURE_SSL_REDIRECT=False)
class DominioTests(TestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_user('gestor', password='test-only-password')
        self.a = Proveedor.objects.create(nombre='A', estado='activo')
        self.b = Proveedor.objects.create(nombre='B', estado='activo')
        AdministradorProveedor.objects.create(usuario=self.usuario, proveedor=self.a)
        self.categoria = Categoria.objects.create(nombre='Raíz')
        self.producto = Producto.objects.create(nombre='Ajeno', proveedor=self.b, categoria=self.categoria, precio=10)
        self.client.force_login(self.usuario)

    def test_proveedor_y_pertenencia_unica(self):
        self.assertTrue(self.a.slug)
        with self.assertRaises(IntegrityError), transaction.atomic():
            AdministradorProveedor.objects.create(usuario=self.usuario, proveedor=self.a)

    def test_categoria_ciclos_y_nivel(self):
        hija = Categoria.objects.create(nombre='Hija', padre=self.categoria)
        self.assertEqual(hija.nivel, 1)
        self.categoria.padre = hija
        with self.assertRaises(ValidationError):
            self.categoria.save()

    def test_aislamiento_get_y_post(self):
        urls = [reverse('gestion_productos', args=[self.b.pk]), reverse('gestion_negocio', args=[self.b.pk]), reverse('gestion_producto_editar', args=[self.a.pk, self.producto.pk]), reverse('gestion_producto_nuevo', args=[self.b.pk])]
        for url in urls:
            self.assertEqual(self.client.get(url).status_code, 404)
            self.assertEqual(self.client.post(url, {'nombre': 'Ataque'}).status_code, 404)
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.nombre, 'Ajeno')

    def datos(self):
        return {'nombre': 'Nuevo', 'descripcion': 'Descripción', 'categoria': self.categoria.pk, 'precio': '20.00', 'stock': 3, 'stock_minimo': 1, 'activo': 'on', 'proveedor': self.b.pk, 'imagenes-TOTAL_FORMS': 0, 'imagenes-INITIAL_FORMS': 0}

    def test_creacion_segura_y_stock(self):
        response = self.client.post(reverse('gestion_producto_nuevo', args=[self.a.pk]), self.datos())
        self.assertEqual(response.status_code, 302)
        producto = Producto.objects.get(nombre='Nuevo')
        self.assertEqual(producto.proveedor, self.a)
        self.assertEqual(producto.disponibilidad, 'Disponible')
        producto.stock = 1
        self.assertEqual(producto.disponibilidad, 'Stock bajo')
        producto.stock = 0
        self.assertEqual(producto.disponibilidad, 'Agotado')
        producto.activo = False
        self.assertEqual(producto.disponibilidad, 'Inactivo')

    def test_edicion_galeria_y_cambio_principal(self):
        propio = Producto.objects.create(nombre='Propio', proveedor=self.a, categoria=self.categoria, precio=1)
        primera = ProductoImagen.objects.create(producto=propio, imagen='primera.jpg', principal=True)
        segunda = ProductoImagen.objects.create(producto=propio, imagen='segunda.jpg')
        datos = self.datos()
        datos.update({'imagenes-TOTAL_FORMS': 3, 'imagenes-INITIAL_FORMS': 2,
                      'imagenes-0-id': primera.pk, 'imagenes-0-orden': 0,
                      'imagenes-1-id': segunda.pk, 'imagenes-1-orden': 1,
                      'imagenes-1-principal': 'on', 'imagenes-2-orden': 0})
        response = self.client.post(reverse('gestion_producto_editar', args=[self.a.pk, propio.pk]), datos)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(propio.imagenes.get(principal=True).pk, segunda.pk)

    def test_dos_imagenes_principales_rechazadas(self):
        primera = ProductoImagen.objects.create(producto=self.producto, imagen='primera.jpg')
        segunda = ProductoImagen.objects.create(producto=self.producto, imagen='segunda.jpg')
        datos = {'imagenes-TOTAL_FORMS': 2, 'imagenes-INITIAL_FORMS': 2}
        for index, imagen in enumerate([primera, segunda]):
            datos.update({f'imagenes-{index}-id': imagen.pk, f'imagenes-{index}-orden': index, f'imagenes-{index}-principal': 'on'})
        self.assertFalse(ImagenFormSet(datos, instance=self.producto).is_valid())

    def test_sku_duplicado_devuelve_error_de_formulario(self):
        Producto.objects.create(nombre='Existente', proveedor=self.a, categoria=self.categoria, precio=1, sku='SKU')
        datos = self.datos()
        datos['sku'] = 'SKU'
        response = self.client.post(reverse('gestion_producto_nuevo', args=[self.a.pk]), datos)
        self.assertEqual(response.status_code, 200)
        self.assertIn('sku', response.context['form'].errors)
        self.assertFalse(Producto.objects.filter(nombre='Nuevo').exists())

    def test_suspension_revoca_acceso(self):
        self.a.estado = 'suspendido'
        self.a.save()
        self.assertEqual(self.client.get(reverse('gestion_productos', args=[self.a.pk])).status_code, 404)

    def test_acceso_desactivado(self):
        self.a.accesos.update(activo=False)
        self.assertEqual(self.client.get(reverse('gestion_productos', args=[self.a.pk])).status_code, 404)

    def test_staff_no_es_superadministrador(self):
        self.usuario.is_staff = True
        self.usuario.save()
        self.assertEqual(self.client.get('/admin/').status_code, 302)
        self.assertEqual(self.client.get('/enviar-correo/').status_code, 404)

    def test_restricciones_precios_sku_imagen(self):
        self.producto.sku = 'ABC'
        self.producto.save()
        with self.assertRaises(IntegrityError), transaction.atomic():
            Producto.objects.create(nombre='Duplicado', proveedor=self.b, categoria=self.categoria, precio=1, sku='ABC')
        with self.assertRaises(IntegrityError), transaction.atomic():
            Producto.objects.create(nombre='Negativo', proveedor=self.a, categoria=self.categoria, precio=-1)
        self.producto.precio_promocional = Decimal('11')
        with self.assertRaises(ValidationError):
            self.producto.full_clean()
        ProductoImagen.objects.create(producto=self.producto, imagen='uno.jpg', principal=True)
        with self.assertRaises(IntegrityError), transaction.atomic():
            ProductoImagen.objects.create(producto=self.producto, imagen='dos.jpg', principal=True)

    def test_imagen_ajena_rechazada(self):
        imagen = ProductoImagen.objects.create(producto=self.producto, imagen='ajena.jpg')
        propio = Producto.objects.create(nombre='Propio', proveedor=self.a, categoria=self.categoria, precio=1)
        formset = ImagenFormSet({'imagenes-TOTAL_FORMS': 1, 'imagenes-INITIAL_FORMS': 1, 'imagenes-0-id': imagen.pk, 'imagenes-0-orden': 0, 'imagenes-0-DELETE': 'on'}, instance=propio)
        self.assertFalse(formset.is_valid())

    def test_anonimo_y_csrf(self):
        self.client.logout()
        self.assertEqual(self.client.get('/gestion/').status_code, 302)
        from django.test import Client
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.usuario)
        self.assertEqual(client.post(reverse('gestion_producto_nuevo', args=[self.a.pk]), self.datos()).status_code, 403)

    def test_catalogo_oculta_inactivos_y_sin_imagen(self):
        self.assertEqual(self.client.get('/catalogo/').status_code, 200)
        self.b.estado = 'suspendido'
        self.b.save()
        self.assertNotContains(self.client.get('/catalogo/'), 'Ajeno')

class MigracionTests(TransactionTestCase):
    def test_conserva_catalogo_legacy(self):
        executor = MigrationExecutor(connection)
        old = [('servicios', '0004_profile')]
        latest = [('servicios', '0007_alter_categoria_slug_alter_girocomercial_slug_and_more')]
        executor.migrate(old)
        apps = executor.loader.project_state(old).apps
        categoria = apps.get_model('servicios', 'Categoria').objects.create(nombre='Legado')
        producto = apps.get_model('servicios', 'Producto').objects.create(nombre='Original', descripcion='Texto', precio='12.50', categoria=categoria, imagen='productos/antigua.jpg')
        try:
            executor = MigrationExecutor(connection)
            executor.migrate(latest)
            actual = Producto.objects.get(pk=producto.pk)
            self.assertEqual(actual.precio, Decimal('12.50'))
            self.assertEqual(actual.proveedor.estado, 'inactivo')
            self.assertEqual(actual.imagenes.get().imagen.name, 'productos/antigua.jpg')
            self.assertTrue(actual.slug)
        finally:
            MigrationExecutor(connection).migrate(latest)
