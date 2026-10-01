from django.db import migrations

def guardar_condiciones(apps, schema_editor):
    Membresia = apps.get_model('servicios', 'MembresiaProveedor')
    campos = ('nombre', 'precio', 'duracion_dias', 'max_productos', 'max_usuarios', 'promociones', 'estadisticas', 'activo')
    for m in Membresia.objects.using(schema_editor.connection.alias).select_related('plan').iterator():
        m.condiciones = {k: str(getattr(m.plan, k)) if k == 'precio' else getattr(m.plan, k) for k in campos}
        m.save(update_fields=['condiciones'])

class Migration(migrations.Migration):
    dependencies = [('servicios', '0012_membresiaproveedor_condiciones_and_more')]
    operations = [migrations.RunPython(guardar_condiciones, migrations.RunPython.noop)]
