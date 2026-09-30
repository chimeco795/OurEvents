from django.db import migrations
from django.utils.text import slugify


def trasladar(apps, schema_editor):
    alias = schema_editor.connection.alias
    Proveedor = apps.get_model('servicios', 'Proveedor')
    Producto = apps.get_model('servicios', 'Producto')
    Imagen = apps.get_model('servicios', 'ProductoImagen')
    productos = Producto.objects.using(alias)
    if productos.filter(proveedor__isnull=True).exists():
        proveedor = Proveedor.objects.using(alias).create(nombre='Catálogo legado: pendiente de asignación', slug='catalogo-legado', estado='inactivo')
        productos.filter(proveedor__isnull=True).update(proveedor=proveedor)
    for nombre in ['Categoria', 'Producto', 'Proveedor', 'GiroComercial']:
        Modelo = apps.get_model('servicios', nombre)
        for obj in Modelo.objects.using(alias).all().iterator():
            obj.slug = f'{slugify(obj.nombre)[:70] or "registro"}-{obj.pk}'
            obj.save(using=alias, update_fields=['slug'])
    for producto in productos.exclude(imagen='').iterator():
        Imagen.objects.using(alias).get_or_create(producto_id=producto.pk, imagen=producto.imagen.name, defaults={'principal': True, 'texto_alternativo': producto.nombre})


class Migration(migrations.Migration):
    dependencies = [('servicios', '0005_girocomercial_alter_categoria_options_and_more')]
    # Reversión deliberadamente no destructiva; una restauración exacta usa el respaldo.
    operations = [migrations.RunPython(trasladar, migrations.RunPython.noop)]
