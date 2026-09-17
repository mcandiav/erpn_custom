# Requirements Checklist: Customer - Identidad multidocumento internacional

## Business model

- [x] `Customer.tax_id` permanece como campo canónico del número documental.
- [x] No se crea un segundo campo custom para duplicar RUT/DNI/CPF/Passport.
- [x] Tipos iniciales congelados: RUT, DNI, CPF, Passport.
- [x] Se distingue tipo documental de número documental.
- [x] Se distingue país emisor de país de residencia/dirección del Customer.
- [x] Identidad lógica definida como tipo + país emisor + número normalizado.

## RUT

- [x] RUT se asocia a Chile.
- [x] RUT usa normalización canónica `body-DV`.
- [x] RUT valida módulo 11.
- [x] Se reutiliza `erpn_custom.chile.rut.normalize_chilean_tax_id`.
- [x] La validación RUT solo aplica cuando tipo = RUT.

## CPF

- [x] CPF se asocia a Brasil.
- [x] CPF no usa algoritmo RUT.
- [x] Se exige normalizador/validador CPF propio antes de declarar soporte terminado.
- [x] Ceros iniciales deben preservarse.

## DNI

- [x] DNI no usa algoritmo RUT.
- [x] País emisor obligatorio.
- [x] Ceros iniciales se preservan.
- [x] No se convierte a entero.
- [x] Se permite ampliar validación por país sin cambiar el modelo.

## Passport

- [x] Passport no usa algoritmo RUT/CPF.
- [x] País emisor obligatorio.
- [x] Se trata como string.
- [x] No se impone una regex universal destructiva.

## UI / metadata

- [x] Se agrega `custom_tax_id_type`.
- [x] Se agrega `custom_tax_id_country`.
- [x] `tax_id` deja de tener etiqueta exclusivamente RUT.
- [x] Tipo, país y número deben estar disponibles en Quick Entry.
- [x] Tipo/país/número deben poder filtrarse administrativamente.
- [x] Defaults de nuevos Customers no deben recategorizar legados silenciosamente.

## Uniqueness

- [x] La unicidad global aislada de `tax_id` se identifica como incompatible.
- [x] La nueva unicidad es compuesta.
- [x] Customers disabled siguen reservando identidad.
- [x] Se exige protección frente a concurrencia, no solo chequeo secuencial en Python.
- [x] Duplicados históricos deben reportarse, no fusionarse automáticamente.

## Migration

- [x] RUT existente válido -> RUT/Chile.
- [x] `tax_id` vacío -> no inventar documento.
- [x] Valor legacy no RUT -> conflicto, sin inferir DNI/CPF/Passport.
- [x] Migración debe ser idempotente.
- [x] Server Script legado se desactiva por patch una vez activa la nueva autoridad.
- [x] Patch tolera que el Server Script no exista.

## Banking compatibility

- [x] Spec 004 conserva matching RUT.
- [x] Matching solo indexa Customers RUT/Chile.
- [x] DNI/CPF/Passport quedan fuera del índice RUT.
- [x] `Bank Transaction.custom_rut_del_pagador` conserva semántica bancaria original.
- [x] Spec 005 debe reutilizar misma regla; no duplicarla.

## Versioning / ownership

- [x] Todo cambio vive en `erpn_custom`.
- [x] No se modifica ERPNext/Frappe core.
- [x] Campos, labels, property setters, patches, índices y tests deben quedar versionados.
- [x] La documentación de estado vigente padre solo se actualiza después de implementación real.
- [x] Crear Spec 006 no cambia por sí solo la Spec activa del Programador.

## Test coverage required

- [x] RUT válido/ inválido.
- [x] CPF válido/ inválido.
- [x] DNI con país y cero inicial.
- [x] Passport alfanumérico con país.
- [x] Duplicate exact identity.
- [x] Same number across different issuers.
- [x] Disabled duplicate.
- [x] Migration valid RUT.
- [x] Migration empty legacy.
- [x] Migration conflict.
- [x] Patch idempotency.
- [x] API/import/backend path.
- [x] Bank matching positive RUT.
- [x] Bank matching negative DNI/CPF/Passport.

## Technical decisions intentionally left for planning/evidence

- [ ] Confirmar mecanismo exacto para retirar `tax_id` unique en Frappe v16/site.
- [ ] Confirmar constraint/identity key final para unicidad compuesta.
- [ ] Confirmar algoritmo/vectores CPF usados en tests.
- [ ] Confirmar nombres canónicos Country Chile/Brasil.
- [ ] Confirmar evento/hook backend Customer.
- [ ] Confirmar límites seguros de longitud y normalización genérica DNI/Passport.
- [ ] Confirmar estrategia concreta de prueba de concurrencia.

Los ítems abiertos son de implementación técnica; no cambian las decisiones funcionales aprobadas en `spec.md`.
