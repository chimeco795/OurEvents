# OurEvents · Marketplace multi-proveedor

OurEvents conecta compradores con negocios y genera solicitudes de compra. **No procesa pagos.** Pago, facturación y entrega se acuerdan directamente entre las partes. La fase 2 evoluciona los modelos y datos de la fase 1; no reemplaza el proyecto.

## Ejecutar en local (CMD)

En esta copia el entorno, `.env`, las migraciones y los datos demo ya están preparados:

```cmd
cd /d D:\Archivos\ChatGPT\OurEvents
.venv\Scripts\activate.bat
python manage.py runserver
```

Abrir http://127.0.0.1:8000/. Detener con Ctrl+C. Si ya había un servidor ejecutándose antes de actualizar la rama, reiniciarlo.

Para una instalación nueva con Python 3.12:

```cmd
python -m venv .venv
.venv\Scripts\activate.bat
python -m pip install -r requirements-lock.txt
copy .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

Sustituir `SECRET_KEY` en `.env` por el valor generado. Después:

```cmd
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
```

`seed_demo` requiere `DEBUG=True`. Para una instalación sin demo, crear el administrador con `python manage.py createsuperuser`.

## Arquitectura

Monolito modular: Django 5.2 LTS, SQLite, templates Django y CSS local responsive. La interfaz pública no depende de Bootstrap/CDN, React ni servicios externos. Los templates legados siguen disponibles.

| Responsabilidad | Ubicación |
|---|---|
| Entidades y constraints | `servicios/models.py` |
| Reglas puras de transición | `servicios/domain/orders.py` |
| Casos de uso transaccionales | `servicios/application/` |
| Consultas, búsqueda y reputación | `servicios/queries.py` |
| Adaptadores de sesión y email | `servicios/infrastructure/` |
| Autorización por negocio | `servicios/permissions.py` |
| Entradas HTTP | `forms.py`, `marketplace_views.py`, `views.py` |
| Componentes y presentación | `templates/components/`, `templates/marketplace/`, `static/css/marketplace.css` |

Se mantienen Proveedor, AdministradorProveedor, GiroComercial, Categoria, Producto, ProductoImagen, Profile y Comentario. Se agregan Orden, OrdenDetalle, OpinionProducto, OpinionProveedor, Notificacion, PlanMembresia y MembresiaProveedor. OpinionBase es abstracto: no crea otra tabla. Los comentarios legados no participan en la reputación.

`Orden` es el agregado que conserva sus detalles y totales históricos. Las operaciones críticas pasan por servicios; las vistas validan formularios y delegan. No hay capas ceremoniales, microservicios, colas, pasarelas de pago ni API REST añadida.

## Modelo de negocio y flujo de órdenes

El carrito de sesión guarda únicamente IDs y cantidades; los precios se resuelven siempre en el servidor. Los productos se agrupan por proveedor y cada grupo genera su propia orden. Cantidad por producto: 1–999; hasta 100 productos por solicitud. El folio y la clave idempotente impiden duplicar una orden por reenvío del formulario. Si cambia el carrito, su confirmación anterior deja de ser válida.

| Estado actual | Acciones del proveedor |
|---|---|
| NUEVA | VISTA, RECHAZADA, CANCELADA |
| VISTA | ACEPTADA, RECHAZADA, CANCELADA |
| ACEPTADA | EN_PROCESO, CANCELADA |
| EN_PROCESO | ATENDIDA, CANCELADA |
| ATENDIDA | COMPLETADA, CANCELADA |
| COMPLETADA / RECHAZADA / CANCELADA | Ninguna |

El comprador sólo puede cancelar NUEVA o VISTA. El superadministrador usa el mismo flujo de negocio. El Django Admin muestra órdenes y detalles como históricos de sólo lectura; no permite saltarse transiciones ni eliminar órdenes.

- Crear solicitud: no modifica stock. Puede solicitarse un producto agotado; el proveedor deberá reponer existencias antes de aceptar.
- Aceptar: comprueba actividad y existencias y reserva todos los detalles en una transacción. Si falla uno, no descuenta ninguno.
- Cancelar antes de aceptar / rechazar: no modifica stock.
- Cancelar después de reservar: devuelve unidades una única vez.
- Completar: mantiene el descuento ya realizado.

El nombre y precio promocional o normal se copian al detalle. Cambiar el catálogo no altera el histórico. El subtotal es informativo.

SQLite usa transacciones `IMMEDIATE` y timeout de 20 segundos, serializando escritores. Las transiciones incluyen bloqueo y actualización condicional; stock se modifica con expresiones `F` y condición de suficiencia. La prueba concurrente verifica que dos órdenes no consumen las mismas existencias. Para mayor carga, migrar a PostgreSQL y repetir pruebas de concurrencia; no se promete capacidad ilimitada de escritura en SQLite. La edición rápida y los formularios de producto rechazan un stock obsoleto para evitar sobrescribir reservas.

## Roles, seguridad y administración

- Comprador: registro, perfil, solicitudes, órdenes propias, opiniones verificadas y notificaciones propias.
- Gestor: asignación activa en AdministradorProveedor; acceso sólo a sus negocios activos. No necesita `is_staff`.
- Superadministrador: Django Admin y gestión global. `is_staff` por sí solo no da acceso al panel global.

Verificación, estado del negocio y membresía quedan fuera del formulario del proveedor. POST con CSRF para mutaciones. Consultas de ownership en backend para órdenes, productos, inventario, respuestas y notificaciones. Suspender el proveedor o revocar una asignación retira sus permisos. El comprador conserva acceso a su historial.

`SECRET_KEY` es obligatoria. `.env` no se versiona; el entorno exportado tiene prioridad. `DEBUG=False` activa cookies seguras, redirección HTTPS y HSTS. Ajustar `ALLOWED_HOSTS` a los hosts reales. El proyecto no confía automáticamente en headers de proxy. Idioma español de México y zona `America/Mexico_City`.

**Rotar las credenciales expuestas por el repositorio original antes de cualquier despliegue.** El historial anterior todavía puede contenerlas. No se realizó force push ni purga del historial. SQLite, media, cachés, entornos y respaldos quedan ignorados por Git. Servir media en producción sin ejecución de contenido subido y con límites de almacenamiento apropiados.

## Opiniones y reputación

Una opinión sólo se crea si el usuario es el comprador de una orden COMPLETADA. El producto debe formar parte de sus detalles o el proveedor debe coincidir con la orden. Constraints únicos por usuario + orden + producto/proveedor y estrellas 1–5. La verificación se deriva de la orden, no de un checkbox. El proveedor puede responder una vez a cada opinión de su negocio; la moderación sólo la gestiona el administrador.

Promedios, cantidad, distribución de estrellas y órdenes completadas se calculan con ORM. Sólo opiniones publicadas y verificadas alimentan los agregados. No hay columnas de reputación duplicadas. La cuenta muestra órdenes con valoraciones pendientes.

## Membresías

El superadministrador asigna planes y vigencias manualmente. Una membresía activa por negocio; si vence o no existe, rigen los límites del plan gratuito por defecto. No se borran productos al vencer: se impide crear más hasta ajustarse al límite. Los productos inactivos también cuentan.

| Plan demo | Productos | Administradores | Promociones |
|---|---:|---:|---|
| GRATIS | 5 | 1 | No |
| PROFESIONAL | 100 | 5 | Sí |
| EMPRESA | Sin límite | Sin límite | Sí |

Límites validados en backend, tanto en gestión como al guardar modelos. Los indicadores básicos del dashboard están disponibles para todos. El campo `estadisticas` prepara capacidades futuras; no hay informes avanzados en esta fase. No hay cobros automáticos.

## Notificaciones y correo

Notificaciones internas persistentes para órdenes, opiniones y respuestas, con centro paginado e indicador de no leídas. Se crean en la misma transacción que el evento de negocio. Correos de nueva orden, aceptación y finalización se despachan después del commit mediante un adaptador; un error SMTP se registra y no anula la operación.

Por defecto se usa backend consola. Para SMTP configurar `EMAIL_BACKEND`, `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_USE_TLS`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` y `DEFAULT_FROM_EMAIL`. `CONTACT_EMAIL` controla el destinatario del formulario de contacto. No hay WhatsApp integrado, workers ni reintentos durables de correo; las notificaciones internas son la fuente persistente.

