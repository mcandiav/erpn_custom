# Feature Specification: Customer - Identidad multidocumento internacional

**Feature Branch**: `[006-customer-multidocument-identity]`

**Created**: 2026-09-17

**Status**: Closed / implementada y aceptada en sandbox (2026-09-17)

**Parent context**: `001-fragallardo-erpnext-foundation`, `003-fragallardo-mvp-operativo`, `004-pagos-clientes-mapeo-depositos`, `005-banco-chile-tiempo-real`

## 1. Decisión de negocio congelada

A partir de esta especificación, `Customer.tax_id` deja de significar exclusivamente **RUT chileno** y pasa a ser el **campo canónico de ERPNext para almacenar el número de identificación del Customer**, independientemente del tipo de documento.

`Customer.tax_id` podrá contener inicialmente uno de estos cuatro tipos de identificación:

- `RUT`
- `DNI`
- `CPF`
- `Passport`

No se debe crear un segundo campo custom que duplique el número de identificación del Customer. El número vive en `Customer.tax_id`; un campo custom adicional indicará qué clase de documento contiene `tax_id`.

La regla conceptual queda congelada como:

```text
Customer identity = document_type + issuing_country + tax_id
```

Para los documentos cuyo país está implícito por definición en este alcance inicial:

```text
RUT -> Chile
CPF -> Brasil
```

Para `DNI` y `Passport`, el país emisor debe conservarse explícitamente porque el mismo tipo y el mismo número pueden existir en jurisdicciones diferentes.

`Customer.country`, direcciones y residencia comercial NO sustituyen al país emisor del documento. Una persona puede residir en un país y portar un documento emitido por otro.

## 2. Problema que resuelve

La configuración vigente de FRAgallardo usa el campo estándar `Customer.tax_id` con etiqueta visible `RUT`, marcado como único, y un Server Script activo `Validar y normalizar RUT Cliente` que ejecuta validación chilena por módulo 11 sobre cualquier valor ingresado.

Ese diseño impide registrar correctamente Customers extranjeros cuyo identificador sea DNI, CPF o Passport porque todo valor de `tax_id` es interpretado como RUT chileno.

Además, las Specs bancarias `003`, `004` y `005` ya utilizan `Customer.tax_id` para matching exacto de RUT contra depósitos de Banco de Chile. La solución multidocumento debe ampliar el modelo de identidad sin romper ese comportamiento chileno ya implementado o especificado.

## 3. Objetivo

Permitir que `Customer` represente clientes chilenos y extranjeros con una identidad documental explícita, validable y no ambigua, manteniendo `Customer.tax_id` como dato maestro del número de documento y preservando la compatibilidad del matching bancario chileno por RUT.

La implementación debe ser reproducible desde `erpn_custom`, sin depender de personalizaciones manuales no versionadas y sin modificar ERPNext/Frappe core.

## 4. Principios arquitectónicos

### 4.1 Un solo campo canónico para el número

`Customer.tax_id` es la única fuente maestra del número de identificación del Customer.

Está prohibido introducir campos como:

- `custom_rut`
- `custom_dni`
- `custom_cpf`
- `custom_passport_number`
- `custom_document_number`

si su propósito es almacenar una segunda copia del mismo identificador primario.

### 4.2 El tipo determina la semántica y validación

El valor de `tax_id` por sí solo no determina el algoritmo de validación. La semántica la define `custom_tax_id_type`.

Ejemplo:

```text
custom_tax_id_type = RUT
tax_id = 13698154-4
```

es distinto conceptualmente de:

```text
custom_tax_id_type = DNI
tax_id = 13698154
```

### 4.3 País emisor separado de residencia

Se incorpora `custom_tax_id_country` como país emisor/jurisdicción del documento.

No se debe inferir identidad documental desde:

- `Customer.country`;
- Territory;
- dirección principal;
- país de facturación;
- nacionalidad inferida por nombre, teléfono o email.

### 4.4 Validación determinística, nunca heurística

La capa de identidad no debe decidir el tipo de documento por apariencia del número. El usuario o proceso creador declara el tipo; la aplicación valida de acuerdo con ese tipo y país.

### 4.5 Compatibilidad bancaria chilena explícita

