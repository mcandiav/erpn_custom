# Feature Specification: MCV Chile Desktop

**Feature Branch**: `[007-mcv-chile-desktop]`

**Created**: 2026-09-17

**Status**: Implementada en código (`16.0.5`). Pendiente migrate sandbox + aceptación operativa.

**Parent context**: `004-pagos-clientes-mapeo-depositos`, `006-customer-multidocument-identity`

## 0. Regla de trabajo para el Programador

Esta Spec está activa, pero **NO autoriza a programar inmediatamente**.

Flujo obligatorio:

1. leer este `spec.md` y el código actual relacionado;
2. contrastar la especificación con el estado real del repositorio y del sandbox;
3. presentar a Miguel un plan técnico concreto de implementación, indicando archivos a crear/modificar, migración/patch y pruebas;
4. esperar el **OK explícito de Miguel**;
5. solo después implementar.

No reinterpretar otras Specs como trabajo activo. Esta Spec 007 cubre exclusivamente organización del Desktop/Workspace para funcionalidades MCV Chile.

## 1. Decisión de producto congelada

La entrada principal de escritorio para personalizaciones propias de Miguel debe llamarse:

```text
MCV Chile
```

`MCV` es la convención visual para identificar funcionalidades programadas/customizadas por Miguel.

La estructura final visible debe ser:

```text
MCV Chile
├── Pagos de Clientes
└── Courier
    └── Chilexpress Settings
```

Interpretación funcional:

- `MCV Chile` es la carpeta raíz de Desktop para personalizaciones chilenas propias de `erpn_custom`.
- `Pagos de Clientes` conserva su funcionalidad actual sin regresiones.
- `Courier` es el acceso de logística/transportistas.
- `Chilexpress Settings` es, por ahora, el único acceso dentro de `Courier`.
- Starken y FAZT quedan fuera de esta Spec; podrán agregarse posteriormente bajo `Courier`.

## 2. Problema que resuelve

El Desktop actual fue creado originalmente mediante el patch:

```text
erpn_custom/patches/v0_0_1_chile_desktop_icons.py
```

Ese patch crea:

```text
Chile
└── Pagos de Clientes
```

Durante la configuración manual de Chilexpress se creó además desde UI:

- un Workspace `MCV CHILE`, con título visible `MCV Chile`;
- un Desktop Icon `MCV CHILE` mediante `Añadir al Escritorio`.

Ese icono manual no quedó integrado correctamente a la estructura estándar del Desktop: es un Link no estándar, sin padre, mientras que `Chile` es actualmente una carpeta estándar de `erpn_custom` y `Pagos de Clientes` cuelga de ella.

El objetivo es normalizar todo mediante código versionado y dejar una única estructura reproducible.

## 3. Estado actual conocido

### 3.1 Desktop Icon `Chile`

Estado observado:

```text
label         = Chile
icon_type     = Folder
link_type     = Workspace Sidebar
parent_icon   = vacío
standard      = 1
app           = erpn_custom
idx           = 0
bg_color      = blue
```

### 3.2 Desktop Icon `Pagos de Clientes`

Estado observado:

```text
label         = Pagos de Clientes
icon_type     = Link
link_type     = Workspace Sidebar
link_to       = Pagos de Clientes
parent_icon   = Chile
standard      = 1
app           = erpn_custom
idx           = 1
```

### 3.3 Workspace Sidebar `Pagos de Clientes`

Ya existe y funciona. Debe conservarse.

Incluye actualmente accesos a:

- `Pagos de Clientes`;
- `Pagos de Clientes / Vinculador`;
- `Configuración del Vinculador`;
- `Historial de Vinculación`;
- `Historial de Intentos`.

La Spec 007 no redefine esa funcionalidad.

### 3.4 Artefactos manuales temporales

Durante la configuración UI se crearon:

```text
Workspace: MCV CHILE
Title:     MCV Chile
Module:    Chile
App:       erpn_custom
```

Y un Desktop Icon manual:

```text
label         = MCV CHILE
icon_type     = Link
link_type     = Workspace Sidebar
link_to       = MCV CHILE
parent_icon   = vacío
standard      = 0
idx           = 0
```

Estos artefactos no deben producir duplicados visibles después de Spec 007.

