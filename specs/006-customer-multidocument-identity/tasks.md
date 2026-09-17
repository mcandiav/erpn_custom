# Tasks: Customer - Identidad multidocumento internacional

## Notes

- Esta Spec NO reemplaza automáticamente la Spec activa del Programador indicada en `README.md`.
- Ejecutar estas tareas solo cuando Spec 006 sea declarada frente activo.
- Todas las rutas son relativas a la raíz `ERPnext-Custom/erpn_custom/`.
- No modificar ERPNext/Frappe core.
- No crear un campo alternativo al número: `Customer.tax_id` sigue siendo fuente canónica.

## Phase 0 - Evidence and safeguards

- [ ] T001 Inspeccionar metadata efectiva de `Customer.tax_id` en sandbox: label, fieldtype, length, unique, reqd, quick entry/filter behavior.
- [ ] T002 Inspeccionar índices/constraints físicos de `tabCustomer` y documentar cómo se materializa la unicidad actual de `tax_id`.
- [ ] T003 Contar Customers totales, con `tax_id`, sin `tax_id`, RUT válidos y valores no RUT usando modo read-only.
- [ ] T004 Detectar duplicados de RUT después de normalización; no modificar ni fusionar registros.
- [ ] T005 Confirmar `name` canónico de Country para Chile y Brasil en el site.
- [ ] T006 Buscar cualquier Server Script/hook/adaptación adicional que lea o reescriba `Customer.tax_id`.
- [ ] T007 Confirmar dependencias actuales de `Customer.tax_id` en `deposit_mapping.py`, `matching.py`, MCP, imports y tests.
- [ ] T008 Registrar evidencia final de Phase 0 en `specs/006-customer-multidocument-identity/research.md` antes de cambios destructivos.

## Phase 1 - Domain tests first

- [ ] T009 Crear tests de contrato para dispatcher de identidad tipo/país/número.
- [ ] T010 Cubrir RUT válido con puntos, guion y K minúscula reutilizando `erpn_custom.chile.rut.normalize_chilean_tax_id`.
- [ ] T011 Cubrir RUT con DV inválido y valor vacío.
- [ ] T012 Investigar/documentar algoritmo CPF y seleccionar vectores de prueba válidos e inválidos confiables.
- [ ] T013 Crear tests CPF: válido, puntuado, DV inválido, longitud inválida, secuencia inválida, cero inicial.
- [ ] T014 Crear tests DNI: país obligatorio, trim, preservación de cero inicial, no conversión a entero.
- [ ] T015 Crear tests Passport: país obligatorio, valor alfanumérico y ausencia de regex global destructiva.
- [ ] T016 Crear tests de identidad compuesta: mismo número/tipo en países distintos permitido; misma identidad exacta rechazada.
- [ ] T017 Crear test que confirme que un Customer `disabled=1` sigue reservando su identidad.

## Phase 2 - Versioned Customer metadata

- [ ] T018 Crear patch/fixtures para `Customer.custom_tax_id_type` Select con opciones exactas `RUT`, `DNI`, `CPF`, `Passport`.
- [ ] T019 Crear patch/fixtures para `Customer.custom_tax_id_country` Link a `Country`.
- [ ] T020 Versionar label de `Customer.tax_id` como `Número de documento / Tax ID` o texto final equivalente aprobado sin semántica exclusiva RUT.
- [ ] T021 Mantener `tax_id`, tipo y país disponibles en Quick Entry.
- [ ] T022 Mantener `tax_id`, tipo y país disponibles como filtros administrativos según soporte Frappe.
- [ ] T023 Garantizar que el default RUT aplica a Customer nuevo sin convertir artificialmente legados vacíos en identidad completa.

## Phase 3 - Identity service

- [ ] T024 Crear módulo común de identidad dentro de `erpn_custom` sin acoplar DNI/CPF/Passport al namespace Chile.
- [ ] T025 Implementar orquestador `normalize_customer_identity(document_type, country, tax_id)` o API interna equivalente.
- [ ] T026 Para RUT, reutilizar exclusivamente la función canónica `normalize_chilean_tax_id()`.
- [ ] T027 Implementar normalizador/validador CPF separado y testeado.
- [ ] T028 Implementar normalización DNI dependiente de país con fallback genérico no destructivo v1.
- [ ] T029 Implementar normalización Passport dependiente de país con fallback genérico no destructivo v1.
- [ ] T030 Forzar país Chile en RUT desde backend.
- [ ] T031 Forzar país Brasil en CPF desde backend.
- [ ] T032 Exigir país explícito en DNI y Passport.
- [ ] T033 Implementar mensajes de error específicos por tipo, sin error `RUT inválido` para documentos extranjeros.

## Phase 4 - Customer lifecycle integration

- [ ] T034 Determinar y documentar el hook/backend event soportado en Frappe v16 para validar antes de persistir Customer.
- [ ] T035 Integrar servicio de identidad al lifecycle de Customer.
- [ ] T036 Revalidar toda la identidad al cambiar `tax_id`, tipo o país.
- [ ] T037 Confirmar que REST/Data Import/código backend también pasan por la autoridad de validación; no depender solo de JS de formulario.
- [ ] T038 Agregar ayudas UI únicamente como complemento, nunca como única validación.

## Phase 5 - Legacy migration

