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
| 2026-09-27 | 16.0.55 | Item: se elimina la sección vacía `custom_encargo_section` y Clasificación se ancla en `asset_naming_series` | En 16.0.54 la sección oculta quedó tras Marca y ocultó Unidad de Medida (obligatoria) y la columna derecha del encabezado | Pendiente deploy automático |
| 2026-09-27 | 16.0.54 | Item: Marca sube al encabezado bajo Grupo de Productos (Property Setter `field_order` generado desde el meta estándar) y Proveedor de marca queda justo debajo | Miguel: la marca es un dato inicial, no final | Pendiente deploy automático |
| 2026-09-27 | 16.0.53 | Item: las listas de clasificación se cargan en el control (`set_data`) y un valor escrito fuera de la lista se borra con aviso; sección Clasificación movida a la pestaña Detalles (bajo el encabezado) con Proveedor de marca dentro; la sección vacía "Origen Marca / Proveedor" queda oculta | Prueba de Miguel: Talla no mostraba opciones, aceptaba texto libre y la sección aparecía en Contabilidad (Frappe v16 ubica un Section Break personalizado antes de la siguiente sección de su ancla) | Pendiente deploy automático |
| 2026-09-27 | 16.0.52 | Parche `v0_0_24` limpia el caché `app_modules` y reconstruye el mapa de módulos antes de `reload_doc` | El deploy de 16.0.51 falló en migrate con `Module catalog not found`: Frappe v16 reutiliza el mapa de módulos en Redis y no veía el módulo nuevo de `modules.txt` | Pendiente deploy automático |
| 2026-09-27 | 16.0.51 | Spec 014 Etapa 3a: cada talla marcada con Familia (Calzado / Ropa; vacío = todas) en `Item Attribute Value.custom_familia`, y el Item solo ofrece las tallas de su familia y departamento. DocType nuevo `Diccionario Aduana` (módulo Catalog, solo System Manager): tipo de dato + texto normalizado → valor ERP, estados En espera / Clasificado / A descripción, `translate()` encola lo desconocido; semilla de 204 alias (colores, tipos, departamentos, marcas existentes) | Un zapato mostraba tallas de ropa; la recarga de datos y los encargos necesitan traducir texto libre a valores oficiales sin inventar | 16 unittests locales OK |
| 2026-09-27 | 16.0.50 | Spec 014 Etapa 2: listas sembradas. Color 22 registros multilingües (combinaciones → Multicolor); Talla 70 valores `US · EU · CL` por Departamento (CL = EU − 1 propuesto; ropa con letras; Unisex en escala hombre con equivalente mujer; niños con etiqueta de marca); Tono 59 desde catálogo; atributo nuevo Contenido (Maquillaje, Cuidado, Suplementos) con 16 valores | Regla 80/20 de Miguel: listas para el 80%, el resto (colores de marca, estampados, ancho de calzado) va en la descripción | 12 unittests locales OK |
| 2026-09-27 | 16.0.49 | `catalog/setup.py` renombrado a `catalog/provision.py` | El deploy automático trata cualquier `setup.py` como cambio de dependencias y corre `bench setup requirements`, que falla (servicio sin `uv` en PATH); 16.0.47 quedó a medio desplegar | Deploy automático `SUCCESS` |
| 2026-09-27 | 16.0.48 | Patch `v0_0_22`: crea las listas Color y Tono (vacías), omitidas por 16.0.47 | `get_doc(dict)` no marca el documento como nuevo | Migrate 16.0.47 verificado: árbol, 10 campos y listas Taco/Manga/Tamaño/Talla OK |
| 2026-09-27 | 16.0.47 | Spec 014 Etapa 1: árbol Grupo → Familia → Tipo (4 / 13 / 60) en Item Group; listas en Item Attribute (Color, Talla, Taco, Manga, Tamaño, Tono) con Departamento por valor; campos de clasificación en Item (Familia calculada, Departamento, atributos según Familia, Es pack, SKU proveedor); validación contra lista; ComercialFRA solo lee listas y árbol, System Manager las mantiene | Clasificación Shopify inservible para vender (decisión Miguel V3.5) | 17 unittests locales OK; verificación en sitio tras migrate |
| 2026-09-26 | config (sin código) | Moneda CLP: símbolo `CLP$`, formato `#.###`, fracción vacía, unidades 1, fracción mínima 1. System Settings: Precisión de la divisa `0` (global; revisar al abrir otra moneda) | CLP no tiene decimales | OV-00008 muestra `CLP$ 50.000`, en palabras sin centavos |
| 2026-09-26 | 16.0.46 | Barra de saldo de la OV muestra montos como `CLP$35.000` (código de moneda, miles con punto, sin decimales en CLP) | CLP no usa decimales; el código prepara multi-país | Verificación visual en OV |
| 2026-09-26 | 16.0.45 | Series de documentos cortas en español (tabla anterior) + serie automática de devoluciones | Nombres ERPNext largos y poco representativos (decisión Miguel) | 28 unittests locales OK; verificación en sitio con OV nueva |

### Spec vigente del Programador

**Spec activa:** `014-clasificacion-producto-busqueda` — árbol Grupo → Familia → Tipo, atributos controlados por Familia (tallas US · EU · CL en una sola lista por Departamento, colores multilingües en un solo registro), diccionario de aduana, búsqueda por facetas para la vendedora y recarga limpia de la carga de prueba. La Spec se trabaja localmente (no se versiona). Etapa 1 en `16.0.47`; siguientes etapas: listas Color/Talla/Tono desde el catálogo, aduana, búsqueda y Encargo, recarga limpia (destructiva, con VP y OK de Miguel).

**Spec anterior:** `013-encargo-preventa-recepcion` — modelo ENC para separar demanda pendiente de stock físico, generar encargos desde Sales Order, entregar una lista mínima al shopper Miami y conciliar el producto real en recepción Chile.

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
