from datetime import timedelta
from io import BytesIO
from uuid import uuid5, NAMESPACE_URL
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone
from PIL import Image, ImageDraw
from servicios.models import (Proveedor, AdministradorProveedor, GiroComercial, Categoria, Producto, ProductoImagen, PlanMembresia, MembresiaProveedor, Orden)
from servicios.application.orders import crear_orden, cambiar_estado
from servicios.application.reviews import crear_opinion_producto, crear_opinion_proveedor

DEMO_PASSWORD = 'OurEventsDemo2026!'
NOMBRES = ['Pan de masa madre', 'Galletas de avena', 'Caja de pan artesanal', 'Pastel de zanahoria', 'Granola de la casa', 'Café de especialidad', 'Ramo de temporada', 'Centro de mesa natural', 'Planta en maceta', 'Arreglo de flores secas', 'Terrario pequeño', 'Ramo de eucalipto', 'Taza de cerámica', 'Vela aromática', 'Florero de barro', 'Cojín de algodón', 'Canasta tejida', 'Cuadro botánico', 'Bolsa de tela', 'Collar artesanal', 'Sombrero tejido', 'Pañoleta estampada', 'Cartera de piel', 'Pulsera de cuentas', 'Kit de celebración', 'Guirnalda de papel', 'Invitaciones personalizadas', 'Set de globos', 'Recuerdos para invitados', 'Letrero de bienvenida']