### 3.5 `Chilexpress Settings`

Ya existe como Single DocType del módulo `Chile` dentro de `erpn_custom`.

Campos actuales relevantes:

```text
environment
coverage_api_key
rating_api_key
shipping_api_key
```

Estado operativo actual: ambiente `Test` y credenciales de las tres APIs Chilexpress almacenadas en el site.

**La Spec 007 no debe borrar, recrear ni exponer esos valores.**

## 4. Objetivo

Reorganizar de forma versionada, repetible e idempotente el Desktop de `erpn_custom` para que la carpeta raíz visible sea `MCV Chile`, con `Pagos de Clientes` y `Courier` como hijos, y `Chilexpress Settings` accesible desde `Courier`.

La implementación debe sobrevivir a `bench migrate` y no depender de configuraciones manuales no versionadas.

## 5. Alcance incluido

- Crear/normalizar la carpeta Desktop raíz `MCV Chile`.
- Reparentar `Pagos de Clientes` desde `Chile` hacia `MCV Chile`.
- Crear un `Workspace Sidebar` llamado `Courier`.
- Crear un Desktop Icon `Courier` hijo de `MCV Chile`.
- Agregar `Chilexpress Settings` al sidebar `Courier`.
- Eliminar, reconvertir u ocultar de forma segura la antigua carpeta visible `Chile`, de modo que no quede duplicada en Desktop.
- Limpiar de forma segura el Desktop Icon manual `MCV CHILE` creado por UI, para que no exista un segundo acceso raíz con el mismo significado.
- Tratar el Workspace manual `MCV CHILE` como artefacto temporal de configuración: si está vacío y coincide con el creado en esta sesión, puede eliminarse; si contiene contenido inesperado, la implementación debe preservarlo y reportar la diferencia en vez de borrarlo silenciosamente.
- Registrar la migración como un patch nuevo de `erpn_custom`.
- Limpiar caches relevantes de Desktop/boot después de la migración.
- Añadir pruebas de regresión para la topología final.

## 6. Fuera de alcance

- Consumir APIs de Chilexpress.
- Probar endpoints Cobertura/Cotizador/Envíos.
- Implementar cotización de fletes.
- Crear envíos, etiquetas o tracking.
- Integrar Starken.
- Integrar FAZT.
- Cambiar datos de negocio de `Pagos de Clientes`.
- Cambiar lógica de matching bancario.
- Cambiar las credenciales almacenadas en `Chilexpress Settings`.
- Modificar ERPNext/Frappe core.
- Crear una nueva arquitectura general de módulos fuera de `erpn_custom`.

## 7. Diseño funcional esperado

### 7.1 Desktop raíz

Debe existir una única carpeta visible:

```text
MCV Chile
```

Propiedades funcionales:

- tipo: Folder;
- estándar/versionada por la app;
- app: `erpn_custom`;
- visible;
- sin parent icon;
- no debe depender del Workspace manual `MCV CHILE` para renderizarse.

### 7.2 Hijo `Pagos de Clientes`

Debe continuar siendo un Link a:

```text
Workspace Sidebar = Pagos de Clientes
```

Su único cambio funcional en esta Spec es:

```text
parent_icon: Chile -> MCV Chile
```

El contenido del sidebar existente se conserva.

### 7.3 Hijo `Courier`

Debe crearse como Link a:

```text
Workspace Sidebar = Courier
```

Debe quedar como hijo de `MCV Chile`.

### 7.4 Workspace Sidebar `Courier`

Debe pertenecer al módulo `Chile` y a la app `erpn_custom`.

Contenido mínimo v1:

```text
Chilexpress Settings
```

Tipo de enlace esperado:

```text
DocType -> Chilexpress Settings
```

Como `Chilexpress Settings` es Single, al seleccionar el enlace el usuario debe llegar al formulario único de configuración, no a una lista vacía.

## 8. Estrategia de patch requerida

La implementación debe usar **un patch nuevo**. Está prohibido modificar retrospectivamente `v0_0_1_chile_desktop_icons.py` como mecanismo principal de despliegue.

Nombre esperado salvo justificación técnica explícita en el plan:

