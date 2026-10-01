from django.db import migrations


def asignar_principales(apps, schema_editor):
    User = apps.get_model('auth', 'User')
    Proveedor = apps.get_model('servicios', 'Proveedor')
    Acceso = apps.get_model('servicios', 'AdministradorProveedor')
    db = schema_editor.connection.alias
    custodio = None
    for proveedor in Proveedor.objects.using(db).all().iterator():
        acceso = Acceso.objects.using(db).filter(proveedor=proveedor, activo=True, usuario__is_active=True).order_by('pk').first()
        if acceso:
            Acceso.objects.using(db).filter(pk=acceso.pk).update(es_principal=True)
        else:
            if custodio is None:
                custodio = User.objects.using(db).filter(is_superuser=True, is_active=True).order_by('pk').first()
                if custodio is None:
                    custodio, creado = User.objects.using(db).get_or_create(username='__ourevents_custodia__', defaults={'is_active': False, 'password': '!'})
                    if not creado and custodio.is_active:
                        raise RuntimeError('El usuario de custodia ya existe como cuenta activa. Revisar antes de migrar.')
            Acceso.objects.using(db).update_or_create(proveedor=proveedor, usuario=custodio, defaults={'activo': True, 'es_principal': True})


class Migration(migrations.Migration):
    dependencies = [('servicios', '0009_administradorproveedor_es_principal_and_more')]
    operations = [migrations.RunPython(asignar_principales, migrations.RunPython.noop)]
