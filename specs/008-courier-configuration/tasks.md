# Tasks: Courier Configuration multi-provider

> **Estado de cierre (2026-09-17):** Spec 008 implementada (`16.0.6`→`16.0.9`), desplegada en `derp.at-once.cl`, UI aceptada y conectividad Chilexpress Test (coverage/rating/shipping) verificada. Esta lista queda como trazabilidad histórica; la cola vigente es `../../README.md`.

**Input**: `spec.md`, `plan.md`, `data-model.md`

**Estado**: cerrado.

## Phase 1 — Evidence gate / inspección

- [ ] T001 Leer `README.md`, Spec 008, código de Spec 007 y `despachos_transportistas.md`.
- [ ] T002 Inspeccionar read-only `Chilexpress Settings` en sandbox: DocType, fields, environment y flags de secrets seteados, sin imprimir valores.
- [ ] T003 Inspeccionar topología actual `Desktop Icon` / `Workspace Sidebar` de `MCV Chile` y `Courier`.
- [ ] T004 Confirmar archivos/fixtures/patches actuales de Spec 007.
- [ ] T005 Investigar y documentar comportamiento Frappe 16 de Password field dentro de child table.
- [ ] T006 Confirmar cómo el runtime de bench carga variables `.env` y cuál será el mecanismo soportado para resolver endpoints.
- [ ] T007 Presentar a Miguel hallazgos, archivos a modificar, estrategia de secret migration y cualquier ajuste necesario al plan.
- [ ] T008 Esperar OK explícito de Miguel antes de comenzar cambios de código.

## Phase 2 — Modelo genérico

- [ ] T009 Crear DocType `Courier Provider` con código estable, nombre y estado activo/inactivo.
- [ ] T010 Crear DocType `Courier Configuration` como documento normal, no Single.
- [ ] T011 Crear child DocType/mecanismo equivalente `Courier Credential` con almacenamiento cifrado seguro.
- [ ] T012 Implementar validación de `environment` = `Test` / `Producción`.
- [ ] T013 Implementar unicidad lógica `provider + environment`, salvo ajuste aprobado por Miguel tras evidencia de múltiples cuentas.
- [ ] T014 Implementar unicidad de `credential_key` dentro de una misma configuración.
- [ ] T015 Crear pruebas del modelo: provider único, configuraciones separadas Test/Producción, desactivación y credentials variables.

## Phase 3 — Seed Chilexpress

- [ ] T016 Crear/asegurar `Courier Provider = Chilexpress` (`provider_code` estable).
- [ ] T017 Decidir con evidencia si seed se hace por fixture, patch o ambos de manera consistente.
- [ ] T018 NO crear todavía providers Starken/FAZT salvo que Miguel lo apruebe expresamente en el plan final.

## Phase 4 — Migración heredada segura

- [ ] T019 Crear patch nuevo para Spec 008; naming previsto `v0_0_8_courier_configuration.py` salvo justificación.
- [ ] T020 Leer `environment` desde `Chilexpress Settings`.
- [ ] T021 Copiar `coverage_api_key` mediante API segura de Frappe al credential genérico correspondiente.
- [ ] T022 Copiar `rating_api_key` mediante API segura de Frappe.
- [ ] T023 Copiar `shipping_api_key` mediante API segura de Frappe.
- [ ] T024 No fallar silenciosamente ante credential ausente: preservar estado y reportar sin secreto.
- [ ] T025 Verificar presencia/recuperabilidad de secrets destino sin imprimir ni comparar en logs valores completos.
- [ ] T026 Garantizar idempotencia si provider/configuration/credentials ya existen.
- [ ] T027 Ante error de migración de secrets, abortar cambio de navegación y preservar legado.
- [ ] T028 Mantener `Chilexpress Settings` físicamente intacto después del patch.
- [ ] T029 Crear tests de migración completa, parcial, repetida y con destino preexistente.

## Phase 5 — Endpoints / entorno

- [ ] T030 Crear o actualizar `.env.example` en la ubicación confirmada por el runtime/proyecto.
- [ ] T031 Documentar variables Chilexpress Test: Coverage, Rating, Shipping.
- [ ] T032 Documentar variables Chilexpress Producción: Coverage, Rating, Shipping.
- [ ] T033 No incluir URLs reales si el proyecto las considera environment-specific/no versionables; seguir la convención de `.env.example` aprobada.
- [ ] T034 Implementar únicamente el resolver/config boundary necesario si el runtime lo requiere; no hacer requests HTTP.
- [ ] T035 Crear test de presencia/naming de configuración sin depender de endpoints externos reales.

## Phase 6 — Navegación

- [ ] T036 Actualizar `Workspace Sidebar Courier` para apuntar a `Courier Configuration` / etiqueta visible `Configuración de Couriers`.
- [ ] T037 Retirar `Chilexpress Settings` del sidebar visible sin eliminar el DocType.
- [ ] T038 Mantener `MCV Chile`, `Pagos de Clientes` y Desktop Icon `Courier` sin cambios innecesarios.
- [ ] T039 Actualizar fixtures finales de sidebar para instalaciones futuras.
- [ ] T040 Crear test de navegación final y regresión de Pagos.

## Phase 7 — Seguridad y regresión

- [ ] T041 Buscar referencias a secrets reales; confirmar que no entraron a Git, fixtures, tests o logs.
- [ ] T042 Confirmar que endpoints no quedaron hardcodeados como configuración definitiva en el modelo.
- [ ] T043 Confirmar que no se creó adapter universal dinámico.
- [ ] T044 Confirmar que no se implementaron requests a Chilexpress/Starken/FAZT.
- [ ] T045 Ejecutar suite de tests de Spec 008 y regresión relevante de Spec 007.

## Phase 8 — Release sandbox

- [ ] T046 Registrar patch en `patches.txt`.
- [ ] T047 Bump de versión según regla del repo.
- [ ] T048 Commit/push con versión correspondiente.
- [ ] T049 Desplegar en sandbox.
- [ ] T050 Ejecutar `bench --site derp.at-once.cl migrate`.
- [ ] T051 Verificar `Courier Provider = Chilexpress`.
- [ ] T052 Verificar configuración heredada migrada al environment correcto.
- [ ] T053 Verificar que las credentials destino están seteadas sin mostrarlas.
- [ ] T054 Verificar que `Chilexpress Settings` sigue existiendo como respaldo legado.
- [ ] T055 Verificar UI: `MCV Chile -> Courier -> Configuración de Couriers`.
- [ ] T056 Verificar que Pagos de Clientes no sufrió regresión.

## Phase 9 — Aceptación y cierre

- [ ] T057 Presentar resultado a Miguel y esperar aceptación operativa.
- [ ] T058 Tras aceptación, marcar Spec 008 cerrada en `spec.md` y `README.md`.
- [ ] T059 Mantener `Chilexpress Settings` deprecado pero no eliminado; su eliminación requiere decisión/Spec posterior.

## Checkpoints críticos

- **CP1** después de T007: no programar sin OK.
- **CP2** después de T025: no cambiar navegación si la migración de secretos no fue validada.
- **CP3** después de T050: no cerrar Spec sin validación visual y de secretos.

## Regla de impacto mínimo

La implementación debe corregir exclusivamente el modelo de configuración de couriers. No ampliar alcance hacia integración API, Shipment, cotización, OT/OF, labels o tracking.