```text
erpn_custom/patches/v0_0_7_mcv_chile_desktop.py
```

El patch debe registrarse en:

```text
erpn_custom/patches.txt
```

sección:

```text
[post_model_sync]
```

El patch debe poder ejecutarse sobre el estado actual del sandbox y también sobre una instalación que ya tenga ejecutado `v0_0_1_chile_desktop_icons`.

## 9. Reglas de migración e idempotencia

### 9.1 `Chile`

Si existe Desktop Icon `Chile` creado por `erpn_custom`:

- no dejarlo visible como segunda carpeta raíz al finalizar;
- reutilizar/reconvertir o sustituir de manera segura según cierre el plan técnico;
- actualizar todos los hijos relevantes antes de eliminarlo, si se elimina.

### 9.2 `Pagos de Clientes`

Si existe:

- conservar `link_to = Pagos de Clientes`;
- conservar `link_type = Workspace Sidebar`;
- conservar condición estándar/app;
- cambiar únicamente lo necesario para que el parent final sea `MCV Chile`.

Si no existe, el patch debe poder recrearlo con el contrato vigente sin fallar.

### 9.3 `MCV CHILE` manual

Si existe Desktop Icon manual `MCV CHILE`:

- no debe quedar como acceso raíz duplicado;
- debe limpiarse o normalizarse determinísticamente;
- no se permite terminar con `MCV Chile` y `MCV CHILE` como dos entradas distintas visibles.

### 9.4 Workspace manual `MCV CHILE`

Si existe y está vacío:

- puede eliminarse como artefacto temporal, si el plan técnico confirma que no se necesita para la estructura final.

Si contiene atajos, links, bloques u otro contenido no esperado:

- no borrarlo silenciosamente;
- preservar el contenido y reportar la anomalía para decisión humana.

### 9.5 `Courier`

El patch debe hacer upsert del Sidebar y Desktop Icon de `Courier`.

Ejecutar la lógica más de una vez no debe:

- duplicar items del sidebar;
- duplicar Desktop Icons;
- cambiar el orden de forma acumulativa;
- borrar settings o credenciales;
- producir errores si los registros ya existen.

## 10. Seguridad de credenciales

`coverage_api_key`, `rating_api_key` y `shipping_api_key` son secretos almacenados como Password fields.

La implementación MUST:

- no imprimirlos en logs;
- no leerlos para esta migración salvo que sea estrictamente necesario, lo que actualmente no lo es;
- no serializarlos en fixtures;
- no copiarlos a código;
- no recrear `Chilexpress Settings` de una forma que pierda los valores existentes;
- no incluir valores reales en tests.

Spec 007 solo agrega navegación hacia el DocType ya existente.

## 11. User Stories & Acceptance Scenarios

### User Story 1 - Acceso raíz MCV (P1)

Como administrador, quiero identificar claramente mis personalizaciones para no mezclarlas con módulos estándar de ERPNext.

**Acceptance Scenarios**:

1. **Given** el sandbox después de `bench migrate`, **When** abro Desktop, **Then** aparece `MCV Chile` como carpeta raíz visible.
2. **Given** la estructura final, **When** observo Desktop, **Then** no aparece otra carpeta raíz `Chile` que duplique el mismo contenido.
3. **Given** el Desktop Icon manual previo `MCV CHILE`, **When** finaliza la migración, **Then** no queda una segunda entrada raíz duplicada.

### User Story 2 - Pagos conserva operación (P1)

Como usuario de cobranza, quiero seguir entrando a Pagos de Clientes desde el nuevo contenedor sin perder funcionalidad.

**Acceptance Scenarios**:

1. **Given** `MCV Chile`, **When** lo abro, **Then** veo `Pagos de Clientes`.
2. **Given** `Pagos de Clientes`, **When** lo selecciono, **Then** abre el sidebar existente con sus accesos actuales.
3. **Given** historial/vinculador/configuración, **When** navego desde Pagos, **Then** los enlaces continúan funcionando igual que antes.

### User Story 3 - Acceso Courier (P1)

Como configurador, quiero tener un punto único de acceso para transportistas.

**Acceptance Scenarios**:

