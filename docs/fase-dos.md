# Fase 2: arquitectura y validación

Base: `codex/marketplace-phase-one`, commit `210e934`. Rama de trabajo: `codex/marketplace-phase-two`.

## Separación de responsabilidades

- Dominio: entidades existentes, nuevos agregados y restricciones de persistencia. Mapa puro de transiciones en `domain/orders.py`.
- Aplicación: `orders.py`, `reviews.py`, `memberships.py`, `notifications.py`, `catalog.py`. Los servicios validan actores y operan transaccionalmente.
- Infraestructura: carrito con sesión Django, email posterior al commit y ORM/SQLite. Sin dependencias de pagos o mensajería externas.
- Presentación: formularios, vistas pequeñas, consultas separadas, templates con componentes comunes y tokens CSS.

Se mantiene una sola app para no alterar tablas, permisos o migraciones de fase 1. Los límites de módulo permiten separar apps más adelante si lo exige el crecimiento. No se cambió el modelo de usuario.

## Decisiones

La orden conserva precio y nombre históricos. Su existencia no promete inventario hasta aceptación. Cancelación por comprador antes de reserva y por proveedor hasta ATENDIDA; estados terminales no se reabren. La cancelación posterior a reserva devuelve stock una vez. Django Admin no permite editar estados directamente.

La clave idempotente pertenece a un grupo de la solicitud y se invalida al cambiar el carrito. Precio promocional resuelto en servidor. Las operaciones de inventario evitan lecturas y escrituras perdidas con condiciones SQL y snapshots en formularios.

El email es un efecto secundario posterior al commit y puede fallar sin afectar la orden. No se añadió un sistema de reintentos durables; las notificaciones internas preservan el evento para el usuario.

Membresía vencida vuelve a límites gratuitos, sin eliminación de datos. Las promociones existentes necesitan ajuste al editar un producto sin un plan que las permita. El plan controla nuevas promociones, productos y administradores; las estadísticas avanzadas sólo tienen la capacidad preparada.

## Evidencia funcional

- Base local migrada a 0008 con respaldo previo; originales conservados.
- Seed ejecutado dos veces, sin duplicados; prueba adicional automatizada de idempotencia y bloqueo en producción.
- Flujo HTTP automatizado: login de comprador, búsqueda, ficha, carrito de dos productos, orden, proveedor, aceptación, procesamiento, atención, finalización, opiniones y consultas de admin.
- Flujo adicional en navegador: orden `OE-3D741C4D5C2C4D8D`, dos productos de Pan de Barrio, subtotal 173.00. Ambos stocks pasaron de 29 a 28 al aceptar, permanecieron en 28 al completar. Opiniones de proveedor y producto publicadas con verificación derivada de esa orden. La ficha pasó a mostrar dos opiniones.
- Portada y ficha revisadas en móvil; se corrigieron mínimos de columnas y controles que provocaban desbordamiento a 375 px. Tablas de inventario/órdenes tienen contenedores de desplazamiento horizontal.
- Sin recursos visuales remotos necesarios: SVGs de identidad y placeholders PNG locales.

## Alcance y operación

El código y los datos demo no son un despliegue de producción. SMTP real, revisión externa de accesibilidad, carga de alto volumen, almacenamiento de imágenes y recuperación operativa deben verificarse con la infraestructura final. La concurrencia cubierta utiliza SQLite local; repetir pruebas al cambiar de motor. Las credenciales históricas del repositorio deben revocarse aunque ya no estén en los archivos actuales.

## Resultado final de verificaciones

38 pruebas aprobadas; `makemigrations`, `migrate`, `check`, `makemigrations --check --dry-run` y `pip check` correctos. Todas las pantallas de gestión se comprobaron con respuesta HTTP 200 y el 404 de producción con respuesta 404 y template propio.

| Ancho solicitado | Ancho útil (sin scrollbar) | Contenido de portada |
|---:|---:|---:|
| 320 | 305 | 305 |
| 375 | 360 | 360 |
| 768 | 753 | 753 |
| 1024 | 1009 | 1009 |
| 1440 | 1425 | 1425 |

Sin imágenes rotas en portada. Catálogo revisado visualmente a 375 y 1440 px y ficha a 320 px. La navegación secundaria y las tablas permiten desplazamiento dentro de su propio contenedor en móvil.
