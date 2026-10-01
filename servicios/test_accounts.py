"""Cuenta y administración: flujos HTTP, tokens, permisos y conservación de datos."""
import re
from datetime import timedelta
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core import mail, signing
from django.core.exceptions import ValidationError, PermissionDenied
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from servicios.models import Profile, PlanMembresia, MembresiaProveedor, AdministradorProveedor, RegistroAdministrativo, Notificacion
from servicios.application import accounts, email_verification, plans
from servicios.application.providers import solicitar_proveedor, asignar_membresia
from servicios.application.memberships import plan_actual
from servicios.application.notifications import crear_notificacion
from servicios.account_queries import resumen_tienda
from servicios.test_marketplace import DatosMixin

@override_settings(SECURE_SSL_REDIRECT=False, EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class CuentasTests(DatosMixin, TestCase):
    def setUp(self):
        self.datos()
        self.admin = get_user_model().objects.create_superuser('super', 'super@example.test', 'local-admin-2026')
        self.buyer.email = 'buyer@example.test'
        self.buyer.save()
        self.client.force_login(self.buyer)

    def token_verificacion(self):
        with self.captureOnCommitCallbacks(execute=True):
            email_verification.enviar_verificacion(self.buyer, 'http://testserver')
        return re.search(r'/verificar-correo/([^/]+)/', mail.outbox[-1].body).group(1)

    def test_menu_cuenta_y_anonimo(self):
        response = self.client.get('/mi-cuenta/')
        for texto in ['Seguridad', 'Mis tiendas', 'Cerrar sesión', 'Correo pendiente de verificar', 'Órdenes recientes']:
            self.assertContains(response, texto)
        self.assertNotContains(response, 'href="/admin/')
        self.client.logout()
        response = self.client.get('/')
        self.assertContains(response, 'Iniciar sesión'); self.assertContains(response, 'Crear cuenta')

    def test_logout_solo_post_y_mensaje(self):
        self.assertEqual(self.client.get('/logout/').status_code, 405)
        response = self.client.post('/logout/', follow=True)
        self.assertContains(response, 'Sesión cerrada correctamente.')
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_cambiar_password_mantiene_sesion(self):
        response = self.client.post(reverse('password_change'), {'old_password':'local-test-2026','new_password1':'Renovada!Cuenta2026','new_password2':'Renovada!Cuenta2026'}, follow=True)
        self.assertContains(response, 'Contraseña actualizada')
        self.assertIn('_auth_user_id', self.client.session)
        self.buyer.refresh_from_db(); self.assertTrue(self.buyer.check_password('Renovada!Cuenta2026'))

    def test_cambiar_password_rechaza_actual_incorrecta(self):
        self.client.post(reverse('password_change'), {'old_password':'incorrecta','new_password1':'Renovada!Cuenta2026','new_password2':'Renovada!Cuenta2026'})
        self.buyer.refresh_from_db(); self.assertTrue(self.buyer.check_password('local-test-2026'))

    def test_recuperacion_generica_limite_y_token(self):
        self.client.logout()
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post('/recuperar-contrasena/', {'email':self.buyer.email})
        self.assertEqual(len(mail.outbox),1)
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post('/recuperar-contrasena/', {'email':self.buyer.email})
            ausente = self.client.post('/recuperar-contrasena/', {'email':'no-existe@example.test'})
        self.assertEqual(len(mail.outbox),1); self.assertEqual(response.url, ausente.url)
        enlace = re.search(r'http://testserver(/restablecer/[^\s]+)', mail.outbox[0].body).group(1)
        formulario = self.client.get(enlace)
        self.assertEqual(formulario.status_code,302)
        resultado = self.client.post(formulario.url, {'new_password1':'Restablecida!2026','new_password2':'Restablecida!2026'}, follow=True)
        self.assertContains(resultado, 'Tu contraseña está lista')
        self.assertContains(self.client.get(enlace), 'El enlace no está disponible')

    def test_recuperacion_vencida(self):
        uid = urlsafe_base64_encode(force_bytes(self.buyer.pk))
        token = default_token_generator.make_token(self.buyer)
        with override_settings(PASSWORD_RESET_TIMEOUT=-1):
            self.assertContains(self.client.get(reverse('password_reset_confirm',args=[uid,token])), 'El enlace no está disponible')

    def test_verificacion_token_confirmacion_y_no_reuso(self):
        token = self.token_verificacion()
        url = reverse('verificar_email',args=[token])
        self.client.get(url)
        self.assertFalse(Profile.objects.get(user=self.buyer).correo_verificado)
        self.assertEqual(self.client.post(url).status_code,302)
        self.assertTrue(Profile.objects.get(user=self.buyer).correo_verificado)
        with self.assertRaises(ValidationError): email_verification.verificar(token)

    def test_verificacion_correo_cambiado_manipulado_y_vencido(self):
        token = self.token_verificacion()
        with self.assertRaises(ValidationError): email_verification.verificar(token+'x')
        with patch('django.core.signing.time.time', return_value=timezone.now().timestamp()+90000):
            with self.assertRaises(ValidationError): email_verification.verificar(token)
        accounts.guardar_datos(self.buyer, {'email':'nuevo@example.test'})
        with self.assertRaises(ValidationError): email_verification.verificar(token)
        accounts.guardar_datos(self.buyer, {'email':'buyer@example.test'})
        with self.assertRaises(ValidationError): email_verification.verificar(token)
        with self.assertRaises(ValidationError): email_verification.enviar_verificacion(self.buyer, 'http://testserver')

    def test_reenvio_limite_persistente(self):
        self.token_verificacion()
        with self.assertRaises(ValidationError): email_verification.enviar_verificacion(self.buyer,'http://testserver')
        Profile.objects.filter(user=self.buyer).update(ultimo_envio_verificacion=timezone.now()-timedelta(minutes=3))
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(reverse('reenviar_verificacion'))
        self.assertEqual(len(mail.outbox),2)

    def test_registro_sesion_y_correo(self):
        self.client.logout()
        with self.captureOnCommitCallbacks(execute=True):
            response=self.client.post('/registro/',{'username':'nueva','first_name':'Ana','last_name':'López','email':'ana@example.test','password1':'AltaCuenta!2026','password2':'AltaCuenta!2026'})
        self.assertRedirects(response,'/mi-cuenta/')
        user=get_user_model().objects.get(username='nueva')
        self.assertFalse(user.is_superuser); self.assertEqual(user.first_name,'Ana'); self.assertEqual(len(mail.outbox),1)

    def test_perfil_invalida_verificacion_y_no_modifica_otro_usuario(self):
        email_verification.verificar(self.token_verificacion())
        self.client.post('/mi-cuenta/perfil/',{'first_name':'Cambio','last_name':'Local','email':'nuevo@example.test','telefono':'5551234','user':self.admin.pk,'is_superuser':'on'})
        self.buyer.refresh_from_db();self.admin.refresh_from_db()
        self.assertEqual(self.buyer.first_name,'Cambio');self.assertFalse(self.buyer.is_superuser)
        self.assertEqual(self.admin.email,'super@example.test')
        self.assertFalse(Profile.objects.get(user=self.buyer).correo_verificado)
        self.assertEqual(Profile.objects.get(user=self.buyer).telefono,'5551234')

    def test_solicitud_requiere_correo_verificado_en_servicio(self):
        with self.assertRaisesMessage(ValidationError,'Verifica tu correo'):
            solicitar_proveedor(self.buyer,{})
        self.assertContains(self.client.get('/quiero-vender/'),'Verifica tu correo')

    def test_admin_crear_sin_password_ni_elevacion_y_establecer(self):
        self.client.force_login(self.admin)
        with self.captureOnCommitCallbacks(execute=True):
            response=self.client.post('/administracion/usuarios/nuevo/',{'username':'invitado','first_name':'Invitado','last_name':'Local','email':'invitado@example.test','is_active':'on','is_superuser':'on','password':'insegura'})
        user=get_user_model().objects.get(username='invitado')
        self.assertFalse(user.has_usable_password());self.assertFalse(user.is_superuser)
        self.assertRedirects(response,reverse('admin_usuario',args=[user.pk]))
        enlace=re.search(r'http://testserver(/restablecer/[^\s]+)',mail.outbox[0].body).group(1)
        self.client.logout();pagina=self.client.get(enlace)
        self.client.post(pagina.url,{'new_password1':'InvitadoSeguro!2026','new_password2':'InvitadoSeguro!2026'})
        user.refresh_from_db();self.assertTrue(user.check_password('InvitadoSeguro!2026'))

    def test_admin_desactivar_reactivar_y_ultimo_super(self):
        accounts.estado_usuario(self.admin,self.buyer.pk,False)
        self.buyer.refresh_from_db();self.assertFalse(self.buyer.is_active)
        accounts.estado_usuario(self.admin,self.buyer.pk,True)
        with self.assertRaises(ValidationError):accounts.estado_usuario(self.admin,self.admin.pk,False)
        with self.assertRaises(ValidationError):accounts.estado_usuario(self.admin,self.seller.pk,False)
        self.assertEqual(RegistroAdministrativo.objects.filter(tipo_objeto='user',objeto_id=self.buyer.pk).count(),2)

    def test_permisos_admin_get_post(self):
        for ruta in ['/administracion/usuarios/','/administracion/usuarios/nuevo/',f'/administracion/usuarios/{self.admin.pk}/',f'/administracion/usuarios/{self.admin.pk}/accion/','/administracion/planes/','/administracion/planes/nuevo/','/administracion/membresias/']:
            self.assertEqual(self.client.get(ruta).status_code,403)
            self.assertEqual(self.client.post(ruta,{}).status_code,403)
        with self.assertRaises(PermissionDenied):accounts.estado_usuario(self.buyer,self.other.pk,False)

    def test_preferencias_correo_y_internas_obligatorias(self):
        self.client.post('/mi-cuenta/preferencias/',{})
        with self.captureOnCommitCallbacks(execute=True):
            crear_notificacion([self.buyer.pk],'nueva_orden','Prueba','Mensaje','/mis-ordenes/',correo=True)
            crear_notificacion([self.buyer.pk],'nueva_opinion','Opinión','Mensaje','/mis-ordenes/')
        self.assertEqual(len(mail.outbox),0)
        self.assertEqual(Notificacion.objects.filter(usuario=self.buyer).count(),2)
        self.client.post('/mi-cuenta/preferencias/',{'email_nueva_orden':'on'})
        with self.captureOnCommitCallbacks(execute=True):crear_notificacion([self.buyer.pk],'nueva_orden','Prueba','Mensaje','/mis-ordenes/')
        self.assertEqual(len(mail.outbox),1)

    def test_multiples_tiendas_selector_checklist_aislamiento(self):
        plan = PlanMembresia.objects.create(nombre='Equipo', max_usuarios=3)
        asignar_membresia(self.admin, self.ajeno.pk, plan.pk)
        AdministradorProveedor.objects.create(proveedor=self.ajeno,usuario=self.seller)
        self.client.force_login(self.seller)
        respuesta=self.client.get('/mis-tiendas/')
        self.assertContains(respuesta,self.proveedor.nombre);self.assertContains(respuesta,self.ajeno.nombre)
        respuesta=self.client.get(f'/gestion/{self.proveedor.pk}/')
        self.assertContains(respuesta,'Gestionando: '+self.proveedor.nombre)
        self.assertContains(respuesta,'data-store-selector');self.assertContains(respuesta,'Configuración')
        self.client.force_login(self.buyer)
        self.assertEqual(self.client.get(f'/gestion/{self.proveedor.pk}/').status_code,404)
        self.assertNotContains(self.client.get('/mis-tiendas/'),self.proveedor.nombre)

    def test_checklist_derivado_y_publicacion_real(self):
        antes=resumen_tienda(self.proveedor)
        self.proveedor.descripcion='Descripción';self.proveedor.ubicacion='Centro';self.proveedor.telefono='123'
        despues=resumen_tienda(self.proveedor)
        self.assertGreater(despues['porcentaje'],antes['porcentaje']);self.assertTrue(despues['publicada'])
        self.proveedor.estado='suspendido';self.assertFalse(resumen_tienda(self.proveedor)['publicada'])

    def test_csrf_mutaciones_cuenta_y_admin(self):
        csrf=Client(enforce_csrf_checks=True);csrf.force_login(self.admin)
        for ruta in ['/logout/','/mi-cuenta/perfil/','/mi-cuenta/verificacion/enviar/','/mi-cuenta/preferencias/','/administracion/usuarios/nuevo/','/administracion/planes/nuevo/']:
            self.assertEqual(csrf.post(ruta,{}).status_code,403)

    def test_planes_crear_editar_desactivar_y_historial(self):
        datos={'nombre':'Especial','precio':'10','duracion_dias':40,'max_productos':50,'max_usuarios':3,'promociones':True,'estadisticas':False,'activo':True}
        plan=plans.guardar_plan(self.admin,datos)
        contrato=asignar_membresia(self.admin,self.proveedor.pk,plan.pk)
        snapshot=contrato.condiciones.copy()
        datos.update(precio='20',max_productos=1)
        with self.assertRaisesMessage(ValidationError,'1 proveedores'):plans.guardar_plan(self.admin,datos,plan.pk)
        plans.guardar_plan(self.admin,datos,plan.pk,confirmar=True)
        contrato.refresh_from_db();self.assertEqual(contrato.condiciones,snapshot);self.assertEqual(self.proveedor.productos.count(),2)
        datos['activo']=False
        plans.guardar_plan(self.admin,datos,plan.pk,confirmar=True)
        self.assertEqual(plan_actual(self.proveedor).pk,plan.pk)
        with self.assertRaises(ValidationError):asignar_membresia(self.admin,self.ajeno.pk,plan.pk)
        self.assertTrue(MembresiaProveedor.objects.filter(pk=contrato.pk).exists())

    def test_plan_gratis_y_validacion_limites(self):
        datos={'nombre':'GRATIS','precio':0,'duracion_dias':30,'max_productos':None,'max_usuarios':None,'promociones':False,'estadisticas':False,'activo':True}
        plan=plans.guardar_plan(self.admin,datos)
        with self.assertRaises(ValidationError):plans.guardar_plan(self.admin,{**datos,'activo':False},plan.pk)
        with self.assertRaises(ValidationError):plans.guardar_plan(self.admin,{**datos,'nombre':'Otro','duracion_dias':0})
        with self.assertRaises(ValidationError):plans.guardar_plan(self.admin,{**datos,'nombre':'Otro','max_usuarios':0})
        with self.assertRaises(PermissionDenied):plans.guardar_plan(self.buyer,datos)

    def test_admin_flujo_http_planes_membresias_y_usuario(self):
        self.client.force_login(self.admin)
        datos={'nombre':'HTTP plan','precio':'25','duracion_dias':'60','max_productos':'100','max_usuarios':'5','activo':'on'}
        self.assertRedirects(self.client.post('/administracion/planes/nuevo/',datos),'/administracion/planes/')
        plan=PlanMembresia.objects.get(nombre='HTTP plan')
        self.assertRedirects(self.client.post(reverse('admin_plan',args=[plan.pk]),{**datos,'precio':'35'}),'/administracion/planes/')
        self.client.post(reverse('admin_asignar_plan',args=[self.proveedor.pk]),{'plan':plan.pk})
        for ruta in ['/administracion/planes/',reverse('admin_plan',args=[plan.pk]),'/administracion/membresias/?estado=activa',reverse('admin_usuario',args=[self.buyer.pk]),'/administracion/usuarios/?q=buyer']:
            self.assertEqual(self.client.get(ruta).status_code,200)
        self.assertContains(self.client.get('/administracion/membresias/?plan='+str(plan.pk)),self.proveedor.nombre)
        self.assertNotContains(self.client.get('/administracion/membresias/?estado=vencida'),self.proveedor.nombre)
        self.assertNotContains(self.client.get('/administracion/proveedores/nuevo/'), '/admin/auth/user/')
        self.assertContains(self.client.get('/administracion/'), 'Administración técnica')
