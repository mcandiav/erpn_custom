import frappe

from erpn_custom.encargo.inventory import ENCARGO_WAREHOUSE, ENCARGO_WAREHOUSE_NAME, PURCHASE_CURRENCY, STOCK_WAREHOUSE


def execute():
	create_encargo_warehouse()
	backfill_encargos()


def create_encargo_warehouse():
	"""Units received for a customer wait here; they are not free stock for new sales (Spec 018 §8.1)."""
	if frappe.db.exists("Warehouse", ENCARGO_WAREHOUSE):
		return
	matriz = frappe.db.get_value("Warehouse", STOCK_WAREHOUSE, ["company", "parent_warehouse"], as_dict=True)
	if not matriz:
		print(f"{STOCK_WAREHOUSE} no existe: no se crea {ENCARGO_WAREHOUSE}")
		return
	warehouse = frappe.get_doc(
		{
			"doctype": "Warehouse",
			"warehouse_name": ENCARGO_WAREHOUSE_NAME,
			"company": matriz.company,
			"parent_warehouse": matriz.parent_warehouse,
			"is_group": 0,
		}
	)
	warehouse.insert(ignore_permissions=True)
	if warehouse.name != ENCARGO_WAREHOUSE:
		print(f"Bodega creada como {warehouse.name}; se esperaba {ENCARGO_WAREHOUSE}")


def backfill_encargos():
	frappe.db.sql(
		"update `tabEncargo` set purchase_currency=%s where ifnull(purchase_currency, '')=''",
		(PURCHASE_CURRENCY,),
	)
	frappe.db.sql(
		"""update `tabEncargo`
		set received_qty=ifnull(received_qty, 0),
			pending_receive_qty=greatest(ifnull(requested_qty, 0) - ifnull(received_qty, 0), 0)"""
	)