## Demo local

`python manage.py seed_demo` es idempotente y exclusivo de desarrollo (`DEBUG=True`). No cambia contraseñas de cuentas existentes y aborta si encuentra uno de los nombres reservados que no pertenece al grupo demo. No usar estas cuentas en producción.

Crea 5 giros, 8 categorías raíz, 15 subcategorías, 5 negocios y 30 productos con imágenes PNG generadas localmente. Conserva el catálogo legado. Hay variación de precios, stock, promociones y verificación; membresías profesionales, órdenes nuevas/aceptadas/en proceso/completadas/canceladas, opiniones verificadas y notificaciones. El seed no sobrescribe cambios realizados después por el usuario. Las órdenes adicionales creadas durante la validación local permanecen como datos de prueba.

### CUENTAS DEMO OUREVENTS

Contraseña inicial común: **`OurEventsDemo2026!`**

| Rol | Usuario | URL |
|---|---|---|
| Super admin | `admin` | http://127.0.0.1:8000/admin/ |
| Proveedor 1 | `proveedor1` | http://127.0.0.1:8000/gestion/ |
| Proveedor 2 | `proveedor2` | http://127.0.0.1:8000/gestion/ |
| Comprador | `comprador` | http://127.0.0.1:8000/mi-cuenta/ |

