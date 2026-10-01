from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction, close_old_connections
from django.test import TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from servicios.models import (Proveedor, AdministradorProveedor, SolicitudProveedor, GiroComercial, PlanMembresia, MembresiaProveedor, ReporteContenido, RegistroAdministrativo, Notificacion, OpinionProducto)
from servicios.application.providers import (solicitar_proveedor, revisar_solicitud, crear_proveedor_manual, administrar_proveedor, agregar_equipo, cambiar_acceso, asignar_membresia)
from servicios.application.moderation import reportar_contenido, moderar_reporte
from servicios.test_marketplace import DatosMixin


class AltaMixin(DatosMixin):
    def preparar(self):
        self.datos()
        self.admin = get_user_model().objects.create_superuser('admin_test', password='local-admin-test')
        self.giro = GiroComercial.objects.create(nombre='Alimentos artesanales')
        self.gratis = PlanMembresia.objects.create(nombre='GRATIS', max_productos=5, max_usuarios=1, precio=0)
        self.pro = PlanMembresia.objects.create(nombre='PRO', max_productos=100, max_usuarios=3, promociones=True)
        self.datos_alta = {'nombre_negocio':'Nueva tienda', 'descripcion':'Un negocio de alimentos', 'correo':'tienda@example.test', 'telefono':'5551234567', 'ubicacion':'Ciudad de México', 'giros':[self.giro]}

    def solicitud(self):
        return solicitar_proveedor(self.buyer, self.datos_alta)


