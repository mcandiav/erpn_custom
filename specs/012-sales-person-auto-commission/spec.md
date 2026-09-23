# Feature Specification: Atribución automática de vendedor y comisión en Sales Order

**Feature Branch**: `[012-sales-person-auto-commission]`

**Created**: 2026-09-20

**Status**: Accepted — 2026-09-23. Evidencia sandbox `SAL-ORD-2026-00015`.

**Parent context**: `Perfiles FRAgallardo.md`, `config-vendedor-operativo-fra.md`, ERPNext/Frappe v16, piloto Amaranta Fernandez.

## 0. Problema

ERPNext tiene correctamente configurada a **Amaranta Fernandez** como `Sales Person`, vinculada al Employee `HR-EMP-00002`, con `Commission Rate = 1%`.

Sin embargo, una Sales Order creada por Amaranta no agrega automáticamente a Amaranta en la tabla estándar `Sales Team`. En consecuencia, la OV queda sin vendedor atribuido y ERPNext calcula comisión/incentivo igual a cero.

Caso observado en sandbox:

- usuario vendedor: `amaranta@fragallardo.com`;
- Sales Person: `Amaranta Fernandez`;
- Employee: `HR-EMP-00002`;
- Commission Rate: `1%`;
- Sales Order: `SAL-ORD-2026-00014`;
- total: CLP 50.000;
- `sales_team`: vacío;
- comisión resultante: 0.

La configuración del Sales Person es correcta. Falta automatizar la atribución del usuario que crea la OV.

## 1. Objetivo

Cuando un usuario comercial cree una Sales Order y la OV no tenga todavía filas en `Sales Team`, ERPn Custom debe:

1. identificar al usuario de sesión que está creando/guardando la OV;
2. resolver el Employee asociado a ese usuario;
3. resolver el Sales Person asociado a ese Employee;
4. agregar ese Sales Person a `Sales Team`;
5. asignar `Contribution (%) = 100`;
6. utilizar la `Commission Rate` configurada en el Sales Person;
7. dejar que ERPNext calcule los importes estándar de contribución e incentivo/comisión.

No se implementará un motor de comisiones paralelo.

## 2. Regla de negocio

Regla principal:

```text
Usuario creador de la OV
    -> Employee.user_id
    -> Sales Person.employee
    -> Sales Team de la OV
    -> Contribution 100%
    -> Commission Rate del Sales Person
    -> cálculo estándar ERPNext
```

Ejemplo Amaranta:

```text
amaranta@fragallardo.com
-> HR-EMP-00002
-> Amaranta Fernandez
-> Contribution 100%
-> Commission Rate 1%
-> Venta neta CLP 50.000
-> Incentivo esperado CLP 500
```

## 3. Fuente de verdad de la comisión

La tasa de comisión vive en el maestro estándar `Sales Person.commission_rate`.

No duplicar la tasa en:

- User;
- Employee;
- Customer;
- Sales Order mediante Custom Field;
- configuración custom paralela.

La Sales Order debe persistir la fila estándar de `Sales Team` con la tasa/copias que ERPNext utilice normalmente para la transacción.

## 4. Momento de atribución

La atribución se ejecutará server-side antes de guardar/validar la Sales Order, en un evento compatible con Frappe v16 como `before_validate` o `validate`, después de confirmar mediante prueba cuál conserva correctamente el cálculo estándar de Sales Team.

La implementación final debe usar `doc_events` en `hooks.py`.

No depender del navegador ni de Client Script para la regla de negocio.

## 5. Condiciones de aplicación

La automatización solo se aplica cuando:

1. el documento es una `Sales Order`;
2. existe un usuario de sesión válido;
3. `sales_team` está vacío;
4. el usuario tiene un Employee activo y asociado;
5. existe exactamente un Sales Person habilitado asociado a ese Employee.

Si `sales_team` ya tiene una o más filas:

- NO agregar otra;
- NO cambiar vendedores;
- NO recalcular porcentajes definidos por el usuario;
- NO sobrescribir una venta compartida.

## 6. Resolución Usuario -> Employee -> Sales Person

### 6.1 Usuario a Employee

Buscar un Employee habilitado cuyo `user_id` sea igual a `frappe.session.user`.

Resultado esperado: exactamente un Employee.

### 6.2 Employee a Sales Person

Buscar un Sales Person habilitado cuyo `employee` sea el Employee resuelto.

Resultado esperado: exactamente un Sales Person operativo.

