# Feature Specification: Navegación operacional VendedorFRA sin Desktop general

**Feature Branch**: `[011-vendedorfra-operational-navigation]`

**Created**: 2026-09-19

**Status**: Active — código implementado en `erpn_custom` (guard JS + `app_include_js`); pendiente build/cache en sitio, pruebas operativas y cierre.

**Parent context**: `Perfiles FRAgallardo.md`, `config-vendedor-operativo-fra.md`, piloto Amaranta Fernandez, Frappe/ERPNext v16.

## 0. Regla de trabajo

1. Leer `README.md` de este repo y esta Spec.
2. Revisar el comportamiento real de navegación de Frappe v16 instalado antes de escribir código.
3. Presentar plan técnico por etapas + plan de pruebas.
4. Esperar OK explícito de Miguel antes de programar.
5. No modificar Frappe/ERPNext core.
6. No ampliar permisos para resolver un problema visual.
7. No hardcodear el usuario `amaranta@fragallardo.com`; la solución debe depender de rol/configuración operacional.

## 1. Problema observado

El usuario piloto de ventas tiene correctamente restringidos sus permisos funcionales mediante el rol `ComercialFRA`, pero al ingresar a ERPNext aterriza en el Desktop general `/desk`.

En ese Desktop aparecen iconos de áreas que no corresponden a su trabajo cotidiano, entre ellas:

- Organización
- Contabilidad
- Bienes
- Compras
- Manufactura
- Calidad
- Ventas
- Almacén
- Subcontratación

Esto produce ruido, ambigüedad y una experiencia inadecuada para un usuario operativo, aunque los permisos reales de DocType sigan impidiendo acciones no autorizadas.

También se comprobó en el sitio:

- `User.default_workspace = ComercialFRA`
- `User.default_app = erpn_custom`
- `User.module_profile = ComercialFRA`

Aun así, una sesión nueva del usuario piloto continúa llegando al Desktop general.

El Workspace `ComercialFRA` ya existe y ofrece una interfaz mucho más adecuada, con acceso directo a:

- Clientes
- Contactos
- Direcciones
- Productos
- Precios de Productos
- Órdenes de venta

Por lo tanto el problema no es falta de Workspace, sino que el usuario operativo sigue expuesto al Desktop general.

## 2. Fundamento de la necesidad

### 2.1 Evidencia upstream de Frappe v16

La necesidad no nace de una preferencia estética sino de limitaciones/bugs conocidos de navegación en Frappe v16:

1. **frappe/frappe#41702 — “Blocking modules via Module Profile no longer hides their desktop icons”**
   - reportado específicamente sobre Frappe v16.28.0;
   - los módulos bloqueados pueden seguir mostrando iconos clickeables en Desktop.
   - https://github.com/frappe/frappe/issues/41702

2. **frappe/frappe#40517 — “Workspace Role Permissions and Module Profile Restrictions Not Applied to Desktop Icons”**
   - documenta que las restricciones de Workspace/Module Profile no se reflejan correctamente en los iconos del Desktop.
   - https://github.com/frappe/frappe/issues/40517

3. **frappe/frappe#38691 / PR #38726 — Default Workspace routing**
   - documenta fallas en el enrutamiento al Workspace predeterminado y un ajuste posterior en Frappe.
   - https://github.com/frappe/frappe/issues/38691
   - https://github.com/frappe/frappe/pull/38726

4. **PR #39927 — “feat: simplify navigation”**
   - reconoce explícitamente que v16 tiene un problema de navegación;
   - orienta la evolución del producto hacia navegación centrada en workspaces/selector lateral y menor protagonismo del Desktop de iconos.
   - https://github.com/frappe/frappe/pull/39927

### 2.2 Decisión de negocio FRA

Para un administrador es aceptable disponer del Desktop general porque administra múltiples áreas.

Para un vendedor operativo FRA no lo es. La interfaz debe:

