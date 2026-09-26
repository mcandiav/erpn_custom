### ERPn Custom

Customizaciones FRAgallardo para ERPNext, normativa Chile e integraciones.

### Versionado de producto

- Fuente: `erpn_custom/__init__.py` → `__version__` (semver `MAJOR.MINOR.PATCH`).
- Major `16` alinea con ERPNext/Frappe 16; la rama Git `version-16` no es la versión de producto.
- Cada push a deploy sube el **PATCH** (`16.0.1` → `16.0.2` …). MINOR solo al cerrar un corte mayor.
- Subject de commit: `[16.0.N] …`

### Nomenclatura de documentos (desde 16.0.45)

Series cortas en español, contador de 5 dígitos que reinicia cada año (`OV-2026-00001`). Fuente única: `erpn_custom/naming/series.py`, aplicada por el patch `v0_0_20_document_series` (Property Setter `options` + `default` de `naming_series`). Las devoluciones toman su serie automáticamente (`before_insert`).

| Documento | Serie | Devolución |
|---|---|---|
| Cotización | `COT-` | — |
| Orden de venta | `OV-` | — |
| Nota de entrega | `NE-` | `NE-DEV-` |
| Factura de venta | `FAC-` | `NC-` |
| Entrada de pago | `PAG-` | — |
| Asiento contable | `AST-` | — |
| Movimiento bancario | `MB-` | — |
| Solicitud de materiales | `SM-` | — |
| Solicitud de cotización | `SC-` | — |
| Cotización de proveedor | `CP-` | — |
| Orden de compra | `OC-` | — |
| Recibo de compra | `REC-` | `REC-DEV-` |
| Factura de compra | `FC-` | `NCC-` |
| Entrada de inventario | `MOV-` | — |
| Reconciliación de inventario | `AJU-` | — |
| Lista de selección | `PICK-` | — |
| Iniciativa (Lead) | `PROS-` | — |
| Oportunidad | `OPO-` | — |

- Los documentos anteriores conservan su nombre (`SAL-ORD-…`, `ACC-SINV-…`); no hay renombrado retroactivo.
- `ENC-` (Encargo) sin cambio. Clientes, proveedores y productos no se tocan.
- El nombre interno (`FAC-`, `NC-`, `NE-`) no es el folio SII del DTE.

**Bitácora**

| Fecha | Versión | Cambio | Motivo | Validación |
|---|---|---|---|---|
| 2026-09-26 | 16.0.45 | Series de documentos cortas en español (tabla anterior) + serie automática de devoluciones | Nombres ERPNext largos y poco representativos (decisión Miguel) | 28 unittests locales OK; verificación en sitio con OV nueva |

### Spec vigente del Programador

**Spec activa:** `013-encargo-preventa-recepcion` — modelo ENC para separar demanda pendiente de stock físico, generar encargos desde Sales Order, entregar una lista mínima al shopper Miami y conciliar el producto real en recepción Chile.

Documento: `specs/013-encargo-preventa-recepcion/spec.md`

**Estado 013:** planificación técnica autorizada. El Programador debe leer README + Spec 013, inspeccionar ERPNext/Frappe v16 instalado, revisar hooks existentes de Sales Order, presentar plan de archivos/idempotencia/concurrencia/pruebas y **esperar OK explícito de Miguel antes de escribir código**.

**Decisiones principales 013:**

- ENC **no** es Warehouse ni stock virtual; es una cola de abastecimiento comprometido.
- Item conocido: la OV conserva el Item real y ENC cubre sólo el faltante.
- Producto desconocido: utilizar un único Item técnico no-stock `ENCARGO-PENDIENTE`, siempre vinculado a un ENC.
- No crear Items ficticios por foto/descripción.
- La porción disponible debe reutilizar Stock Reservation estándar de ERPNext; no crear un motor custom de reservas.
- Shopper externo: página Website/Portal mínima, sin Desk, para ver pendientes y marcar `COMPRADO` / `NO ENCONTRADO`.
- La identidad definitiva del Item se resuelve bajo control FRA en recepción Chile.
- Compra equivocada no devuelta → stock normal; el ENC original continúa pendiente.
- No reescribir destructivamente una Sales Order submitted al resolver el Item real.

**Última Spec cerrada:** `012-sales-person-auto-commission` — 2026-09-23. Atribución automática User → Employee → Sales Person → Sales Team en Sales Order (`before_validate`). Producto desde `16.0.35`.

**Evidencia aceptación sandbox 012:** `SAL-ORD-2026-00015` (owner `amaranta@fragallardo.com`, submitted): Sales Team = `Amaranta Fernandez`, Contribution 100%, Commission Rate 1%, allocated_amount CLP 50.000, **Incentives CLP 500**. Caso histórico `SAL-ORD-2026-00014` permanece sin Sales Team (sin reescritura retroactiva).

**Decisión de negocio 012 (2026-09-23):** la comisión se **anota** en la OV al crearla (Sales Team). Queda **a firme para pago** solo al liquidar remuneraciones, filtrando OVs **entregadas**. El pago no es parte de Spec 012.

