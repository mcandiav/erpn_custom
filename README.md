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
| 2026-09-27 | 16.0.69 | Spec 014 US6: la búsqueda de productos ofrece "Crear Encargo con estos filtros" (sin resultados y al pie de los resultados); abre Agregar Encargo con Marca, Grupo, Departamento y atributos precargados y el texto buscado como Descripción. Si el filtro de grupo no es el último nivel, el Grupo queda vacío para elegir el tipo | Spec 014 §4 punto 4: sin resultado, un solo paso a Agregar Encargo | Validado en el sitio: filtros sin resultados, familia deja Grupo vacío, texto como Descripción |
| 2026-09-27 | 16.0.70 | Encargo huérfano: al guardar una Orden de Venta en borrador, cada Encargo Draft cuya línea ya no existe pasa a Cancelled con aviso "ENC-… cancelado: se eliminó su línea de la orden". Al validar la orden solo se activan (Open/PENDING) los Encargos cuya línea sigue en la orden. Sustituir un encargo por un producto de bodega = borrar la línea y agregar el producto | Al borrar una línea ENCARGO-PENDIENTE quedaba su Encargo Draft y se abría al validar la orden, llegando al shopper por error | 4 pruebas unitarias nuevas OK; validado en el sitio: ENC-2026-00007 Cancelled al borrar su línea en OV-2026-00002 |
| 2026-09-28 | 16.0.71 | Permisos ComercialFRA para el flujo de la orden (patch v0_0_31): Orden de Venta con validar, cancelar y corregir; Encargo leer/crear/editar; Entrada de reserva de stock leer/crear/validar/cancelar. Eliminar queda reservado a roles superiores | Validar OV-2026-00002 con amaranta fallaba con "Sin permiso para Entrada de reserva de stock": ERPNext crea y cancela la reserva con el usuario actual | Desplegado; la validación seguía fallando (faltaba editar) |
| 2026-09-28 | 16.0.72 | Entrada de reserva de stock: ComercialFRA suma editar (patch v0_0_32 reaplica v0_0_31). Una reserva validada no se puede modificar; eliminar sigue sin darse | ERPNext exige editar al guardar antes de validar; con 16.0.71 seguía "Sin permiso para Entrada de reserva de stock" | Pendiente validación en el sitio |
| 2026-09-28 | 16.0.73 | Spec 013 Fase C — Shopper: rol web `ShopperFRA` (sin Desk ni permisos sobre Encargo; patch v0_0_33) y página móvil `/encargos-shopper` (inicio del rol). El shopper elige lugar (Supplier con marcas, "Todos" o lugar no listado), ve los Encargos Open/PENDING con foto, variante y cantidad, sin cliente, precio de venta ni orden. "Lo encontré": 1/4 barcode (cámara si el navegador lo permite), 2/4 foto producto, 3/4 foto etiqueta, 4/4 precio; confirmar graba todo y `PURCHASED` en una sola operación con bloqueo de fila (otro shopper no la pisa; reintento idéntico no duplica); más de una unidad exige confirmar la cantidad completa. "No encontrado": el Encargo sigue PENDING y visible, se registra el intento (tabla `Encargo Purchase Attempt`) y al tercero queda "Revisar con comercial". Campos nuevos en Encargo: `purchase_supplier` (el `supplier` existente sigue siendo el sugerido), `proposed_supplier_name` (nunca crea Supplier), `purchase_barcode` (no toca el Item), `purchase_price` (Float 2 decimales), fotos de producto y etiqueta | Spec 013 §5, §28 y Fase C con addenda 2026-09-28 | 14 unittests nuevos OK; pendiente validación en el sitio con un usuario Shopper |
| 2026-09-28 | 16.0.74 | Spec 013 Addenda A/B/C y §33: ficha Encargo con sección "Compra Shopper" (estado, shopper, fecha, Supplier validado o lugar propuesto, barcode, precio y fotos de producto y etiqueta visibles) separada de la solicitud original; historial de intentos «No encontrado» dentro de la misma sección; al tercer intento aviso rojo en la ficha "Contactar al cliente" (campo `needs_commercial_review`, filtro de lista), sin cancelar. Página Shopper con barra inferior de módulos (Compras · Más) preparada para sumar Cajas/Recepción Miami; cada módulo conserva su contexto y los filtros de Compras se recuerdan en el teléfono; Más: cambiar lugar, actualizar, cerrar sesión | Addenda de la Spec 013 no cubiertos en 16.0.73 | Presentación solamente (sin cambios de datos ni endpoints); pendiente validación en el sitio |
| 2026-09-28 | 16.0.75 | Página Shopper: "Escanear con la cámara" usa `html5-qrcode` (la misma librería del escáner del Desk, servida por Frappe en `/assets/frappe/node_modules/html5-qrcode/`), con detector nativo cuando existe; lee EAN-13/8, UPC-A/E, Code 128/39, ITF y QR; mensajes según la causa (permiso denegado, sin cámara trasera, cámara en uso); la cámara se apaga al leer, cancelar, cambiar de paso o cerrar | Miguel: el escaneo no funcionaba en el celular (la versión anterior dependía de `BarcodeDetector`, inexistente en Safari iPhone) | Pendiente validación en el celular |
| 2026-09-28 | 16.0.76 | Página Shopper: "Cerrar sesión" (módulo Más) hace POST a `/api/method/logout` y vuelve a `/login`; antes era un enlace GET a `web_logout`, que Frappe 16 rechaza con "No permitido" | Miguel: el shopper no podía cerrar sesión | Verificado en el sitio: GET `logout`/`web_logout` = 403, POST `logout` = 200; validado por Miguel en el celular |
| 2026-09-28 | 16.0.77 | Página Shopper: módulo "Mis compras" (solo lectura) con las compras `PURCHASED` del propio shopper (`list_purchased`); filtro Hoy / Últimos 7 días / Todo (Hoy por defecto), cantidad y total pagado del período; cada tarjeta muestra fecha y hora, lugar, precio, cantidad, barcode y las fotos de producto y etiqueta. El visor privado de imágenes entrega las fotos de una compra solo a su shopper; un pendiente sigue mostrando solo la imagen de referencia. Sin cambios de modelo; no muestra cliente, OV, precio de venta ni vendedor | Instrucción de Miguel: el shopper no podía ver lo que compró. La Spec 013 no define esta vista (desalineación documental a registrar por el Arquitecto) | 17 unittests del shopper OK; suite completa sin fallas nuevas (9 fallas y 1 error previos); validado por Miguel en el celular |
| 2026-09-28 | 16.0.78 | Página Shopper: "Ver referencia" normaliza `reference_url` (campo de texto libre): con `http(s)://` se usa tal cual; si parece dominio (`www.zara.com/...`) se antepone `https://`; si es texto sin dirección se muestra como "Referencia: …" en vez de un enlace roto | Miguel: "Ver referencia" no funcionaba (un valor sin `https://` abría una ruta inexistente dentro de derp.at-once.cl) | Casos probados con node; reemplazado por 16.0.79 |
| 2026-09-28 | 16.0.79 | Página Shopper: se quita "Ver referencia"; `reference_url` deja de enviarse al shopper (fuera de `LIST_FIELDS` y de la tarjeta) | Miguel: el Encargo de prueba tenía en `reference_url` el enlace a `OV-2026-00003` (el shopper veía "no autorizado" y el número de OV); el shopper ya ve todos los datos del Encargo en la tarjeta | 17 unittests del shopper OK; pendiente validación en el celular |
| 2026-09-28 | 16.0.80 | Formulario Encargo (Desk): bajo "Reference URL" aparece "Abrir enlace ↗" clicable (antepone `https://` si falta; texto que no es dirección no genera enlace). Página Shopper: tocar una foto (imagen del encargo, foto de producto o de etiqueta en "Mis compras") la amplía a pantalla completa; tocar de nuevo la cierra | Miguel: el enlace de referencia debe verse en el Encargo y las miniaturas deben ampliarse | Sintaxis JS verificada con node; sin cambios de modelo; ampliar fotos validado por Miguel en el celular |
| 2026-09-28 | 16.0.81 | Página Shopper: vuelve "Ver referencia ↗" (tarjetas de Compras y Mis compras) con `reference_url` filtrado en servidor (`reference_link`): enlaces a tiendas se muestran (se antepone `https://` si falta); enlaces al propio ERP (dominio del sitio o rutas `/desk`, `/app`…) no se envían al celular; texto que no es dirección se muestra como "Referencia: …". Revierte el ocultamiento de 16.0.79 | Miguel: la referencia cargada en el Encargo debe verse en el detalle del shopper. El Encargo de prueba tiene el enlace a `OV-2026-00003`, que queda oculto por diseño | 19 unittests del shopper OK; suite completa sin fallas nuevas; pendiente validación en el celular con un enlace de tienda |
| 2026-09-30 | 16.0.87 | Línea de la Orden de Venta: el botón "Ver Encargo ENC-…" se ubica en la barra del título de la fila y aparece también con la OV validada; antes estaba dentro de las acciones de fila, que Frappe oculta cuando la tabla ya no es editable. El clic abre el Encargo sin colapsar la fila | Miguel: en OV-2026-00077 validada no aparecía el acceso al Encargo | Sintaxis JS verificada con node; pendiente validación en el sitio |
| 2026-09-30 | 16.0.86 | Orden de Venta: la Fecha de entrega vacía toma la fecha de la orden + 7 días. El formulario la precarga al abrir una OV nueva y el servidor la completa en `before_validate` (`selling/delivery_date.py`) si llega vacía por API o importación. La vendedora puede cambiarla; nunca se toca una fecha ya elegida ni una OV validada | Miguel: la fecha de entrega obligatoria entorpecía guardar la OV | 4 unittests nuevos OK; suite completa sin fallas nuevas; pendiente validación en el sitio |
| 2026-09-30 | 16.0.85 | Spec 015: la Orden de Venta en borrador se guarda sin líneas (patch `v0_0_34`, Property Setter `Sales Order.items.reqd = 0`, solo Sales Order), así Agregar Encargo se usa sin fila fantasma. `before_submit` exige primero al menos una línea y luego pago aplicado > 0 (`chile.sales_order_credit.applied_to_order`: suma de `Payment Entry Reference` submitted de la OV; el saldo del cliente no aplicado no cuenta), antes del split stock/Encargo, la validación de ENCARGO-PENDIENTE, los Encargos de faltantes y la reserva. Sin cambios en `on_submit` (Encargos a Open/PENDING y reserva) ni en el Shopper. Se salta 16.0.82–16.0.84, ya usadas y revertidas | Spec 015: el vendedor creaba y borraba una fila temporal para obtener el número de OV (caso OV-2026-00076) | 3 unittests nuevos OK; suite completa sin fallas nuevas (9 fallas y 1 error previos); pendiente validación en el sitio con ComercialFRA |
| 2026-09-27 | 16.0.68 | Encargo: vista previa de la Imagen de referencia bajo el campo, al ancho completo de la columna; clic abre la imagen en otra pestaña; se actualiza al cambiar la imagen | Miguel: la imagen solo se veía como enlace al PNG | Validado en el sitio (ENC-2026-00006) |
| 2026-09-27 | 16.0.67 | Encargo: los campos de texto antiguos Size/Color se ocultan cuando el Encargo tiene Grupo de producto (siguen llenándose por dentro para comprador y recepción); solo se ven en Encargos antiguos sin grupo | Miguel: la ficha mostraba Tamaño y Color dos veces | Validado en el sitio (ENC-2026-00006) |
| 2026-09-27 | 16.0.66 | Línea ENCARGO-PENDIENTE de la orden: la descripción suma las características del Encargo (Marca, Grupo, Departamento, atributos, Modelo) y la imagen del Encargo; se actualiza al guardar el Encargo con la orden en borrador y en cada validate de la orden (`encargo/sales_order_line.py`). Botón "Ver Encargo ENC-…" en el encabezado de la ventana de la fila. Aviso cuando un atributo escrito a mano no está en la lista (el control Autocomplete lo borraba en silencio) en producto, Encargo y diálogo. Encargo conocido copia también la Familia del producto. Lista de Encargos: columna Grupo, filtros Talla y Color, buscador por marca/grupo/talla/color. Parche `v0_0_30`: Familia de Encargos conocidos y resumen de líneas en órdenes en borrador | Miguel: al abrir la línea no se veían imagen, color ni los datos ingresados; llegar al Encargo era difícil; el color inventado se borraba sin aviso; ENC-2026-00002 sin Familia | 44 unittests locales OK; validado en el sitio: botón Ver Encargo, resumen e imagen en la línea de OV-2026-00001, color inventado no se graba, ENC-2026-00002 con Familia Calzado |
| 2026-09-27 | 16.0.65 | Encargo con la clasificación del producto: campos Grupo de producto (solo tipos), Familia (calculada), Departamento y Color/Talla/Taco/Manga/Tamaño/Tono/Contenido con los mismos nombres y listas que el Item; validación compartida `catalog.item.apply_classification` (Item y Encargo) y JS compartido `public/js/classification.js` (en Calzado solo tallas de calzado del departamento). Encargo desconocido exige Marca y Grupo de producto; Talla/Color de texto se llenan desde las listas. "Agregar Encargo" usa esos campos y ofrece "Copiar de un producto similar" (código de barras en blanco). Parche `v0_0_29` completa la clasificación de los Encargos conocidos | Miguel: el Encargo debe elegirse de listas, como al crear un producto; el diálogo tenía Talla/Color/Modelo en texto libre | 36 unittests locales OK; validado en el sitio: copiar de 198446906618 y cambiar talla, Encargo desde cero con Cartera (solo Tamaño y Color), color inventado rechazado, formulario Item sin cambios |
| 2026-09-27 | 16.0.64 | Encargo de producto conocido: marca, talla (o tamaño), color y descripción se copian del Item y el modelo queda vacío en cada guardado y al crearlo desde la OV; en el formulario esos campos son de solo lectura. Parche `v0_0_28` corrige los Encargos conocidos existentes | Miguel: mismo código de barras = mismo producto, no se edita nada; otra talla/color es otro código o un Encargo de producto desconocido. ENC-2026-00002 tenía talla "5.5", color "blanco" y modelo "zadig" escritos a mano sobre una bota US 7.5 café | 30 unittests locales OK; validado en el sitio (ENC-2026-00002 con talla y color del Item) |
| 2026-09-27 | 16.0.63 | Spec 014 Etapa 3b: botón "Buscar producto" en la Orden de Venta (borrador). Filtros: código/nombre/SKU, Grupo/Familia/Tipo (incluye todo lo que cuelga debajo), Marca, Departamento (Mujer y Hombre incluyen Unisex), Bodega y los atributos de la familia elegida. Muestra todos los productos, con o sin stock, ordenados por marca y nombre, con disponible en la bodega (existencia − reservado) y total de todas las bodegas; "Agregar" crea la línea con la bodega elegida. Sin stock, el Encargo lo crea el flujo existente de la Spec 013 al guardar. Servidor: `erpn_custom.catalog.search` | Miguel: por ahora solo la búsqueda del vendedor; nombre del producto = el del proveedor/fabricante. Spec 014 §3.4 corregida por Arquitectura para eliminar la generación automática del nombre | Validado en el sitio: OV SAL-ORD-2026-00017 con 2 unidades de 198446906618 (stock 1) → 1 reservada (MAT-SRE-2026-00012) y ENC-2026-00002 por 1 |
| 2026-09-27 | 16.0.62 | Importador: una columna por atributo (color, talla, taco, manga, tamano, tono, contenido) respetando los atributos de la familia; talla corta resuelta por familia+departamento ("S" Mujer → "S · US 4-6 · EU 36-38"); en Bolsos la columna talla alimenta Tamaño ("Ns" se ignora); el tipo debe ser hoja del árbol aunque venga del Diccionario. `purge_catalog` elimina inventarios en borrador | Primera carga de 66: tallas sin departamento, bolsos sin Tamaño y un tipo apuntando a una familia | Recarga de prueba OK: 66 productos con Grupo-Familia-Tipo, marca y todos los atributos de su familia; apertura AJU-2026-00001 validada (81 unidades) |
| 2026-09-27 | 16.0.61 | Importador `erpn_custom.catalog.importer.import_products` (bench execute, System Manager): lee la hoja "productos" de un .xlsx subido como File privado, traduce Marca/Tipo/Departamento/Color/Talla con el Diccionario Aduana (textos desconocidos quedan "En espera"), exige marca y tipo hoja, código de barras = código y nunca repetido, texto sobrante a la descripción; `dry_run=1` solo informa y genera CSV de incompletos; real crea productos y un inventario inicial en borrador en Matriz - FRAG. Limpieza ejecutada: quedan ENCARGO-PENDIENTE y Notengocodigo | Recarga limpia del catálogo con Grupo-Familia-Tipo y atributos; prueba con 100 filas con stock | Pendiente simulación |
| 2026-09-27 | 16.0.60 | `purge_catalog` acepta `include_stalled_reposts=1` para incluir reprocesos del inventario anulado que quedaron detenidos en "In Progress" | 370 reprocesos detenidos desde 13:02 tras el borrado masivo y reinicios de workers | Pendiente simulación |
| 2026-09-27 | 16.0.59 | `purge_catalog` elimina también los Repost Item Valuation por producto/almacén que ERPNext crea al anular el inventario (misma fecha y compañía); se niega si alguno sigue en curso | La simulación mostró 928 productos bloqueados por esos reprocesos | Pendiente simulación con reprocesos terminados |
| 2026-09-27 | 16.0.58 | `purge_catalog` informa el documento real que bloquea cada producto (Frappe lo oculta tras "You can disable this Item") y agrupa los bloqueos por tipo de documento | La simulación dejó 930 productos bloqueados sin motivo visible | Pendiente nueva simulación |
| 2026-09-27 | 16.0.57 | Herramienta `erpn_custom.catalog.purge.purge_catalog` (bench execute, solo System Manager): elimina comprobantes de inventario ya anulados con sus movimientos anulados, luego todo Item borrable (salvo `ENCARGO-PENDIENTE`) y los grupos fuera del árbol; `dry_run=1` simula y deshace | Recarga limpia adelantada antes de la 3b: los productos del CSV no tienen Grupo-Familia-Tipo ni atributos | Pendiente simulación en el sitio |
| 2026-09-27 | 16.0.56 | Item: Marca obligatoria (validación en servidor + asterisco en el formulario), excepto el producto técnico `ENCARGO-PENDIENTE` | Decisión de Miguel. 4 productos sin marca al activarla: `ENCARGO-PENDIENTE` (exento), `198446914354`, `Notengocodigo`, `TEST-MVP-001` (pedirán marca al editarse) | Pendiente deploy automático |
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

**Spec activa:** `015-sales-order-draft-payment-gate` — AUTORIZADA. Permitir guardar OV Draft sin líneas; Submit exige al menos una línea válida y pago aplicado > 0; Encargos llegan al Shopper solo tras Submit exitoso. El Programador debe leer README + Spec/plan/tasks 015, inspeccionar el core/meta efectivo y ejecutar el corte sin rediseñar Spec 013.

Documento: `specs/015-sales-order-draft-payment-gate/spec.md`

**Spec cerrada:** `014-clasificacion-producto-busqueda` — árbol Grupo → Familia → Tipo, atributos controlados por Familia (tallas US · EU · CL en una sola lista por Departamento, colores multilingües en un solo registro), diccionario de aduana, búsqueda por facetas para la vendedora y recarga limpia de la carga de prueba. La Spec se trabaja localmente (no se versiona). Etapa 1 en `16.0.47`; **completa y validada en el sitio en `16.0.69`** (2026-09-27): US1–US8 y §6 Encargo clasificado. Próxima Spec: por definir por el Arquitecto (candidatas: precio de venta y costos de compra; vista de celular con escaneo, §11).

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