### 6.3 Ambigüedad

Si existen múltiples registros válidos para cualquiera de las relaciones:

- no elegir arbitrariamente;
- bloquear la atribución automática con un mensaje claro;
- no insertar una fila incorrecta.

## 7. Usuarios sin Sales Person

Una Sales Order creada por Administrator, integración, usuario técnico o usuario no vendedor puede no tener Employee/Sales Person.

En ese caso:

- no inventar vendedor;
- no asignar Amaranta ni otro Sales Person por defecto;
- dejar `Sales Team` sin modificación, salvo que la política vigente del documento requiera otra cosa;
- registrar comportamiento mediante tests.

La ausencia de Sales Person para un usuario no comercial no debe romper integraciones ni procesos administrativos existentes.

## 8. Ventas compartidas

La automatización inicial cubre ventas con un único vendedor.

Para ventas compartidas:

- el usuario puede cargar manualmente Sales Team antes de confirmar;
- si existe al menos una fila, la automatización no interviene;
- ERPNext conserva su lógica estándar de `Contribution (%)`.

Ejemplo:

- Amaranta 70%;
- otro vendedor 30%.

La Spec no crea reglas automáticas de reparto.

## 9. Cambios de vendedor posteriores

Esta Spec no reasigna automáticamente una OV ya atribuida.

Si una OV tiene Sales Team:

- editar usuario creador no cambia vendedor;
- guardar nuevamente no reemplaza Sales Team;
- modificar manualmente Sales Team sigue siendo posible según permisos.

La atribución automática es un **default de creación**, no un ownership rígido.

## 10. Comisión histórica

Una modificación futura del `Commission Rate` del Sales Person no debe reinterpretar silenciosamente ventas históricas ya confirmadas.

El Programador debe validar el comportamiento estándar de ERPNext y asegurar que la transacción conserve la tasa aplicada según la semántica estándar de Sales Team.

No implementar recálculo histórico masivo.

## 11. Seguridad

La lógica debe ser server-side.

Debe evitar:

- confiar en valores enviados únicamente por JS;
- permitir que un usuario inyecte un Sales Person no permitido por una ruta custom;
- usar `ignore_permissions=True` innecesariamente;
- otorgar permisos contables adicionales al rol `ComercialFRA`;
- dar acceso directo a Payment Entry, GL Entry o configuración contable.

Esta Spec solo atribuye vendedor/comisión dentro de Sales Order.

## 12. Relación con ComercialFRA

`ComercialFRA` conserva sus permisos actuales sobre Sales Order.

La automatización no requiere agregar roles estándar amplios como:

- Sales User;
- Sales Manager;
- Accounts User;
- Accounts Manager.

La regla debe funcionar para Amaranta con su rol actual `ComercialFRA`.

## 13. Interacción con el código de saldo a favor

Existe código custom `erpn_custom.chile.sales_order_credit` utilizado desde `public/js/sales_order.js`.

Esta Spec no modifica el cálculo financiero del saldo a favor ni Payment Entry.

Sin embargo, durante implementación debe verificarse que el guard de permisos de ese módulo permita a `ComercialFRA` ejecutar únicamente las funciones comerciales autorizadas de consulta/aplicación de saldo sin ampliar funciones de reversión contable.

Ese ajuste puede incluirse en el mismo corte solo si es estrictamente necesario para que la Sales Order de ComercialFRA funcione sin error, manteniendo privilegio mínimo.

## 14. Arquitectura propuesta

Archivo nuevo sugerido:

```text
erpn_custom/selling/sales_person_assignment.py
```

Responsabilidad:

- resolver usuario -> Employee -> Sales Person;
- aplicar Sales Team únicamente si está vacío;
- no contener lógica de UI;
- ser testeable de forma aislada.

Hook esperado en `hooks.py`:

```text
doc_events["Sales Order"]["validate" o "before_validate"]
    -> erpn_custom.selling.sales_person_assignment.assign_sales_person
```

El Programador debe confirmar el evento exacto más compatible con el cálculo estándar ERPNext antes de implementar.

## 15. Fuera de alcance

- crear un motor custom de comisiones;
- calcular nómina o pagar la comisión;
- contabilizar provisiones de comisión;
- generar Salary Slip;
- definir cuándo se paga efectivamente la comisión;
- comisiones escalonadas por metas;
- bonos;
- reparto automático entre múltiples vendedores;
- comisiones distintas por Item/categoría;
- cambiar la tasa 1% de Amaranta;
- cambiar Sales Person estándar por un DocType custom.

