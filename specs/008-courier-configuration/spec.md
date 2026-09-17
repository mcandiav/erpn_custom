# Feature Specification: Courier Configuration multi-provider

**Feature Branch**: `[008-courier-configuration]`

**Created**: 2026-09-17

**Status**: Ready for planning / pendiente de revisión técnica y OK de Miguel

**Parent context**: `007-mcv-chile-desktop`, `despachos_transportistas.md`

## 0. Regla de trabajo para el Programador

Esta Spec corrige una decisión filosófica detectada después del cierre de Spec 007.

La Spec 007 queda histórica y no debe reescribirse para ocultar el diseño anterior.

Flujo obligatorio:

1. leer esta Spec, `README.md`, el código de Spec 007 y el estado real del sandbox;
2. inspeccionar cómo está implementado `Chilexpress Settings`, qué datos/credenciales existen y cómo Frappe 16 persiste Password fields;
3. presentar a Miguel el plan técnico concreto de migración y los archivos a crear/modificar;
4. esperar el OK explícito de Miguel;
5. solo después implementar.

No implementar llamadas reales a APIs de couriers en esta Spec.

## 1. Pifia filosófica detectada

Spec 007 implementó correctamente la organización general:

```text
MCV Chile
├── Pagos de Clientes
└── Courier
```

pero dejó el acceso de `Courier` acoplado directamente a un DocType específico:

```text
Courier
└── Chilexpress Settings
```

Eso contradice la arquitectura multi-courier ya definida para el proyecto.

El error no está en la carpeta `Courier` ni en el Desktop. El error está en el **modelo de configuración**, que quedó centrado en un proveedor en vez de representar el concepto general `Courier`.

## 2. Decisión filosófica congelada

La configuración operativa de couriers será genérica y multi-provider.

La estructura visible objetivo será:

```text
MCV Chile
├── Pagos de Clientes
└── Courier
    └── Configuración de Couriers
```

`Configuración de Couriers` será el único punto administrativo para registrar y administrar proveedores soportados.

No habrá un DocType Settings separado por courier como modelo definitivo.

## 3. Separación de responsabilidades

La arquitectura debe respetar estas cuatro capas:

### 3.1 Courier Provider

Representa **quién es el transportista**.

Ejemplos:

- Chilexpress
- Starken
- FAZT
- futuros proveedores

Debe ser dato maestro, no una lista hardcodeada en un campo Select.

Agregar o desactivar un proveedor comercial no debe requerir cambiar el esquema del DocType principal.

### 3.2 Courier Configuration

Representa **cómo usa FRAgallardo ese proveedor**.

Incluye como mínimo:

- provider;
- environment (`Test` / `Producción`);
- enabled;
- alias o nombre operativo si es necesario;
- cuenta/convenio/código de cliente cuando corresponda;
- credenciales requeridas por ese proveedor.

Debe permitir coexistencia de configuraciones Test y Producción para el mismo provider.

### 3.3 Endpoints (misma pantalla que credenciales)

Representa **dónde están los servicios externos** para ese provider + environment.

Los endpoints **no** viven en `.env` como contrato obligatorio de Spec 008. Quedan en `Courier Configuration`, en la misma child table de servicios, emparejados con su API key:

| Servicio | API Key (Password) | Endpoint URL (Data) |
|---|---|---|
| coverage_api_key | … | … |
| rating_api_key | … | … |
| shipping_api_key | … | … |

Reglas:

- contrato fijo de 3 roles (Cobertura / Cotización / Envío) para todos los couriers;
- al crear Configuration se precargan las 3 filas;
- courier con una sola API/URL → mismo secret y misma URL en las 3 filas (sin excepciones de esquema);
- URLs no son secretos; no van a Git ni a logs con valores de ambiente real en fixtures;
- adapters leen Desk (`Courier Configuration`), no variables de entorno, para resolver endpoint + key.

`.env.example` puede documentar nombres históricos como referencia, pero **no** es la fuente de verdad operativa.

### 3.4 Courier Adapter

Representa **cómo hablar con la API de cada courier**.

Los adapters sí son programables y específicos por proveedor porque cada API puede tener:

- autenticación diferente;
- headers distintos;
- payloads diferentes;
- nombres de variables propios;
- códigos/estados distintos;
- OT/OF/AWB u otras nomenclaturas;
- modelos de error diferentes;
- operaciones disponibles diferentes.

La arquitectura futura será:

```text
Shipment
   ↓
Courier contract común
   ├── ChilexpressAdapter
   ├── StarkenAdapter
   ├── FaztAdapter
   └── futuro adapter
```

Lo genérico es el contrato; no se intentará construir un adapter universal configurable que traslade lógica de programación a la base de datos.

