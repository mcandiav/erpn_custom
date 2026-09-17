# Feature Specification: B2C — Cliente Individual = Contacto espejo

**Feature Branch**: `[010-customer-contact-mirror]`

**Created**: 2026-09-17

**Status**: Draft — decisión de negocio acordada; pendiente plan técnico + OK de implementación

**Parent context**: `006-customer-multidocument-identity`, `009-chilexpress-shipment-integration`, operación Fragallardo B2C

## 0. Regla de trabajo

1. Leer `README.md`, esta Spec y el DocType `Customer` / `Contact` real en ERPNext v16.
2. Presentar plan técnico por etapas + pruebas.
3. Esperar OK explícito de Miguel antes de programar.
4. No modificar Frappe/ERPNext core.
5. No quitar la obligatoriedad de Contacto en `Shipment` (decisión descartada a favor del espejo silencioso).

## 1. Problema

Fragallardo opera **B2C**: el Cliente Individual es quien compra y quien recibe en ~99% de los casos.

ERPNext exige un DocType **Contact** ligado al Cliente para el campo obligatorio de entrega en `Shipment` (y otros flujos). Hoy el operador debe crear Contacto a mano; si no queda ligado al Cliente, el link del Envío no lo lista. Eso duplica trabajo y genera fricción operativa sin valor de negocio B2C.

## 2. Objetivo

Para `Customer` con `customer_type = Individual`:

- al **crear** el Cliente, crear automáticamente un **Contacto primario** espejo (nombre, email, teléfono) ligado al Cliente;
- al **actualizar** esos datos en el Cliente, sincronizar el Contacto espejo;
- que el Envío / Chilexpress sigan usando el Contacto estándar de ERPNext sin cambio de UI;
- un **backfill** una vez para clientes Individual existentes sin Contacto ligado.

No aplica a `Customer` tipo **Company** (B2B futuro intacto).

## 3. Decisión arquitectónica congelada

### 3.1 Enfoque elegido: backend silencioso

```text
Customer Individual (after_insert / on_update)
        ↓
Contact primario espejo (is_primary_contact)
        ↓
Dynamic Link → Customer
        ↓
Shipment.delivery_contact_name lo encuentra filtrado por Cliente
```

- Cero UI nueva (ni checkbox ni botón obligatorio).
- No se elimina la obligatoriedad de Contacto en Shipment.
- No se inventa un segundo modelo de “destinatario”.

### 3.2 Alternativas descartadas (por ahora)

| Alternativa | Motivo de descarte |
|---|---|
| Quitar obligatoriedad de Contacto en Envío | Chilexpress y otros módulos esperan Contacto; desplaza el problema al adaptador |
| Solo botón “Usar datos del cliente” en Envío | No arregla alta ni los ~1000 existentes |
| Checkbox visible “Es también el contacto” | Más UI; el espejo silencioso basta para B2C |

### 3.3 Datos a espejar

Desde `Customer` hacia `Contact` primario:

- nombre completo / `customer_name` → nombre del Contacto;
- `email_id` (si existe en Customer) → email del Contacto;
- `mobile_no` / teléfono disponible en Customer → móvil/teléfono del Contacto.

Si el Cliente no tiene email/teléfono al crear, el Contacto igual se crea con el nombre; se completa en sync cuando el Cliente los gane.

### 3.4 Idempotencia y no pisar Contactos humanos

- Si ya existe un Contacto primario ligado al Cliente Individual, **no** crear otro.
- Sync solo actualiza el Contacto marcado como espejo/primario gestionado por esta feature (criterio técnico a fijar en plan: p. ej. flag custom mínimo o convención “único primary link”).
- Si el operador crea un Contacto adicional (ej. “Carlos el marido”), ese Contacto **no** se borra ni se sobrescribe; el espejo primario sigue siendo el del Cliente.

## 4. User Stories

### US1 — Alta manual de Cliente Individual (Priority: P1)

Como operador, al crear un Cliente Individual a mano, quiero que el Contacto de entrega exista solo, para poder usarlo en el Envío sin pasos extra.

**Acceptance**:

