# Contract: Customer Identity v1

## Purpose

Define el contrato único que toda creación, edición, importación, integración y matching debe respetar para la identidad documental de `Customer`.

## Canonical fields

```text
Customer.custom_tax_id_type
Customer.custom_tax_id_country
Customer.tax_id
```

`tax_id` es el número. No crear una segunda copia custom del número.

## Supported document types v1

```text
RUT
DNI
CPF
Passport
```

Cualquier valor diferente se rechaza hasta que una Spec posterior lo incorpore.

## Validation contract

### RUT

Preconditions:

```text
custom_tax_id_type == "RUT"
```

Effects:

```text
custom_tax_id_country := Chile
tax_id := normalize_chilean_tax_id(tax_id)
```

Failure:

- RUT vacío para Customer nuevo;
- formato que no pueda normalizarse;
- DV inválido;
- identidad compuesta duplicada.

### CPF

Preconditions:

```text
custom_tax_id_type == "CPF"
```

Effects:

```text
custom_tax_id_country := Brasil
tax_id := normalize_cpf(tax_id)
```

Failure:

- vacío;
- CPF estructural/algorítmicamente inválido;
- identidad compuesta duplicada.

### DNI

Preconditions:

```text
custom_tax_id_type == "DNI"
custom_tax_id_country is not empty
```

Effects:

```text
tax_id := normalize_dni(country, tax_id)
```

La función puede delegar a regla genérica no destructiva cuando aún no exista un validador específico para el país.

Failure:

- país vacío;
- número vacío;
- regla país-específica incumplida cuando exista;
- identidad compuesta duplicada.

### Passport

Preconditions:

```text
custom_tax_id_type == "Passport"
custom_tax_id_country is not empty
```

Effects:

```text
tax_id := normalize_passport(country, tax_id)
```

Failure:

- país vacío;
- número vacío;
- regla país-específica incumplida cuando exista;
- identidad compuesta duplicada.

## Validation ordering

Toda escritura debe respetar el orden lógico:

1. validar tipo permitido;
2. resolver/validar país emisor;
3. normalizar número según tipo/país;
4. validar número;
5. asignar valor normalizado a `Customer.tax_id`;
6. comprobar unicidad compuesta;
7. permitir persistencia.

No comprobar unicidad sobre una forma no normalizada.

## Bank matching contract

La función que prepara Customers candidatos para Banco de Chile debe aplicar:

```text
Customer.custom_tax_id_type == "RUT"
Customer.custom_tax_id_country == Chile
Customer.tax_id valid as Chilean RUT
```

Solo después se compara contra el RUT normalizado del pagador.

DNI, CPF y Passport deben ser invisibles para esa regla.

## Import/API contract

Crear Customer por REST, Data Import, integración o código interno no autoriza a omitir las reglas de dominio.

La implementación debe ubicar la validación en un punto que se ejecute al guardar el documento por las vías soportadas, no únicamente en JavaScript de formulario.

La UI puede prevenir errores anticipadamente, pero el backend es autoridad final.

## Error semantics

Los mensajes deben nombrar el tipo correcto.

Permitido:

```text
RUT inválido: el dígito verificador no corresponde.
País emisor es obligatorio para Passport.
Ya existe un Customer con este DNI emitido por Argentina.
```

Prohibido:

```text
RUT inválido
```

cuando el usuario está guardando DNI, CPF o Passport.

## Legacy migration contract

- RUT existente válido -> RUT/Chile.
- `tax_id` vacío -> no inventar valor.
- valor legado no RUT -> conflicto explícito; no inferir otro tipo.
- Server Script legado debe quedar desactivado al activar este contrato.

## Concurrency contract

La unicidad no se considera cumplida si solo funciona en uso secuencial. Dos solicitudes concurrentes con la misma identidad deben producir como máximo un Customer persistido con esa identidad; la otra debe fallar limpiamente.

## Non-goals

- múltiples documentos por Customer;
- identidad biométrica;
- nacionalidad;
- residencia;
- validación remota gubernamental;
- matching probabilístico.