## 4. Contrato común futuro de adapters

Esta Spec no implementa adapters reales, pero deja congelado el contrato conceptual para futuras Specs:

- `cotizar()`
- `crear_envio()`
- `obtener_etiqueta()`
- `consultar_tracking()`
- `cancelar_envio()` cuando el proveedor lo soporte
- `solicitar_retiro()` cuando el proveedor lo soporte

Agregar un courier nuevo puede requerir un nuevo adapter, pero no debe requerir modificar Ventas, Inventario, Pagos, Shipment central ni otros adapters.

## 5. Modelo de datos objetivo

### 5.1 `Courier Provider`

DocType maestro.

Campos mínimos esperados:

- `provider_name` o naming equivalente canónico;
- `provider_code` estable y técnico;
- `enabled` / disabled según convención Frappe;
- descripción opcional.

Reglas:

- `provider_code` debe ser único y estable;
- no eliminar físicamente proveedores que ya tengan historia operativa; preferir desactivar;
- seed inicial: Chilexpress;
- Starken y FAZT pueden existir como maestros inactivos o incorporarse cuando exista definición suficiente, según cierre el plan técnico.

### 5.2 `Courier Configuration`

DocType normal, NO Single.

Campos mínimos:

- `provider`: Link a `Courier Provider`;
- `environment`: Select exacto `Test` / `Producción`;
- `enabled`;
- `account_reference` / cuenta/convenio, si aplica;
- child table de credenciales o mecanismo genérico equivalente validado por Frappe 16.

Unicidad lógica mínima:

```text
provider + environment
```

salvo que el plan técnico demuestre necesidad real de múltiples cuentas simultáneas del mismo provider/ambiente. En ese caso la clave deberá incluir alias/cuenta y quedar explícitamente documentada antes de implementar.

### 5.3 Credenciales + Endpoints (misma child table)

Contrato estándar multi-courier (3 roles fijos, sin columnas nuevas por courier):

```text
Courier Credential (child)
├── credential_key   Select: coverage_api_key | rating_api_key | shipping_api_key
├── secret_value     Password (API key)
└── endpoint_url     Data (URL del servicio; no es secreto)
```

Al crear `Courier Configuration` se precargan las 3 filas.

Courier con una sola API/URL: mismo `secret_value` y misma `endpoint_url` en las 3 filas. Sin excepciones de esquema.

`secret_value` usa Password de Frappe 16. `endpoint_url` es Data editable en Desk.

## 6. Endpoints en Desk (no `.env` obligatorio)

Regla congelada (enmienda 2026-09-17):

```text
Adapter = cómo hablar
ERPNext = con qué provider/ambiente/credenciales/endpoints hablar
```

Test y Producción ya separan ambientes en `Courier Configuration`; cada registro tiene sus keys **y** sus URLs en la misma pantalla.

Los valores reales de URL:

- no se versionan en Git/fixtures;
- no se imprimen en logs de forma innecesaria;
- se editan en UI junto a las API keys.

`.env` / `.env.example` dejan de ser la fuente de verdad de endpoints de courier. El resolver futuro lee `Courier Configuration`.

## 7. Migración desde `Chilexpress Settings`

Estado heredado de Spec 007:

`Chilexpress Settings` es un Single DocType con al menos:

```text
environment
coverage_api_key
rating_api_key
shipping_api_key
```

La migración debe ser conservadora.

Orden obligatorio:

1. inspeccionar existencia y estado del DocType heredado;
2. crear el nuevo modelo genérico;
3. crear/asegurar `Courier Provider = Chilexpress`;
4. crear la correspondiente `Courier Configuration` para el ambiente heredado;
5. migrar las credenciales sin exponer sus valores;
6. comprobar que el destino puede recuperar los secretos de manera válida;
7. cambiar la navegación de `Courier` para apuntar a `Configuración de Couriers`;
8. dejar `Chilexpress Settings` fuera de navegación y marcado/declarado legado;
9. NO eliminar físicamente `Chilexpress Settings` en esta Spec salvo que Miguel lo autorice expresamente después de validar la migración.

No se debe borrar primero y migrar después.

## 8. Navegación final

La topología de Spec 007 se conserva:

```text
MCV Chile
├── Pagos de Clientes
└── Courier
```

Solo cambia el contenido del sidebar `Courier`:

```text
ANTES
Courier
└── Chilexpress Settings

DESPUÉS
Courier
└── Configuración de Couriers
```

No recrear ni renombrar innecesariamente `MCV Chile`, `Pagos de Clientes` o el icono `Courier` ya funcional.

## 9. Alcance incluido

