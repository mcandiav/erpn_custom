"""Spec 019: each unit received for an ENCARGO-PENDIENTE line becomes one unit of the real Item on the Sales Order.

ERPNext "Update Items" cancels and recreates every Stock Reservation Entry of the order, which would undo the
partial reservations of Specs 013/018. The order is therefore changed with the same ERPNext building blocks
(set_order_defaults, validate_child_on_delete and the post-save sequence of update_child_qty_rate) except that
step; the only reservation touched is the one of the unit being materialized.
"""

import frappe
from frappe import _
from frappe.utils import flt, now_datetime, strip_html

from erpn_custom.encargo import ENCARGO_PENDIENTE_ITEM, inventory

PENDING = "PENDING"
MATERIALIZED = "MATERIALIZED"
REVERSED = "REVERSED"
ERROR = "ERROR"
RETRYABLE = (PENDING, ERROR)
LOG_DOCTYPE = "Encargo Materializacion"
ENCARGO_FIELDS = [
	"name",
	"status",
	"source_type",
	"sales_order",
	"sales_order_item",
	"requested_qty",
	"materialized_qty",
]
# Commercial conditions of the technical line; the shopper cost never reaches the sale price.
INHERITED_FIELDS = (
	"rate",
	"price_list_rate",
	"discount_percentage",
	"discount_amount",
	"margin_type",
	"margin_rate_or_amount",
	"rate_with_margin",
	"delivery_date",
	"cost_center",
	"project",
)
NUMERIC_MATCH_FIELDS = ("rate", "price_list_rate", "discount_percentage", "discount_amount")


def applies(encargo):
	return bool(encargo) and encargo.get("source_type") == "UNKNOWN_ITEM"


def pending_qty(requested_qty, materialized_qty):
	return max(flt(requested_qty) - flt(materialized_qty), 0)


def incompatible_message():
	return _(
		"La línea ENCARGO-PENDIENTE tiene movimientos posteriores incompatibles. "
		"Requiere revisión de ComercialFRA/System Manager antes de materializar."
	)


def order_problem(order_docstatus, encargo_status):
	if order_docstatus == 2:
		return _("La Orden de Venta está cancelada: la unidad no se vincula (Spec 018, stock normal o resolución comercial).")
	if order_docstatus != 1:
		return _("La Orden de Venta no está validada.")
	if encargo_status == "Cancelled":
		return _("El Encargo está cancelado.")
	return None


def technical_problem(row, pending):
	"""Spec 019 §11: only quantity not delivered nor billed, and matching the Encargo, is transformed."""
	if pending < 1:
		return _("El Encargo ya está materializado completo: la unidad no puede consumir una demanda inexistente.")
	if not row:
		return _("La línea ENCARGO-PENDIENTE del Encargo ya no existe en la Orden de Venta.")
	if row.get("item_code") != ENCARGO_PENDIENTE_ITEM:
		return _("La línea del Encargo ya no es ENCARGO-PENDIENTE.")
	if flt(row.get("delivered_qty")) or flt(row.get("billed_amt")) or flt(row.get("qty")) != flt(pending):
		return incompatible_message()
	return None


def is_compatible(row, encargo, item_code, technical, warehouse):
	"""A real line of the same Encargo grows only while nothing commercial differs (Spec 019 §6)."""
	if row.get("custom_encargo_origin") != encargo or row.get("item_code") != item_code:
		return False
	if row.get("warehouse") != warehouse or row.get("uom") != row.get("stock_uom"):
		return False
	return all(flt(row.get(field)) == flt(technical.get(field)) for field in NUMERIC_MATCH_FIELDS)


def compatible_row(rows, encargo, item_code, technical, warehouse):
	return next((row for row in rows if is_compatible(row, encargo, item_code, technical, warehouse)), None)


def real_row_values(technical, encargo, warehouse):
	values = {field: technical.get(field) for field in INHERITED_FIELDS if technical.get(field) not in (None, "")}
	values.update(
		{
			"qty": 1,
			"warehouse": warehouse,
			"custom_encargo_origin": encargo,
			"custom_encargo_source_row": technical.get("name"),
		}
	)
	return values


def reverse_problem(real_row):
	if not real_row:
		return _("La línea real de la Orden de Venta ya no existe: revisa la OV antes de devolver la unidad.")
	if flt(real_row.get("delivered_qty")) > flt(real_row.get("qty")) - 1:
		return _("La unidad ya fue entregada al cliente: usa la devolución estándar de la entrega.")
	if flt(real_row.get("billed_amt")) > flt(real_row.get("rate")) * (flt(real_row.get("qty")) - 1):
		return _("La línea real ya está facturada: usa la nota de crédito estándar antes de devolver la unidad.")
	return None


def _lock_encargo(name):
	return frappe.db.get_value("Encargo", name, ENCARGO_FIELDS, as_dict=True, for_update=True)


