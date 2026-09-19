# Tasks: Navegación operacional VendedorFRA

**Input**: `spec.md`, `plan.md`

**Estado**: implementación lista en código; pendiente build/cache en sitio + pruebas operativas + OK de cierre.

## Phase 0 — Análisis

- [x] T001 Leer README + Spec 011 completa.
- [x] T002 Verificar router real de Frappe v16 en `/desk` y `/desk/comercialfra`.
- [x] T003 Verificar forma real de `frappe.boot.user.default_workspace`.
- [x] T004 Confirmar mecanismo de evento/router a usar.
- [x] T005 Presentar plan técnico y plan de pruebas a Miguel.
- [x] T006 Obtener OK explícito de Miguel.

## Phase 1 — Implementación

- [x] T007 Crear asset JS de navegación operacional con responsabilidad única.
- [x] T008 Implementar política de elegibilidad sin hardcodear usuario.
- [x] T009 Implementar detección estricta de Desktop raíz.
- [x] T010 Implementar redirección a `ComercialFRA` sin loops.
- [x] T011 Registrar asset mediante `app_include_js` sin sobrescribir otros includes.

## Phase 2 — Pruebas técnicas

- [ ] T012 Amaranta: login limpio → ComercialFRA.
- [ ] T013 Amaranta: URL manual `/desk` → ComercialFRA.
- [ ] T014 Amaranta: Home/logo desde Customer/Sales Order → ComercialFRA.
- [ ] T015 Amaranta: rutas funcionales permitidas no redirigen.
- [ ] T016 Browser Back/Forward sin loop.
- [ ] T017 Consola sin errores.
- [ ] T018 Administrator: `/desk` permanece estándar.
- [ ] T019 Usuario no ComercialFRA: comportamiento estándar.

## Phase 3 — Aceptación y cierre

- [ ] T020 Verificación operativa con Miguel/Amaranta.
- [ ] T021 Confirmar que permisos no cambiaron.
- [ ] T022 Documentar resultado real en Spec/README.
- [ ] T023 Bump de versión según regla del repo.
- [ ] T024 Commit + push con código y Spec asociados.
