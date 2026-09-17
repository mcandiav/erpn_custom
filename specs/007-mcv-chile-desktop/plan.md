# Implementation Plan: MCV Chile Desktop

**Branch**: `version-16` | **Date**: 2026-09-17 | **Spec**: [`spec.md`](./spec.md)

**Input**: Feature specification from `specs/007-mcv-chile-desktop/spec.md`

**Estado**: plan técnico aprobado por Miguel tras inspección sandbox; **implementado y cerrado** 2026-09-17 (`16.0.5`, migrate OK).

## Summary

Normalizar el Desktop de `erpn_custom` a la estructura versionada:

```text
MCV Chile
├── Pagos de Clientes
└── Courier
    └── Chilexpress Settings
```

Mediante un **patch nuevo** idempotente `v0_0_7_mcv_chile_desktop.py`, fixtures alineadas, limpieza segura de artefactos manuales UI, invalidación de caches y tests de topología. Sin APIs Chilexpress, sin tocar Password fields, sin modificar Frappe/ERPNext core.

## Technical Context

**Language/Version**: Python 3 (Frappe 16 / ERPNext 16)

**Primary Dependencies**: Frappe Desk (`Desktop Icon`, `Workspace Sidebar`, `Workspace`), app `erpn_custom`

**Storage**: MariaDB del site `derp.at-once.cl` (metadatos Desk / Singles; no datos de negocio de pagos)

**Testing**: `unittest` bajo `erpn_custom/` (mismo patrón que Specs previas)

**Target Platform**: Sandbox `derp.at-once.cl` (VM ERP, bench `/home/n8n/frappe-bench`)

**Project Type**: Frappe app customization (`erpn_custom`)

**Constraints**:

- Patch nuevo; no reescribir `v0_0_1_chile_desktop_icons.py` como mecanismo de deploy.
- Idempotencia / upsert; sin duplicar sidebars ni icons.
- No leer/loguear/serializar `coverage_api_key`, `rating_api_key`, `shipping_api_key`.
- No recrear el DocType `Chilexpress Settings` (Custom DocType creado por UI).
- Collation case-insensitive: limpiar `MCV CHILE` **antes** de crear `MCV Chile`.

**Scale/Scope**: Solo navegación Desktop/Sidebar; 1 patch + fixtures + tests.

## Constitution Check

| Gate | Resultado |
|---|---|
| Cambios solo en `erpn_custom` | PASS |
| Sin core Frappe/ERPNext | PASS |
| Spec vigente = 007 (README) | PASS |
| Credenciales no en código/logs/tests | PASS |
| VP / evidencia site antes de mutar | PASS (inspección 2026-09-17) |
| Speckit plan/tasks antes de código | PASS (este documento) |

## Evidence gate (sandbox 2026-09-17)

Inspección read-only vía `bench console` en `derp.at-once.cl`:

### Desktop Icon

| name | tipo | parent | standard | app | notas |
|---|---|---|---|---|---|
| `Chile` | Folder | — | 1 | erpn_custom | `earth` / `blue`, idx 0 |
| `MCV CHILE` | Link → sidebar `MCV CHILE` | — | 0 | null | raíz duplicada, `gray` |
| `Pagos de Clientes` | Link → sidebar Pagos | `Chile` | 1 | erpn_custom | idx 1 |
| `Courier` | — | — | — | — | **no existe** |
| `MCV Chile` | — | — | — | — | **no existe** |

### Workspace Sidebar

| name | standard | items |
|---|---|---|
| `Pagos de Clientes` | 1 | Pagos, Vinculador, (resto vigente en site/fixture) — **conservar** |
| `MCV CHILE` | 0 | 1 auto-link Workspace `MCV CHILE` |
| `Courier` | — | **no existe** |

### Workspace `MCV CHILE`

- `title`: `MCV Chile`
- `content`: `[]` (`content_is_placeholder=true`)
- links/shortcuts: 0  
→ **eliminable** como artefacto temporal.

### Chilexpress Settings

- DocType existe, `issingle=1`, `custom=1`, `module=Chile`
- Campos: `environment` (Select), tres Password keys
- `environment` actual: `Producción`
- Las tres keys están seteadas (`*_set=true`); **no se leyeron valores**
- **No** está en el árbol de código `erpn_custom` → fuera de alcance versionarlo en Spec 007; solo enlazar

## Technical decisions (cerradas)

