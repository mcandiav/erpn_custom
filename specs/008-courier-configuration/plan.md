# Implementation Plan: Courier Configuration multi-provider

**Branch**: `version-16` | **Date**: 2026-09-17 | **Spec**: [`spec.md`](./spec.md)

**Input**: `specs/008-courier-configuration/spec.md`

**Estado**: borrador técnico para revisión del Programador; no autoriza implementación sin inspección real + OK explícito de Miguel.

## Summary

Corregir el acoplamiento heredado de Spec 007 (`Courier -> Chilexpress Settings`) creando un modelo genérico multi-courier:

```text
MCV Chile
└── Courier
    └── Configuración de Couriers
```

con:

- `Courier Provider` como maestro;
- `Courier Configuration` como DocType normal;
- credenciales variables por provider en estructura genérica segura;
- endpoints externos fuera del modelo de datos, resueltos desde `.env`;
- adapters futuros específicos por courier, fuera de alcance de Spec 008;
- migración conservadora desde `Chilexpress Settings` sin eliminar el legado.

## Technical Context

**Language/Version**: Python 3 / Frappe 16 / ERPNext 16

**Primary Dependencies**: Frappe DocType, Password fields, Workspace Sidebar, patches, app `erpn_custom`

**Storage**: MariaDB del site; secretos mediante mecanismo cifrado de Frappe

**Target**: sandbox `derp.at-once.cl`

**Constraints**:

- no llamadas HTTP externas;
- no borrar `Chilexpress Settings` en esta Spec;
- no exponer secretos;
- no cambiar topología raíz `MCV Chile` de Spec 007;
- no hardcodear endpoints;
- no construir adapter universal dinámico.

## Constitution / architecture check

| Gate | Resultado esperado |
|---|---|
| Cambios dentro de `erpn_custom` | PASS |
| No modificar core | PASS |
| Multi-courier desde modelo | PASS |
| Endpoints fuera de DocType | PASS |
| Secrets fuera de Git/logs | PASS |
| Adapter real fuera de alcance | PASS |
| Migración reversible/conservadora | PASS |

## Evidence gate obligatorio antes de código

El Programador debe inspeccionar y documentar:

1. estado actual de `Chilexpress Settings` en sandbox;
2. `environment` actual;
3. cuáles de las tres Password keys están seteadas, sin leer/imprimir valores;
4. metadata real de los fields Password;
5. topología actual del sidebar `Courier` después de Spec 007;
6. archivos/fixtures creados por Spec 007;
7. mecanismo real del runtime para variables `.env`;
8. comportamiento Frappe 16 de Password en child DocType.

Si el patrón de credenciales propuesto no es seguro/viable en child table, detenerse y presentar alternativa genérica antes de implementar.

## Technical decisions ya congeladas

1. `Courier Provider` no será Select.
2. `Courier Configuration` no será Single.
3. Configuración soportará Test/Producción por provider.
4. Credenciales deben ser genéricas por clave, no columnas específicas por courier.
5. Endpoints se resuelven desde `.env`.
6. `.env.example` se versiona sin valores reales.
7. Cada futura API puede requerir Adapter específico.
8. Spec 008 no implementa Adapter operativo.
9. `Chilexpress Settings` se conserva como legado después de migrar.
10. `Courier` cambia solo su destino de navegación.

## Decisiones que debe cerrar el Programador

- nombres definitivos de DocTypes/fields según convención Frappe;
- patrón seguro de secret storage variable;
- índice/validación de unicidad provider + environment;
- estrategia exacta de migración Password → Password;
- mecanismo runtime exacto para lectura de `.env`;
- fixtures/patches requeridos;
- seed de Chilexpress;
- si crear Starken/FAZT inactivos o no;
- validación de credenciales migradas sin revelar valores.

## Project Structure prevista

