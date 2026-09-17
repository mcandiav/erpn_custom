### ERPn Custom

Customizaciones FRAgallardo para ERPNext, normativa Chile e integraciones.

### Spec vigente del Programador

**Spec activa:** `004-pagos-clientes-mapeo-depositos`

**Corte actual:** asignación manual de pagos huérfanos (depósito sin RUT de cliente / pagador tercero → Customer beneficiario + saldo vía `realize_attributed_deposit`) y vista operativa **Pagos huérfanos** en `Pagos de Clientes`.

Documento rector del corte: `specs/004-pagos-clientes-mapeo-depositos/manual-orphan-payment-assignment.md`

**Estado implementación (código):** `assign_orphan_deposit` + sección UI **Pagos huérfanos** + auditoría `Deposit Mapping Attempt` (trigger Manual / rule `manual-attribution-v1`). Pendiente aceptación operativa con `ACC-BTN-2026-01705`.

**No implementar por defecto:** Spec `005-banco-chile-tiempo-real` ni el MVP comercial `003`, salvo que Miguel lo nombre explícitamente en el hilo.

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