- nuevo DocType maestro `Courier Provider`;
- nuevo DocType normal `Courier Configuration`;
- mecanismo genérico y seguro de credenciales por provider;
- seed/migración de Chilexpress;
- migración de `environment` y las tres credenciales existentes;
- `.env.example` con contrato de endpoints Chilexpress Test/Producción;
- cambio del sidebar `Courier` hacia la configuración genérica;
- preservación del DocType heredado hasta aceptación;
- tests de modelo, migración, unicidad, seguridad y navegación;
- patch nuevo, idempotente y versionado;
- documentación del estado legado de Spec 007.

## 10. Fuera de alcance

- llamadas HTTP reales a Chilexpress;
- implementar `ChilexpressAdapter` funcional;
- implementar StarkenAdapter;
- implementar FaztAdapter;
- cotizar envíos;
- crear OT/OF;
- generar etiquetas;
- tracking;
- selección automática de courier;
- cambiar Shipment/Delivery Note;
- borrar físicamente `Chilexpress Settings` sin aceptación posterior;
- guardar endpoints reales en Git/fixtures;
- crear un adapter universal basado en metadata dinámica.

## 11. Reglas de seguridad

- secretos nunca en Git;
- secretos nunca en `.env.example`;
- secretos nunca en logs de migración;
- tests usan valores ficticios;
- migración de Password fields debe usar APIs seguras de Frappe, no SQL plano con secreto desencriptado;
- no imprimir valores durante verificación;
- endpoints reales tampoco deben quedar hardcodeados en tests o fixtures si son ambiente-específicos;
- el patch debe ser idempotente.

## 12. User Stories & Acceptance Scenarios

### US1 - Configuración multi-courier (P1)

Como administrador quiero configurar couriers desde un modelo común para no crear un Settings DocType distinto por proveedor.

**Acceptance**:

1. Existe `Courier Provider`.
2. Existe `Courier Configuration` como DocType normal.
3. Una configuración referencia provider y environment.
4. Se puede tener Chilexpress/Test y Chilexpress/Producción como registros distintos.

### US2 - Migrar Chilexpress sin pérdida (P1)

Como administrador quiero conservar la configuración ya cargada de Chilexpress.

**Acceptance**:

1. El ambiente existente se conserva.
2. Las tres credenciales existentes quedan disponibles en el nuevo modelo.
3. Ningún valor secreto aparece en logs.
4. El DocType heredado no se elimina antes de validar el destino.

### US3 - Navegación coherente (P1)

Como configurador quiero entrar a Courier y administrar proveedores desde un único lugar.

**Acceptance**:

1. `MCV Chile -> Courier` sigue existiendo.
2. `Courier` muestra `Configuración de Couriers`.
3. Ya no muestra `Chilexpress Settings` como acceso principal.
4. Pagos de Clientes no cambia.

### US4 - Endpoints editables por ambiente (P1)

Como configurador quiero cargar la URL de cada servicio (Cobertura / Cotización / Envío) en la misma pantalla que la API key, sin editar adapters ni `.env`.

**Acceptance**:

1. Cada fila de servicio tiene `secret_value` y `endpoint_url`.
2. Test y Producción pueden tener URLs distintas en registros distintos.
3. No existen URLs de servicio Chilexpress hardcodeadas como contrato definitivo del adapter.
4. El futuro adapter resuelve endpoint desde `Courier Configuration`.

### US5 - Preparado para nuevos couriers (P2)

Como administrador quiero incorporar un nuevo provider sin cambiar el esquema de `Courier Configuration`.

**Acceptance**:

1. Provider es Link a maestro, no Select fijo.
2. Las credenciales/endpoints usan el contrato de 3 roles sin nuevas columnas específicas.
3. Un provider puede desactivarse sin borrarse.
4. Agregar soporte técnico de una nueva API queda limitado al futuro adapter.

## 13. Functional Requirements

