import frappe
from frappe import _
from frappe.utils import add_to_date, get_datetime, now_datetime

from erpn_custom.chile.couriers.registry import get_courier_adapter

CREATION_STATES_BLOCKING = ("Creating", "Created", "Uncertain")
STALE_CREATING_MINUTES = 2


def _get_shipment(name):
	return frappe.get_doc("Shipment", name)


def _get_config(shipment):
	config_name = (shipment.custom_courier_configuration or "").strip()
	if not config_name:
		frappe.throw(_("Seleccione Courier Configuration en el Shipment"))
	config = frappe.get_doc("Courier Configuration", config_name)
	if not config.enabled:
		frappe.throw(_("Courier Configuration {0} está deshabilitada").format(config_name))
	return config


def _provider_code(config):
	return frappe.db.get_value("Courier Provider", config.provider, "provider_code") or config.provider


def _adapter_for(config):
	return get_courier_adapter(_provider_code(config))


def _ensure_creation_key(shipment):
	key = (shipment.custom_courier_creation_key or "").strip()
	if key:
		return key
	key = f"SHIP-{shipment.name}"
	frappe.db.set_value("Shipment", shipment.name, "custom_courier_creation_key", key, update_modified=False)
	shipment.custom_courier_creation_key = key
	return key


def _mark_stale_creating(shipment):
	state = (shipment.custom_courier_creation_state or "").strip() or "Not Requested"
	if state != "Creating":
		return state
	modified = get_datetime(shipment.modified)
	if modified and modified <= add_to_date(now_datetime(), minutes=-STALE_CREATING_MINUTES):
		frappe.db.set_value(
			"Shipment",
			shipment.name,
			"custom_courier_creation_state",
			"Uncertain",
			update_modified=False,
		)
		shipment.custom_courier_creation_state = "Uncertain"
		frappe.db.commit()
		return "Uncertain"
	return state


@frappe.whitelist()
def preflight_shipment(shipment_name):
	shipment = _get_shipment(shipment_name)
	config = _get_config(shipment)
	adapter = _adapter_for(config)
	result = adapter.validate_shipment(shipment, config)
	return result


@frappe.whitelist()
def quote_shipment(shipment_name):
	shipment = _get_shipment(shipment_name)
	config = _get_config(shipment)
	adapter = _adapter_for(config)
	pre = adapter.validate_shipment(shipment, config)
	if not pre.get("ok"):
		return {"ok": False, "errors": pre.get("errors") or [], "quotes": []}
	quotes = adapter.cotizar(shipment, config)
	return {"ok": True, "errors": [], "quotes": quotes}


@frappe.whitelist()
def select_quote(shipment_name, service_code, service_name, price):
	shipment = _get_shipment(shipment_name)
	_get_config(shipment)
	frappe.db.set_value(
		"Shipment",
		shipment.name,
		{
			"custom_courier_service_code": service_code,
			"carrier_service": service_name,
			"carrier": "Chilexpress",
			"service_provider": "erpn_custom",
			"shipment_amount": price,
		},
	)
	frappe.db.commit()
	return {"ok": True}


