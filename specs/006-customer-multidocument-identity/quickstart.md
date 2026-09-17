# Quickstart: Customer - Identidad multidocumento internacional

## Purpose

Guía breve de aceptación funcional una vez implementada Spec 006. No sustituye tests automatizados ni el plan de migración.

## Preconditions

- app `erpn_custom` actualizada con Spec 006;
- patches ejecutados;
- Customer metadata nueva visible;
- Server Script legado RUT deshabilitado;
- no existen conflictos de migración pendientes que bloqueen uniqueness;
- Country Chile/Brasil resueltos con nombres canónicos del site.

## Scenario A - RUT chileno

1. Crear Customer nuevo.
2. Confirmar default `Tipo de documento = RUT`.
3. Confirmar país emisor Chile.
4. Ingresar un RUT de prueba válido con puntos/guion.
5. Guardar.

Expected:

- se guarda;
- `tax_id` queda en formato canónico sin puntos;
- país queda Chile;
- DV fue validado.

Negative:

- cambiar DV por uno incorrecto;
- el Customer debe rechazarse con mensaje específico RUT.

## Scenario B - DNI extranjero

1. Crear Customer.
2. Cambiar tipo a `DNI`.
3. Elegir país emisor.
4. Ingresar número de prueba, incluyendo caso con cero inicial si corresponde al vector de test.
5. Guardar.

Expected:

- no aparece error módulo 11 chileno;
- cero inicial no se pierde;
- `tax_id` sigue siendo el campo donde queda el número;
- país queda persistido.

Negative:

- quitar país emisor;
- guardado debe rechazarse.

## Scenario C - CPF

1. Crear Customer.
2. Elegir `CPF`.
3. Verificar que país queda Brasil.
4. Ingresar vector CPF válido de prueba.
5. Guardar.

Expected:

- normalización CPF aplicada;
- país Brasil;
- no se ejecuta RUT validation.

Negative:

- usar vector CPF inválido;
- guardado se rechaza como CPF inválido, no RUT inválido.

## Scenario D - Passport

1. Crear Customer.
2. Elegir `Passport`.
3. Seleccionar país emisor.
4. Ingresar un número alfanumérico de prueba.
5. Guardar.

Expected:

- valor se conserva conforme a normalizador Passport;
- no se fuerza Chile/Brasil;
- no se aplica regex RUT/CPF.

Negative:

- dejar país vacío;
- guardado se rechaza.

## Scenario E - Composite uniqueness

### Exact duplicate

Crear Customer A con:

```text
Tipo: DNI
País: <X>
Número: <N>
```

Intentar crear Customer B con la misma combinación.

Expected: B rechazado.

### Same number, different issuer

Crear identidad con el mismo tipo/número pero país emisor diferente cuando el contrato lo permita.

Expected: no debe fallar únicamente por `tax_id` global unique; la decisión depende de identidad compuesta.

### Disabled record

Deshabilitar Customer A e intentar crear otro con la misma identidad exacta.

Expected: rechazo; disabled no libera identidad.

## Scenario F - Migration regression

Seleccionar Customer existente anterior a Spec 006 con RUT conocido.

Expected:

```text
custom_tax_id_type = RUT
custom_tax_id_country = Chile
tax_id = mismo RUT canónico
```

No se debe haber creado otro campo con copia del RUT.

## Scenario G - Banco de Chile regression

1. Usar un Bank Transaction controlado con `custom_rut_del_pagador` de un Customer RUT/Chile.
2. Ejecutar motor Spec 004.

Expected:

- Customer correcto sigue siendo candidato y se atribuye según reglas de Spec 004.

Luego crear Customer extranjero con `tax_id` visualmente parecido.

Expected:

- DNI/CPF/Passport no entra en candidatos RUT.

## Scenario H - Legacy Server Script

Revisar Server Script:

```text
Validar y normalizar RUT Cliente
```

Expected:

- deshabilitado;
- la validación efectiva proviene de `erpn_custom`.

## Pass criteria

Quickstart se considera aprobado solo si A-H cumplen sin editar manualmente metadata del DocType durante la prueba.
