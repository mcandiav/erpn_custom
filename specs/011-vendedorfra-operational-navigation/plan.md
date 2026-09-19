# Implementation Plan: Navegación operacional VendedorFRA

**Branch**: `version-16` | **Date**: 2026-09-19 | **Spec**: [`spec.md`](./spec.md)

**Estado**: implementado en código (2026-09-19). Pendiente build/cache en sitio + pruebas.

## Summary

Crear un guard de navegación mínimo en `erpn_custom` para que usuarios operativos `ComercialFRA` no trabajen desde el Desktop general `/desk` y terminen en el Workspace `/desk/comercialfra`.

No se modifican permisos, Module Profile, Desktop Icons ni core.

## Architecture

```text
Frappe Desk
  └─ app_include_js → operational_navigation.js
       ├─ resolve user policy
       ├─ detect exact Desk root
       └─ redirect → /desk/comercialfra
```

## Technical decisions proposed

| Decisión | Valor |
|---|---|
| Capa | Cliente Desk, asset global de `erpn_custom` |
| Integración | `app_include_js` |
| Target actual | `ComercialFRA` |
| Elegibilidad | rol `ComercialFRA` + default workspace compatible + exclusión admin |
| Core | no modificar |
| DB/schema | sin cambios |
| Email piloto | no hardcodear |
| Seguridad | sin cambios; sigue en Role Permissions |
| Extensibilidad | política central preparada para más workspaces FRA |
| Rollback | quitar asset/hook |

## Phase 0 — Verificación técnica

Antes de escribir código, el Programador debe confirmar en la versión instalada:

1. valor real de `frappe.get_route()` en `/desk`;
2. valor real en `/desk/comercialfra`;
3. forma de `frappe.boot.user.default_workspace`;
4. evento/API correcta para escuchar cambios de router;
5. existencia de cualquier `app_include_js` previo para no sobrescribirlo.

## Phase 1 — Guard

Implementar una unidad pequeña con dos responsabilidades:

1. `is_operational_user()`
2. `redirect_operational_home_if_needed()`

La condición debe ser explícita y testeable.

## Phase 2 — Integración Frappe

- registrar asset en `hooks.py`;
- build/cache/migrate solo si el flujo normal de la app lo requiere;
- no tocar Frappe/ERPNext core.

## Phase 3 — Validación

Validar con:

- Amaranta;
- Administrator;
- usuario no ComercialFRA;
- navegación por Customer / Sales Order / Item;
- Home/logo;
- URL manual `/desk`;
- Browser Back/Forward;
- consola JS.

## Rollback

Retirar el asset de `app_include_js` y rebuild/cache. Sin rollback de datos.