def _lock_order(name):
	# Two units of the same order arriving at once must not read the same line quantities.
	frappe.db.sql("select name from `tabSales Order` where name=%s for update", (name,))
	return frappe.get_doc("Sales Order", name)


def _row(order, name):
	return next((row for row in order.items if row.name == name), None)


def _set_qty(row_name, qty):
	# stock_qty, amounts and totals are recomputed by _refresh_order.
	frappe.db.set_value("Sales Order Item", row_name, "qty", qty, update_modified=False)


def _insert_row(order_name, item_code, values):
	from erpnext.controllers.accounts_controller import set_order_defaults

	child = set_order_defaults(
		"Sales Order", order_name, "Sales Order Item", "items", {"item_code": item_code, "delivery_date": values.get("delivery_date")}
	)
	child.update(values)
	child.flags.ignore_validate_update_after_submit = True
	order = frappe.get_doc("Sales Order", order_name)
	child.idx = len(order.items) + 1
	child.insert()
	return child.name


def _delete_row(order_name, row_name):
	from erpnext.controllers.accounts_controller import validate_child_on_delete

	order = frappe.get_doc("Sales Order", order_name)
	row = _row(order, row_name)
	validate_child_on_delete(row, order)
	row.cancel()
	row.delete()


def _refresh_order(order_name):
	"""Post-save sequence of erpnext update_child_qty_rate, without its cancel-and-recreate of reservations."""
	from erpnext.stock.doctype.packed_item.packed_item import make_packing_list

	order = frappe.get_doc("Sales Order", order_name)
	order.flags.ignore_validate_update_after_submit = True
	order.set_qty_as_per_stock_uom()
	order.calculate_taxes_and_totals()
	order.set_total_in_words()
	if not order.is_subcontracted:
		make_packing_list(order)
		order.set_gross_profit()
	frappe.get_cached_doc("Authorization Control").validate_approving_authority(
		order.doctype, order.company, order.base_grand_total
	)
	order.set_payment_schedule()
	order.check_credit_limit()
	for idx, row in enumerate(order.items, start=1):
		row.idx = idx
	order.save()
	order.validate_selling_price()
	order.validate_for_duplicate_items()
	order.validate_warehouse()
	order.update_reserved_qty()
	order.update_project()
	order.update_prevdoc_status("submit")
	order.update_delivery_status()
	order.reload()
	order.update_blanket_order()
	order.update_billing_percentage()
	order.set_status()
	order.validate_uom_is_integer("uom", "qty")
	order.validate_uom_is_integer("stock_uom", "stock_qty")


def _set_encargo_qty(encargo, materialized):
	frappe.db.set_value(
		"Encargo",
		encargo.name,
		{
			"materialized_qty": materialized,
			"pending_materialize_qty": pending_qty(encargo.requested_qty, materialized),
		},
		update_modified=True,
	)


def _log(unit, result, user, **values):
	count = frappe.db.count(LOG_DOCTYPE, {"parent": unit.encargo})
	frappe.get_doc(
		{
			"doctype": LOG_DOCTYPE,
			"name": frappe.generate_hash(length=10),
			"parent": unit.encargo,
			"parenttype": "Encargo",
			"parentfield": "materializations",
			"idx": count + 1,
			"result": result,
			"event_on": now_datetime(),
			"user": user,
			"recepcion_unidad": unit.name,
			"scan_event_id": unit.scan_event_id,
			"sales_order": unit.sales_order,
			"item": unit.item,
			"qty": 1,
			**values,
		}
	).db_insert()


def _materialize(unit, user):
	enc = _lock_encargo(unit.encargo)
	if not enc:
		frappe.throw(_("Encargo {0} no encontrado.").format(unit.encargo))
	order = _lock_order(enc.sales_order)
	problem = order_problem(order.docstatus, enc.status)
	pending = pending_qty(enc.requested_qty, enc.materialized_qty)
	technical = _row(order, enc.sales_order_item)
	problem = problem or technical_problem(technical, pending)
	if problem:
		frappe.throw(problem)

	before = flt(technical.qty)
	target = compatible_row(order.items, enc.name, unit.item, technical, unit.warehouse)
	if target:
		_set_qty(target.name, flt(target.qty) + 1)
		real_row = target.name
	else:
		real_row = _insert_row(order.name, unit.item, real_row_values(technical, enc.name, unit.warehouse))
	if before > 1:
		_set_qty(technical.name, before - 1)
	else:
		_delete_row(order.name, technical.name)
	_refresh_order(order.name)

	unit.stock_reservation_entry, unit.reservation_note = inventory.reserve_unit(
		order.name, real_row, unit.item, unit.warehouse
	)
	materialized = flt(enc.materialized_qty) + 1
	_set_encargo_qty(enc, materialized)
	_log(
		unit,
		MATERIALIZED,
		user,
		source_row=technical.name,
		sales_order_item=real_row,
		technical_qty_before=before,
		technical_qty_after=before - 1,
		materialized_qty=materialized,
	)
	return real_row


