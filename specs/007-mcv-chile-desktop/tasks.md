# Tasks: MCV Chile Desktop

**Input**: `specs/007-mcv-chile-desktop/spec.md` + `plan.md`

**Prerequisites**: plan.md aprobado; inspección sandbox 2026-09-17 registrada en plan.md

**Notes**:

- Rutas relativas a la raíz del repo `erpn_custom/`.
- No modificar Frappe/ERPNext core.
- No recrear ni mutar Password fields de `Chilexpress Settings`.
- No editar `patches/v0_0_1_chile_desktop_icons.py` como mecanismo de deploy.
- Ejecutar implementación solo tras OK explícito de Miguel para programar (además del OK de Speckit ya otorgado).

## Phase 0 - Evidence (completada)

- [x] T001 Inspeccionar Desktop Icons `Chile`, `Pagos de Clientes`, `MCV CHILE`, ausencia de `Courier`/`MCV Chile`.
- [x] T002 Inspeccionar Workspace Sidebars `Pagos de Clientes` y `MCV CHILE`; confirmar ausencia de `Courier`.
- [x] T003 Confirmar Workspace `MCV CHILE` con `content=[]` (placeholder vacío → eliminable).
- [x] T004 Confirmar DocType Single custom `Chilexpress Settings` (módulo Chile) y flags `*_api_key_set` sin leer secretos.
- [x] T005 Registrar evidencia y decisiones en `plan.md` (collation `MCV CHILE` vs `MCV Chile`).

## Phase 1 - Tests first

- [ ] T006 Crear `erpn_custom/chile/test_mcv_chile_desktop.py` con contrato de topología final.
- [ ] T007 [P] [US1] Test: existe Folder `MCV Chile` (`standard=1`, `app=erpn_custom`, sin parent).
- [ ] T008 [P] [US1] Test: no existe Desktop Icon raíz visible `Chile` ni duplicado `MCV CHILE`.
- [ ] T009 [P] [US2] Test: `Pagos de Clientes` tiene `parent_icon=MCV Chile` y `link_to=Pagos de Clientes`.
- [ ] T010 [P] [US3] Test: existe Sidebar `Courier` con exactamente un item DocType → `Chilexpress Settings`.
- [ ] T011 [P] [US3] Test: Desktop Icon `Courier` hijo de `MCV Chile`.
- [ ] T012 [US4] Test: ejecutar lógica del patch dos veces sin duplicar icons/items.
- [ ] T013 [US4] Test: no se invoca lectura de Password values en el patch (contrato por diseño / no asserts de secretos).

## Phase 2 - Patch and fixtures

- [ ] T014 Crear `erpn_custom/patches/v0_0_7_mcv_chile_desktop.py` con helpers upsert/cleanup según algoritmo de `plan.md`.
- [ ] T015 Registrar `erpn_custom.patches.v0_0_7_mcv_chile_desktop` en `erpn_custom/patches.txt` sección `[post_model_sync]` (después de patches existentes).
- [ ] T016 Implementar `cleanup_manual_mcv_chile()`: borrar Desktop Icon + Sidebar `MCV CHILE`; borrar Workspace solo si placeholder/vacío; si contenido inesperado → preservar + `frappe.log_error`.
- [ ] T017 [US1] Implementar upsert Folder `MCV Chile` (`earth`, `blue`, `idx=0`).
- [ ] T018 [US2] Reparentar/upsert Desktop Icon `Pagos de Clientes` → `parent_icon=MCV Chile` (`idx=1`).
- [ ] T019 [US3] Upsert Workspace Sidebar `Courier` (módulo `Chile`, app `erpn_custom`, standard=1) con item único Chilexpress Settings; set items (no append acumulativo).
- [ ] T020 [US3] Upsert Desktop Icon `Courier` (`parent_icon=MCV Chile`, `idx=2`, link Workspace Sidebar `Courier`).
- [ ] T021 [US1] Eliminar Desktop Icon legado `Chile` tras reparentar (fallback `hidden=1` solo si delete bloqueado).
- [ ] T022 Invalidar caches `desktop_icons` y `bootinfo`.
- [ ] T023 [P] Crear fixture `erpn_custom/desktop_icon/mcv_chile.json`.
- [ ] T024 [P] Actualizar `erpn_custom/desktop_icon/pagos_de_clientes.json` (`parent_icon=MCV Chile`).
- [ ] T025 [P] Crear `erpn_custom/desktop_icon/courier.json`.
- [ ] T026 [P] Crear `erpn_custom/workspace_sidebar/courier.json`.
- [ ] T027 Retirar `erpn_custom/desktop_icon/chile.json` para que sync futuro no regenere la carpeta antigua.

## Phase 3 - Verification and release

- [ ] T028 Ejecutar tests de `test_mcv_chile_desktop` (y suite relevante si aplica) hasta verde.
- [ ] T029 Bump `erpn_custom/__init__.py` `__version__` `16.0.4` → `16.0.5`.
- [ ] T030 Commit + push a GitHub en rama de deploy con subject `[16.0.5] …`.
- [ ] T031 En VM ERP: actualizar app y `bench --site derp.at-once.cl migrate`.
- [ ] T032 [US1] Validar Desktop: una sola raíz `MCV Chile`; sin `Chile` ni `MCV CHILE` duplicados.
- [ ] T033 [US2] Validar Pagos: sidebar y accesos operativos intactos.
- [ ] T034 [US3] Validar Courier → abre Single `Chilexpress Settings`.
- [ ] T035 [US4] Confirmar `environment` y que las tres keys siguen seteadas (sin pegar secretos en chat/docs).
- [ ] T036 Actualizar `README.md` (Spec vigente / cierre 007) solo tras aceptación operativa de Miguel.
- [ ] T037 Marcar Spec 007 status implementada/cerrada en `spec.md` tras aceptación.

## Checkpoint order (Spec §18)

1. Evidence (Phase 0) ✅  
2. Tests (Phase 1)  
3. Patch + fixtures (Phase 2)  
4. Run tests  
5. Deploy + migrate  
6. Visual + credentials check  
7. Close Spec