El matching de depósitos por RUT solo debe considerar Customers cuya identidad declare:

```text
custom_tax_id_type = RUT
custom_tax_id_country = Chile
```

Un DNI, CPF o Passport que por casualidad normalice visualmente a una cadena similar nunca debe entrar al índice de RUT de Banco de Chile.

## 5. Alcance

### 5.1 Incluido

- Mantener `Customer.tax_id` como número de identificación canónico.
- Agregar un campo versionado `custom_tax_id_type` al DocType `Customer`.
- Agregar un campo versionado `custom_tax_id_country` al DocType `Customer`.
- Opciones iniciales exactas de `custom_tax_id_type`: `RUT`, `DNI`, `CPF`, `Passport`.
- Valor predeterminado para nuevos Customers del negocio FRAgallardo: `RUT`.
- País emisor predeterminado/inferido para `RUT`: `Chile`.
- País emisor predeterminado/inferido para `CPF`: `Brazil`/valor canónico de Country existente en ERPNext para Brasil.
- Para `DNI` y `Passport`, exigir país emisor explícito antes de aceptar una identidad completa.
- Cambiar la etiqueta visible de `Customer.tax_id` desde `RUT` a `Número de documento / Tax ID` o equivalente inequívoco aprobado en diseño UI.
- Mantener `tax_id` disponible en filtros y Quick Entry.
- Mostrar tipo, país emisor y número juntos en el formulario y Quick Entry.
- Reemplazar la validación global de RUT por una validación condicional por tipo.
- Reutilizar `erpn_custom.chile.rut.normalize_chilean_tax_id()` para identidades tipo RUT en vez de duplicar algoritmo.
- Definir normalización específica por tipo.
- Reemplazar la unicidad global actual de `tax_id` por una regla de identidad compuesta.
- Migrar Customers existentes sin perder `tax_id`.
- Desactivar de forma versionada el Server Script legado `Validar y normalizar RUT Cliente` cuando la nueva validación de app entre en vigor.
- Adaptar el matching bancario de Specs 003/004/005 para indexar exclusivamente identidades RUT.
- Pruebas unitarias y de integración para los cuatro tipos.
- Pruebas de migración y regresión del matching Banco de Chile.

### 5.2 Fuera de alcance inicial

- Almacenar múltiples documentos simultáneos para un mismo Customer.
- Historial de documentos vencidos o reemplazados.
- OCR de pasaportes/documentos.
- Consulta a registros civiles o APIs gubernamentales.
- Verificación biométrica.
- Validación online de vigencia de pasaporte.
- Deducir nacionalidad o residencia desde el documento.
- Introducir `Otro` como tipo genérico; cualquier nuevo tipo debe agregarse conscientemente a la lista y su contrato de normalización.
- Cambiar la evidencia bancaria `custom_rut_del_pagador` de Banco de Chile: ese campo sigue representando literalmente RUT del pagador cuando el banco lo informa.
- Modificar ERPNext/Frappe core.

## 6. Modelo funcional de identidad

### 6.1 Campos

#### `Customer.custom_tax_id_type`

- Tipo Frappe previsto: `Select`.
- Etiqueta: `Tipo de documento`.
- Opciones iniciales, exactamente:
  - `RUT`
  - `DNI`
  - `CPF`
  - `Passport`
- Para nuevos Customers: obligatorio.
- Default de FRAgallardo: `RUT`.
- Debe estar disponible en Quick Entry y filtros.

#### `Customer.custom_tax_id_country`

- Tipo Frappe previsto: `Link` a `Country`.
- Etiqueta: `País emisor del documento`.
- Para `RUT`: valor canónico Chile y no debe terminar guardado con otro país.
- Para `CPF`: valor canónico Brasil y no debe terminar guardado con otro país.
- Para `DNI`: obligatorio y elegido explícitamente.
- Para `Passport`: obligatorio y elegido explícitamente.
- Debe estar disponible en Quick Entry y filtros.

#### `Customer.tax_id`

- Campo estándar ERPNext existente.
- No se reemplaza ni duplica.
- Nueva etiqueta visible: `Número de documento / Tax ID`.
- Contiene el identificador normalizado conforme a su tipo.
- Para nuevos Customers: obligatorio una vez elegido un tipo de documento.
- Continúa disponible en Quick Entry y filtros.
- Ya no puede conservar unicidad global independiente del tipo/país.

