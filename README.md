### ERPn Custom

Customizaciones FRAgallardo para ERPNext, normativa Chile e integraciones.

### Versionado de producto

- Fuente: `erpn_custom/__init__.py` → `__version__` (semver `MAJOR.MINOR.PATCH`).
- Major `16` alinea con ERPNext/Frappe 16; la rama Git `version-16` no es la versión de producto.
- Cada push a deploy sube el **PATCH** (`16.0.1` → `16.0.2` …). MINOR solo al cerrar un corte mayor.
- Subject de commit: `[16.0.N] …`

### Spec vigente del Programador

**Spec activa:** `011-vendedorfra-operational-navigation` — navegación operacional para VendedorFRA/ComercialFRA, evitando el Desktop general `/desk` y usando `ComercialFRA` como punto de entrada/Home.

Documento: `specs/011-vendedorfra-operational-navigation/spec.md`

**Estado:** `16.0.34` — Spec 011 **pausada en Desktop**: se deja el zoo nativo de Frappe v16. Desactivados `app_include_js` / `extend_bootinfo` de navegación operacional (demasiada fricción). Login sigue pudiendo usar `default_workspace = ComercialFRA`. Código retenido en `navigation/` sin enganche.

**Spec anterior implementada:** `010-customer-contact-mirror` — producto desde `16.0.22`; pendiente su cierre/aceptación documental final si aún corresponde.

**Última Spec cerrada:** `009-chilexpress-shipment-integration`

**Cierre 009:** 2026-09-17 — Chilexpress Adapter vinculado a `Shipment` aceptado operativamente (producto hasta `16.0.21`). Evidencia Test en `SHIPMENT-00001` / Cynthia Contreras Soto: preflight/cotización (service `3` CHEX), OT idempotente `712678881073`, tracking `EN PRE-RECEPCION | SANTIAGO CENTRO`, **etiqueta de envío OK** (JPEG en create, File adjunto). Nota no bloqueante: reprint API APIM Test 404; reimpresión desde el adjunto del create. Fuera de alcance: Production, Starken/FAZT, cron tracking.

Documento histórico: `specs/009-chilexpress-shipment-integration/spec.md`

**Cierre 008:** 2026-09-17 — modelo multi-courier (`Courier Provider` + `Courier Configuration` + `endpoint_url`), UI aceptada y conectividad Chilexpress Test verificada (coverage/rating/shipping).

**Base previa:** Courier → Configuración de Couriers; Chilexpress Test configurado con 3 servicios + endpoints Desk.

**Specs cerradas en cola:** `004-pagos-clientes-mapeo-depositos`, `006-customer-multidocument-identity`, `007-mcv-chile-desktop`, `008-courier-configuration`, `009-chilexpress-shipment-integration`.

**Cierre 007:** 2026-09-17 — Desktop `MCV Chile` verificado.

**Cierre 006:** 2026-09-17 — identidad multidocumento aceptada operativamente.

**No reabrir por defecto:** Specs cerradas `003`–`009`. No ampliar alcance sin OK de Miguel.

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