def ilustracion(indice, nombre):
    colores = ['#eedbc5', '#dfebd5', '#d8e4e8', '#e9dce7', '#ece5c9']
    img = Image.new('RGB', (720, 540), colores[indice // 6 % 5])
    draw = ImageDraw.Draw(img)
    draw.ellipse((170, 90, 560, 470), fill='#ffffff')
    if indice // 6 == 0:
        draw.ellipse((235, 175, 510, 345), fill='#bd844d')
        for offset in range(3): draw.line((295+offset*50, 200, 270+offset*50, 300), fill='#edd6ad', width=12)
    elif indice // 6 == 1:
        for x,y in [(300,210),(390,170),(440,250),(340,300)]:
            draw.line((360,410,x,y),fill='#356647',width=8)
            draw.ellipse((x-45,y-45,x+45,y+45),fill=['#b98399','#d4a66c'][indice%2])
            draw.ellipse((x-12,y-12,x+12,y+12),fill='#f3d690')
    elif indice // 6 == 2:
        draw.rounded_rectangle((270,180,455,375),radius=35,fill='#b7785a')
        draw.ellipse((286,160,441,204),fill='#805441')
        draw.arc((420,195,505,310),270,90,fill='#b7785a',width=17)
    elif indice // 6 == 3:
        draw.rounded_rectangle((255,220,470,390),radius=15,fill='#6a8a76')
        draw.arc((295,125,435,310),180,360,fill='#41654f',width=18)
    else:
        for x,y,c in [(270,200,'#92b0a0'),(380,150,'#d9a982'),(470,210,'#b8a6bd')]:
            draw.line((x,y,360,410),fill='#63716b',width=3)
            draw.ellipse((x-40,y-50,x+40,y+50),fill=c)
    draw.text((28,500), 'OurEvents / DEMO',fill='#235b47')
    out=BytesIO(); img.save(out,format='PNG'); return out.getvalue()


class Command(BaseCommand):
    help = 'Crea datos demo locales de forma idempotente. Requiere DEBUG=True.'

    @transaction.atomic
    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError('seed_demo está deshabilitado con DEBUG=False.')
        User = get_user_model()
        nombres_usuario = ['admin', 'proveedor1', 'proveedor2', 'comprador', 'solicitante1', 'solicitante2', 'solicitante3', 'colaborador']
        grupo, _ = Group.objects.get_or_create(name='ourevents-demo-local')
        for nombre in nombres_usuario:
            existente = User.objects.filter(username=nombre).first()
            if existente and not existente.groups.filter(pk=grupo.pk).exists():
                raise CommandError(f'La cuenta {nombre} ya existe y no es demo. No se modificó ninguna cuenta; usa una base de desarrollo separada.')
        usuarios = {}
        for nombre in nombres_usuario:
            usuario, creado = User.objects.get_or_create(username=nombre)
            if creado:
                usuario.set_password(DEMO_PASSWORD)
                usuario.is_staff = usuario.is_superuser = nombre == 'admin'
                usuario.save()
                usuario.groups.add(grupo)
            usuarios[nombre] = usuario
        planes = []
        for nombre, precio, productos, admins, promo in [('GRATIS',0,5,1,False),('PROFESIONAL',299,100,5,True),('EMPRESA',799,None,None,True)]:
            plan, _ = PlanMembresia.objects.get_or_create(nombre=nombre, defaults={'precio':precio,'max_productos':productos,'max_usuarios':admins,'promociones':promo,'estadisticas':promo})
            planes.append(plan)
        giros = [GiroComercial.objects.get_or_create(nombre=n)[0] for n in ['Alimentos artesanales','Florería','Diseño para el hogar','Moda local','Celebraciones']]
        raices = [Categoria.objects.get_or_create(slug='demo-categoria-'+str(i),defaults={'nombre':n, 'orden':i})[0] for i,n in enumerate(['Alimentos','Flores y plantas','Hogar','Moda','Celebraciones','Regalos','Arte','Bienestar'])]
        subcategorias = [Categoria.objects.get_or_create(slug='demo-subcategoria-'+str(i), defaults={'nombre':n,'padre':raices[i//3]})[0] for i,n in enumerate(['Panadería','Dulces','Café y despensa','Ramos','Plantas','Arreglos','Cerámica','Textiles','Decoración','Accesorios','Bolsas','Complementos','Fiestas','Papelería','Recuerdos'])]
        negocios=[]
        for i,nombre in enumerate(['Pan de Barrio','Casa Botánica','Taller Tierra','Luna & Lino','Celebra Bonito']):
            proveedor, creado = Proveedor.objects.get_or_create(slug='demo-negocio-'+str(i+1),defaults={'nombre':nombre,'estado':'activo','verificado':i%2==0,'fecha_verificacion':timezone.now() if i%2==0 else None,'descripcion':'Somos un negocio local. Creamos productos con cuidado y atención a los detalles. Escríbenos para preparar tu próxima solicitud.','ubicacion':['Roma Norte, Ciudad de México','Coyoacán, Ciudad de México','Centro, Puebla','Centro, Guadalajara','Condesa, Ciudad de México'][i], 'telefono':'55500000'+str(i).zfill(2)})
            if creado:
                proveedor.giros.add(giros[i])
            MembresiaProveedor.objects.get_or_create(proveedor=proveedor, activa=True, defaults={'plan':planes[1], 'inicio':timezone.localdate(),'fin':timezone.localdate()+timedelta(days=365)})
            AdministradorProveedor.objects.get_or_create(proveedor=proveedor, usuario=usuarios['proveedor1' if i%2==0 else 'proveedor2'])
            negocios.append(proveedor)
        productos=[]
        for i,nombre in enumerate(NOMBRES):
            producto, creado = Producto.objects.get_or_create(slug='demo-producto-'+str(i+1),defaults={'proveedor':negocios[i//6],'categoria':subcategorias[(i//6)*3+(i%3)],'nombre':nombre,'descripcion_corta':'Hecho con cuidado, pensado para ti.','descripcion':'Un producto de nuestro catálogo local, elaborado con materiales seleccionados. Consulta opciones, tiempos de preparación y entrega directamente con el negocio. Las imágenes son ilustraciones de demostración.','precio':str(85+i*23),'precio_promocional':str(65+i*23) if i%4==0 else None,'stock':30 if i%6<4 else (2 if i%6==4 else 0),'stock_minimo':4,'destacado':i%3==0,'sku':f'DEMO-{i+1:03d}'})
            if creado:
                imagen = ProductoImagen(producto=producto,principal=True,texto_alternativo=nombre+' · ilustración demo')
                imagen.imagen.save(f'demo-{i+1}.png',ContentFile(ilustracion(i,nombre)))
            productos.append(producto)
        estados = ['NUEVA','ACEPTADA','EN_PROCESO','COMPLETADA','CANCELADA','COMPLETADA']
        ruta = ['VISTA','ACEPTADA','EN_PROCESO','ATENDIDA','COMPLETADA']
        for i,estado in enumerate(estados):
            clave = uuid5(NAMESPACE_URL,f'ourevents-demo-orden-{i}')
            if Orden.objects.filter(clave_solicitud=clave).exists():
                continue
            negocio = negocios[i%5]
            seleccion = list(negocio.productos.filter(slug__startswith='demo-',stock__gte=10).order_by('pk')[:2])
            orden = crear_orden(usuarios['comprador'],negocio.pk,{p.pk:1 for p in seleccion},clave,'Solicitud de demostración')
            if estado == 'CANCELADA':
                cambiar_estado(usuarios['comprador'],orden.pk,'CANCELADA')
            elif estado != 'NUEVA':
                for destino in ruta:
                    cambiar_estado(usuarios['admin'],orden.pk,destino)
                    if destino == estado: break
            if estado == 'COMPLETADA':
                crear_opinion_proveedor(usuarios['comprador'],orden.pk,5,'Muy buena atención y comunicación. Una experiencia que repetiría.')
                for producto in seleccion:
                    crear_opinion_producto(usuarios['comprador'],orden.pk,producto.pk,4+i%2,'Producto bien preparado y tal como lo esperaba. ¡Recomendado!')
        from servicios.management.demo_providers import seed_provider_lifecycle
        seed_provider_lifecycle(usuarios)
        self.stdout.write(self.style.SUCCESS('Demo listo: 8 cuentas, 6 negocios, 30 productos y ciclo de alta/moderación. Ejecuciones posteriores conservan datos y contraseñas existentes.'))
        self.stdout.write('Usuarios: admin, proveedor1, proveedor2, comprador, solicitante1, solicitante2, solicitante3, colaborador. Contraseña inicial: '+DEMO_PASSWORD)