1. **Given** un Cliente Individual nuevo con nombre (y opcionalmente email/teléfono), **When** se guarda, **Then** existe un Contacto ligado a ese Cliente y aparece en el link de Contacto del Shipment filtrado por ese Cliente.
2. **Given** un Cliente Company nuevo, **When** se guarda, **Then** esta feature **no** crea Contacto automático.

### US2 — Sync al actualizar Cliente (Priority: P1)

Como operador, si cambio email o teléfono del Cliente Individual, quiero que el Contacto espejo se actualice.

**Acceptance**:

1. **Given** Cliente Individual con Contacto espejo, **When** cambio `mobile_no` o email en el Cliente y guardo, **Then** el Contacto espejo refleja los nuevos valores.
2. **Given** un segundo Contacto manual ligado al mismo Cliente, **When** actualizo el Cliente, **Then** ese segundo Contacto no se modifica.

### US3 — Backfill de existentes (Priority: P2)

Como operador, quiero que los Clientes Individual ya existentes sin Contacto reciban el espejo en un proceso controlado una vez.

**Acceptance**:

1. **Given** N Clientes Individual sin Contacto ligado, **When** corre el backfill, **Then** cada uno tiene un Contacto primario ligado.
2. **Given** Cliente Individual que ya tiene Contacto primario, **When** corre el backfill, **Then** no se duplica.

### US4 — Envío Chilexpress (Priority: P1)

Como operador, en un Shipment hacia un Cliente Individual con espejo, quiero seleccionar el Contacto sin crear fichas a mano.

**Acceptance**:

1. **Given** Cliente Individual con espejo, **When** abro Shipment → Entregar a → Contacto, **Then** el Contacto espejo aparece en la lista filtrada.
2. **Given** ese Contacto seleccionado, **When** cotizo/creo OT Chilexpress, **Then** el adaptador obtiene nombre/teléfono/email del Contacto como hoy.

## 5. Edge Cases

- Cliente Individual sin email ni teléfono: crear Contacto solo con nombre; sync completa después.
- Renombre del Cliente: actualizar nombre del Contacto espejo.
- Contacto primario existente creado a mano antes de la feature: tratarlo como espejo elegible (no duplicar); sync solo si se acuerda en plan que es seguro.
- Import masivo de Clientes: el hook `after_insert` debe dispararse por fila o el backfill cubre el lote.
- Deshabilitar Cliente: no borrar Contacto automáticamente en esta Spec.

## 6. Fuera de alcance

- Auto-completar Contacto en el formulario Shipment sin selección (sigue eligiendo el link).
- UI nueva (checkbox/botón) salvo que una Spec posterior lo pida.
- Espejo para Customer Company.
- Cambiar DocType Contact core o quitar reqd de `delivery_contact_name` en Shipment.
- Cierre de Spec 009 (sigue su propio hilo de aceptación).

## 7. Criterios de éxito

- Alta manual Individual → Contacto listo en &lt; 1 guardado.
- Backfill reproducible desde `erpn_custom` (patch o comando documentado).
- Shipment + Chilexpress Test siguen operando sin cambio de contrato del adaptador.
- Cero duplicados de Contacto primario por Cliente Individual tras backfill + re-ejecución.

## 8. Impacto

| Área | Impacto |
|---|---|
| `Customer` hooks en `erpn_custom` | Alto (create/sync) |
| `Contact` + Dynamic Link | Alto (creación) |
| `Shipment` / Chilexpress | Bajo (consume Contacto igual) |
| UI Desk | Ninguno |
| Datos existentes | Backfill controlado |

## 9. Pregunta cerrada (respondida)

> ¿Al crear un cliente nuevo de forma manual la copia se hará al crearlo?

**Sí.** En `after_insert` del Cliente Individual se crea el Contacto espejo en el mismo guardado. El operador no hace un segundo paso.

## 10. Siguiente acción

1. Speckit: `plan.md` + `tasks.md` de esta feature.
2. OK de Miguel → implementar en `erpn_custom` + backfill.
3. Actualizar `README.md` Spec vigente solo cuando Miguel active esta Spec en la cola (hoy Spec vigente sigue siendo `009` hasta su cierre/aceptación).
