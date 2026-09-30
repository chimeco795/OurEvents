# Documento histórico de fase 1

La implementación vigente de fase 2 se describe en [fase-dos.md](fase-dos.md) y en el README.

# Análisis y evolución del dominio

## Repositorio encontrado

Proyecto Django con `OurEvents/settings.py` y `OurEvents/urls.py`; una app `servicios` con Categoria, Producto, Comentario y Profile. Autenticación Django y señal para crear perfiles. Cuatro migraciones, templates Bootstrap y recursos estáticos/PWA. `data_load.py` dependía de Faker no declarado. `requirements.txt` mezclaba dependencias Django, Flask, análisis de datos y empaquetado sin uso en el código del proyecto. No había pruebas funcionales.

Riesgos detectados: secretos SMTP y Django en configuración; DEBUG fijo; endpoint público de correo de prueba; contacto duplicado anulaba el login requerido; comentarios sin validación y con fecha obligatoria omitida; ruta de template incorrecta; catálogo asumía imagen obligatoria; categoría con borrado en cascada de productos; app config duplicada; ausencia de separación de proveedores. SQLite, entorno virtual y bytecode estaban versionados. El service worker almacenaba la portada con contenido de sesión; ahora solamente considera estáticos y elimina la caché antigua.

Se revisaron código Python, migraciones, dependencias, rutas, templates, estáticos y distribución de archivos versionados. Los paquetes vendorizados del antiguo entorno no se trataron como código propio ni se reutilizaron.

## Dominio propuesto

Implementado: User/Profile → AdministradorProveedor → Proveedor; Proveedor ↔ GiroComercial; Categoria → padre; Producto → Proveedor y Categoria; ProductoImagen → Producto. Borrado protegido de proveedores/categorías referenciados. Las asignaciones de administradores y estados de proveedor las controla el superadministrador. Un usuario puede gestionar varios negocios, sin rol global que le otorgue acceso a otros.

Siguiente fase: Orden(cliente, proveedor, folio, estado, notas, fechas) y OrdenDetalle(producto, cantidad, precio histórico, subtotal). Un servicio transaccional agrupará por proveedor, validará precios/stock en servidor y manejará idempotencia. Antes de implementar se debe fijar cuándo se reserva/descuenta stock y cómo se repone al cancelar. Transiciones explícitas y controladas por actor. Notificaciones internas persistentes después de confirmar la transacción; correo opcional mediante adaptador, con estado de entrega y reintentos. Sin WhatsApp externo ni pagos.

Después: OpinionProducto y OpinionProveedor vinculadas al usuario y la orden completada; restricciones únicas por usuario/orden/producto y por usuario/orden/proveedor; estado de moderación e imágenes independientes. Verificación calculada a partir de la orden válida, nunca de un checkbox enviado por el cliente. Estadísticas agregadas mediante consultas, conservando por separado los comentarios generales heredados.

Membresías: PlanMembresia con límites y capacidades; MembresiaProveedor con vigencia y asignación manual. Comprobar límites transaccionalmente al crear productos/administradores. No facturar ni cobrar automáticamente. Más adelante panel de órdenes/opiniones/membresías, búsqueda, filtros y páginas públicas con slugs.

Separar apps sólo cuando los servicios de órdenes y reputación justifiquen límites claros. Mover modelos existentes requeriría migraciones de estado controladas conservando tablas, content types y permisos; no renombrar tablas por estética. Futuros servicios recibirán usuario y proveedor explícitos y reutilizarán las reglas de autorización.

## Archivos de fase 1

- Configuración: `OurEvents/settings.py`, `OurEvents/urls.py`, `.env.example`, `.gitignore`, dependencias y lock.
- Dominio: `servicios/models.py`, migraciones 0005–0007, `signals.py`, `apps.py`.
- Acceso y gestión: `permissions.py`, `forms.py`, `views.py`, `urls.py`, `admin.py`.
- Presentación mínima: `templates/gestion/*`, `templates/base.html`, `templates/catalogo.html`, `static/service-worker.js`.
- Calidad y operación: `tests.py`, `data_load.py`, `README.md`, este análisis.

## Límites y decisiones pendientes

No se creó interfaz final, registro autónomo, órdenes, membresías ni reputación verificada. Los comentarios generales siguen visibles como legado y requieren futura moderación. Antes de exposición pública conviene añadir límites de solicitudes de login/contacto/comentarios, política de retención y límites de almacenamiento de imágenes. SQLite es adecuado para esta fase; la concurrencia de inventario/órdenes deberá validarse específicamente o trasladarse a PostgreSQL. El saneamiento del historial y la rotación de secretos requieren coordinación con el titular.