- [ ] T039 Crear patch idempotente de backfill de Customers existentes.
- [ ] T040 Para `tax_id` válido como RUT, asignar tipo RUT, país Chile y forma canónica.
- [ ] T041 Para `tax_id` vacío, conservar Customer sin inventar identificación y contabilizarlo como legado incompleto.
- [ ] T042 Para valor no RUT existente, registrar conflicto y NO inferir DNI/CPF/Passport.
- [ ] T043 Producir resumen del patch: total, RUT migrados, vacíos, conflictos, duplicados, errores.
- [ ] T044 Asegurar que ejecutar el patch nuevamente no altera registros correctamente migrados.

## Phase 6 - Composite uniqueness

- [ ] T045 Seleccionar mecanismo técnico final de unicidad compuesta con evidencia: índice compuesto o clave técnica derivada + unique/constraint.
- [ ] T046 Retirar la unicidad global aislada de `Customer.tax_id` de forma versionada y reversible a nivel de metadata/DB sin perder datos.
- [ ] T047 Implementar validación funcional previa con mensaje amigable al usuario.
- [ ] T048 Implementar garantía DB/transaccional que cierre carrera concurrente.
- [ ] T049 Probar misma secuencia de número bajo tipo/país distintos según contrato.
- [ ] T050 Probar duplicado exacto y verificar que solo un Customer puede persistir.
- [ ] T051 Probar duplicado contra Customer deshabilitado.

## Phase 7 - Bank matching regression

- [ ] T052 Modificar selección/indexación de Customers de Spec 004 para incluir únicamente `RUT` + Chile.
- [ ] T053 Mantener `Bank Transaction.custom_rut_del_pagador` y `custom_rut_pagador_normalizado` sin cambio semántico.
- [ ] T054 Agregar test: depósito RUT encuentra Customer RUT/Chile correcto.
- [ ] T055 Agregar test: Customer DNI numéricamente similar no entra como candidato.
- [ ] T056 Agregar test: Customer CPF no entra como candidato.
- [ ] T057 Agregar test: Customer Passport no entra como candidato.
- [ ] T058 Revisar Spec 005/código de integración en tiempo real para reutilizar el mismo filtro, sin segunda lógica paralela.

## Phase 8 - Retire legacy Server Script

- [ ] T059 Crear patch idempotente que busque el Server Script exacto `Validar y normalizar RUT Cliente`.
- [ ] T060 Si existe, desactivarlo únicamente después de que la nueva autoridad backend esté instalada y probada.
- [ ] T061 Si no existe, el patch debe continuar sin error.
- [ ] T062 Verificar que después del deploy solo existe una autoridad de validación efectiva para Customer identity.

## Phase 9 - Integration and migration tests

- [ ] T063 Test de migración de Customer RUT existente.
- [ ] T064 Test de migración de Customer vacío.
- [ ] T065 Test de migración de valor legacy no RUT -> conflicto sin inferencia.
- [ ] T066 Test de patch ejecutado dos veces.
- [ ] T067 Test de creación Customer RUT por backend.
- [ ] T068 Test de creación Customer DNI por backend.
- [ ] T069 Test de creación Customer CPF por backend.
- [ ] T070 Test de creación Customer Passport por backend.
- [ ] T071 Test de cambio RUT -> DNI sin ajustar número -> error cuando corresponda.
- [ ] T072 Test de cambio DNI -> RUT con DV inválido -> error RUT correcto.
- [ ] T073 Test de import/API path para confirmar que no se puede bypassar validación solo omitiendo UI.
- [ ] T074 Test de concurrencia para duplicate identity cuando el framework de tests lo permita; si no, prueba de constraint DB equivalente.

## Phase 10 - Manual acceptance in sandbox

- [ ] T075 Abrir Quick Entry Customer y confirmar orden Tipo -> País -> Número.
- [ ] T076 Crear Customer RUT con formato visual y comprobar forma canónica.
- [ ] T077 Crear Customer DNI con país extranjero y comprobar ausencia de módulo 11.
- [ ] T078 Crear Customer CPF y comprobar país Brasil + validador CPF.
- [ ] T079 Crear Customer Passport y comprobar país obligatorio.
- [ ] T080 Intentar duplicado exacto de cada clase relevante y comprobar rechazo.
- [ ] T081 Probar mismo número documental en países distintos donde el contrato lo permita.
- [ ] T082 Ejecutar mapping de un depósito real/controlado RUT y comprobar no regresión.
- [ ] T083 Confirmar que Customer extranjero no aparece como match bancario RUT.
- [ ] T084 Confirmar Server Script legado deshabilitado.

## Phase 11 - Documentation and closure

- [ ] T085 Actualizar `../configuracion_erpnext.md` únicamente después de implementar, sustituyendo el estado vigente RUT-only por el estado real multidocumento.
- [ ] T086 Actualizar Specs 003/004/005 donde describen `Customer.tax_id` como exclusivamente RUT, agregando referencia a Spec 006 sin reescribir evidencia histórica innecesariamente.
- [ ] T087 Documentar cualquier campo técnico de identity key e índice creado.
- [ ] T088 Documentar procedimiento de rollback y limitación: después de existir Customers extranjeros no se puede reactivar el validador global RUT como rollback seguro.
- [ ] T089 Ejecutar suite completa relevante de `erpn_custom` y registrar resultado.
- [ ] T090 Actualizar `README.md` Spec vigente solo si Miguel declara formalmente Spec 006 como frente activo/cerrado; no hacerlo por la mera creación documental.
