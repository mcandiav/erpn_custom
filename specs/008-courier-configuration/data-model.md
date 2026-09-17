# Data Model: Courier Configuration

## 1. Principio

Separar identidad del proveedor, configuración de la cuenta, secretos, endpoints de infraestructura y lógica API.

```text
Courier Provider
      ↓
Courier Configuration
      ↓
Courier Credential

.env/.env.example  -> endpoints
Courier Adapter    -> protocolo/API
```

## 2. Courier Provider

DocType maestro.

Campos propuestos:

| Campo | Tipo | Regla |
|---|---|---|
| provider_name | Data | nombre visible, requerido |
| provider_code | Data | técnico, único, estable, requerido |
| enabled | Check | activo/inactivo |
| description | Small Text | opcional |

Seed mínimo: `Chilexpress`.

No borrar proveedores con uso histórico; desactivar.

## 3. Courier Configuration

DocType normal.

Campos propuestos:

| Campo | Tipo | Regla |
|---|---|---|
| provider | Link -> Courier Provider | requerido |
| environment | Select | `Test` / `Producción` |
| enabled | Check | requerido |
| account_reference | Data | opcional; convenio/código de cuenta |
| credentials | Table -> Courier Credential | secretos variables |

Unicidad lógica inicial:

```text
provider + environment
```

Si la inspección demuestra que FRAgallardo requiere múltiples cuentas simultáneas para un mismo provider/ambiente, el Programador debe detenerse y proponer extender la clave antes de implementar.

## 4. Courier Credential

Child DocType conceptual.

Campos propuestos:

| Campo | Tipo | Regla |
|---|---|---|
| credential_key | Data | requerido; clave técnica estable |
| secret_value | Password o mecanismo cifrado equivalente | requerido cuando corresponda |

Restricción lógica:

```text
credential_key único dentro de una Courier Configuration
```

No modelar credenciales específicas como columnas nuevas en `Courier Configuration`.

## 5. Chilexpress migrado

Ejemplo conceptual:

```text
Courier Provider
provider_name = Chilexpress
provider_code = chilexpress

Courier Configuration
provider = Chilexpress
environment = <valor heredado>
enabled = 1

Courier Credential
coverage_api_key = ********
rating_api_key   = ********
shipping_api_key = ********
```

Los valores reales nunca aparecen en fixtures, documentación o logs.

## 6. Endpoints

No se persisten como datos de negocio.

Se resuelven desde variables de entorno por provider/ambiente/servicio.

Contrato inicial Chilexpress:

```text
CHILEXPRESS_TEST_COVERAGE_URL
CHILEXPRESS_TEST_RATING_URL
CHILEXPRESS_TEST_SHIPPING_URL
CHILEXPRESS_PROD_COVERAGE_URL
CHILEXPRESS_PROD_RATING_URL
CHILEXPRESS_PROD_SHIPPING_URL
```

El Programador debe confirmar el mecanismo runtime real para carga de `.env` antes de implementar lector alguno.

## 7. Adapter futuro

No es entidad de base de datos.

Cada provider soportado técnicamente tendrá código específico que implemente un contrato común. La relación conceptual se resuelve por `provider_code`.

Ejemplo futuro:

```text
provider_code = chilexpress -> ChilexpressAdapter
provider_code = starken     -> StarkenAdapter
```

No crear un campo editable para elegir clases Python ni rutas arbitrarias desde UI en Spec 008.

## 8. Migración legado

Fuente:

```text
Single DocType: Chilexpress Settings
environment
coverage_api_key
rating_api_key
shipping_api_key
```

Destino:

```text
Courier Provider + Courier Configuration + Courier Credential
```

La migración debe:

1. copiar;
2. verificar presencia/recuperabilidad del destino sin revelar secretos;
3. cambiar navegación;
4. conservar legado fuera de navegación.

No borrar el Single heredado en Spec 008.
