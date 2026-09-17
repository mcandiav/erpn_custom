# Research: Customer - Identidad multidocumento internacional

## 1. Fuentes inspeccionadas

### Configuración funcional vigente

Fuente:

```text
../configuracion_erpnext.md
```

Estado documentado de `Customer`:

- `tax_id` es campo estándar;
- etiqueta visible actual: `RUT`;
- disponible en filtro estándar;
- disponible en Quick Entry;
- configurado como único;
- no obligatorio actualmente;
- persistencia RUT canónica `12345678-9`;
- Server Script `Validar y normalizar RUT Cliente` activo;
- evento `Before Validate`;
- validación módulo 11.

### Sandbox ERPNext

Verificación 2026-09-17 mediante MCP `ERPsb`:

- site: `derp.at-once.cl`;
- Frappe: `16.28.0`;
- existe exactamente el Server Script relevante `Validar y normalizar RUT Cliente`;
- está habilitado;
- `reference_doctype = Customer`;
- el source lee `doc.tax_id`;
- elimina `.`, `-` y espacios;
- valida cuerpo numérico y DV 0-9/K;
- calcula módulo 11;
- reescribe `doc.tax_id` a `body-DV`.

Conclusión: cualquier documento extranjero ingresado actualmente a `tax_id` queda sometido a semántica RUT y puede ser rechazado.

### Código `erpn_custom`

Fuente canónica RUT ya existente:

```text
erpn_custom/chile/rut.py
```

Función:

```text
normalize_chilean_tax_id(value)
```

Características observadas:

- remueve caracteres no numéricos/K;
- upper de K;
- valida cuerpo y DV;
- módulo 11;
- devuelve `body-DV` o `None`.

Conclusión: no debe escribirse un segundo algoritmo RUT para Customer. Spec 006 debe reutilizar este normalizador.

### Dependencias bancarias existentes

Búsqueda de `tax_id`/RUT en repo confirma dependencias en:

- `erpn_custom/chile/deposit_mapping.py`;
- `erpn_custom/chile/matching.py`;
- Spec 003;
- Spec 004;
- Spec 005.

Spec 004 congela actualmente:

```text
Customer identity: Customer.tax_id
matching: normalize Bank Transaction.custom_rut_del_pagador
          against normalized Customer.tax_id
```

Conclusión: transformar `tax_id` en campo multidocumento sin filtrar por tipo provocaría una regresión conceptual y potencialmente coincidencias falsas. El matching debe filtrar RUT/Chile antes de normalizar.

## 2. Decisiones derivadas de evidencia

### R1 - No crear `custom_document_number`

**Decision**: `Customer.tax_id` conserva el número.

**Rationale**: ya es el campo usado por ERPNext y por el código bancario. Duplicarlo crearía dos fuentes de verdad y una migración innecesaria.

### R2 - Agregar tipo documental explícito

**Decision**: agregar `custom_tax_id_type`.

**Valores v1**:

- RUT
- DNI
- CPF
- Passport

**Rationale**: la forma textual del número no es suficiente para decidir qué algoritmo aplicar.

### R3 - Agregar país emisor explícito

**Decision**: agregar `custom_tax_id_country` Link a Country.

**Rationale**: `DNI` y `Passport` no son globalmente identificables solo por tipo+número. Además, residencia/dirección del Customer no representa necesariamente jurisdicción emisora.

### R4 - RUT y CPF fijan país

**Decision**:

```text
RUT -> Chile
CPF -> Brasil
```

El backend debe imponer consistencia aunque la UI permita visualizar/cambiar inicialmente el campo.

### R5 - Server Script legado debe salir de la autoridad

**Decision**: mover el dominio de validación a código versionado `erpn_custom` y desactivar el Server Script mediante patch idempotente.

**Rationale**:

- el script actual es global y RUT-only;
- una regla centralizada en app es reproducible entre sites;
- evita divergencia sandbox/producción;
- permite tests unitarios.

### R6 - Matching Banco de Chile sigue siendo RUT-only

**Decision**: Spec 006 no generaliza el dato bancario. El banco informa RUT del pagador; por tanto el matching automático solo consulta Customers `RUT/Chile`.

## 3. Riesgos identificados

### Risk A - `tax_id` unique actual

La configuración documentada marca `tax_id` como único. Eso es incompatible con una identidad compuesta cuando dos jurisdicciones puedan emitir el mismo número textual.

Ejemplo conceptual:

```text
DNI / país A / 12345678
DNI / país B / 12345678
```

Si `tax_id` conserva unique global, el segundo Customer fallaría aunque las identidades sean distintas.

**Acción de plan**: verificar cómo está materializada la propiedad unique en Frappe v16/site actual y retirarla de forma versionada antes de validar escenarios cross-country.

### Risk B - Unicidad solo en Python puede tener carrera

Dos requests concurrentes pueden pasar un `frappe.db.exists()` antes de que ninguna haya hecho commit.

**Acción de plan**: preferir una garantía DB o clave derivada única, además del mensaje funcional amigable.

### Risk C - Defaults durante backfill

Si `custom_tax_id_type` se crea con default `RUT`, un Customer histórico con `tax_id` vacío podría parecer semánticamente RUT aunque no tenga documento.

**Acción de plan**: diferenciar creación nueva de backfill. No usar el default como evidencia de clasificación histórica.

### Risk D - Duplicación del algoritmo RUT

El Server Script y `erpn_custom.chile.rut` implementan el mismo dominio por separado.

**Acción**: después de Spec 006 debe existir una autoridad de backend en app; el script queda deshabilitado.