### 6.2 Clave lógica de unicidad

La identidad lógica de una persona/entidad en este alcance es:

```text
(custom_tax_id_type, custom_tax_id_country, tax_id_normalizado)
```

Dos Customers activos o inactivos no deben poder compartir exactamente esa misma identidad documental, salvo una migración controlada que detecte duplicados históricos y los deje reportados para resolución antes de habilitar la restricción.

La unicidad debe incluir también Customers deshabilitados para impedir que deshabilitar un registro permita crear un duplicado silencioso del mismo documento.

### 6.3 Razón de incluir país emisor

La combinación solo `tipo + número` no es suficientemente robusta para `DNI` y `Passport`. La misma secuencia puede existir bajo emisores diferentes. Por eso `custom_tax_id_country` forma parte de la identidad lógica aunque el Customer resida en otro lugar.

## 7. Reglas de normalización y validación v1

### 7.1 RUT

Entrada aceptable:

- con o sin puntos;
- con o sin guion;
- espacios accidentales;
- `K` en mayúscula o minúscula.

Persistencia canónica:

```text
12345678-9
12345678-K
```

Reglas:

- cuerpo numérico;
- DV `0-9` o `K`;
- validación módulo 11;
- país emisor forzado a Chile;
- reutilizar `normalize_chilean_tax_id()` como función canónica.

Un RUT inválido debe impedir guardar el Customer con un mensaje claro.

### 7.2 CPF

La arquitectura debe disponer de normalizador/validador específico CPF separado del código RUT.

Persistencia canónica prevista:

```text
solo dígitos, 11 caracteres
```

El diseño/plan técnico debe confirmar el algoritmo oficial que se implementará y sus casos inválidos antes de codificar. No se debe aceptar un CPF como si fuera un RUT ni viceversa.

País emisor: Brasil.

### 7.3 DNI

`DNI` es un nombre de documento usado por más de una jurisdicción; por eso el país emisor es obligatorio.

Regla v1:

- no aplicar algoritmo chileno;
- no aplicar algoritmo CPF;
- normalización y restricciones adicionales se seleccionan por país cuando exista una regla documentada;
- si no existe validador específico para el país, se aplica la regla genérica no destructiva: trim de extremos, rechazo de vacío y límite de longitud seguro definido en diseño técnico;
- no eliminar ceros iniciales;
- no convertir el valor a entero.

Agregar una validación país-específica futura no debe exigir cambiar el modelo de datos.

### 7.4 Passport

Regla v1:

- país emisor obligatorio;
- trim de extremos;
- preservar información significativa del número;
- no convertir a entero;
- no aplicar módulo 11 chileno ni reglas CPF;
- normalización de mayúsculas solo si el análisis técnico confirma que no destruye semántica para los países soportados;
- no inventar una longitud universal de pasaporte.

La especificación prohíbe una regex global excesivamente restrictiva para todos los pasaportes.

## 8. Reglas de creación y edición

### 8.1 Nuevo Customer chileno

Flujo esperado:

1. `Tipo de documento = RUT` por default.
2. `País emisor = Chile` automáticamente.
3. usuario ingresa RUT en `tax_id`.
4. sistema normaliza y valida.
5. sistema comprueba unicidad compuesta.
6. Customer se guarda con RUT canónico.

### 8.2 Nuevo Customer extranjero con DNI

1. usuario cambia tipo a `DNI`.
2. sistema deja de ejecutar validación RUT.
3. usuario selecciona país emisor.
4. usuario ingresa el número en `tax_id`.
5. sistema aplica normalización/validación definida para ese país o regla genérica v1.
6. sistema comprueba unicidad compuesta.

### 8.3 Nuevo Customer brasileño con CPF

1. usuario cambia tipo a `CPF`.
2. país emisor queda Brasil.
3. usuario ingresa CPF en `tax_id`.
4. se aplica normalizador/validador CPF.
5. se valida unicidad compuesta.

### 8.4 Nuevo Customer con Passport

