"""Pruebas del dominio y del flujo HTTP, incluidas concurrencia e idempotencia."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from io import StringIO
from uuid import uuid4
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError, PermissionDenied
from django.core.management import call_command, CommandError
from django.db import IntegrityError, transaction, close_old_connections
from django.test import TestCase, TransactionTestCase, override_settings, Client
from django.utils import timezone
from servicios.models import (Proveedor, AdministradorProveedor, Categoria, Producto, Orden, OpinionProducto, OpinionProveedor, Notificacion, PlanMembresia, MembresiaProveedor)
from servicios.application.orders import crear_orden, cambiar_estado
from servicios.application.reviews import crear_opinion_producto, crear_opinion_proveedor, responder_opinion
from servicios.application.catalog import actualizar_stock
from servicios.queries import productos_publicos


class DatosMixin:
    def datos(self):
        User = get_user_model()
        self.buyer = User.objects.create_user('buyer', password='local-test-2026')
        self.other = User.objects.create_user('other', password='local-test-2026')
        self.seller = User.objects.create_user('seller', password='local-test-2026')
        self.seller2 = User.objects.create_user('seller2', password='local-test-2026')
        self.proveedor = Proveedor.objects.create(nombre='Pan de prueba', estado='activo')
        self.ajeno = Proveedor.objects.create(nombre='Otro negocio', estado='activo')
        AdministradorProveedor.objects.create(proveedor=self.proveedor, usuario=self.seller)
        AdministradorProveedor.objects.create(proveedor=self.ajeno, usuario=self.seller2)
        self.categoria = Categoria.objects.create(nombre='Alimentos')
        self.hija = Categoria.objects.create(nombre='Panadería', padre=self.categoria)
        self.p1 = Producto.objects.create(proveedor=self.proveedor, categoria=self.hija, nombre='Pan integral', descripcion='Masa madre', precio='15.50', stock=10)
        self.p2 = Producto.objects.create(proveedor=self.proveedor, categoria=self.hija, nombre='Galletas', descripcion='Avena', precio='20', stock=5)
        self.p3 = Producto.objects.create(proveedor=self.ajeno, categoria=self.categoria, nombre='Café', precio='25', stock=20)

    def orden(self, cantidades=None):
        return crear_orden(self.buyer, self.proveedor.pk, cantidades or {self.p1.pk:2, self.p2.pk:1}, uuid4())

    def completar(self, orden):
        for estado in ['VISTA','ACEPTADA','EN_PROCESO','ATENDIDA','COMPLETADA']:
            orden = cambiar_estado(self.seller, orden.pk, estado)
        return orden


@override_settings(SECURE_SSL_REDIRECT=False, EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class MarketplaceTests(DatosMixin, TestCase):
    def setUp(self):
        self.datos()

    def test_creacion_detalles_historia_y_no_reserva(self):
        orden = self.orden()
        self.assertEqual(orden.subtotal, Decimal('51'))
        self.assertEqual(orden.detalles.count(), 2)
        self.p1.nombre = 'Nombre actualizado'
        self.p1.precio = 100
        self.p1.save()
        detalle = orden.detalles.get(producto=self.p1)
        self.assertEqual(detalle.nombre_producto_historico, 'Pan integral')
        self.assertEqual(detalle.precio_unitario, Decimal('15.50'))
        self.p1.refresh_from_db()
        self.assertEqual(self.p1.stock, 10)

    def test_separacion_proveedores_y_cantidades(self):
        for cantidades in [{self.p3.pk:1}, {self.p1.pk:0}, {self.p1.pk:-1}, {self.p1.pk:1000}, {self.p1.pk:True}]:
            with self.assertRaises(ValidationError):
                crear_orden(self.buyer,self.proveedor.pk,cantidades,uuid4())
        self.assertEqual(Orden.objects.count(),0)

    def test_idempotencia(self):
        clave=uuid4()
        a=crear_orden(self.buyer,self.proveedor.pk,{self.p1.pk:1},clave)
        b=crear_orden(self.buyer,self.proveedor.pk,{self.p1.pk:1},clave)
        self.assertEqual(a.pk,b.pk)
        self.assertEqual(Notificacion.objects.count(),1)
        with self.assertRaises(PermissionDenied):
            crear_orden(self.other,self.proveedor.pk,{self.p1.pk:1},clave)

    def test_reserva_cancelacion_y_doble_devolucion(self):
        orden=self.orden()
        cambiar_estado(self.seller,orden.pk,'VISTA')
        cambiar_estado(self.seller,orden.pk,'ACEPTADA')
        self.p1.refresh_from_db(); self.assertEqual(self.p1.stock,8)
        cambiar_estado(self.seller,orden.pk,'CANCELADA')
        self.p1.refresh_from_db(); self.assertEqual(self.p1.stock,10)
        with self.assertRaises(ValidationError): cambiar_estado(self.seller,orden.pk,'CANCELADA')
        self.p1.refresh_from_db(); self.assertEqual(self.p1.stock,10)

    def test_stock_insuficiente_revierte_todos_los_detalles(self):
        orden=self.orden({self.p1.pk:1,self.p2.pk:8})
        cambiar_estado(self.seller,orden.pk,'VISTA')
        with self.assertRaises(ValidationError): cambiar_estado(self.seller,orden.pk,'ACEPTADA')
        self.p1.refresh_from_db(); orden.refresh_from_db()
        self.assertEqual(self.p1.stock,10); self.assertEqual(orden.estado,'VISTA')

    def test_rechazo_y_cancelacion_sin_reserva(self):
        for estado,actor in [('RECHAZADA',self.seller),('CANCELADA',self.buyer)]:
            orden=self.orden(); cambiar_estado(actor,orden.pk,estado)
        self.p1.refresh_from_db(); self.assertEqual(self.p1.stock,10)

    def test_transiciones_y_actores(self):
        orden=self.orden()
        for actor,estado in [(self.buyer,'ACEPTADA'),(self.seller,'COMPLETADA'),(self.seller,'ACEPTADA')]:
            with self.assertRaises(ValidationError): cambiar_estado(actor,orden.pk,estado)
        self.completar(orden)
        with self.assertRaises(ValidationError): cambiar_estado(self.seller,orden.pk,'NUEVA')
        self.p1.refresh_from_db(); self.assertEqual(self.p1.stock,8)

    def test_aislamiento_ordenes(self):
        orden=self.orden()
        for actor in [self.other,self.seller2]:
            self.client.force_login(actor)
            self.assertEqual(self.client.get(f'/ordenes/{orden.pk}/').status_code,403)
            self.assertEqual(self.client.post(f'/ordenes/{orden.pk}/estado/',{'estado':'CANCELADA'}).status_code,403)
        self.assertEqual(self.client.get(f'/gestion/{self.proveedor.pk}/ordenes/').status_code,404)

    def test_opiniones_verificadas_duplicados_y_producto_ajeno(self):
        orden=self.orden()
        with self.assertRaises(ValidationError): crear_opinion_producto(self.buyer,orden.pk,self.p1.pk,5,'Bien')
        self.completar(orden)
        opinion=crear_opinion_producto(self.buyer,orden.pk,self.p1.pk,5,'Bien')
        self.assertTrue(opinion.compra_verificada)
        for usuario,producto,estrellas in [(self.buyer,self.p1.pk,5),(self.buyer,self.p3.pk,5),(self.buyer,self.p2.pk,6)]:
            with self.assertRaises(ValidationError): crear_opinion_producto(usuario,orden.pk,producto,estrellas,'Bien')
        with self.assertRaises(PermissionDenied): crear_opinion_proveedor(self.other,orden.pk,5,'Falsa')
        crear_opinion_proveedor(self.buyer,orden.pk,4,'Atención buena')
        with self.assertRaises(ValidationError): crear_opinion_proveedor(self.buyer,orden.pk,4,'Duplicada')
        self.assertEqual(productos_publicos().get(pk=self.p1.pk).valoracion,5)
        opinion.estado='oculta'; opinion.save()
        self.assertEqual(productos_publicos().get(pk=self.p1.pk).valoracion,0)

    def test_respuesta_ownership_y_unicidad(self):
        orden=self.completar(self.orden())
        opinion=crear_opinion_proveedor(self.buyer,orden.pk,5,'Bien')
        with self.assertRaises(PermissionDenied): responder_opinion(self.seller2,'proveedor',opinion.pk,'Gracias')
        responder_opinion(self.seller,'proveedor',opinion.pk,'Gracias')
        with self.assertRaises(ValidationError): responder_opinion(self.seller,'proveedor',opinion.pk,'Otra')
        self.assertTrue(Notificacion.objects.filter(usuario=self.buyer,tipo='respuesta_opinion').exists())

    def test_constraint_opinion_db(self):
        orden=self.completar(self.orden())
        crear_opinion_proveedor(self.buyer,orden.pk,5,'Bien')
        with self.assertRaises(IntegrityError),transaction.atomic():
            OpinionProveedor.objects.create(usuario=self.buyer,orden=orden,proveedor=self.proveedor,estrellas=5,comentario='Duplicada')

    def test_limites_membresia_y_vencimiento(self):
        for i in range(3): Producto.objects.create(proveedor=self.proveedor,categoria=self.hija,nombre=f'Extra {i}',precio=1)
        with self.assertRaises(ValidationError): Producto.objects.create(proveedor=self.proveedor,categoria=self.hija,nombre='Sexto',precio=1)
        self.p1.precio_promocional=10
        with self.assertRaises(ValidationError): self.p1.save()
        plan=PlanMembresia.objects.create(nombre='PRO',max_productos=100,max_usuarios=2,promociones=True)
        m=MembresiaProveedor.objects.create(proveedor=self.proveedor,plan=plan,fin=timezone.localdate()+timedelta(days=30))
        self.p1.save()
        Producto.objects.create(proveedor=self.proveedor,categoria=self.hija,nombre='Sexto',precio=1)
        m.inicio=timezone.localdate()-timedelta(days=31); m.fin=timezone.localdate()-timedelta(days=1);m.save()
        with self.assertRaises(ValidationError): Producto.objects.create(proveedor=self.proveedor,categoria=self.hija,nombre='Séptimo',precio=1)

    def test_limite_administradores(self):
        with self.assertRaises(ValidationError): AdministradorProveedor.objects.create(proveedor=self.proveedor,usuario=self.other)

    def test_busqueda_filtros_jerarquia_y_precio(self):
        for query in ['q=masa','q=Panadería',f'categoria={self.categoria.pk}',f'proveedor={self.proveedor.pk}&minimo=15&maximo=16&disponible=on']:
            response=self.client.get('/buscar/?'+query)
            self.assertEqual(response.status_code,200)
            self.assertContains(response,'Pan integral')
        self.assertNotContains(self.client.get('/buscar/?minimo=50'),'Pan integral')
        self.assertContains(self.client.get('/buscar/?minimo=100&maximo=1'),'no puede superar')
        self.categoria.activa=False;self.categoria.save()
        self.assertNotContains(self.client.get('/catalogo/'),'Pan integral')

    def test_carrito_multi_proveedor_y_reenvio(self):
        self.client.force_login(self.buyer)
        for p in [self.p1,self.p2,self.p3]: self.client.post(f'/solicitud/producto/{p.pk}/',{'cantidad':2,'agregar':1})
        response=self.client.get('/solicitud/')
        self.assertEqual(len(response.context['grupos']),2)
        clave=self.client.session['claves_solicitud'][str(self.proveedor.pk)]
        response=self.client.post(f'/solicitud/{self.proveedor.pk}/generar/',{'clave':clave})
        self.assertEqual(response.status_code,302)
        self.assertEqual(Orden.objects.get().detalles.count(),2)
        self.client.post(f'/solicitud/{self.proveedor.pk}/generar/',{'clave':clave})
        self.assertEqual(Orden.objects.count(),1)
        self.assertEqual(self.client.session['solicitud'],{str(self.p3.pk):2})

    def test_notificaciones_privadas_y_email_no_bloquea(self):
        orden=self.orden()
        aviso=Notificacion.objects.get()
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(f'/notificaciones/{aviso.pk}/leida/').status_code,404)
        with patch('servicios.infrastructure.email.send_mail',side_effect=OSError('SMTP fuera de servicio')):
            self.seller.email='seller@example.test';self.seller.save()
            with self.assertLogs('servicios.infrastructure.email', level='ERROR'), self.captureOnCommitCallbacks(execute=True):
                otra=self.orden()
        self.assertTrue(Orden.objects.filter(pk=otra.pk).exists())

    def test_inventario_edicion_obsoleta(self):
        orden=self.orden();cambiar_estado(self.seller,orden.pk,'VISTA');cambiar_estado(self.seller,orden.pk,'ACEPTADA')
        with self.assertRaises(ValidationError): actualizar_stock(self.seller,self.proveedor.pk,self.p1.pk,10,1,10)
        self.p1.refresh_from_db();self.assertEqual(self.p1.stock,8)

    def test_campos_privilegiados_no_editables(self):
        self.client.force_login(self.seller)
        self.client.post(f'/gestion/{self.proveedor.pk}/datos/',{'nombre':'Pan de prueba','verificado':'on','estado':'activo'})
        self.proveedor.refresh_from_db();self.assertFalse(self.proveedor.verificado)
        self.assertEqual(self.client.post(f'/gestion/{self.proveedor.pk}/membresia/',{'plan':10}).status_code,200)
        self.assertFalse(self.proveedor.membresias.exists())

    def test_seed_desactivado_en_produccion(self):
        with override_settings(DEBUG=False),self.assertRaises(CommandError): call_command('seed_demo',stdout=StringIO())

    def test_formulario_producto_no_sobrescribe_reserva(self):
        from servicios.forms import ProductoForm, ImagenFormSet
        from servicios.application.catalog import guardar_producto
        datos = {'categoria':self.hija.pk, 'nombre':'Pan integral', 'descripcion':'Masa madre', 'precio':'15.50', 'stock':10, 'stock_anterior':10, 'stock_minimo':0, 'activo':'on', 'imagenes-TOTAL_FORMS':0, 'imagenes-INITIAL_FORMS':0}
        form = ProductoForm(datos, instance=self.p1)
        imagenes = ImagenFormSet(datos, instance=self.p1)
        self.assertTrue(form.is_valid());self.assertTrue(imagenes.is_valid())
        orden=self.orden();cambiar_estado(self.seller,orden.pk,'VISTA');cambiar_estado(self.seller,orden.pk,'ACEPTADA')
        with self.assertRaises(ValidationError): guardar_producto(self.seller,form,imagenes)
        self.p1.refresh_from_db();self.assertEqual(self.p1.stock,8)

    def test_seed_idempotente(self):
        import tempfile
        with tempfile.TemporaryDirectory() as media, override_settings(DEBUG=True, MEDIA_ROOT=media):
            call_command('seed_demo',stdout=StringIO())
            conteos=(Orden.objects.count(),Producto.objects.count(),Notificacion.objects.count())
            call_command('seed_demo',stdout=StringIO())
            self.assertEqual(conteos,(Orden.objects.count(),Producto.objects.count(),Notificacion.objects.count()))
            self.assertEqual(Producto.objects.filter(slug__startswith='demo-producto-').count(),30)

    def test_flujo_http_completo(self):
        self.assertTrue(self.client.login(username='buyer',password='local-test-2026'))
        self.assertContains(self.client.get('/buscar/?q=Pan'),'Pan integral')
        self.assertEqual(self.client.get(f'/producto/{self.p1.slug}/').status_code,200)
        for p in [self.p1,self.p2]:self.client.post(f'/solicitud/producto/{p.pk}/',{'cantidad':1})
        self.client.get('/solicitud/')
        clave=self.client.session['claves_solicitud'][str(self.proveedor.pk)]
        self.client.post(f'/solicitud/{self.proveedor.pk}/generar/',{'clave':clave})
        orden=Orden.objects.get()
        self.assertEqual(self.client.get(f'/ordenes/{orden.pk}/').status_code,200)
        self.client.login(username='seller',password='local-test-2026')
        for estado in ['VISTA','ACEPTADA','EN_PROCESO','ATENDIDA','COMPLETADA']:
            self.assertEqual(self.client.post(f'/ordenes/{orden.pk}/estado/',{'estado':estado}).status_code,302)
        self.p1.refresh_from_db();self.assertEqual(self.p1.stock,9)
        self.client.login(username='buyer',password='local-test-2026')
        for url in [f'/ordenes/{orden.pk}/opinion/',f'/ordenes/{orden.pk}/opinion/{self.p1.pk}/']:
            self.assertEqual(self.client.post(url,{'estrellas':5,'comentario':'Excelente'}).status_code,302)
        self.assertEqual(OpinionProducto.objects.count(),1)
        self.assertEqual(OpinionProveedor.objects.count(),1)
        admin=get_user_model().objects.create_superuser('root','root@example.test','test-admin-2026')
        self.client.force_login(admin)
        for url in [f'/admin/servicios/orden/{orden.pk}/change/','/admin/servicios/opinionproveedor/','/admin/servicios/membresiaproveedor/']:
            self.assertEqual(self.client.get(url).status_code,200)


class ConcurrenciaTests(DatosMixin, TransactionTestCase):
    def setUp(self):
        self.datos()

    def test_dos_aceptaciones_no_sobrevenden(self):
        a=self.orden({self.p1.pk:7});b=self.orden({self.p1.pk:7})
        cambiar_estado(self.seller,a.pk,'VISTA');cambiar_estado(self.seller,b.pk,'VISTA')
        def aceptar(pk):
            close_old_connections()
            try:
                actor=get_user_model().objects.get(pk=self.seller.pk)
                cambiar_estado(actor,pk,'ACEPTADA')
                return 'ok'
            except ValidationError:
                return 'sin_stock'
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            resultados=list(pool.map(aceptar,[a.pk,b.pk]))
        self.assertCountEqual(resultados,['ok','sin_stock'])
        self.p1.refresh_from_db();self.assertEqual(self.p1.stock,3)