### Risk E - Código de matching no filtra tipo

La función actual `index_customers_by_normalized_tax_id` recibe Customers y normaliza `tax_id`; si se le entregan documentos extranjeros puede interpretarlos incorrectamente o generar `None`/colisiones.

**Acción**: seleccionar RUT/Chile antes de indexar y agregar tests negativos con DNI/CPF/Passport.

### Risk F - Passport no admite una regex universal segura

Los formatos varían por emisor.

**Acción**: v1 usa validación genérica conservadora + país; reglas específicas podrán añadirse por país sin cambiar el modelo.

## 4. Preguntas técnicas que deben cerrarse en Plan

No son preguntas de negocio; el requisito funcional ya está aprobado.

1. ¿Property Setter, Custom Field metadata o patch SQL es el mecanismo soportado para retirar `unique` de `tax_id` en el site actual?
2. ¿La base actual posee realmente un índice unique físico sobre `tabCustomer.tax_id` y con qué nombre?
3. ¿Conviene una columna técnica `custom_identity_key` con unique o un índice compuesto DB sobre tipo+país+tax_id?
4. ¿Cómo se maneja de forma limpia una violación concurrente de unique para devolver mensaje funcional?
5. ¿Cuál es el `name` canónico del Country Brasil en el site y cómo se evita depender de traducción UI?
6. ¿Dónde se ubicará el servicio común de identidad para que Customer validation y matching reutilicen funciones sin acoplar documentos extranjeros al módulo `chile`?
7. ¿Qué algoritmo/vectores oficiales se adoptarán para CPF?
8. ¿Qué límite de longitud de base de datos tiene `Customer.tax_id` en ERPNext v16 y es suficiente para Passport soportado?
9. ¿Cómo se versionarán Quick Entry y labels sin cambio manual posterior?

## 5. Arquitectura de módulos sugerida para evaluar

Sin congelar nombres físicos exactos, una separación mantenible sería:

```text
erpn_custom/
  identity/
    __init__.py
    customer.py        # orquestación tipo/país/tax_id
    cpf.py             # normalización/validación CPF
    dni.py             # dispatcher/regla genérica por país
    passport.py        # regla conservadora por país
  chile/
    rut.py             # se mantiene autoridad RUT
    matching.py        # matching bancario RUT-only
```

El servicio `identity/customer.py` puede importar `chile.rut`, pero `chile.rut` no debe depender de Customer ni de módulos extranjeros.

## 6. Estrategia de migración recomendada

Fases seguras:

### Fase A - Diagnóstico read-only

- contar Customers totales;
- contar `tax_id` vacíos/no vacíos;
- probar todos los `tax_id` no vacíos con normalizador RUT;
- listar valores no RUT;
- detectar duplicados normalizados;
- verificar índice/unique físico.

No modificar datos.

### Fase B - Crear metadata nueva

- Custom Fields tipo/país;
- ajustes UI;
- todavía mantener mecanismo de validación legado hasta que el nuevo esté listo, evitando ventana sin validación.

### Fase C - Backfill

- RUT válido -> RUT/Chile;
- vacío -> legado incompleto;
- no RUT -> conflicto reportado.

### Fase D - Nuevo validador

- activar hooks/app logic;
- tests verdes;
- adaptar matching RUT-only.

### Fase E - Unicidad nueva

- retirar unique global `tax_id`;
- activar garantía compuesta;
- validar escenarios cross-country.

### Fase F - Retirar autoridad vieja

- desactivar Server Script legado;
- smoke tests completos.

## 7. Criterios de evidencia para cerrar investigación

Antes de ejecutar implementación irreversible, `plan.md` debe registrar:

- salida/confirmación del esquema real `Customer.tax_id`;
- mecanismo elegido de uniqueness;
- vectores de CPF válidos e inválidos usados en tests;
- nombre canónico de Country Chile/Brasil;
- ruta y evento del hook Customer;
- plan de rollback de metadata/constraint sin pérdida de `tax_id`.

## 8. Phase 0 closure (2026-09-17) — decisiones de implementación

Evidencia MCP `user-ERPNext` site `derp.at-once.cl` / Frappe `16.28.0`:

| Ítem | Decisión / evidencia |
|---|---|
| Server Script legado | Existe `Validar y normalizar RUT Cliente`, `disabled=0`, evento DocType Customer, reescribe `tax_id` con módulo 11 |
| Hook app previo | Solo `Bank Transaction.validate` en `hooks.py`; no había hook Customer en app |
| Matching | `deposit_mapping.py` indexaba todos los Customers `disabled=0` por `tax_id` (2 call sites) |
| Country canónico | `Chile` y `Brazil` (nombres estándar ERPNext en inglés) |
| Unicidad | Campo técnico `custom_identity_key` + unique DB tras backfill; Property Setter `tax_id.unique=0` + drop índice físico si existe |
| Hook Customer | `doc_events["Customer"]["validate"]` → `erpn_custom.identity.customer.validate_customer_identity` |
| CPF | Algoritmo módulo 11 brasileño; vectores: válido `529.982.247-25`, `11144477735`, `390.533.447-05`; inválido DV `529.982.247-20`, repetidos `00000000000` |
| Default RUT | Solo en Customer nuevo (JS + backend); **sin** default en Custom Field para no contaminar legados vacíos |
| Patches | `v0_0_5_customer_identity_fields` → `backfill` → `unique` → `disable_legacy_rut_server_script` |
| Versión producto | bump `__version__` a `16.0.3` |