1. usuario elige `Passport`.
2. país emisor se vuelve obligatorio.
3. número se almacena en `tax_id`.
4. no se aplica validación RUT/CPF.
5. se aplica normalización segura de Passport definida por el contrato.
6. se valida unicidad compuesta.

### 8.5 Cambio de tipo sobre un Customer existente

Cambiar `custom_tax_id_type` o `custom_tax_id_country` debe provocar revalidación completa del `tax_id` actual.

El sistema no debe reinterpretar silenciosamente un RUT existente como DNI, CPF o Passport.

Si el valor actual no es válido bajo la nueva combinación tipo/país, el guardado debe rechazarse hasta que el usuario ingrese una identidad válida.

Toda edición debe volver a verificar unicidad.

## 9. Migración de datos existentes

### 9.1 Precondición observada

El sandbox posee actualmente un Server Script activo `Validar y normalizar RUT Cliente` que fuerza todo `Customer.tax_id` no vacío a formato RUT válido. La configuración documentada indica además que `tax_id` está hoy etiquetado `RUT` y configurado como único.

### 9.2 Regla de backfill

Para cada Customer existente:

1. si `tax_id` está vacío:
   - no inventar número;
   - no abortar la migración;
   - dejar el registro como legado incompleto según la política técnica definida en `data-model.md`;
2. si `tax_id` no está vacío y `normalize_chilean_tax_id(tax_id)` devuelve valor válido:
   - `custom_tax_id_type = RUT`;
   - `custom_tax_id_country = Chile`;
   - `tax_id = valor RUT canónico`;
3. si `tax_id` no está vacío pero no valida como RUT:
   - no inferir DNI/CPF/Passport;
   - registrar el Customer como conflicto de migración;
   - la migración no debe recategorizarlo silenciosamente.

### 9.3 Duplicados históricos

Antes de retirar la unicidad global de `tax_id` y activar la nueva restricción compuesta:

- ejecutar un diagnóstico de duplicados sobre la identidad normalizada;
- si existen duplicados, producir un reporte con Customer names afectados;
- no fusionar Customers automáticamente;
- no elegir un ganador por fecha o actividad;
- resolver o aislar la inconsistencia antes de declarar migración completa.

### 9.4 Server Script legado

Una vez que la validación de `erpn_custom` esté instalada y probada:

- el Server Script `Validar y normalizar RUT Cliente` debe quedar desactivado de forma reproducible mediante patch/migración de la app;
- no deben quedar dos validadores independientes modificando `tax_id` en el mismo evento;
- en una instalación nueva donde el script no exista, el patch debe ser idempotente y no fallar.

El script puede conservarse deshabilitado como evidencia histórica; eliminarlo físicamente no es requisito.

## 10. Compatibilidad con depósitos y Specs existentes

### 10.1 Spec 004 - matching exacto de depósitos

Actualmente el motor construye un índice a partir de `Customer.tax_id` normalizado como RUT.

Después de Spec 006, la consulta/indexación debe filtrar Customers elegibles:

```text
custom_tax_id_type = RUT
custom_tax_id_country = Chile
```

Luego normaliza `tax_id` con `normalize_chilean_tax_id()`.

Customers DNI/CPF/Passport quedan fuera de ese índice aunque su cadena contenga números compatibles visualmente.

### 10.2 Evidencia bancaria

`Bank Transaction.custom_rut_del_pagador` continúa siendo RUT del pagador porque esa semántica proviene de Banco de Chile.

No debe renombrarse a `tax_id` genérico como consecuencia de esta Spec.

### 10.3 Pagador tercero

La regla ya establecida se mantiene:

```text
pagador bancario != necesariamente Customer beneficiario
```

Spec 006 solo define identidad del Customer; no reemplaza la asignación manual o futura tabla payer-beneficiary de Spec 004.

### 10.4 Spec 005 Banco de Chile tiempo real

Cualquier matching en tiempo real debe reutilizar exactamente el mismo selector de Customers RUT de Spec 004/006. Está prohibido crear una segunda regla paralela que ignore `custom_tax_id_type`.

## 11. User Scenarios & Testing

### User Story 1 - Cliente chileno conserva funcionamiento actual (P1)

Como usuario comercial, quiero crear un Customer con RUT y que siga validándose exactamente como identidad chilena para no perder el comportamiento actual.