def materialize(unit, user=None):
	"""Runs after the Material Receipt in the same transaction; a failure never undoes the receipt (Spec 019 §16)."""
	if unit.materialization_status == MATERIALIZED:
		return
	user = user or unit.received_by
	frappe.db.savepoint("encargo_materialize")
	try:
		real_row = _materialize(unit, user)
	except Exception as e:
		frappe.db.rollback(save_point="encargo_materialize")
		frappe.clear_messages()
		unit.materialization_status = ERROR
		unit.materialization_message = _("No se pudo vincular a la OV: {0}").format(strip_html(str(e)))[:500]
		unit.reservation_note = _("Apartado por bodega y Encargo hasta vincular la unidad a la Orden de Venta.")
		_log(unit, ERROR, user, message=unit.materialization_message)
		return
	unit.update(
		{
			"materialization_status": MATERIALIZED,
			"materialized_row": real_row,
			"materialized_on": now_datetime(),
			"materialized_by": user,
			"materialization_message": None,
		}
	)


def _restore_technical_row(order, enc, real):
	"""The returned unit is again an undetermined obligation on the order (Spec 019 §14)."""
	from erpn_custom.encargo.sales_order_line import line_values

	technical = _row(order, enc.sales_order_item)
	if technical and technical.item_code == ENCARGO_PENDIENTE_ITEM:
		_set_qty(technical.name, flt(technical.qty) + 1)
		return technical.name
	source = frappe.db.get_value("Encargo", enc.name, ["description", "reference_image"], as_dict=True)
	values = {field: real.get(field) for field in INHERITED_FIELDS if real.get(field) not in (None, "")}
	values.update({"qty": 1, "custom_encargo": enc.name, "custom_encargo_qty": 1, **line_values(source)})
	name = _insert_row(order.name, ENCARGO_PENDIENTE_ITEM, values)
	frappe.db.set_value("Encargo", enc.name, "sales_order_item", name, update_modified=False)
	return name


def reverse(unit, user, reason=None):
	"""Devolver a stock of a materialized unit: the real line gives the unit back to ENCARGO-PENDIENTE."""
	if unit.materialization_status != MATERIALIZED:
		return
	enc = _lock_encargo(unit.encargo)
	order = _lock_order(enc.sales_order)
	real = _row(order, unit.materialized_row)
	problem = reverse_problem(real)
	if problem:
		frappe.throw(problem)
	technical = _restore_technical_row(order, enc, real)
	if flt(real.qty) > 1:
		_set_qty(real.name, flt(real.qty) - 1)
	else:
		_delete_row(order.name, real.name)
	_refresh_order(order.name)
	materialized = max(flt(enc.materialized_qty) - 1, 0)
	_set_encargo_qty(enc, materialized)
	_log(
		unit,
		REVERSED,
		user,
		source_row=technical,
		sales_order_item=real.name,
		materialized_qty=materialized,
		message=reason,
	)
	unit.materialization_status = REVERSED


def block_pending_delivery(doc, method=None):
	"""Delivery Note before_validate: ENCARGO-PENDIENTE is never delivered; its real Item arrives through Spec 019."""
	if doc.get("is_return"):
		return
	pending = [row for row in doc.get("items") or [] if row.item_code == ENCARGO_PENDIENTE_ITEM]
	if not pending:
		return
	if doc.is_new() and len(pending) < len(doc.items):
		for row in pending:
			doc.remove(row)
		for idx, row in enumerate(doc.items, start=1):
			row.idx = idx
		frappe.msgprint(
			_("Se quitaron {0} línea(s) ENCARGO-PENDIENTE: se entregan cuando llega el producto real.").format(len(pending)),
			alert=True,
			indicator="orange",
		)
		return
	frappe.throw(_("ENCARGO-PENDIENTE no se entrega: espera la recepción en Chile del producto real."))


@frappe.whitelist()
def order_summary(sales_order):
	"""Requested / materialized / pending per Encargo of the order, with its real lines (Spec 019 §17.1)."""
	frappe.has_permission("Sales Order", "read", sales_order, throw=True)
	encargos = frappe.get_all(
		"Encargo",
		filters={"sales_order": sales_order, "source_type": "UNKNOWN_ITEM", "status": ("!=", "Cancelled")},
		fields=["name", "requested_qty", "materialized_qty", "pending_materialize_qty", "sales_order_item"],
		order_by="creation asc",
	)
	if not encargos:
		return []
	lines = frappe.get_all(
		"Sales Order Item",
		filters={"parent": sales_order, "parenttype": "Sales Order", "custom_encargo_origin": ("is", "set")},
		fields=["name", "idx", "item_code", "item_name", "qty", "custom_encargo_origin"],
		order_by="idx asc",
	)
	for enc in encargos:
		enc.lines = [line for line in lines if line.custom_encargo_origin == enc.name]
	return encargos