@frappe.whitelist()
def create_courier_shipment(shipment_name):
	shipment = _get_shipment(shipment_name)
	config = _get_config(shipment)
	adapter = _adapter_for(config)

	# Reload fresh state under write lock semantics via db values.
	shipment.reload()
	state = _mark_stale_creating(shipment)
	if shipment.shipment_id:
		frappe.throw(_("Este Shipment ya tiene OT {0}").format(shipment.shipment_id))
	if state in CREATION_STATES_BLOCKING:
		frappe.throw(
			_("No se puede crear OT: estado de integración es {0}. Reconcilie antes de reintentar.").format(
				state
			)
		)

	pre = adapter.validate_shipment(shipment, config)
	if not pre.get("ok"):
		return {"ok": False, "errors": pre.get("errors") or []}
	if not (shipment.custom_courier_service_code or "").strip():
		frappe.throw(_("Seleccione un servicio cotizado antes de crear el envío"))

	creation_key = _ensure_creation_key(shipment)
	frappe.db.set_value(
		"Shipment",
		shipment.name,
		{
			"custom_courier_creation_state": "Creating",
			"custom_courier_creation_key": creation_key,
		},
		update_modified=True,
	)
	frappe.db.commit()

	try:
		result = adapter.crear_envio(shipment, config)
	except Exception as exc:
		message = str(exc)
		if message.startswith("CHILEXPRESS_TRANSPORT_ERROR::") or "Timeout" in message or "Connection" in message:
			frappe.db.set_value(
				"Shipment",
				shipment.name,
				"custom_courier_creation_state",
				"Uncertain",
			)
			frappe.db.commit()
			frappe.throw(
				_(
					"Resultado incierto al crear OT Chilexpress. No se reintentará automáticamente. "
					"Use Reconciliar/cargar OT manualmente. Detalle: {0}"
				).format(message.replace("CHILEXPRESS_TRANSPORT_ERROR::", "")[:180])
			)
		frappe.db.set_value("Shipment", shipment.name, "custom_courier_creation_state", "Failed")
		frappe.db.commit()
		raise

	ot = (result.get("transport_order_number") or result.get("external_shipment_id") or "").strip()
	if not ot:
		frappe.db.set_value("Shipment", shipment.name, "custom_courier_creation_state", "Uncertain")
		frappe.db.commit()
		frappe.throw(_("Chilexpress respondió sin OT. Estado Uncertain; no reintentar automáticamente."))

	values = {
		"carrier": "Chilexpress",
		"service_provider": "erpn_custom",
		"carrier_service": result.get("service_name") or shipment.carrier_service,
		"custom_courier_service_code": result.get("service_code") or shipment.custom_courier_service_code,
		"shipment_id": ot,
		"awb_number": result.get("awb_number") or result.get("tracking_number") or ot,
		"shipment_amount": result.get("amount") or shipment.shipment_amount,
		"status": "Booked",
		"tracking_status": "In Progress",
		"custom_courier_creation_state": "Created",
		"custom_courier_created_at": now_datetime(),
	}
	frappe.db.set_value("Shipment", shipment.name, values)
	frappe.db.commit()

	label_attached = False
	label_error = ""
	label_b64 = result.get("label_base64")
	if label_b64:
		try:
			from erpn_custom.chile.couriers.chilexpress import ChilexpressAdapter

			content, _mime, ext = ChilexpressAdapter._decode_label_content(label_b64)
			_attach_label_bytes(
				shipment.name,
				f"{shipment.name}-{ot}-chilexpress-label.{ext}",
				content,
			)
			label_attached = True
		except Exception as exc:
			label_attached = False
			label_error = str(exc)[:180]
			frappe.log_error(title="Chilexpress label attach failed", message=str(exc))

	out = {
		"ok": True,
		"shipment_id": ot,
		"awb_number": values["awb_number"],
		"label_attached": label_attached,
	}
	if label_error:
		out["label_error"] = label_error
	return out


@frappe.whitelist()
def fetch_label(shipment_name):
	shipment = _get_shipment(shipment_name)
	config = _get_config(shipment)
	adapter = _adapter_for(config)
	if not shipment.shipment_id and not shipment.awb_number:
		frappe.throw(_("No hay OT creada para obtener etiqueta"))
	label = adapter.obtener_etiqueta(shipment, config)
	file_url = _attach_label_bytes(shipment.name, label["file_name"], label["content"])
	return {"ok": True, "file_url": file_url}


@frappe.whitelist()
def update_tracking(shipment_name):
	shipment = _get_shipment(shipment_name)
	config = _get_config(shipment)
	adapter = _adapter_for(config)
	result = adapter.consultar_tracking(shipment, config)
	frappe.db.set_value(
		"Shipment",
		shipment.name,
		{
			"tracking_status": result.get("tracking_status") or shipment.tracking_status,
			"tracking_status_info": result.get("tracking_status_info") or "",
			"custom_last_tracking_at": now_datetime(),
		},
	)
	frappe.db.commit()
	return {"ok": True, **result}


@frappe.whitelist()
def reconcile_uncertain(shipment_name, transport_order_number=None):
	"""Manual reconcile for Uncertain state. Does not POST a new OT."""
	shipment = _get_shipment(shipment_name)
	state = (shipment.custom_courier_creation_state or "").strip()
	if state not in ("Uncertain", "Creating", "Failed"):
		frappe.throw(_("Reconciliar solo aplica a Creating/Uncertain/Failed"))
	ot = (transport_order_number or "").strip()
	if not ot:
		frappe.throw(_("Indique el número de OT Chilexpress para reconciliar"))
	frappe.db.set_value(
		"Shipment",
		shipment.name,
		{
			"shipment_id": ot,
			"awb_number": shipment.awb_number or ot,
			"carrier": "Chilexpress",
			"service_provider": "erpn_custom",
			"status": "Booked",
			"tracking_status": shipment.tracking_status or "In Progress",
			"custom_courier_creation_state": "Created",
			"custom_courier_created_at": now_datetime(),
		},
	)
	frappe.db.commit()
	return {"ok": True, "shipment_id": ot}


def _attach_label_bytes(shipment_name, file_name, content):
	from frappe.utils.file_manager import save_file

	file_doc = save_file(
		file_name,
		content,
		"Shipment",
		shipment_name,
		is_private=1,
	)
	return file_doc.file_url
