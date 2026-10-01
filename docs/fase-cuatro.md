# Validación de fase 4

Base: a9aa515. Rama: codex/marketplace-phase-four.

## Automática

80 pruebas: las 58 existentes y 22 casos de cuenta/administración. Las pruebas anteriores de alta ahora preparan explícitamente un comprador con correo verificado, conforme a la nueva precondición. Se prueba también que el servicio rechaza solicitudes sin verificación.

Cobertura nueva: menú y centro de cuenta, logout exclusivo por POST, CSRF, cambio de contraseña y continuidad de sesión, recuperación con respuesta genérica y tokens de un uso/vencidos, verificación y reenvío limitado, invalidación al cambiar y restaurar correo, perfil aislado, invitación administrativa sin contraseña en claro ni elevación, activación/desactivación y último responsable, preferencias de email con avisos internos obligatorios, planes con impacto confirmado, condiciones históricas, filtros de membresía, múltiples tiendas, selector, checklist y permisos backend.

Comandos: `makemigrations`, `migrate`, `check`, `makemigrations --check --dry-run`, `test`, `pip check` y `seed_demo`. No se requieren nuevas dependencias.

## Navegador local

Servidor en 127.0.0.1:8010, datos demo locales:

- Comprador: acceso, Mi cuenta, guardar teléfono de prueba, estado de correo, Seguridad, logout con mensaje en Home y solicitud de recuperación con confirmación genérica. El establecimiento final de contraseña y su reutilización se cubren en pruebas HTTP con cuentas aisladas; no se cambiaron las contraseñas demo.
- Administrador: panel propio; alta de `validacion_fase4` mediante enlace; detalle, desactivar, reactivar y auditoría; crear `VALIDACION FASE 4`, editar duración de 45 a 60 días y asignar a Taller Tierra conservando el contrato anterior.
- Proveedor: acceso como proveedor1, tres tiendas visibles, seleccionar Pan de Barrio y cambiar a Taller Tierra con el selector; contexto, checklist calculado (67%), inventario y navegación propios.
- Visual: menú desplegable revisado en escritorio, 375 px y 320 px. Se corrigió el anclaje móvil para evitar recorte por el margen izquierdo. A 320 px los bordes del menú quedan dentro de la ventana. Escape, cierre al hacer clic fuera y navegación por teclado conservan controles HTML nativos.

## Límites operativos

No es un despliegue a producción. Configurar SMTP/HTTPS y respaldo para el entorno real. En desarrollo los correos aparecen en consola. La entrega de correo es best-effort, sin cola ni reintento durable. El límite de dos minutos por cuenta cubre reenvíos de recuperación/verificación; un control global por IP contra abuso de registro queda como operación futura. No hay pagos.
