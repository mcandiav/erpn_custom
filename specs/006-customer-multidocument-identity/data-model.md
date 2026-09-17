# Data Model: Customer - Identidad multidocumento internacional

## 1. Principio rector

ERPNext `Customer` sigue siendo el maestro comercial. Esta feature no crea una tabla paralela de personas ni un segundo registro de identificación.

El número documental se mantiene en el campo estándar:

```text
Customer.tax_id
```

La semántica se completa con dos campos custom versionados:

```text
Customer.custom_tax_id_type
Customer.custom_tax_id_country
```

Identidad lógica:

```text
(custom_tax_id_type, custom_tax_id_country, tax_id_normalizado)
```

## 2. Entidad Customer

### 2.1 Campos estándar relevantes

| Campo | Rol en Spec 006 | Regla |
|---|---|---|
| `name` | PK técnica Frappe | No cambia |
| `customer_name` | Nombre comercial/persona | No es identificador documental |
| `tax_id` | Número de documento / Tax ID | Fuente canónica del número |
| `disabled` | Estado del Customer | No libera la identidad para duplicación |
| `customer_type` | Tipo estándar ERPNext | No sustituye tipo documental |

### 2.2 Campo `custom_tax_id_type`

| Propiedad | Valor requerido |
|---|---|
| fieldtype | `Select` |
| label | `Tipo de documento` |
| options | `RUT\nDNI\nCPF\nPassport` |
| default | `RUT` para nuevos Customers FRAgallardo |
| in_quick_entry | Sí |
| in_standard_filter | Sí |
| read_only | No |
| mandatory | Sí para nuevos Customers; tratamiento especial para legados durante migración |

No agregar `Otro` en v1.

### 2.3 Campo `custom_tax_id_country`

| Propiedad | Valor requerido |
|---|---|
| fieldtype | `Link` |
| options | `Country` |
| label | `País emisor del documento` |
| in_quick_entry | Sí |
| in_standard_filter | Sí |
| mandatory | Condicional/efectivamente obligatorio para una identidad completa |

Reglas:

- RUT -> Chile.
- CPF -> Brasil.
- DNI -> selección explícita.
- Passport -> selección explícita.

El valor persistido debe ser el `name` canónico del DocType `Country`, no una traducción visual hardcodeada.

### 2.4 Campo `tax_id`

Estado actual documentado:

- campo estándar;
- etiqueta visible `RUT`;
- unique activo en el site;
- Quick Entry activo;
- filtro estándar activo;
- normalización global mediante Server Script.

Estado objetivo:

- sigue siendo estándar;
- etiqueta deja de ser exclusivamente RUT;
- conserva Quick Entry/filtros;
- contiene número normalizado conforme a tipo;
- no usa unicidad global aislada;
- participa en identidad compuesta.

## 3. Canonicalización por tipo

### 3.1 RUT / Chile

Función canónica existente:

```python
erpn_custom.chile.rut.normalize_chilean_tax_id(value)
```

Contrato:

```text
input:  13.698.154-4
output: 13698154-4
```

```text
input:  rut inválido
output: None / error de validación de dominio
```

La implementación de Customer debe reutilizar esta función y convertir el resultado inválido en error de validación comprensible.

### 3.2 CPF / Brasil

Crear módulo canónico separado, sugerido:

```text
erpn_custom.identity.cpf
```

o ubicación equivalente aprobada en plan.

Contrato funcional:

- acepta representación visual con puntuación si el plan confirma esa UX;
- normaliza a 11 dígitos;
- conserva ceros iniciales;
- valida dígitos verificadores;
- rechaza secuencias inválidas conforme al algoritmo documentado;
- nunca llama al normalizador RUT.

### 3.3 DNI

Crear una capa de normalización dependiente de país:

```text
normalize_document(type="DNI", country=<Country>, value=<tax_id>)
```

En v1, si no existe validador país-específico:

- trim de extremos;
- tratar como string;
- no convertir a entero;
- preservar ceros iniciales;
- no eliminar caracteres internos sin una regla país-específica documentada.

La ausencia de una validación fuerte no autoriza a inferir que un número pertenece a otra jurisdicción.

### 3.4 Passport

Contrato genérico v1:

- trim de extremos;
- string no vacío;
- país emisor obligatorio;
- no conversión numérica;
- no regex universal restrictiva;
- cualquier normalización adicional debe estar respaldada por regla país-específica.

## 4. Identidad compuesta y unicidad

### 4.1 Clave lógica

```text
identity_key = (
    custom_tax_id_type,
    custom_tax_id_country,
    normalized_tax_id
)
```

### 4.2 Scope de unicidad

La identidad debe ser única entre todos los Customers del site, incluidos `disabled=1`.

Justificación: deshabilitar un Customer no debe permitir crear un segundo maestro con el mismo documento y fragmentar historial financiero/comercial.

### 4.3 Concurrencia

Una validación Python `exists()` por sí sola puede ser insuficiente ante dos creaciones concurrentes. El plan debe decidir y probar un mecanismo que evite carrera TOCTOU.

Opciones técnicas a investigar:

- índice/constraint SQL compuesto mantenido por patch;
- clave derivada única persistida en campo técnico custom;
- locking transaccional soportado por Frappe/MariaDB;
- combinación de validación funcional + constraint.

No se congela la técnica aquí; sí se congela el resultado: no pueden persistirse dos Customers con la misma identidad compuesta.

## 5. Campo técnico derivado opcional

El plan puede crear un campo técnico como:

```text
custom_identity_key
```