**Acceptance Scenarios**:

1. **Given** tipo `RUT`, **When** ingreso `13.698.154-4`, **Then** se persiste `13698154-4` y país Chile.
2. **Given** tipo `RUT`, **When** ingreso un DV incorrecto, **Then** el sistema rechaza el guardado.
3. **Given** un RUT ya asignado a otro Customer, **When** intento registrar la misma identidad, **Then** el sistema rechaza el duplicado e identifica el conflicto.

### User Story 2 - Cliente extranjero con DNI (P1)

Como vendedor, quiero registrar un extranjero con DNI sin que ERPNext intente validarlo como RUT chileno.

**Acceptance Scenarios**:

1. **Given** tipo `DNI` y país emisor informado, **When** ingreso un número válido conforme al contrato aplicable, **Then** se guarda en `tax_id` sin ejecutar módulo 11 chileno.
2. **Given** tipo `DNI` sin país emisor, **When** guardo, **Then** se rechaza por identidad incompleta.
3. **Given** DNI con cero inicial, **When** guardo, **Then** el cero no se elimina por conversión numérica.

### User Story 3 - Cliente brasileño con CPF (P1)

Como vendedor, quiero registrar un Customer con CPF y conservarlo separado semánticamente de RUT y DNI.

**Acceptance Scenarios**:

1. **Given** tipo `CPF`, **When** ingreso el número, **Then** país emisor queda Brasil y nunca Chile.
2. **Given** CPF inválido según algoritmo aprobado, **When** guardo, **Then** se rechaza.
3. **Given** un CPF ya registrado, **When** intento duplicarlo bajo CPF/Brasil, **Then** se rechaza por identidad duplicada.

### User Story 4 - Cliente con Passport (P1)

Como vendedor, quiero registrar un pasaporte extranjero sin aplicar reglas tributarias chilenas.

**Acceptance Scenarios**:

1. **Given** tipo `Passport`, país emisor y número, **When** guardo, **Then** el número queda en `Customer.tax_id` y no se ejecuta módulo 11.
2. **Given** Passport sin país emisor, **When** guardo, **Then** se rechaza.
3. **Given** mismo número de Passport emitido por dos países distintos, **When** ambas identidades cumplen sus reglas, **Then** la unicidad compuesta no las trata automáticamente como la misma identidad.

### User Story 5 - Migrar clientes actuales sin pérdida (P1)

Como administrador, quiero desplegar la mejora sobre el ERP existente sin tener que reingresar los RUT actuales.

**Acceptance Scenarios**:

1. **Given** Customer existente con RUT válido, **When** corre el patch, **Then** conserva `tax_id`, recibe tipo RUT y país Chile.
2. **Given** Customer legado sin `tax_id`, **When** corre el patch, **Then** no se inventa documento ni se elimina el Customer.
3. **Given** un valor no clasificable como RUT, **When** corre migración, **Then** queda reportado y no se infiere otro tipo.

### User Story 6 - Matching bancario no sufre regresión (P1)

Como responsable de Cobranza, quiero que los depósitos chilenos continúen mapeándose por RUT y que un documento extranjero jamás genere una coincidencia falsa.

**Acceptance Scenarios**:

1. **Given** depósito con RUT exacto y Customer tipo RUT/Chile, **When** corre el mapeo, **Then** se conserva la coincidencia exacta de Spec 004.
2. **Given** Customer tipo DNI cuyo `tax_id` es numéricamente parecido al RUT del depósito, **When** corre el mapeo, **Then** ese Customer no entra como candidato RUT.
3. **Given** Customer CPF o Passport, **When** corre el matching Banco de Chile, **Then** queda excluido del índice RUT.

## 12. Functional Requirements

