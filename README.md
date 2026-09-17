### ERPn Custom

Customizaciones FRAgallardo para ERPNext, normativa Chile e integraciones.

### Versionado de producto

- Fuente: `erpn_custom/__init__.py` → `__version__` (semver `MAJOR.MINOR.PATCH`).
- Major `16` alinea con ERPNext/Frappe 16; la rama Git `version-16` no es la versión de producto.
- Cada push a deploy sube el **PATCH** (`16.0.1` → `16.0.2` …). MINOR solo al cerrar un corte mayor.
- Subject de commit: `[16.0.N] …`

### Spec vigente del Programador

**Spec activa:** `009-chilexpress-shipment-integration`

**Estado:** validada en sandbox Chilexpress Test (`16.0.17`). Pendiente aceptación formal de Miguel para cierre.

**Evidencia Test (SHIPMENT-00001 / Cynthia Contreras Soto):**

| Paso | Resultado |
|---|---|
| Preflight / cotización / servicio | OK (service `3` CHEX) |
| Crear OT idempotente | OK — OT `712678881073`, reintento bloqueado |
| Tracking | OK — `EN PRE-RECEPCION \| SANTIAGO CENTRO` vía `POST .../tracking` |
| Etiqueta en create | OK — JPEG Base64 (`labelType=2`), adjunto File |
| Reimpresión API | No disponible en producto APIM Test (404); etiqueta se guarda en create |

**Objetivo vigente:** aceptar Spec 009 o pedir ajuste puntual (p. ej. path oficial de reprint cuando Chilexpress lo publique en Test).

Documento rector: `specs/009-chilexpress-shipment-integration/spec.md`

**Última Spec cerrada:** `008-courier-configuration`

**Siguiente Spec documentada (no activa aún):** `010-customer-contact-mirror` — espejo silencioso Cliente Individual → Contacto primario (B2C). Draft en `specs/010-customer-contact-mirror/spec.md`. No entra a cola de código hasta que Miguel lo declare Spec vigente (tras cerrar o pausar 009).

**Cierre 008:** 2026-09-17 — modelo multi-courier (`Courier Provider` + `Courier Configuration` + `endpoint_url`), UI aceptada y conectividad Chilexpress Test verificada (coverage/rating/shipping).

**Base previa:** Courier → Configuración de Couriers; Chilexpress Test configurado con 3 servicios + endpoints Desk.

**Specs cerradas en cola:** `004-pagos-clientes-mapeo-depositos`, `006-customer-multidocument-identity`, `007-mcv-chile-desktop`, `008-courier-configuration`.

**Cierre 007:** 2026-09-17 — Desktop `MCV Chile` verificado.

**Cierre 006:** 2026-09-17 — identidad multidocumento aceptada operativamente.

**No reabrir por defecto:** Specs cerradas `003`–`008`. Spec `009` está en aceptación; no ampliar alcance sin OK de Miguel.

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