- reducir decisiones innecesarias;
- evitar entradas ambiguas;
- presentar únicamente las funciones necesarias para vender;
- hacer el flujo repetible y fácil de aprender;
- separar experiencia de usuario de seguridad.

**Los permisos continúan siendo la capa de seguridad. La navegación operacional es una capa de UX.**

## 3. Objetivo

Para usuarios operativos que cumplan la política de navegación FRA, el punto de entrada y el “Inicio” del Desk deben ser el Workspace operacional, actualmente:

`/desk/comercialfra`

El usuario no debe trabajar desde el Desktop general `/desk`.

## 4. Política inicial de elegibilidad

Para esta Spec el comportamiento aplica cuando se cumplan conjuntamente:

1. el usuario posee el rol `ComercialFRA`;
2. su Workspace predeterminado es `ComercialFRA`;
3. no es `Administrator`;
4. no se trata de un administrador que deba conservar explícitamente el Desktop general.

No hardcodear correo, nombre ni ID del usuario piloto.

La implementación debe quedar preparada para extender la política posteriormente a otros roles/workspaces FRA (`PagosFRA`, `DespachoFRA`, `RecepcionFRA`) sin reescribir el mecanismo base.

## 5. Comportamiento requerido

### US1 — Login del vendedor (P1)

**Given** un usuario elegible con `ComercialFRA`,  
**When** inicia sesión normalmente,  
**Then** su experiencia final debe quedar en `/desk/comercialfra`, aunque Frappe inicialmente lo envíe a `/desk`.

### US2 — Inicio/Home del Desk (P1)

**Given** un usuario elegible navegando por Customer, Sales Order, Item u otra pantalla autorizada,  
**When** pulsa el logo/Home o cualquier navegación estándar que lo lleve exactamente a `/desk`,  
**Then** debe ser redirigido a `/desk/comercialfra`.

### US3 — Acceso manual a /desk (P1)

**Given** un usuario elegible,  
**When** escribe o abre exactamente `/desk`,  
**Then** debe terminar en `/desk/comercialfra`.

### US4 — Navegación funcional normal (P1)

**Given** un usuario elegible,  
**When** navega a rutas funcionales como Customer, Sales Order, Item o al propio Workspace,  
**Then** no debe ser redirigido arbitrariamente ni perder el contexto.

### US5 — Administrador sin impacto (P1)

**Given** Administrator o un usuario administrativo no elegible,  
**When** entra a `/desk`,  
**Then** conserva el Desktop general estándar.

## 6. Decisión arquitectónica propuesta

### 6.1 Enfoque

Implementar en `erpn_custom` un **guard de navegación del Desk**, cargado globalmente mediante el mecanismo estándar de assets/hooks de Frappe.

Responsabilidad única del guard:

```text
route exacta /desk
    +
usuario elegible por política FRA
    ↓
/desk/comercialfra
```

No modificar el core de Frappe.

### 6.2 Implementación esperada

El Programador debe validar la API exacta de router disponible en la versión instalada y proponer la variante final antes de programar.

Diseño esperado:

- nuevo asset JS de propósito único, por ejemplo:
  - `erpn_custom/public/js/operational_navigation.js`
- carga global por `app_include_js` en `hooks.py`;
- función pura/separable que determine si el usuario es elegible;
- función que determine si la ruta actual representa **solo** el Desktop raíz;
- ejecución:
  - al cargar Desk;
  - al cambiar de ruta hacia el Desktop raíz;
- target:
  - Workspace configurado/permitido, actualmente `ComercialFRA`.

### 6.3 Restricciones técnicas

- NO modificar `frappe` ni `erpnext`.
- NO crear fork.
- NO ocultar iconos uno por uno.
- NO usar Module Profile como mecanismo de solución.
- NO modificar permisos para esconder navegación.
- NO interceptar rutas funcionales distintas de Desktop raíz.
- NO generar bucles de redirección.
- NO depender del email de Amaranta.
- NO romper Browser Back/Forward.
- NO introducir una nueva tabla/DocType para esta Spec salvo justificación técnica previa y OK.