- **FR-001**: `Customer.tax_id` MUST seguir siendo el campo canónico donde se persiste el número de documento.
- **FR-002**: La solución MUST NOT crear un segundo campo primario de número documental.
- **FR-003**: `Customer` MUST disponer de `custom_tax_id_type` versionado desde `erpn_custom`.
- **FR-004**: Las opciones iniciales MUST ser exactamente `RUT`, `DNI`, `CPF`, `Passport`.
- **FR-005**: `Customer` MUST disponer de `custom_tax_id_country` Link a Country.
- **FR-006**: Para nuevos Customers, tipo y número MUST ser obligatorios; país MUST quedar resuelto conforme al tipo.
- **FR-007**: RUT MUST forzar país Chile.
- **FR-008**: CPF MUST forzar país Brasil.
- **FR-009**: DNI MUST exigir país emisor explícito salvo que una futura regla país-específica establezca un default inequívoco.
- **FR-010**: Passport MUST exigir país emisor explícito.
- **FR-011**: RUT MUST normalizarse y validarse mediante la función canónica compartida de `erpn_custom`.
- **FR-012**: La validación módulo 11 chilena MUST ejecutarse únicamente cuando el tipo sea RUT.
- **FR-013**: Un DNI, CPF o Passport MUST NOT pasar por el validador de RUT.
- **FR-014**: CPF MUST tener su propio normalizador/validador antes de declararse soporte completo de CPF.
- **FR-015**: DNI MUST conservar ceros iniciales y tratarse como texto.
- **FR-016**: Passport MUST tratarse como texto y no usar una regex universal destructiva.
- **FR-017**: `tax_id` MUST dejar de tener unicidad global aislada si esa propiedad está activa en el site.
- **FR-018**: La aplicación MUST garantizar unicidad lógica por `tipo + país emisor + número normalizado`.
- **FR-019**: La unicidad MUST considerar Customers deshabilitados.
- **FR-020**: Cambiar tipo o país MUST revalidar el `tax_id` existente antes de guardar.
- **FR-021**: La UI MUST mostrar Tipo, País emisor y Número como un conjunto comprensible en Customer y Quick Entry.
- **FR-022**: La etiqueta visible de `tax_id` MUST dejar de ser exclusivamente `RUT`.
- **FR-023**: La migración MUST clasificar RUT existentes válidos como RUT/Chile sin cambiar su identidad.
- **FR-024**: La migración MUST NOT inventar tipo extranjero a partir de valores no reconocidos.
- **FR-025**: La migración MUST NOT inventar `tax_id` para Customers que no lo tengan.
- **FR-026**: El Server Script legado `Validar y normalizar RUT Cliente` MUST quedar desactivado cuando la validación versionada de app esté activa.
- **FR-027**: El patch que desactiva el Server Script MUST ser idempotente y tolerar que el script no exista.
- **FR-028**: Matching Banco de Chile MUST considerar únicamente Customers RUT/Chile.
- **FR-029**: `Bank Transaction.custom_rut_del_pagador` MUST conservar su semántica de evidencia RUT chilena.
- **FR-030**: Specs 003/004/005 MUST reutilizar un único selector/normalizador canónico de Customer RUT; no se permite lógica duplicada inconsistente.
- **FR-031**: Toda personalización, Property Setter, Custom Field, índice y patch MUST ser reproducible desde `erpn_custom`.
- **FR-032**: La solución MUST NOT modificar ERPNext/Frappe core.
- **FR-033**: Errores de validación MUST indicar tipo de documento y causa, sin mensajes falsos de RUT para documentos extranjeros.
- **FR-034**: La implementación MUST incluir pruebas de migración, validación, unicidad y regresión bancaria.

## 13. Non-Functional Requirements

- **NFR-001 Determinism**: la misma combinación tipo/país/entrada debe normalizar siempre al mismo valor o fallar de la misma forma.
- **NFR-002 Idempotency**: ejecutar patches/migración más de una vez no debe recategorizar ni corromper datos ya migrados.
- **NFR-003 Auditability**: conflictos detectados durante migración deben poder listarse con Customer afectado y causa.
- **NFR-004 Compatibility**: ningún Customer RUT válido existente debe perder capacidad de matching bancario por efecto de esta feature.
- **NFR-005 Data preservation**: no truncar, convertir a entero ni eliminar ceros significativos de identificaciones no RUT.
- **NFR-006 Maintainability**: normalizadores por tipo deben estar aislados y ser testeables, no implementados como un bloque condicional repetido en múltiples módulos.
- **NFR-007 Security/Privacy**: logs técnicos no deben imprimir masivamente números completos de documentos cuando no sea necesario para diagnóstico; los reportes operativos deben respetar permisos de Customer.