## 16. User stories

### US1 — Venta normal de Amaranta (P1)

**Given** Amaranta tiene Employee y Sales Person habilitados con 1%,  
**And** crea una nueva Sales Order sin Sales Team,  
**When** guarda la OV,  
**Then** Sales Team contiene Amaranta Fernandez al 100%,  
**And** Commission Rate es 1%,  
**And** ERPNext calcula el incentivo estándar.

### US2 — Venta CLP 50.000 (P1)

**Given** una venta neta de CLP 50.000 atribuida 100% a Amaranta con tasa 1%,  
**When** ERPNext calcula Sales Team,  
**Then** el incentivo esperado es CLP 500.

### US3 — Sales Team manual preexistente (P1)

**Given** una OV ya tiene Sales Team,  
**When** se guarda,  
**Then** la automatización no agrega ni reemplaza vendedores.

### US4 — Usuario administrativo sin Sales Person (P1)

**Given** Administrator crea una OV y no tiene Sales Person,  
**When** guarda,  
**Then** la OV no falla por esta automatización  
**And** no se asigna vendedor ficticio.

### US5 — Usuario comercial mal configurado (P1)

**Given** un usuario comercial tiene Employee pero no Sales Person,  
**When** crea una OV,  
**Then** no se atribuye otra persona por defecto  
**And** el sistema debe producir comportamiento diagnosticable según el plan aprobado.

### US6 — Reapertura/edición (P1)

**Given** una OV ya tiene Amaranta en Sales Team,  
**When** se edita y vuelve a guardar,  
**Then** no se duplica la fila.

## 17. Criterios de aceptación

La Spec queda aceptada cuando en sandbox se demuestre:

1. Amaranta crea una nueva OV sin tocar Sales Team.
2. Al guardar, aparece automáticamente `Amaranta Fernandez`.
3. `Contribution (%) = 100`.
4. `Commission Rate = 1`.
5. En una venta neta CLP 50.000, `Incentives = CLP 500`.
6. Guardar la misma OV varias veces no duplica Sales Team.
7. Una OV con Sales Team manual no es sobrescrita.
8. Administrator/usuario técnico sin Sales Person puede seguir creando documentos según sus permisos sin recibir Amaranta por defecto.
9. No se agregan roles estándar amplios a Amaranta.
10. No se modifica core Frappe/ERPNext.
11. Tests automatizados pasan.
12. El caso real `SAL-ORD-2026-00014` queda como evidencia histórica del problema, no debe alterarse automáticamente por una migración retroactiva.

## 18. Rollback

Rollback de código:

1. retirar el hook de Sales Order;
2. retirar el módulo de asignación automática;
3. ejecutar migrate/build solo si el mecanismo utilizado lo requiere;
4. ERPNext vuelve al comportamiento estándar: Sales Team debe cargarse manualmente.

No requiere migración destructiva ni reversión de datos.

## 19. Riesgos

**Riesgo principal:** atribuir una venta a la persona equivocada.

Mitigación:

- relación explícita User -> Employee -> Sales Person;
- no usar nombres/correos hardcodeados;
- no actuar si hay ambigüedad;
- no sobrescribir Sales Team existente;
- tests de idempotencia.

**Riesgo secundario:** afectar integraciones o usuarios administrativos que crean Sales Orders.

Mitigación:

- si no existe Sales Person válido, no inventar atribución;
- tests específicos para Administrator/usuarios técnicos.

## 20. Decisiones congeladas

- se usa `Sales Person` estándar;
- se usa `Sales Team` estándar;
- `Sales Person.commission_rate` es la fuente de verdad;
- Amaranta conserva 1%;
- atribución automática solo cuando Sales Team está vacío;
- Contribution inicial = 100%;
- no se liga vendedor al Customer;
- no se crea motor custom de comisiones;
- implementación server-side;
- no se recalculan ventas históricas.

## 21. Siguiente acción del Programador

Antes de programar:

1. leer esta Spec;
2. inspeccionar el controller estándar de Sales Order y Sales Team en la versión instalada;
3. confirmar el evento `before_validate` vs `validate`;
4. confirmar cómo ERPNext copia/calcula `commission_rate`, `allocated_amount` e `incentives`;
5. presentar plan técnico por etapas;
6. presentar plan de pruebas;
7. esperar OK explícito de Miguel.