```text
specs/008-courier-configuration/
├── spec.md
├── plan.md
├── data-model.md
└── tasks.md

erpn_custom/
├── patches.txt
├── patches/
│   └── v0_0_8_courier_configuration.py          # esperado, confirmar naming
├── chile/
│   ├── doctype/
│   │   ├── courier_provider/
│   │   ├── courier_configuration/
│   │   └── courier_credential/
│   └── test_courier_configuration.py
├── workspace_sidebar/
│   └── courier.json                              # update target
└── ...

.env.example                                      # ubicación exacta a confirmar
```

No modificar archivos históricos de Spec 007 como mecanismo principal de migración; hacer patch nuevo y fixtures finales coherentes.

## Migration strategy

### Etapa A — Crear modelo nuevo

1. Crear DocTypes genéricos.
2. Crear reglas de unicidad/validación.
3. Crear `Courier Provider = Chilexpress`.
4. Dejar navegación actual sin cambios durante esta etapa.

### Etapa B — Migrar Chilexpress

1. Leer `environment` heredado.
2. Leer secretos mediante API segura de Frappe únicamente para copiarlos.
3. Crear/upsert `Courier Configuration` destino.
4. Crear/upsert credenciales destino.
5. Verificar que las claves destino están configuradas y recuperables sin imprimirlas.
6. Ante cualquier falla, no cambiar navegación ni borrar legado.

### Etapa C — Endpoints de infraestructura

1. Crear/actualizar `.env.example` con las variables Chilexpress requeridas.
2. Confirmar mecanismo de carga del `.env` real.
3. No incluir valores reales.
4. No efectuar requests.

### Etapa D — Navegación

Solo tras migración exitosa:

```text
Courier
└── Configuración de Couriers
```

Retirar enlace visible a `Chilexpress Settings`, pero conservar el DocType y sus datos.

### Etapa E — Validación

- modelo genérico visible;
- Chilexpress migrado;
- environment preservado;
- tres secrets preservados cuando estaban presentes;
- legado aún existe;
- sidebar correcto;
- Pagos/MCV Chile sin regresión;
- patch repetible.

## Testing strategy

### Modelo

- `provider_code` único;
- provider + environment no duplicable bajo modelo aprobado;
- environment solo Test/Producción;
- provider desactivable;
- credenciales con claves distintas por provider sin modificar esquema.

### Migración

- fuente completa;
- fuente con una credential ausente;
- ejecución repetida;
- destino preexistente;
- fuente inexistente;
- falla de secret retrieval → abortar cambio de navegación;
- ningún secreto en logs/excepciones.

### Navegación

- `MCV Chile -> Courier` intacto;
- sidebar Courier contiene configuración genérica;
- no contiene Chilexpress Settings como acceso principal;
- Pagos de Clientes intacto.

### Endpoints

- nombres esperados documentados en `.env.example`;
- ninguna URL hardcodeada como configuración definitiva en modelo/adapter de esta Spec.

## Deployment order

1. inspección y plan final del Programador;
2. OK Miguel;
3. implementar DocTypes/tests;
4. implementar patch migración;
5. actualizar `.env.example`;
6. actualizar navegación;
7. ejecutar tests;
8. bump de versión;
9. commit/push;
10. deploy sandbox;
11. `bench --site derp.at-once.cl migrate`;
12. verificar configuración + secretos sin mostrarlos;
13. aceptación Miguel;
14. cerrar 008.

## Rollback philosophy

Mientras `Chilexpress Settings` siga intacto, el rollback conceptual de navegación es posible sin reingresar credenciales.

Spec 008 no debe destruir la fuente heredada. Una futura Spec de limpieza podrá eliminarla únicamente cuando el nuevo modelo haya sido usado y aceptado.

## Out of scope

- requests HTTP;
- adapters funcionales;
- Shipment integration;
- cotización;
- OT/OF/labels/tracking;
- eliminación del legacy DocType;
- Starken/FAZT operativo.