Proveedor 1 administra Pan de Barrio, Taller Tierra y Celebra Bonito. Proveedor 2 administra Casa Botánica y Luna & Lino.

## URLs

| Pantalla | Ruta |
|---|---|
| Home | `/` |
| Catálogo | `/catalogo/` |
| Buscar | `/buscar/?q=pan` |
| Producto | `/producto/<slug>/` |
| Proveedor | `/proveedor/<slug>/` |
| Carrito / solicitud | `/solicitud/` |
| Registro / acceso | `/registro/`, `/login/` |
| Cuenta / perfil | `/mi-cuenta/`, `/mi-cuenta/perfil/` |
| Mis órdenes / detalle | `/mis-ordenes/`, `/ordenes/<id>/` |
| Notificaciones | `/notificaciones/` |
| Negocios / dashboard | `/gestion/`, `/gestion/<id>/` |
| Productos / inventario | `/gestion/<id>/productos/`, `/gestion/<id>/inventario/` |
| Órdenes / opiniones | `/gestion/<id>/ordenes/`, `/gestion/<id>/opiniones/` |
| Membresía / datos | `/gestion/<id>/membresia/`, `/gestion/<id>/datos/` |
| Administración | `/admin/` |

## Migraciones y respaldo

0001–0007 se mantienen. La migración 0008 añade el dominio de fase 2 y sus constraints; no borra tablas ni reasigna el catálogo existente. Antes de aplicarla se respaldó la base local en `backups/pre_phase_two.sqlite3`. Para otra instalación, hacer su propio respaldo consistente de SQLite y media antes de migrar. El catálogo legado sigue inactivo hasta revisión administrativa.

## Verificación

```cmd
python manage.py makemigrations
python manage.py migrate
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test
python -m pip check
```

38 pruebas cubren fase 1 y fase 2: migración, stock, reserva/devolución, rollback de múltiples detalles, transiciones, precios históricos, idempotencia, aislamiento comprador/proveedor, CSRF, opiniones/duplicados/respuestas, membresías, búsqueda/filtros, notificaciones, fallo SMTP, seed idempotente, edición obsoleta y concurrencia real mediante dos conexiones SQLite. La base de pruebas usa `test_ourevents.sqlite3` y se elimina al terminar.

También se verificó el flujo comprador → dos productos → orden → proveedor → reserva → completada → opiniones desde el navegador local, y las consultas administrativas mediante pruebas HTTP. Revisión responsive en 320, 375, 768, 1024 y 1440 px. Ver [registro de validación](docs/fase-dos.md).

