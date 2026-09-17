# Tasks: B2C — Cliente Individual = Contacto espejo

**Input**: `spec.md`, `plan.md`  
**Estado**: implementado en código (`16.0.22`); pendiente migrate + aceptación Desk.

## Phase 0 — Activación

- [x] T001 Declarar Spec 010 vigente en `README.md`
- [x] T002 Congelar decisiones: flag espejo, adopción primary, backfill patch
- [x] T003 Escribir `plan.md` / `tasks.md`

## Phase 1 — Campo + motor

- [x] T004 Patch Custom Field `Contact.custom_is_customer_mirror`
- [x] T005 Servicio create/find/adopt/sync idempotente
- [x] T006 Hooks `Customer` after_insert / on_update
- [x] T007 Tests unitarios de helpers + reglas Individual/Company

## Phase 2 — Backfill

- [x] T008 Patch backfill Individual sin Contacto
- [x] T009 Re-ejecución sin duplicados (idempotente)
- [x] T010 Whitelist `erpn_custom.customer_contact_mirror.service.run_backfill`

## Phase 3 — Cierre

- [x] T011 Bump `__version__` + commit/push
- [ ] T012 Verificación Desk: alta Individual → Contacto en Shipment
- [ ] T013 Actualizar Spec status al aceptar Miguel