## 14. Edge Cases obligatorios

- `tax_id` vacío en Customer legado.
- tipo vacío en Customer legado.
- RUT ingresado con puntos, espacios, guion y `k` minúscula.
- RUT con DV incorrecto.
- CPF con puntuación visual.
- CPF con longitud/algoritmo inválido.
- DNI con cero inicial.
- DNI de países diferentes con la misma secuencia.
- Passport alfanumérico.
- Passport con el mismo número emitido por países distintos.
- cambio RUT -> DNI sin cambiar número.
- cambio DNI -> RUT con valor no válido como RUT.
- Customer deshabilitado con documento que se intenta reutilizar.
- dos Customers históricos que después de normalización producen la misma identidad.
- importación de datos que bypassée la UI pero ejecute hooks de documento.
- matching bancario frente a un Customer DNI cuyo valor coincide textualmente con un RUT sin DV/formato.
- patch ejecutado en site donde el Server Script legado no existe.
- patch ejecutado dos veces.

## 15. Success Criteria

- **SC-001**: se puede crear un Customer RUT y se mantiene el comportamiento chileno actual.
- **SC-002**: se puede crear un Customer DNI sin recibir error de módulo 11 chileno.
- **SC-003**: se puede crear un Customer CPF bajo reglas CPF y país Brasil.
- **SC-004**: se puede crear un Customer Passport con país emisor explícito.
- **SC-005**: todos los números se persisten exclusivamente en `Customer.tax_id`.
- **SC-006**: ningún RUT existente válido se pierde o modifica semánticamente durante la migración.
- **SC-007**: el Server Script legado ya no gobierna documentos extranjeros después del despliegue.
- **SC-008**: un depósito Banco de Chile sigue encontrando al mismo Customer RUT que antes.
- **SC-009**: Customers DNI/CPF/Passport no generan candidatos falsos en matching RUT.
- **SC-010**: la misma identidad compuesta no puede quedar asignada a dos Customers sin que el sistema lo rechace o la migración lo reporte como conflicto.

## 16. Decisiones explícitamente NO abiertas

Estas decisiones ya están tomadas y el programador no debe reinterpretarlas:

1. El número seguirá viviendo en `Customer.tax_id`.
2. Los tipos iniciales son RUT, DNI, CPF y Passport.
3. RUT no será un campo custom separado.
4. El validador chileno será condicional, no global.
5. El modelo debe distinguir país emisor del documento de residencia/dirección del Customer.
6. El matching Banco de Chile continúa siendo matching por RUT chileno.
7. No se modifica ERPNext core.

## 17. Decisiones técnicas que el Plan debe cerrar antes de implementar

Estas no cambian el requisito funcional, pero deben resolverse con evidencia en `research.md`/`plan.md`:

- mecanismo Frappe v16 más seguro para retirar la propiedad `unique` actualmente aplicada a `Customer.tax_id`;
- mecanismo exacto para unicidad compuesta: validación transaccional + índice/constraint de base de datos si es soportable sin tocar core;
- nombre canónico real del Country Brasil en el site (`Brazil`/traducción visual) sin hardcodear una etiqueta traducida incorrecta;
- normalizador y algoritmo CPF con vectores de prueba;
- límites técnicos seguros de longitud para DNI/Passport sin inventar reglas universales;
- cómo exponer tipo/país/número en Quick Entry de manera versionable;
- estrategia de locking/transaction para impedir carreras de duplicado en creación concurrente.

## 18. Dependencias y orden de despliegue

1. diagnosticar esquema y datos actuales;
2. crear campos de tipo y país;
3. backfill de Customers existentes;
4. instalar validadores/normalizadores nuevos;
5. adaptar matching RUT de Spec 004/005;
6. retirar unicidad global de `tax_id` y activar unicidad compuesta segura;
7. desactivar Server Script legado;
8. ejecutar tests de regresión;
9. validar Quick Entry/UI;
10. solo entonces declarar Spec 006 implementada.

El orden puede refinarse técnicamente en `plan.md`, pero nunca debe existir una ventana de despliegue donde todos los Customers pierdan validación o donde el matching bancario use documentos extranjeros como RUT.
