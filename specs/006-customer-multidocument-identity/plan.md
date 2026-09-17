# Implementation Plan: Customer - Identidad multidocumento internacional

## 1. Goal

Implementar un modelo de identidad documental internacional sobre `Customer` manteniendo `Customer.tax_id` como campo canónico del número y agregando tipo + país emisor, sin romper el matching bancario RUT de Chile ni perder datos existentes.

## 2. Implementation boundary

Todo el cambio debe vivir en el repositorio/app `erpn_custom`.

Permitido:

- Custom Fields versionados;
- Property Setters versionados;
- hooks de DocType;
- módulos Python;
- patches;
- tests;
- índices/constraints creados por patch cuando sean necesarios y seguros.

No permitido:

- editar ERPNext/Frappe core;
- depender de un Server Script manual como autoridad final;
- duplicar el número de documento en un nuevo campo;
- introducir un segundo maestro de clientes.

## 3. Deliverables técnicos

### D1 - Metadata Customer

Crear/versionar:

- `custom_tax_id_type`;
- `custom_tax_id_country`;
- etiqueta genérica para `tax_id`;
- Quick Entry/filtros de los tres campos;
- retiro de `unique` global de `tax_id` cuando la nueva unicidad esté lista.

### D2 - Servicio canónico de identidad

Responsabilidades:

- resolver reglas tipo/país;
- normalizar `tax_id`;
- validar documento;
- forzar Chile para RUT;
- forzar Brasil para CPF;
- exigir país para DNI/Passport;
- validar uniqueness;
- producir mensajes de error correctos por tipo.

### D3 - Normalizador CPF

Crear implementación aislada, testeada con vectores válidos/ inválidos documentados.

### D4 - Integración Customer

Conectar el servicio al lifecycle backend de `Customer` en un evento suficientemente temprano para persistir `tax_id` normalizado y suficientemente confiable para todas las vías de escritura soportadas.

El plan técnico debe verificar el evento exacto (`validate`, `before_validate` vía doc_events u otra opción soportada) antes de codificar.

### D5 - Migración

Patch idempotente para:

- crear/asegurar metadata;
- diagnosticar y backfillear RUT existentes;
- reportar conflictos;
- adaptar unique;
- desactivar Server Script legado al final del corte seguro.

Si por seguridad conviene dividirlo, usar varios patches ordenados en vez de uno monolítico.

### D6 - Compatibilidad Spec 004/005

Modificar matching para que solo Customers tipo RUT/Chile entren al índice chileno.

### D7 - Tests

Unitarios:

- RUT;
- CPF;
- DNI genérico;
- Passport genérico;
- dispatcher tipo/país;
- identity key.

Integración:

- Customer create/update;
- unique compuesto;
- migración;
- disabled Customer duplicate attempt;
- concurrent duplicate attempt si la infraestructura de test lo permite;
- Bank Transaction matching regression.

## 4. Sequencing

### Phase 0 - Evidence gate

Antes de modificar datos:

1. inspeccionar meta real de `Customer.tax_id`;
2. confirmar cómo se aplicó `unique`;
3. inspeccionar índices de `tabCustomer`;
4. inventariar Customers existentes y calidad de `tax_id`;
5. confirmar nombres canónicos de Country para Chile/Brasil;
6. confirmar que no existe otra automatización que reescriba `tax_id`.

Output obligatorio: notas en `research.md` o evidencia de implementación asociada.

### Phase 1 - Tests de dominio primero

Escribir tests que expresen el contrato antes de reemplazar el Server Script.

Casos mínimos RUT:

- entrada con puntos;
- K minúscula;
- DV inválido;
- vacío.

Casos mínimos CPF:

- válido;
- válido con puntuación;
- DV inválido;
- longitud inválida;
- secuencia inválida/repetida según algoritmo;
- cero inicial.

DNI:

- país obligatorio;
- cero inicial conservado;
- valor vacío;
- dos países mismo número no colisionan.

Passport:

- país obligatorio;
- alfanumérico;
- mismo número en dos países distintos no colisiona.

### Phase 2 - Metadata sin romper legado

Crear Custom Fields/Property Setters.

Precaución: no retirar todavía el validador RUT legado si el nuevo backend aún no está activo.

El default visual `RUT` aplica a nuevos Customers, pero la migración debe distinguir registros previos sin documento.

### Phase 3 - Servicio de identidad

Implementar API interna conceptual:

```python
normalize_customer_identity(document_type, country, tax_id)
```

Resultado sugerido:

```python
{
    "document_type": "RUT",
    "country": "Chile",
    "tax_id": "13698154-4",
}
```

Errores deben ser excepciones de validación de dominio, no `None` ambiguo en la capa Customer.

### Phase 4 - Hook Customer

Al guardar:

1. obtener tipo;
2. resolver país;
3. normalizar/validar;
4. escribir `tax_id` canónico;
5. construir clave de unicidad;
6. validar duplicado;
7. persistir.