## 7. Alcance

### Incluido

- redirección operacional desde Desktop raíz;
- login que termine finalmente en `ComercialFRA`;
- Home/logo que vuelva a `ComercialFRA`;
- acceso manual a `/desk`;
- protección de Administrator;
- diseño extensible a otros workspaces FRA.

### Fuera de alcance

- arreglar upstream los Desktop Icons de Frappe;
- cambiar el diseño del Desktop de Administrator;
- reimplementar el nuevo sistema de navegación del PR #39927;
- backport completo de Frappe `develop`;
- cambiar permisos de DocTypes;
- esconder Ctrl+K;
- impedir URLs directas a documentos para los que el usuario tenga permiso;
- resolver en esta Spec PagosFRA / DespachoFRA / RecepcionFRA.

## 8. Criterios de aceptación

La Spec se considera aceptada cuando:

1. Sesión limpia de Amaranta → termina en `/desk/comercialfra`.
2. Escribir `https://derp.at-once.cl/desk` como Amaranta → termina en `/desk/comercialfra`.
3. Pulsar Home/logo desde Customer o Sales Order → termina en `/desk/comercialfra`.
4. Abrir cada acceso del Workspace ComercialFRA funciona:
   - Clientes
   - Contactos
   - Direcciones
   - Productos
   - Precios de Productos
   - Órdenes de venta
5. Navegar a un documento permitido NO dispara redirección incorrecta.
6. Administrator → `/desk` sigue mostrando el Desktop estándar.
7. Usuario sin `ComercialFRA` → comportamiento estándar de Frappe.
8. No hay loop, parpadeo continuo ni errores JS en consola.
9. Los permisos efectivos antes/después son idénticos.
10. No existen cambios en core Frappe/ERPNext.

## 9. Casos borde

- Usuario con `ComercialFRA` pero sin Workspace predeterminado: no redirigir silenciosamente a un destino inventado; registrar/usar fallback definido por Programador y aprobado antes de implementar.
- Workspace configurado pero no accesible al usuario: no crear loop; fallar de forma segura y permitir diagnóstico.
- Usuario administrativo que además tenga `ComercialFRA`: la política debe proteger explícitamente el acceso administrativo general.
- Actualización futura de Frappe que resuelva nativamente esta navegación: la customización debe poder retirarse eliminando un hook/asset, sin migración de datos.
- Entrada con parámetros o hash: el guard debe identificar correctamente el Desktop raíz sin afectar rutas hijas.

## 10. Observabilidad y diagnóstico

La solución debe ser simple de diagnosticar:

- nombre del asset y función explícitos;
- comentarios en código indicando que es workaround de navegación Frappe v16 y referenciando #41702 / #40517 / #39927;
- evitar logs ruidosos en producción;
- en caso de error de target, no bloquear completamente el Desk.

## 11. Rollback

Rollback esperado:

1. retirar/deshabilitar el asset del `app_include_js`;
2. build/cache según procedimiento estándar Frappe;
3. el sistema vuelve al comportamiento estándar `/desk`.

No debe requerir restaurar DB ni revertir datos.

## 12. Riesgo

**Riesgo técnico: bajo**, siempre que:

- el guard solo actúe sobre Desktop raíz;
- se use API pública/estable del router disponible en v16;
- se pruebe Administrator y navegador Back/Forward;
- no se toque core.

**Riesgo operativo de no resolverlo: medio/alto** para adopción del ERP, por confusión, errores de navegación y capacitación innecesaria del vendedor.

## 13. Siguiente acción del Programador

Antes de programar:

1. revisar esta Spec y el router real de Frappe v16 del sitio;
2. confirmar cómo representa el Desktop raíz la API del router;
3. confirmar cómo expone `default_workspace` en `frappe.boot.user`;
4. presentar plan de implementación por etapas;
5. presentar plan de pruebas;
6. preguntar: **“Estamos listailor para programar Miguel?”**
7. esperar OK explícito.