Antes de despliegue ejecutar `check --deploy` con la configuración real. HSTS para subdominios y preload quedan desactivados hasta confirmar HTTPS en todo el dominio. Pendientes operativos: rotación de secretos, dominio/correo reales, almacenamiento de media, política de moderación, límites de frecuencia y estrategia de respaldo. No se ha desplegado a producción.

## Fase 3: alta de proveedores y administración

Se incorporan solicitudes para vender, panel propio exclusivo de superusuarios, gestión de tiendas y equipos, asignación manual de membresías y moderación con historial. No incorpora cobros ni pasarela de pagos.

- `/quiero-vender/`: solicitud e historial personal; sólo una solicitud pendiente o en revisión por usuario. Un rechazo permite volver a solicitar.
- `/administracion/`: indicadores, órdenes recientes y membresías próximas a vencer. Secciones `/solicitudes/`, `/proveedores/`, `/usuarios/`, `/membresias/` y `/moderacion/` bajo esa ruta.
- `/administracion/proveedores/nuevo/`: alta manual con administrador existente, giro y plan.
- `/gestion/<id>/datos/`: Mi tienda, imágenes, contacto y perfil comercial (horario, cobertura, pedido mínimo, preparación, entrega y métodos de pago informativos).
- `/gestion/<id>/equipo/`: el principal administra accesos de usuarios existentes dentro del límite del plan. Los colaboradores no pueden gestionar el equipo. Se protege al último principal y se desactivan accesos conservando su historial.
- `/reportar/<tipo>/<id>/` y `/mis-reportes/`: reportes de productos, proveedores y opiniones. El superusuario revisa, descarta o resuelve ocultando opiniones, desactivando productos o suspendiendo tiendas, sin borrar contenido.

La aprobación crea atómicamente una tienda **activa**, un administrador principal y una membresía **GRATIS**. Se publica tras la revisión administrativa; la verificación es una decisión independiente y nunca se concede automáticamente. Las decisiones, accesos y reportes generan auditoría y las notificaciones correspondientes. Cambiar de plan preserva membresías anteriores y valida los límites antes de reducir capacidad.

Modelos nuevos: `SolicitudProveedor`, `ReporteContenido` y `RegistroAdministrativo`. Se amplían `Proveedor` con información comercial y `AdministradorProveedor` con `es_principal` y protección de eliminación del usuario.

Migraciones 0009–0011: añaden los campos/modelos y asignan como principal al primer administrador activo existente. Para tiendas sin administrador utilizable, la migración asigna custodia al primer superusuario activo; si no existe, crea una cuenta de custodia deshabilitada y sin contraseña utilizable. Un superusuario debe reasignar esas tiendas a un principal activo antes de publicarlas. No se cambia su estado ni se borra historial. Respaldo local previo: `backups/pre_phase_three.sqlite3` (excluido de Git).

El seed ahora incluye **8 cuentas, 6 negocios y 30 productos**, dos solicitudes pendientes, una rechazada, una tienda suspendida, un colaborador disponible y reportes de ejemplo. Añade `solicitante1`, `solicitante2`, `solicitante3` y `colaborador`, con la misma contraseña inicial `OurEventsDemo2026!`. `admin` puede entrar a `/administracion/`. La ejecución repetida conserva decisiones y contraseñas existentes.

Para actualizar la instalación local desde CMD:

```cmd
cd /d D:\Archivos\ChatGPT\OurEvents
.venv\Scripts\activate
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
```

La suite completa contiene **58 pruebas**. Las 20 nuevas cubren solicitudes, transiciones, aprobación concurrente, rollback, permisos y POST falsificados, CSRF, límites y protección del equipo, moderación e historial. Incluye el flujo HTTP comprador → solicitud → aprobación → edición de Mi tienda → equipo → reporte → resolución administrativa. Los comandos de verificación anteriores siguen siendo aplicables; ejecutar también `python manage.py seed_demo` para preparar los ejemplos locales.