1. **Given** `MCV Chile`, **When** lo abro, **Then** veo `Courier`.
2. **Given** `Courier`, **When** lo selecciono, **Then** se abre su sidebar.
3. **Given** el sidebar `Courier`, **When** lo observo, **Then** contiene `Chilexpress Settings`.
4. **Given** `Chilexpress Settings`, **When** lo selecciono, **Then** abre el Single DocType configurado.

### User Story 4 - Migración segura (P1)

Como administrador, quiero que reorganizar el Desktop no altere datos ni secretos existentes.

**Acceptance Scenarios**:

1. **Given** credenciales Chilexpress ya almacenadas, **When** corre el patch, **Then** los Password fields conservan sus valores.
2. **Given** datos actuales de Pagos de Clientes, **When** corre el patch, **Then** no se modifica ningún dato bancario o de clientes.
3. **Given** patch ya aplicado, **When** su lógica se ejecuta nuevamente en prueba, **Then** la estructura final no genera duplicados.

## 12. Functional Requirements

- **FR-001**: Desktop MUST tener una carpeta raíz visible llamada `MCV Chile`.
- **FR-002**: La carpeta raíz MUST estar versionada desde `erpn_custom` y asociada a esa app.
- **FR-003**: `Pagos de Clientes` MUST ser hijo de `MCV Chile`.
- **FR-004**: `Pagos de Clientes` MUST seguir enlazando al `Workspace Sidebar` existente `Pagos de Clientes`.
- **FR-005**: Desktop MUST tener un hijo `Courier` bajo `MCV Chile`.
- **FR-006**: `Courier` MUST enlazar a un `Workspace Sidebar` llamado `Courier`.
- **FR-007**: El sidebar `Courier` MUST pertenecer al módulo `Chile` y app `erpn_custom`.
- **FR-008**: El sidebar `Courier` MUST contener un enlace a `Chilexpress Settings`.
- **FR-009**: Seleccionar `Chilexpress Settings` MUST abrir el Single DocType existente.
- **FR-010**: El antiguo Desktop Icon raíz `Chile` MUST NOT quedar visible como duplicado funcional después de la migración.
- **FR-011**: El Desktop Icon manual `MCV CHILE` MUST NOT quedar visible como duplicado de `MCV Chile`.
- **FR-012**: La implementación MUST usar un patch nuevo y MUST NOT depender de editar manualmente la base después del deploy.
- **FR-013**: El patch MUST ser idempotente a nivel de lógica/upsert.
- **FR-014**: El patch MUST limpiar caches necesarios para que la nueva estructura sea visible sin inconsistencia persistente.
- **FR-015**: La migración MUST NOT modificar datos de negocio de Pagos de Clientes.
- **FR-016**: La migración MUST NOT modificar ni perder valores Password de `Chilexpress Settings`.
- **FR-017**: La implementación MUST NOT modificar Frappe/ERPNext core.
- **FR-018**: Si el Workspace temporal `MCV CHILE` contiene contenido inesperado, MUST preservarse y reportarse en vez de borrarse silenciosamente.
- **FR-019**: La estructura final MUST ser reproducible mediante `bench --site <site> migrate` una vez desplegado el código.
- **FR-020**: El repositorio MUST incluir pruebas suficientes para validar topología de Desktop/Sidebar y ausencia de duplicados.

## 13. Non-Functional Requirements

- **NFR-001 Idempotency**: los helpers de upsert deben producir el mismo estado final ante ejecuciones repetidas.
- **NFR-002 Reproducibility**: una instalación equivalente debe obtener la misma estructura mediante migración, sin pasos UI posteriores.
- **NFR-003 Safety**: ninguna limpieza de artefactos manuales debe borrar contenido no esperado sin validación previa.
- **NFR-004 Maintainability**: el nuevo patch debe ser legible y reutilizar helpers existentes cuando tenga sentido, sin mezclar lógica de negocio de otras Specs.
- **NFR-005 Security**: ninguna credencial Chilexpress debe aparecer en logs, código, fixtures ni mensajes de test.
- **NFR-006 Backward compatibility**: los accesos operativos actuales de Pagos de Clientes deben seguir funcionando después de la reorganización.

## 14. Edge Cases obligatorios