@override_settings(SECURE_SSL_REDIRECT=False)
class ProveedoresTests(AltaMixin, TestCase):
    def setUp(self):
        self.preparar()

    def test_solicitud_y_notificacion(self):
        solicitud=self.solicitud()
        self.assertEqual(solicitud.estado,'PENDIENTE')
        self.assertTrue(solicitud.giros.filter(pk=self.giro.pk).exists())
        self.assertTrue(Notificacion.objects.filter(usuario=self.buyer,tipo='solicitud_recibida').exists())

    def test_solicitud_duplicada_activa_servicio_y_db(self):
        self.solicitud()
        with self.assertRaises(ValidationError): self.solicitud()
        with self.assertRaises(IntegrityError),transaction.atomic():
            SolicitudProveedor.objects.create(usuario=self.buyer,nombre_negocio='Duplicada',descripcion='x',correo='x@example.test',telefono='123',ubicacion='x')

    def test_aprobar_crea_tienda_principal_gratis_sin_verificacion(self):
        solicitud=revisar_solicitud(self.admin,self.solicitud().pk,'APROBADA')
        proveedor=solicitud.proveedor
        self.assertEqual(proveedor.estado,'activo');self.assertFalse(proveedor.verificado)
        acceso=proveedor.accesos.get(usuario=self.buyer)
        self.assertTrue(acceso.es_principal and acceso.activo)
        self.assertEqual(proveedor.membresias.get(activa=True).plan,self.gratis)
        self.assertTrue(Notificacion.objects.filter(usuario=self.buyer,tipo='solicitud_aprobada').exists())

    def test_aprobar_dos_veces_no_duplica(self):
        solicitud=self.solicitud()
        revisar_solicitud(self.admin,solicitud.pk,'APROBADA')
        cantidad=Proveedor.objects.count()
        with self.assertRaises(ValidationError): revisar_solicitud(self.admin,solicitud.pk,'APROBADA')
        self.assertEqual(Proveedor.objects.count(),cantidad)

    def test_revision_rechazo_historial_y_nueva_solicitud(self):
        solicitud=self.solicitud()
        revisar_solicitud(self.admin,solicitud.pk,'EN_REVISION')
        with self.assertRaises(ValidationError): self.solicitud()
        with self.assertRaises(ValidationError): revisar_solicitud(self.admin,solicitud.pk,'RECHAZADA','')
        revisar_solicitud(self.admin,solicitud.pk,'RECHAZADA','Faltan datos verificables.')
        nueva=self.solicitud()
        self.assertNotEqual(nueva.pk,solicitud.pk)
        self.assertTrue(SolicitudProveedor.objects.filter(pk=solicitud.pk,estado='RECHAZADA').exists())
        self.assertEqual(RegistroAdministrativo.objects.filter(tipo_objeto='solicitudproveedor',objeto_id=solicitud.pk).count(),3)

    def test_aprobar_con_usuario_inactivo_hace_rollback(self):
        solicitud=self.solicitud()
        get_user_model().objects.filter(pk=self.buyer.pk).update(is_active=False)
        cantidad=Proveedor.objects.count()
        with self.assertRaises(ValidationError): revisar_solicitud(self.admin,solicitud.pk,'APROBADA')
        solicitud.refresh_from_db();self.assertEqual(solicitud.estado,'PENDIENTE')
        self.assertEqual(Proveedor.objects.count(),cantidad)

    def test_creacion_manual_reutiliza_reglas(self):
        proveedor=crear_proveedor_manual(self.admin,{'nombre':'Manual','giros':[self.giro],'verificado':True},self.other.pk,self.pro.pk,'inactivo')
        self.assertFalse(proveedor.verificado)
        self.assertTrue(proveedor.accesos.get().es_principal)
        self.assertEqual(proveedor.membresias.get().plan,self.pro)

    def test_suspension_reactivacion_y_verificacion(self):
        administrar_proveedor(self.admin,self.proveedor.pk,'suspender','Revisión')
        self.client.force_login(self.seller)
        self.assertEqual(self.client.get(f'/gestion/{self.proveedor.pk}/productos/').status_code,404)
        self.assertEqual(self.client.get(f'/proveedor/{self.proveedor.slug}/').status_code,404)
        administrar_proveedor(self.admin,self.proveedor.pk,'reactivar')
        administrar_proveedor(self.admin,self.proveedor.pk,'verificar')
        self.proveedor.refresh_from_db();self.assertIsNotNone(self.proveedor.fecha_verificacion)
        administrar_proveedor(self.admin,self.proveedor.pk,'quitar_verificacion')
        self.proveedor.refresh_from_db();self.assertFalse(self.proveedor.verificado);self.assertIsNone(self.proveedor.fecha_verificacion)
        self.assertTrue(Notificacion.objects.filter(usuario=self.seller,tipo='proveedor_suspender').exists())

    def test_permisos_servicios_solo_superusuario(self):
        solicitud=self.solicitud()
        for usuario in [self.buyer,self.seller]:
            with self.assertRaises(PermissionDenied): revisar_solicitud(usuario,solicitud.pk,'APROBADA')
            with self.assertRaises(PermissionDenied): administrar_proveedor(usuario,self.proveedor.pk,'verificar')
            with self.assertRaises(PermissionDenied): asignar_membresia(usuario,self.proveedor.pk,self.pro.pk)

    def test_panel_admin_denegado_y_posts_falsificados(self):
        solicitud=self.solicitud()
        rutas=['/administracion/','/administracion/solicitudes/','/administracion/proveedores/','/administracion/usuarios/','/administracion/membresias/','/administracion/moderacion/','/administracion/proveedores/nuevo/']
        for usuario in [self.buyer,self.seller]:
            self.client.force_login(usuario)
            for ruta in rutas:
                self.assertEqual(self.client.get(ruta).status_code,403)
            self.assertEqual(self.client.post(f'/administracion/solicitudes/{solicitud.pk}/accion/',{'estado':'APROBADA'}).status_code,403)
            self.assertEqual(self.client.post(f'/administracion/proveedores/{self.proveedor.pk}/accion/',{'accion':'verificar'}).status_code,403)
            self.assertEqual(self.client.post(f'/administracion/proveedores/{self.proveedor.pk}/membresia/',{'plan':self.pro.pk}).status_code,403)
        self.client.force_login(self.admin)
        for ruta in rutas: self.assertEqual(self.client.get(ruta).status_code,200)

    def test_equipo_limite_principal_y_aislamiento(self):
        with self.assertRaises(ValidationError): agregar_equipo(self.seller,self.proveedor.pk,self.other.username)
        asignar_membresia(self.admin,self.proveedor.pk,self.pro.pk)
        acceso=agregar_equipo(self.seller,self.proveedor.pk,self.other.username)
        self.assertFalse(acceso.es_principal)
        with self.assertRaises(PermissionDenied): agregar_equipo(self.other,self.proveedor.pk,self.buyer.username)
        with self.assertRaises(PermissionDenied): cambiar_acceso(self.seller,self.ajeno.pk,acceso.pk,'desactivar')
        with self.assertRaises(PermissionDenied): cambiar_acceso(self.seller,self.proveedor.pk,self.ajeno.accesos.get().pk,'desactivar')
        cambiar_acceso(self.seller,self.proveedor.pk,acceso.pk,'desactivar')
        acceso.refresh_from_db();self.assertFalse(acceso.activo)
        cambiar_acceso(self.seller,self.proveedor.pk,acceso.pk,'reactivar')
        self.assertTrue(Notificacion.objects.filter(usuario=self.other,tipo='equipo_agregado').exists())

    def test_ultimo_principal_protegido_y_transferencia(self):
        principal=self.proveedor.accesos.get()
        self.assertTrue(principal.es_principal)
        for accion in ['desactivar','colaborador']:
            with self.assertRaises(ValidationError): cambiar_acceso(self.seller,self.proveedor.pk,principal.pk,accion)
        asignar_membresia(self.admin,self.proveedor.pk,self.pro.pk)
        nuevo=agregar_equipo(self.seller,self.proveedor.pk,self.other.username)
        cambiar_acceso(self.seller,self.proveedor.pk,nuevo.pk,'principal')
        cambiar_acceso(self.seller,self.proveedor.pk,principal.pk,'desactivar')
        self.assertEqual(self.proveedor.accesos.filter(activo=True,es_principal=True).count(),1)

    def test_reactivacion_respeta_limite_y_downgrade(self):
        asignar_membresia(self.admin,self.proveedor.pk,self.pro.pk)
        acceso=agregar_equipo(self.seller,self.proveedor.pk,self.other.username)
        with self.assertRaises(ValidationError): asignar_membresia(self.admin,self.proveedor.pk,self.gratis.pk)
        cambiar_acceso(self.seller,self.proveedor.pk,acceso.pk,'desactivar')
        asignar_membresia(self.admin,self.proveedor.pk,self.gratis.pk)
        with self.assertRaises(ValidationError): cambiar_acceso(self.seller,self.proveedor.pk,acceso.pk,'reactivar')
        self.assertEqual(self.proveedor.membresias.filter(activa=True).count(),1)

    def test_reporte_y_moderacion_producto_sin_borrar(self):
        reporte=reportar_contenido(self.buyer,'producto',self.p1.pk,'falsa','Descripción incorrecta')
        with self.assertRaises(ValidationError): reportar_contenido(self.buyer,'producto',self.p1.pk,'otro','Duplicado')
        with self.assertRaises(PermissionDenied): moderar_reporte(self.seller,reporte.pk,'desactivar_producto','No')
        moderar_reporte(self.admin,reporte.pk,'revisar','Analizando')
        moderar_reporte(self.admin,reporte.pk,'desactivar_producto','Se detectó información falsa.')
        self.p1.refresh_from_db();reporte.refresh_from_db()
        self.assertFalse(self.p1.activo);self.assertEqual(reporte.estado,'RESUELTO')
        self.assertTrue(Notificacion.objects.filter(usuario=self.buyer,tipo='reporte_resuelto').exists())
        with self.assertRaises(ValidationError): moderar_reporte(self.admin,reporte.pk,'descartar','Ya cerrado')

    def test_moderacion_opinion_y_proveedor(self):
        orden=self.completar(self.orden())
        from servicios.application.reviews import crear_opinion_producto
        opinion=crear_opinion_producto(self.buyer,orden.pk,self.p1.pk,5,'Bien')
        reporte=reportar_contenido(self.other,'opinion_producto',opinion.pk,'spam','Contenido repetido')
        moderar_reporte(self.admin,reporte.pk,'ocultar_opinion','Opinión oculta tras revisar.')
        opinion.refresh_from_db();self.assertEqual(opinion.estado,'oculta')
        reporte=reportar_contenido(self.other,'proveedor',self.proveedor.pk,'fraude','Revisar datos')
        moderar_reporte(self.admin,reporte.pk,'suspender_proveedor','Suspensión preventiva.')
        self.proveedor.refresh_from_db();self.assertEqual(self.proveedor.estado,'suspendido')

    def test_reporte_descartado_y_accion_incompatible(self):
        reporte=reportar_contenido(self.buyer,'producto',self.p1.pk,'otro','Revisar')
        with self.assertRaises(ValidationError): moderar_reporte(self.admin,reporte.pk,'ocultar_opinion','Acción incorrecta')
        moderar_reporte(self.admin,reporte.pk,'descartar','No encontramos incumplimiento.')
        self.p1.refresh_from_db();self.assertTrue(self.p1.activo)

    def test_mis_reportes_no_filtra_datos_ajenos(self):
        reporte=reportar_contenido(self.other,'producto',self.p1.pk,'otro','Contenido privado del reporte')
        self.client.force_login(self.buyer)
        self.assertNotContains(self.client.get('/mis-reportes/'),'Contenido privado del reporte')
        self.assertEqual(self.client.post(f'/administracion/moderacion/{reporte.pk}/accion/',{'accion':'descartar','notas':'Intento'}).status_code,403)
        self.assertEqual(self.client.get(f'/reportar/producto/{self.p1.pk}/').status_code,200)

    def test_csrf_y_post_obligatorio(self):
        from django.test import Client
        solicitud=self.solicitud()
        c=Client(enforce_csrf_checks=True);c.force_login(self.admin)
        url=f'/administracion/solicitudes/{solicitud.pk}/accion/'
        self.assertEqual(c.get(url).status_code,405)
        self.assertEqual(c.post(url,{'estado':'APROBADA'}).status_code,403)

    def test_flujo_http_alta_equipo_y_moderacion(self):
        self.client.force_login(self.buyer)
        datos={**self.datos_alta,'giros':[self.giro.pk]}
        self.assertEqual(self.client.post('/quiero-vender/',datos).status_code,302)
        solicitud=SolicitudProveedor.objects.get(usuario=self.buyer)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.post(f'/administracion/solicitudes/{solicitud.pk}/accion/',{'estado':'APROBADA'}).status_code,302)
        solicitud.refresh_from_db();proveedor=solicitud.proveedor
        self.client.force_login(self.buyer)
        self.assertEqual(self.client.get(f'/gestion/{proveedor.pk}/equipo/').status_code,200)
        datos_tienda={'nombre':'Mi nueva tienda','horario':'Lunes a viernes','zona_cobertura':'Centro','giros':[self.giro.pk],'verificado':'on','estado':'suspendido'}
        self.assertEqual(self.client.post(f'/gestion/{proveedor.pk}/datos/',datos_tienda).status_code,302)
        proveedor.refresh_from_db();self.assertEqual(proveedor.horario,'Lunes a viernes');self.assertFalse(proveedor.verificado);self.assertEqual(proveedor.estado,'activo')
        self.assertContains(self.client.get(f'/proveedor/{proveedor.slug}/'),'Lunes a viernes')
        self.client.post(f'/reportar/producto/{self.p1.pk}/',{'motivo':'otro','comentario':'Revisar por favor'})
        reporte=ReporteContenido.objects.get(usuario=self.buyer)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(f'/administracion/moderacion/{reporte.pk}/').status_code,200)
        self.client.post(f'/administracion/moderacion/{reporte.pk}/accion/',{'accion':'descartar','notas':'Revisión completada.'})
        reporte.refresh_from_db();self.assertEqual(reporte.estado,'DESCARTADO')


class AltaConcurrenteTests(AltaMixin, TransactionTestCase):
    def setUp(self): self.preparar()

    def test_aprobacion_concurrente_crea_un_solo_proveedor(self):
        solicitud=self.solicitud();antes=Proveedor.objects.count()
        def aprobar(_):
            close_old_connections()
            try:
                actor=get_user_model().objects.get(pk=self.admin.pk)
                revisar_solicitud(actor,solicitud.pk,'APROBADA')
                return 'aprobada'
            except ValidationError:
                return 'ya_revisada'
            finally: close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool: resultados=list(pool.map(aprobar,range(2)))
        self.assertCountEqual(resultados,['aprobada','ya_revisada'])
        self.assertEqual(Proveedor.objects.count(),antes+1)
