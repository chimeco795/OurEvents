# OurEvents

Marketplace multi-proveedor desarrollado con Django 5.2 LTS, SQLite, Django Templates y Bootstrap. Esta entrega implementa la **fase 1**, base segura del dominio y gestión de catálogo. No contiene todavía el flujo de órdenes ni la interfaz final.

## Modelo de negocio

OurEvents permitirá descubrir productos y proveedores y generar solicitudes separadas por proveedor. No procesa pagos: pago, entrega y facturación se acuerdan fuera de la plataforma. Las futuras membresías se asignarán manualmente; no se integra ninguna pasarela.

## Instalación (PowerShell, Python 3.12)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(64))"
# Sustituye SECRET_KEY en .env con el valor generado.
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Para esta copia local ya se prepararon `.venv`, un `.env` ignorado y las migraciones. No reutilices el entorno `venv` heredado del repositorio. `requirements-lock.txt` registra las versiones verificadas; puedes instalarlo con `pip install -r requirements-lock.txt` para reproducirlas.

## Variables de entorno

`.env` se carga sin sobrescribir variables ya exportadas. Nunca se versiona. `SECRET_KEY` es obligatoria y no tiene clave predeterminada; `DEBUG` es falso por defecto. Para desarrollo usa `DEBUG=True`. `ALLOWED_HOSTS` contiene hosts separados por comas. En producción configura hosts reales, HTTPS y `DEBUG=False`; las cookies seguras, redirección HTTPS y HSTS se activan automáticamente. No se confía automáticamente en cabeceras de proxy.

El correo usa consola por defecto. Para SMTP configura `EMAIL_BACKEND`, `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_USE_TLS`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `DEFAULT_FROM_EMAIL` y `CONTACT_EMAIL`. Sin destinatario de contacto el formulario no envía correos. El remitente lo controla el servidor y el correo del usuario se usa como Reply-To.

**Antes de desplegar:** rotar la SECRET_KEY y revocar/reemplazar la contraseña SMTP previamente expuestas. Retirarlas del árbol actual no las elimina del historial. No reutilizar la base de datos publicada ni sus cuentas en producción sin revisión de credenciales y datos. La limpieza del historial requiere coordinarse con colaboradores y no se realizó en esta fase.

## Arquitectura y roles

Se conserva `servicios`, las claves primarias y las migraciones originales. `models.py` contiene entidades; `forms.py` valida entradas; `permissions.py` centraliza el alcance por negocio; `views.py` maneja HTTP; `admin.py` permite la administración global.

- Usuario autenticado: perfil y comentarios generales existentes. Registro y edición del perfil se ampliarán en una fase posterior.
- Administrador de proveedor: asignación explícita mediante `AdministradorProveedor`; puede gestionar productos, imágenes, stock y datos de sus negocios activos en `/gestion/`. No necesita `is_staff`.
- Superadministrador: `is_superuser`; accede al Django Admin y a todos los negocios. Un usuario solamente `is_staff` no accede al panel global.
- Proveedor: negocio independiente del usuario. Puede tener múltiples administradores y giros. Suspenderlo o desactivar una asignación revoca la gestión del negocio.

La categoría de un producto es su nodo más específico; sus padres representan los niveles superiores. No hay una segunda columna de subcategoría. Los ciclos se rechazan al guardar categorías. La disponibilidad deriva de actividad del proveedor/producto y stock; no se almacena otra copia del estado. SKU único por proveedor si no está vacío. La galería permite una sola imagen principal, orden y texto alternativo. Los campos de reputación y membresía se introducirán con sus respectivos dominios, sin métricas ficticias o redundantes.

## Carga inicial y uso

1. Crear usuarios desde `/admin/` con una cuenta superadministradora.
2. Crear giros, categorías y proveedores; asignar administradores en el propio proveedor. Activar el proveedor tras revisar sus datos.
3. Entrar como administrador del negocio a `/gestion/` y agregar productos/imágenes. El stock inicia en cero; el catálogo indica agotados.
4. Opcional: `python data_load.py` crea datos demo idempotentes en un negocio inactivo.

La galería conserva `Producto.imagen` como compatibilidad de lectura con el catálogo legado. Los nuevos archivos se guardan en `media/`. En producción servir estáticos y media mediante infraestructura dedicada; los archivos subidos no deben ejecutarse ni servirse como HTML. El servidor de desarrollo sirve media sólo con DEBUG.

## Migraciones y datos existentes

Antes de migrar una instalación existente, hacer un respaldo consistente de SQLite y de los archivos de imágenes.

- `0005`: amplía esquema, inicialmente con proveedor nullable y slugs no únicos.
- `0006`: asigna los productos existentes a un proveedor **inactivo pendiente de asignación**, rellena slugs únicos y copia referencias de la imagen original a la galería sin mover ni borrar archivos.
- `0007`: exige proveedor y unicidad de slugs.

Se conserva el historial de comentarios generales; no se presentan como compras verificadas. La copia local se respaldó en `backups/pre_phase_one.sqlite3` antes de migrar. Los 4 productos, 4 categorías, 10 comentarios y 1 usuario originales permanecen. El stock legado se inicia en cero porque no se conoce el inventario real. Reasignar productos y revisar archivos antes de publicar el proveedor.

La migración de datos tiene reversión no destructiva; para volver exactamente al estado anterior, restaurar el respaldo junto con la versión de código anterior. No se borran tablas arbitrariamente. Los archivos originalmente referidos por SQLite pueden no estar presentes en el repositorio: deben recuperarse del almacenamiento original.

## Verificación

```powershell
python manage.py migrate
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test
python -m pip check
```

15 pruebas cubren creación de proveedor/productos, duplicados, categorías cíclicas, stock, precios, imagen principal, cambio de galería, aislamiento GET/POST, imágenes ajenas, suspensión, revocación, acceso al admin, CSRF, catálogo y migración con datos legados. Órdenes, subtotales y opiniones verificadas se probarán al implementarlos.

Para producción ejecutar además `python manage.py check --deploy` con `DEBUG=False` y la configuración real. Esta fase no incluye despliegue, pruebas de navegador ni auditoría externa de seguridad.

## Limpieza

Se retiraron del índice de Git `venv/`, caches Python y `db.sqlite3`, conservándolos localmente. `.gitignore` excluye `.env`, entornos, SQLite, media, respaldos y estáticos compilados. No se purgó el historial ni se borró la imagen heredada en `comentarios/`; conviene revisar la autorización para distribuirla antes de publicar.

Consulta [el análisis y las fases siguientes](docs/arquitectura.md).

La comprobación de producción deja dos avisos deliberados: HSTS para todos los subdominios y preload. No se habilitan sin conocer el dominio y confirmar HTTPS en todos sus subdominios.