solo si demuestra que simplifica unicidad/indexación de forma robusta.

Si se crea:

- debe ser read-only;
- no visible al usuario normal;
- derivado únicamente de tipo + país + tax_id normalizado;
- determinístico;
- versionado por patch/Custom Field;
- nunca se convierte en una segunda fuente de número documental.

Ejemplo conceptual, no formato obligatorio:

```text
RUT|Chile|13698154-4
CPF|Brazil|01234567890
Passport|Argentina|AB123456
```

No implementar hash irreversible si perjudica diagnóstico sin una razón de seguridad concreta; tampoco exponer la clave completa innecesariamente en logs.

## 6. Estado legado durante migración

Puede existir un Customer histórico con `tax_id` vacío.

Spec 006 no autoriza inventar documento. Por ello se admite temporalmente el estado:

```text
custom_tax_id_type = NULL o default técnico controlado
tax_id = NULL
custom_tax_id_country = NULL
```

solo para registros preexistentes que ya estaban incompletos antes de la migración.

Reglas:

- no eliminar Customer;
- no inventar RUT;
- no bloquear el patch global por estos registros;
- nuevos Customers no pueden quedar en ese estado;
- una estrategia de saneamiento posterior puede completar los legados.

El plan debe evitar que el default `RUT` convierta artificialmente un Customer legado sin documento en una identidad RUT declarada como completa.

## 7. Migración de registros con `tax_id`

Pseudológica requerida:

```text
for customer in Customers:
    if empty(customer.tax_id):
        mark/leave legacy incomplete
        continue

    normalized = normalize_chilean_tax_id(customer.tax_id)

    if normalized:
        customer.custom_tax_id_type = "RUT"
        customer.custom_tax_id_country = Country(Chile)
        customer.tax_id = normalized
        continue

    report migration_conflict(customer, tax_id, reason="non-RUT legacy value")
```

No ejecutar:

```text
if len == 11 -> CPF
if numeric -> DNI
if alphanumeric -> Passport
```

porque sería inferencia insegura.

## 8. Relación con Bank Transaction

### 8.1 Campos bancarios no cambian

`Bank Transaction.custom_rut_del_pagador` continúa siendo evidencia literal del RUT reportado por Banco de Chile.

`custom_rut_pagador_normalizado` continúa siendo derivado chileno cuando aplique.

No existe relación automática entre `custom_tax_id_type` de Customer y el tipo de documento del pagador bancario excepto que el motor de matching exige Customer RUT/Chile.

### 8.2 Índice de Customers para matching

Estado anterior conceptual:

```text
index all Customer.tax_id as Chilean RUT
```

Estado objetivo:

```text
select Customer
where custom_tax_id_type = "RUT"
  and custom_tax_id_country = Chile
then normalize tax_id as Chilean RUT
```

La función que construye el índice debe ignorar documentos extranjeros.

## 9. Cambios de identidad

Editar cualquiera de estos campos:

- `custom_tax_id_type`;
- `custom_tax_id_country`;
- `tax_id`;

implica recalcular y revalidar la identidad completa.

No se permite:

- cambiar tipo y conservar un valor incompatible silenciosamente;
- cambiar país de RUT a otro país;
- cambiar país de CPF a otro país;
- modificar `tax_id` sin revalidar unicidad.

## 10. Borrado y deshabilitación

La Spec no cambia reglas estándar de borrado de Customer.

Deshabilitar no libera la clave de identidad.

Si se permite borrar físicamente un Customer por mecanismos estándar y no existen referencias que lo impidan, la identidad deja de existir porque el maestro deja de existir. La feature no debe implementar borrado especial para liberar documentos.

## 11. Matriz de ejemplos

| Tipo | País emisor | Entrada `tax_id` | Persistencia esperada | Validación |
|---|---|---|---|---|
| RUT | Chile | `13.698.154-4` | `13698154-4` | módulo 11 |
| RUT | Chile | `13698154-4` | `13698154-4` | módulo 11 |
| DNI | Argentina | `01234567` | string normalizado sin perder 0 | regla DNI país / genérica v1 |
| CPF | Brasil | valor con puntuación | 11 dígitos | algoritmo CPF |
| Passport | país elegido | alfanumérico | forma normalizada segura | genérica/país |

Los ejemplos extranjeros no deben usarse como vectores oficiales de validez hasta que `research.md` cierre sus reglas exactas.

## 12. Índices y consultas

El plan debe evaluar como mínimo:

1. lookup por identidad compuesta en creación/edición;
2. lookup masivo de Customers RUT para Spec 004;
3. migración de todos los Customers existentes;
4. filtros administrativos por tipo y país.

Cualquier índice DB agregado debe ser creado/eliminado mediante patch idempotente de `erpn_custom` y documentado.

## 13. Invariantes

1. Un número documental primario vive una sola vez: `Customer.tax_id`.
2. Todo `tax_id` completo tiene un tipo explícito.
3. DNI/Passport tienen país emisor explícito.
4. RUT siempre es Chile.
5. CPF siempre es Brasil.
6. Documento extranjero nunca se valida con módulo 11 chileno.
7. Documento extranjero nunca entra al matching RUT de Banco de Chile.
8. Cambiar tipo/país/número revalida toda la identidad.
9. Deshabilitar Customer no permite duplicar identidad.
10. La migración nunca inventa una clasificación extranjera.
11. No se modifica ERPNext core.
12. Server Script legado no puede quedar compitiendo con el nuevo validador una vez desplegada Spec 006.