- **FR-001**: MUST existir `Courier Provider` como DocType maestro.
- **FR-002**: `Courier Configuration.provider` MUST ser Link a `Courier Provider`.
- **FR-003**: `Courier Configuration` MUST ser DocType normal, no Single.
- **FR-004**: MUST soportar `Test` y `Producción` separadamente.
- **FR-005**: MUST permitir credenciales variables por provider sin columnas nuevas por courier.
- **FR-006**: secretos MUST usar mecanismo cifrado/Password de Frappe 16 validado.
- **FR-007**: endpoints MUST persistirse en `Courier Configuration` (campo `endpoint_url` por servicio), no como contrato obligatorio de `.env`.
- **FR-008**: la child table de servicios MUST incluir las 3 filas estándar con API key + endpoint emparejados.
- **FR-009**: la lógica del futuro adapter MUST resolver endpoint por provider + environment + servicio desde Desk.
- **FR-010**: Spec 008 MUST migrar la configuración heredada de Chilexpress.
- **FR-011**: MUST preservar `coverage_api_key`, `rating_api_key`, `shipping_api_key` durante migración.
- **FR-012**: migración MUST ser idempotente.
- **FR-013**: `Chilexpress Settings` MUST quedar fuera de navegación después de validar el nuevo modelo.
- **FR-014**: `Chilexpress Settings` MUST NOT eliminarse físicamente en esta Spec sin autorización explícita posterior.
- **FR-015**: sidebar `Courier` MUST enlazar a `Configuración de Couriers`.
- **FR-016**: topología `MCV Chile -> Pagos de Clientes + Courier` MUST conservarse.
- **FR-017**: MUST NOT modificar ERPNext/Frappe core.
- **FR-018**: MUST NOT implementar llamadas reales de courier.
- **FR-019**: Provider MUST poder desactivarse sin eliminación física.
- **FR-020**: agregar provider futuro MUST NOT requerir cambiar el esquema de `Courier Configuration`.
- **FR-021**: agregar API futura MAY requerir programar un nuevo adapter específico.
- **FR-022**: adapter universal dinámico queda explícitamente fuera de alcance.

## 14. Non-Functional Requirements

- **NFR-001 Safety**: migración primero copia/verifica, después cambia navegación.
- **NFR-002 Idempotency**: repetir patch no duplica providers/configuraciones/credenciales.
- **NFR-003 Auditability**: conflictos de migración deben reportarse sin exponer secretos.
- **NFR-004 Maintainability**: configuración genérica y adapters específicos.
- **NFR-005 Infrastructure separation**: endpoints separados del modelo ERP.
- **NFR-006 Backward compatibility**: Spec 007 Desktop y Pagos permanecen operativos.
- **NFR-007 Reversibility**: mientras el legado siga presente, rollback de navegación no debe requerir recuperar secretos desde cero.

## 15. Edge Cases obligatorios

- `Chilexpress Settings` no existe.
- existe pero environment vacío.
- alguna de las tres credenciales no está configurada.
- existen credenciales pero no se pueden recuperar con API Frappe segura.
- ya existe `Courier Provider = Chilexpress`.
- ya existe `Courier Configuration` para el mismo provider/environment.
- ejecución repetida del patch.
- sidebar Courier ya fue modificado manualmente.
- variables `.env` faltantes: configuración debe poder existir, pero futuras operaciones API deberán fallar de forma explícita; esta Spec no ejecuta API.
- provider desactivado con configuraciones históricas.
- intento de duplicar provider + environment.

## 16. Success Criteria

- **SC-001**: existe un único modelo genérico de configuración de couriers.
- **SC-002**: Chilexpress queda representado como provider/configuration y no como arquitectura especial.
- **SC-003**: sus credenciales se preservan.
- **SC-004**: sidebar Courier apunta a la configuración genérica.
- **SC-005**: `.env.example` documenta endpoints esperados por ambiente.
- **SC-006**: no se realizan llamadas externas en Spec 008.
- **SC-007**: Starken puede incorporarse posteriormente sin alterar el esquema de configuración.
- **SC-008**: implementar Starken sí puede requerir un adapter propio, sin tocar la lógica central.

## 17. Decisiones explícitamente NO abiertas

1. Spec 007 permanece cerrada e histórica.
2. La corrección se hace en Spec 008.
3. No habrá Starken Settings, FAZT Settings, etc. como modelo arquitectónico definitivo.
4. Courier Provider será maestro, no Select hardcodeado.
5. Courier Configuration será genérico y no Single.
6. Endpoints viven en Courier Configuration (misma pantalla que API keys), emparejados por servicio.
7. Credenciales viven en ERPNext con almacenamiento seguro.
8. Adapters son específicos por courier y programables.
9. No se construirá un adapter universal configurable.
10. MCV Chile -> Courier se conserva.
11. Spec 008 no consume ninguna API.
12. Contrato fijo de 3 roles: coverage / rating / shipping; courier de una sola API/URL repite el mismo valor en las 3 filas.
13. .env no es fuente de verdad de endpoints de courier.

## 18. Decisiones técnicas cerradas para el corte endpoints

- Password en child table (confirmado).
- Naming: credential_key, secret_value, endpoint_url.
- Unicidad provider + environment.
- Precarga de 3 filas default.
- Resolver futuro de endpoint desde Desk.

## 19. Orden esperado del corte endpoints

1. ajustar DocType Courier Credential con endpoint_url;
2. actualizar defaults/tests/resolver;
3. patch idempotente que asegure 3 filas con endpoint vacío;
4. tests;
5. deploy + migrate sandbox;
6. verificación UI (API + endpoint por fila);
7. aceptación Miguel;
8. cerrar Spec 008.
