# Tasks: Atribución automática de vendedor y comisión

## Phase 1 — Evidencia
- [x] T001 Leer README y Spec 012.
- [x] T002 Inspeccionar Sales Order/Sales Team estándar de ERPNext v16 instalado.
- [x] T003 Confirmar cálculo nativo de commission_rate/incentives.
- [x] T004 Confirmar Employee.user_id y Sales Person.employee.
- [x] T005 Elegir before_validate vs validate con evidencia.
- [x] T006 Presentar plan técnico final a Miguel y esperar OK.

## Phase 2 — Resolver vendedor
- [x] T007 Crear módulo server-side de asignación.
- [x] T008 Resolver session user -> Employee habilitado.
- [x] T009 Resolver Employee -> Sales Person habilitado.
- [x] T010 No elegir arbitrariamente ante múltiples coincidencias.
- [x] T011 Manejar usuario no comercial sin atribución ficticia.

## Phase 3 — Sales Team
- [x] T012 Si sales_team está vacío, agregar Sales Person.
- [x] T013 Contribution = 100%.
- [x] T014 Usar commission_rate estándar del Sales Person/ERPNext.
- [x] T015 No sobrescribir Sales Team existente.
- [x] T016 Garantizar idempotencia en re-save.

## Phase 4 — Hook
- [x] T017 Registrar doc_event Sales Order.
- [x] T018 No modificar core.
- [x] T019 No introducir Client Script como fuente de verdad.

## Phase 5 — Tests
- [x] T020 Test Amaranta 1%.
- [x] T021 Test CLP 50.000 -> CLP 500.
- [x] T022 Test re-save sin duplicación.
- [x] T023 Test Sales Team manual preservado.
- [x] T024 Test Administrator/usuario sin Sales Person.
- [x] T025 Test Employee sin Sales Person.
- [x] T026 Test ambigüedad de Sales Person.
- [x] T027 Regresión Sales Order (hook aislado; no altera credit).

## Phase 6 — ComercialFRA
- [x] T028 Reproducir/confirmar PermissionError de sales_order_credit con ComercialFRA.
- [x] T029 Si se confirma, separar permisos de consulta/aplicar vs reversión.
- [x] T030 No ampliar acceso contable general.

Nota T028–T030: `ComercialFRA` ya está en `ALLOWED` de `sales_order_credit.py`; no se requirió cambio en este corte.

## Phase 7 — Sandbox
- [x] T031 Deploy sandbox.
- [x] T032 Amaranta crea OV sin tocar Sales Team.
- [x] T033 Verificar Amaranta 100% / 1%.
- [x] T034 Verificar incentivo estándar.
- [x] T035 Submit y reabrir.
- [x] T036 Verificar ausencia de duplicación.

## Phase 8 — Release
- [x] T037 Bump PATCH.
- [x] T038 Actualizar README con estado real.
- [x] T039 Commit.
- [x] T040 Push version-16.
- [x] T041 Confirmar despliegue.
- [x] T042 Aceptación de Miguel.

**Cierre 2026-09-23:** `SAL-ORD-2026-00015` — Amaranta Fernandez / 100% / 1% / Incentives 500. Histórico `SAL-ORD-2026-00014` sin Sales Team (sin migración retroactiva). Decisión de negocio: anotar en OV; pagar solo OVs entregadas (remuneraciones). **Spec Closed.**
