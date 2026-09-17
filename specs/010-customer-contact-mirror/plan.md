# Implementation Plan: B2C — Cliente Individual = Contacto espejo

**Branch**: `version-16` | **Date**: 2026-09-17 | **Spec**: [`spec.md`](./spec.md)

**Estado**: activo — OK Miguel 2026-09-17.

## Summary

Backend silencioso: al crear/actualizar `Customer` con `customer_type = Individual`, asegurar un `Contact` primario espejo ligado (Dynamic Link) para que `Shipment.delivery_contact_name` lo liste sin UI nueva.

```text
Customer Individual (after_insert / on_update)
  -> Contact espejo (custom_is_customer_mirror + is_primary_contact)
  -> Dynamic Link → Customer
  -> Customer.customer_primary_contact
```

## Technical decisions (locked)

| Decisión | Valor |
|---|---|
| Marcador espejo | `Contact.custom_is_customer_mirror` (Check) |
| Primary manual preexistente | Adoptar: setear flag + sync (no duplicar) |
| Company | No-op |
| UI | Ninguna |
| Backfill | Patch `post_model_sync` + función re-ejecutable |
| Core ERPNext | Sin modificar |

## Architecture

- Paquete: `erpn_custom.customer_contact_mirror`
- Hooks en `hooks.py` → `after_insert` / `on_update` de `Customer`
- Campos espejados: `customer_name` → first/last; `email_id`; `mobile_no`
- Idempotencia: buscar por flag; si no, primary linkado; si no, crear

## Out of scope

- Shipment / Chilexpress contract changes
- Espejo Company
- Quitar reqd de `delivery_contact_name`