La UI JavaScript, si existe, es ayuda; no autoridad.

### Phase 5 - Backfill

Ejecutar patch sobre Customers existentes.

Reglas exactas definidas en Spec/Data Model.

El patch debe emitir resumen:

- total leídos;
- RUT migrados;
- vacíos legacy;
- conflictos no RUT;
- duplicados detectados;
- errores.

No almacenar datos personales completos en logs indiscriminados; para conflictos usar Customer name y representación mínima necesaria bajo logs administrativos.

### Phase 6 - Unicidad compuesta

Solo después de backfill y resolución de conflictos:

- retirar unique global `tax_id`;
- habilitar constraint/clave compuesta elegida;
- validar carrera concurrente;
- probar mismo número bajo países/tipos distintos;
- probar misma identidad exacta duplicada.

### Phase 7 - Matching bancario

Cambiar query/indexación para filtrar:

```text
type = RUT
country = Chile
```

antes de normalizar `tax_id`.

Tests negativos con DNI/CPF/Passport.

### Phase 8 - Desactivar Server Script legado

Cuando tests y smoke test sean verdes:

- patch busca por nombre exacto `Validar y normalizar RUT Cliente`;
- si existe, `disabled = 1`;
- si no existe, no falla;
- guardar evidencia de que ya no hay doble validación.

### Phase 9 - Acceptance

Validar manualmente en sandbox:

1. crear RUT;
2. crear DNI;
3. crear CPF;
4. crear Passport;
5. intentar duplicados;
6. editar tipo con número incompatible;
7. abrir Quick Entry;
8. correr matching de depósito RUT conocido;
9. comprobar que documento extranjero no se considera candidato.

## 5. Proposed code ownership

Sugerencia, sujeta a evidencia del repo:

```text
erpn_custom/
  identity/
    __init__.py
    customer.py
    cpf.py
    dni.py
    passport.py
    test_customer_identity.py
    test_cpf.py
  chile/
    rut.py                    # reutilizar
    matching.py               # adaptar RUT-only
    test_matching.py          # regresión
  patches/
    v0_0_X_customer_identity_fields.py
    v0_0_X_customer_identity_backfill.py
    v0_0_X_customer_identity_unique.py
    v0_0_X_disable_legacy_rut_server_script.py
```

No usar los nombres de versión literales `v0_0_X` sin alinearlos con la secuencia real al implementar.

## 6. Migration safety and rollback

### Before deploy

- backup/snapshot del site según procedimiento operativo vigente;
- diagnóstico read-only guardado;
- tests locales/CI verdes.

### During deploy

- patches idempotentes;
- fallar de forma explícita antes de remover constraints si hay duplicados no resueltos;
- no borrar `tax_id` bajo ningún escenario automático.

### Rollback principle

Si falla después de crear campos pero antes de completar unicidad:

- conservar nuevos campos;
- no borrar datos migrados;
- se puede reactivar temporalmente validación RUT solo si el site vuelve a operar exclusivamente con RUT y no existen Customers extranjeros creados durante la ventana.

Una vez creados Customers extranjeros, volver al Server Script RUT global sería destructivo/incorrecto y no es un rollback válido.

Por ello la ventana de cambio debe tratarse como migración de modelo, no como simple cambio cosmético.

## 7. Performance considerations

- Customer save es operación de bajo volumen comparada con depósitos; validación debe ser O(1) más lookup indexado.
- No escanear todos los Customers en cada guardado.
- Matching Spec 004 debe mantener consulta masiva/indexada y no convertir el filtro por tipo en N+1.
- Backfill sí puede recorrer todos los Customers en patch, preferiblemente por lotes si el volumen lo requiere.

## 8. Observability

Errores funcionales visibles al usuario:

- tipo inválido;
- país faltante;
- documento inválido;
- duplicado.

Errores técnicos:

- constraint inesperado;
- patch incompleto;
- conflicto legado.

No mezclar ambos tipos de mensaje.

## 9. Security / privacy

Los documentos personales son datos sensibles operacionalmente aunque esta Spec no cambie el modelo de permisos ERPNext.

Requisitos:

- respetar permisos estándar de Customer;
- no exponer listados de documentos en endpoints públicos;
- no imprimir dumps masivos de `tax_id` en logs;
- tests deben usar identificadores ficticios/vectores de prueba, no datos reales de clientes salvo acceptance controlado.

## 10. Definition of Done

Spec 006 solo se considera implementada cuando:

- metadata está versionada;
- Server Script legado ya no gobierna Customer;
- RUT sigue funcionando;
- DNI funciona sin RUT validation;
- CPF tiene validación propia;
- Passport funciona con país;
- uniqueness compuesta está garantizada también bajo concurrencia razonable;
- Customers existentes fueron migrados o conflictos quedaron resueltos explícitamente;
- matching Spec 004/005 filtra RUT/Chile;
- tests unitarios + integración + regresión están verdes;
- Quick Entry refleja tipo/país/número;
- no hubo modificación de core.
