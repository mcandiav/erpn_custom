# Data Model: Courier Configuration

## 1. Principio

Separar identidad del proveedor, configuración de cuenta/ambiente, secretos+endpoints operativos y lógica API.

```text
Courier Provider
      ↓
Courier Configuration
      ↓
Courier Credential  (servicio + API key + endpoint URL)

Courier Adapter -> protocolo/API
```

## 2. Courier Provider

DocType maestro.

| Campo | Tipo | Regla |
|---|---|---|
| provider_name | Data | nombre visible, requerido |
| provider_code | Data | técnico, único, estable, requerido |
| enabled | Check | activo/inactivo |
| description | Small Text | opcional |

Seed mínimo: `Chilexpress`.

## 3. Courier Configuration

DocType normal.

| Campo | Tipo | Regla |
|---|---|---|
| provider | Link -> Courier Provider | requerido |
| environment | Select | `Test` / `Producción` |
| enabled | Check | requerido |
| account_reference | Data | opcional |
| credentials | Table -> Courier Credential | 3 filas estándar |

Unicidad: `provider + environment`.

## 4. Courier Credential

Child DocType. Una fila = un rol de servicio (Cobertura / Cotización / Envío).

| Campo | Tipo | Regla |
|---|---|---|
| credential_key | Select | `coverage_api_key` / `rating_api_key` / `shipping_api_key` |
| secret_value | Password | API key |
| endpoint_url | Data | URL del servicio; no secreto |

Al crear Configuration se precargan las 3 filas.

Courier de una sola API/URL: mismo secret y misma URL en las 3 filas.

`credential_key` único dentro de una Configuration.

## 5. Ejemplo Chilexpress Test

```text
Courier Provider: chilexpress
Courier Configuration: environment=Test
  coverage_api_key  | secret=*** | endpoint=https://...
  rating_api_key    | secret=*** | endpoint=https://...
  shipping_api_key  | secret=*** | endpoint=https://...
```

## 6. Endpoints

Persisten en Desk junto a las API keys. No son contrato obligatorio de `.env`.

El adapter futuro resuelve:

```text
provider + environment + servicio -> secret_value + endpoint_url
```

## 7. Adapter futuro

No es entidad de base de datos. Código específico por `provider_code`.

## 8. Legado Chilexpress Settings

Ya tratado en Spec 008: DocType legado eliminable; navegación apunta a Configuración de Couriers.