- `Chile` existe y `MCV Chile` no existe.
- existen simultáneamente `Chile`, `MCV CHILE` manual y `Pagos de Clientes`.
- `Pagos de Clientes` no existe y debe recrearse.
- `Courier` ya existe por una ejecución previa.
- Sidebar `Courier` ya contiene `Chilexpress Settings`.
- Sidebar `Courier` contiene el mismo item duplicado por error histórico.
- Workspace `MCV CHILE` existe vacío.
- Workspace `MCV CHILE` contiene contenido inesperado.
- `Chilexpress Settings` existe y contiene Password values.
- patch ejecutado sobre un site donde no existe el Desktop Icon manual `MCV CHILE`.
- lógica del patch ejecutada dos veces.
- caches de Desktop contienen estructura anterior.

## 15. Success Criteria

- **SC-001**: en Desktop se ve una sola entrada raíz `MCV Chile` para estas personalizaciones.
- **SC-002**: dentro de `MCV Chile` se ven exactamente `Pagos de Clientes` y `Courier` como accesos funcionales de este alcance.
- **SC-003**: `Pagos de Clientes` conserva todos sus accesos actuales.
- **SC-004**: `Courier` permite llegar a `Chilexpress Settings`.
- **SC-005**: `Chile` ya no aparece como carpeta raíz duplicada.
- **SC-006**: `MCV CHILE` manual ya no aparece como acceso raíz duplicado.
- **SC-007**: las tres credenciales Chilexpress siguen almacenadas después del deploy.
- **SC-008**: ejecutar migración no requiere reconfiguración manual posterior del Desktop.
- **SC-009**: no hay cambios en datos de pagos, clientes o transacciones bancarias.

## 16. Decisiones explícitamente NO abiertas

El Programador no debe reinterpretar estas decisiones:

1. El nombre visible raíz es `MCV Chile`.
2. `MCV` identifica desarrollos propios de Miguel.
3. `Pagos de Clientes` queda bajo `MCV Chile`.
4. Debe existir `Courier` bajo `MCV Chile`.
5. `Chilexpress Settings` queda dentro de `Courier`.
6. Esta Spec NO implementa ninguna llamada API Chilexpress.
7. Se usa un patch nuevo; no se reescribe retrospectivamente el patch histórico como solución de despliegue.
8. No se modifica ERPNext/Frappe core.
9. Las credenciales Chilexpress existentes deben preservarse.

## 17. Decisiones técnicas que el Plan debe confirmar antes de implementar

El plan técnico debe confirmar, con inspección del código/site, al menos:

- si conviene renombrar/reutilizar el Desktop Icon `Chile` o crear `MCV Chile` y eliminar el antiguo después de reparentar;
- cómo tratar de forma segura el Desktop Icon manual `MCV CHILE` considerando diferencias de mayúsculas/minúsculas en `name`/`label`;
- si el Workspace manual `MCV CHILE` está efectivamente vacío antes de eliminarlo;
- método exacto para que el item `DocType -> Chilexpress Settings` abra correctamente el Single DocType en Frappe 16;
- caches exactos a invalidar (`desktop_icons`, `bootinfo` u otros si Frappe 16 lo requiere);
- pruebas automáticas apropiadas para `Desktop Icon` y `Workspace Sidebar`;
- orden/`idx` final sin depender de orden accidental de inserción.

Estas decisiones técnicas deben presentarse a Miguel en el plan previo. No iniciar implementación antes de su OK.

## 18. Orden esperado de implementación después del OK

1. inspeccionar estado real de `Desktop Icon`, `Workspace`, `Workspace Sidebar` y `Chilexpress Settings`;
2. crear tests de estado esperado/regresión;
3. crear `v0_0_7_mcv_chile_desktop.py`;
4. registrar patch en `patches.txt`;
5. normalizar `MCV Chile`, `Pagos de Clientes` y `Courier`;
6. limpiar artefactos antiguos/manuales de forma segura;
7. invalidar caches;
8. ejecutar tests;
9. desplegar a sandbox;
10. ejecutar `bench --site derp.at-once.cl migrate`;
11. validar visualmente Desktop y navegación;
12. confirmar que `Chilexpress Settings` conserva ambiente y credenciales;
13. solo entonces marcar Spec 007 como implementada/cerrada.
