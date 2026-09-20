# Plan: Atribución automática de vendedor y comisión

## Etapa 1 — Evidence gate

1. Inspeccionar Sales Order y Sales Team estándar en ERPNext v16 instalado.
2. Confirmar campos y cálculo nativo:
   - sales_person;
   - allocated_percentage;
   - allocated_amount;
   - commission_rate;
   - incentives.
3. Confirmar relaciones:
   - Employee.user_id;
   - Sales Person.employee;
   - Sales Person.commission_rate.
4. Confirmar evento server-side apropiado antes de programar.

## Etapa 2 — Servicio de resolución

Crear un servicio aislado que resuelva:

`session user -> Employee -> Sales Person`

Reglas:
- solo registros habilitados;
- ninguna elección arbitraria;
- resultado nulo seguro para usuarios no comerciales;
- error diagnosticable si existe ambigüedad.

## Etapa 3 — Asignación Sales Team

Si `doc.sales_team` está vacío:
- agregar Sales Person;
- contribution 100%;
- permitir que ERPNext aplique su tasa/cálculo estándar.

Si ya existe Sales Team:
- no modificar.

## Etapa 4 — Hook

Registrar `Sales Order` en `doc_events` usando el evento validado en Etapa 1.

## Etapa 5 — Pruebas

Casos mínimos:
- Amaranta 1% / CLP 50.000 -> CLP 500;
- guardar dos veces -> sin duplicados;
- Sales Team manual -> preservado;
- Administrator sin Sales Person -> no atribución falsa;
- usuario sin Employee;
- Employee sin Sales Person;
- múltiples Sales Person -> error explícito/seguro;
- regresión de Sales Order existente.

## Etapa 6 — ComercialFRA / saldo

Validar que el JS de Sales Order no produzca PermissionError para `ComercialFRA` al llamar `sales_order_credit.credit_summary`.

Si se confirma el bug ya observado:
- separar permisos de consulta/aplicación vs reversión;
- autorizar ComercialFRA solo en funciones comerciales necesarias;
- no otorgar privilegios contables generales.

## Etapa 7 — Sandbox

Prueba punta a punta con Amaranta:
1. crear nueva OV;
2. no tocar Sales Team;
3. guardar;
4. verificar atribución;
5. verificar tasa;
6. verificar incentivo;
7. confirmar/submit;
8. volver a abrir y verificar persistencia.

## Etapa 8 — Cierre

- bump PATCH;
- actualizar README;
- commit;
- push a `version-16`;
- validar despliegue sandbox;
- aceptación de Miguel.