Documento histórico 012: `specs/012-sales-person-auto-commission/spec.md`

**Spec 011:** `011-vendedorfra-operational-navigation` queda **pausada** en `16.0.34`. Se mantiene el Desktop nativo de Frappe v16 y no debe retomarse por defecto.

**Spec anterior implementada:** `010-customer-contact-mirror` — producto desde `16.0.22`; pendiente su cierre/aceptación documental final si aún corresponde.

**Cierre 009:** 2026-09-17 — Chilexpress Adapter vinculado a `Shipment` aceptado operativamente (producto hasta `16.0.21`). Evidencia Test en `SHIPMENT-00001` / Cynthia Contreras Soto: preflight/cotización (service `3` CHEX), OT idempotente `712678881073`, tracking `EN PRE-RECEPCION | SANTIAGO CENTRO`, **etiqueta de envío OK** (JPEG en create, File adjunto). Nota no bloqueante: reprint API APIM Test 404; reimpresión desde el adjunto del create. Fuera de alcance: Production, Starken/FAZT, cron tracking.

Documento histórico: `specs/009-chilexpress-shipment-integration/spec.md`

**Cierre 008:** 2026-09-17 — modelo multi-courier (`Courier Provider` + `Courier Configuration` + `endpoint_url`), UI aceptada y conectividad Chilexpress Test verificada (coverage/rating/shipping).

**Base previa:** Courier → Configuración de Couriers; Chilexpress Test configurado con 3 servicios + endpoints Desk.

**Specs cerradas en cola:** `004-pagos-clientes-mapeo-depositos`, `006-customer-multidocument-identity`, `007-mcv-chile-desktop`, `008-courier-configuration`, `009-chilexpress-shipment-integration`, `012-sales-person-auto-commission`.

**Cierre 007:** 2026-09-17 — Desktop `MCV Chile` verificado.

**Cierre 006:** 2026-09-17 — identidad multidocumento aceptada operativamente.

**No reabrir por defecto:** Specs cerradas `003`–`009` y `012`. No ampliar alcance sin OK de Miguel.

La cola de programación vive **en este repositorio**. El README padre `../README.md` es arquitectura/handoff; no es la cola automática de código.

### Ubicacion dentro del proyecto

Este directorio `ERPnext-custom/erpn_custom/` es el **repositorio GitHub y la raiz tecnica programable** de ERPn Custom. El directorio padre `ERPnext-custom/` contiene documentacion arquitectonica global, pero el Programador no necesita abrirlo ni usarlo como workspace. Para programacion, este repositorio debe ser autosuficiente: Git, Speckit, especificaciones, codigo y pruebas viven aqui.

Estructura tecnica oficial:

```text
erpn_custom/                 # raiz de este repositorio GitHub
├── .github/
├── .cursor/rules/           # reglas Cursor de este workspace (siempre aplicar)
├── .specify/                # motor/configuracion Speckit
├── specs/                   # especificaciones implementables (cola de codigo)
├── README.md                # Spec vigente del Programador + reglas tecnicas
├── pyproject.toml
└── erpn_custom/             # paquete Frappe/Python
```

Reglas obligatorias para desarrollo:

- Ejecutar Speckit siempre desde la raiz de este repositorio.
- Crear y mantener Specs exclusivamente en `specs/` de este repositorio.
- No crear `.specify/` ni `specs/` en el directorio padre `ERPnext-custom/`.
- Antes de programar: leer **este** `README.md` (Spec vigente) y la Spec/corte nombrado. El README padre solo si Miguel lo pide o hay contradiccion a señalar.
- No inferir la Spec a implementar desde `../README.md` seccion 11.
- Si Miguel dice "lo requerido" sin nombrar Spec → preguntar `004 / 005 / otra`.
- Los cambios de codigo y los cambios de Spec asociados deben quedar versionados en este repositorio cuando correspondan.
- La documentacion conceptual general permanece en el directorio padre; las instrucciones implementables para el Programador viven aqui.
- Regla Cursor always-on: `.cursor/rules/00-erpn-custom-workspace.mdc`.

### Installation

You can install this app using the [bench](https://github.com/frappe/bench) CLI:

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app $URL_OF_THIS_REPO --branch version-16
bench install-app erpn_custom
```

### Contributing

This app uses `pre-commit` for code formatting and linting. Please [install pre-commit](https://pre-commit.com/#installation) and enable it for this repository:

```bash
cd apps/erpn_custom
pre-commit install
```

Pre-commit is configured to use the following tools for checking and formatting your code:

- ruff
- eslint
- prettier
- pyupgrade
### CI

This app can use GitHub Actions for CI. The following workflows are configured:

- CI: Installs this app and runs unit tests on every push to `develop` branch.
- Linters: Runs [Frappe Semgrep Rules](https://github.com/frappe/semgrep-rules) and [pip-audit](https://pypi.org/project/pip-audit/) on every pull request.


### License

mit