1. **Raíz visible**: crear Folder `MCV Chile` (`name`=`label`=`MCV Chile`, `icon=earth`, `bg_color=blue`, `standard=1`, `app=erpn_custom`, `idx=0`).
2. **Orden de limpieza (collation)**: eliminar primero Desktop Icon + Workspace Sidebar + Workspace `MCV CHILE`; después insertar `MCV Chile`.
3. **`Chile`**: tras reparentar hijos, eliminar (preferido) o `hidden=1` si delete falla por links; no debe quedar carpeta raíz duplicada.
4. **`Pagos de Clientes`**: solo cambiar `parent_icon` → `MCV Chile`; conservar `link_to` / `link_type` / standard / app; recrear si faltara.
5. **`Courier`**: upsert Workspace Sidebar (módulo `Chile`, app `erpn_custom`, standard=1) con un item `DocType` → `Chilexpress Settings`; Desktop Icon Link hijo de `MCV Chile`, idx=2.
6. **Single DocType**: mismo patrón que Settings de Pagos (`link_type=DocType`); no fixtures del DocType custom.
7. **Caches**: `frappe.cache.delete_key("desktop_icons")` y `frappe.cache.delete_key("bootinfo")`.
8. **Patch histórico `v0_0_1`**: no modificar como deploy; el nuevo patch es la autoridad de la topología final.
9. **Fixtures**: alinear JSON estándar con el estado final para installs futuros (`desktop_icon/mcv_chile.json`, actualizar Pagos, agregar Courier + `workspace_sidebar/courier.json`; retirar `chile.json`).

## Project Structure

### Documentation (this feature)

```text
specs/007-mcv-chile-desktop/
├── spec.md
├── plan.md              # this file
└── tasks.md
```

### Source Code (implementation targets)

```text
erpn_custom/
├── patches.txt
├── patches/
│   └── v0_0_7_mcv_chile_desktop.py    # NEW
├── desktop_icon/
│   ├── chile.json                     # REMOVE or replace
│   ├── mcv_chile.json                 # NEW
│   ├── pagos_de_clientes.json         # UPDATE parent_icon
│   └── courier.json                   # NEW
├── workspace_sidebar/
│   ├── pagos_de_clientes.json         # keep (no functional change required)
│   └── courier.json                   # NEW
├── chile/
│   └── test_mcv_chile_desktop.py      # NEW topology/idempotency tests
└── __init__.py                        # bump 16.0.4 → 16.0.5 at release
```

## Complexity Tracking

Sin violaciones que requieran excepción. El Custom DocType UI de Chilexpress Settings se deja fuera del repo a propósito (alcance Spec 007 = navegación).

## Patch algorithm (normative)

```text
1. cleanup_manual_mcv_chile()
   - if Desktop Icon "MCV CHILE" exists → delete
   - if Workspace Sidebar "MCV CHILE" exists → delete
   - if Workspace "MCV CHILE" exists AND content placeholder/empty → delete
   - if Workspace has unexpected content → preserve + frappe.log_error (do not delete)

2. upsert_folder_mcv_chile()
   - Desktop Icon Folder "MCV Chile" (earth/blue/standard/app)

3. upsert_pagos_de_clientes_icon()
   - parent_icon = "MCV Chile"
   - link_to = "Pagos de Clientes", link_type = Workspace Sidebar

4. upsert_courier_sidebar()
   - items = [{ DocType → Chilexpress Settings }]  # replace set, no append-duplicates
   - only if DocType "Chilexpress Settings" exists; else log and skip item (fail soft with clear log)

5. upsert_courier_icon()
   - parent_icon = "MCV Chile", idx = 2

6. remove_legacy_chile_folder()
   - delete Desktop Icon "Chile" if present (after children reparented)

7. clear caches desktop_icons + bootinfo
```

Idempotencia: segunda ejecución produce el mismo grafo sin duplicar items ni icons.

## Testing strategy

- Unit/integration tests calling patch helpers / `execute()` over DB de test:
  - topología final exacta;
  - ausencia de `Chile` raíz y de `MCV CHILE` manual;
  - sidebar Courier con un solo item Chilexpress Settings;
  - doble `execute()` sin duplicados;
  - no assert de valores Password (solo opcional `db.exists` DocType).
- Manual sandbox post-migrate: Desktop visual, Pagos intacto, Courier → Single form, keys siguen seteadas (verificación por UI/`*_set`, sin pegar secretos).

## Deployment

1. Implementar + tests locales/CI según disponibilidad.
2. Bump `__version__` a `16.0.5`.
3. Commit + push rama deploy (`version-16`) con subject `[16.0.5] …`.
4. En VM: pull/get-app update + `bench --site derp.at-once.cl migrate`.
5. Validación visual + confirmación credenciales.
6. Cerrar Spec 007 en README solo tras aceptación operativa de Miguel.

## Out of scope (explicit)

- Versionar/mover a código el Custom DocType `Chilexpress Settings`.
- Consumo de APIs Chilexpress, Starken, FAZT.
- Cambios a matching/pagos/identidad.
- Edición del patch `v0_0_1_chile_desktop_icons.py` como solución de despliegue.
