import base64
import json
import re
from urllib.parse import urljoin

import frappe
import requests
from frappe import _
from frappe.utils import cint, flt

from erpn_custom.chile.couriers.base import CourierAdapter

TEST_MARKETPLACE_RUT = "96756430"
TEST_SELLER_RUT = "DEFAULT"
CREATING_STALE_MINUTES = 2

_TRACKING_MAP = {
	"ENTREGADO": "Delivered",
	"DELIVERED": "Delivered",
	"DEVUELTO": "Returned",
	"RETURNED": "Returned",
	"EXTRAVIADO": "Lost",
	"LOST": "Lost",
}


class ChilexpressAdapter(CourierAdapter):
	provider_code = "chilexpress"

	def validate_shipment(self, shipment, config):
		errors = []
		if (config.environment or "") != "Test":
			errors.append(
				{
					"section": "config",
					"field": "environment",
					"message": _("Spec 009 solo opera Chilexpress Test"),
				}
			)
		if not (config.account_reference or "").strip():
			errors.append(
				{
					"section": "config",
					"field": "account_reference",
					"message": _("Falta TCC (Account Reference) en Courier Configuration"),
				}
			)
		for service in ("coverage", "rating", "shipping"):
			try:
				self._api_key(config, service)
				self._endpoint(config, service)
			except Exception as exc:
				errors.append(
					{
						"section": "config",
						"field": service,
						"message": str(exc),
					}
				)

		pickup = self._load_address(shipment.pickup_address_name)
		delivery = self._load_address(shipment.delivery_address_name)
		if not pickup:
			errors.append(
				{
					"section": "origin",
					"field": "pickup_address_name",
					"message": _("Falta dirección de origen"),
				}
			)
		else:
			errors.extend(self._address_errors(pickup, "origin"))
		if not delivery:
			errors.append(
				{
					"section": "destination",
					"field": "delivery_address_name",
					"message": _("Falta dirección de destino"),
				}
			)
		else:
			errors.extend(self._address_errors(delivery, "destination"))

		if not shipment.shipment_parcel:
			errors.append(
				{
					"section": "parcels",
					"field": "shipment_parcel",
					"message": _("Debe ingresar al menos un paquete"),
				}
			)
		for idx, parcel in enumerate(shipment.shipment_parcel or [], start=1):
			values = {
				"weight": flt(parcel.weight),
				"length": flt(parcel.length),
				"width": flt(parcel.width),
				"height": flt(parcel.height),
				"count": flt(parcel.count),
			}
			for field, label in (
				("weight", _("peso")),
				("length", _("largo")),
				("width", _("ancho")),
				("height", _("alto")),
				("count", _("cantidad")),
			):
				if values[field] <= 0:
					errors.append(
						{
							"section": "parcels",
							"field": field,
							"parcel_index": idx,
							"message": _(
								"No se puede operar Chilexpress: el paquete #{0} no tiene {1} completo"
							).format(idx, label),
						}
					)

		if flt(shipment.value_of_goods) <= 0:
			errors.append(
				{
					"section": "shipment",
					"field": "value_of_goods",
					"message": _("Value of Goods debe ser mayor a 0"),
				}
			)
		if not (shipment.description_of_content or "").strip():
			errors.append(
				{
					"section": "shipment",
					"field": "description_of_content",
					"message": _("Falta descripción del contenido"),
				}
			)
		return {"ok": not errors, "errors": errors}

	def cotizar(self, shipment, config):
		origin_code, dest_code = self._resolve_coverages(shipment, config)
		parcel = shipment.shipment_parcel[0]
		payload = {
			"originCountyCode": origin_code,
			"destinationCountyCode": dest_code,
			"package": {
				"weight": self._fmt_num(parcel.weight),
				"height": self._fmt_num(parcel.height),
				"width": self._fmt_num(parcel.width),
				"length": self._fmt_num(parcel.length),
			},
			"productType": 3,
			"contentType": 1,
			"declaredWorth": self._fmt_num(shipment.value_of_goods),
			"deliveryTime": 0,
		}
		data = self._request(
			config,
			"rating",
			"POST",
			"/rates/courier",
			json_body=payload,
		)
		options = ((data or {}).get("data") or {}).get("courierServiceOptions") or []
		quotes = []
		for opt in options:
			quotes.append(
				{
					"provider": self.provider_code,
					"environment": config.environment,
					"service_code": str(opt.get("serviceTypeCode") or ""),
					"service_name": opt.get("serviceDescription") or str(opt.get("serviceTypeCode") or ""),
					"price": flt(opt.get("serviceValue")),
					"currency": "CLP",
					"estimated_delivery_days": None,
					"provider_reference": opt,
				}
			)
		return quotes

	def crear_envio(self, shipment, config):
		if (config.environment or "") != "Test":
			frappe.throw(_("Spec 009 solo crea OT en Chilexpress Test"))
		origin_code, dest_code = self._resolve_coverages(shipment, config)
		service_code = (shipment.custom_courier_service_code or "").strip()
		if not service_code:
			frappe.throw(_("Seleccione un servicio cotizado antes de crear el envío"))

		pickup = self._load_address(shipment.pickup_address_name)
		delivery = self._load_address(shipment.delivery_address_name)
		pickup_contact = self._contact_payload(shipment, "pickup")
		delivery_contact = self._contact_payload(shipment, "delivery")
		creation_key = (shipment.custom_courier_creation_key or "").strip() or f"SHIP-{shipment.name}"

		packages = []
		for parcel in shipment.shipment_parcel:
			count = max(cint(parcel.count), 1)
			for _ in range(count):
				packages.append(
					{
						"weight": self._fmt_num(parcel.weight),
						"height": self._fmt_num(parcel.height),
						"width": self._fmt_num(parcel.width),
						"length": self._fmt_num(parcel.length),
						"serviceDeliveryCode": int(str(service_code)),
						"productCode": 3,
						"deliveryReference": creation_key,
						"groupReference": shipment.name,
						"declaredValue": int(flt(shipment.value_of_goods)),
						# Chilexpress expects numeric content classification; 0 is rejected.
						"declaredContent": 1,
						"extendedCoverageAreaIndicator": False,
					}
				)

		payload = {
			"header": {
				"certificateNumber": 0,
				"customerCardNumber": (config.account_reference or "").strip(),
				"countyOfOriginCoverageCode": origin_code,
				"labelType": 2,
				"marketplaceRut": TEST_MARKETPLACE_RUT,
				"sellerRut": TEST_SELLER_RUT,
			},
			"details": [
				{
					"addresses": [
						{
							"addressId": 0,
							"countyCoverageCode": dest_code,
							"streetName": self._street_name(delivery),
							"streetNumber": self._street_number(delivery),
							"supplement": delivery.get("address_line2") or "",
							"addressType": "DEST",
							"deliveryOnCommercialOffice": False,
							"observation": shipment.name,
						},
						{
							"addressId": 0,
							"countyCoverageCode": origin_code,
							"streetName": self._street_name(pickup),
							"streetNumber": self._street_number(pickup),
							"supplement": pickup.get("address_line2") or "",
							"addressType": "DEV",
							"deliveryOnCommercialOffice": False,
							"observation": "DEV",
						},
					],
					"contacts": [pickup_contact, delivery_contact],
					"packages": packages,
				}
			],
		}
		data = self._request(
			config,
			"shipping",
			"POST",
			"/transport-orders",
			json_body=payload,
		)
		detail = self._first_detail(data)
		ot = (
			detail.get("transportOrderNumber")
			or detail.get("transportOrderId")
			or detail.get("otNumber")
			or detail.get("trackingNumber")
			or ""
		)
		tracking = detail.get("trackingNumber") or ot
		label_b64 = detail.get("labelData") or detail.get("label") or ""
		return {
			"provider": self.provider_code,
			"external_shipment_id": str(ot),
			"transport_order_number": str(ot),
			"tracking_number": str(tracking) if tracking else "",
			"awb_number": str(tracking) if tracking else str(ot),
			"service_code": service_code,
			"service_name": shipment.carrier_service or service_code,
			"amount": flt(shipment.shipment_amount),
			"initial_status": "Booked",
			"label_available": bool(label_b64),
			"label_base64": label_b64,
			"provider_reference": detail,
		}

	def obtener_etiqueta(self, shipment, config):
		ot = (shipment.shipment_id or shipment.awb_number or "").strip()
		if not ot:
			frappe.throw(_("No hay OT/tracking para obtener etiqueta"))
		# Prefer reprint endpoint when available; fall back to create-time label storage.
		try:
			data = self._request(
				config,
				"shipping",
				"POST",
				"/transport-orders/reprint",
				json_body={
					"transportOrderNumber": ot,
					"labelType": 2,
					"customerCardNumber": (config.account_reference or "").strip(),
				},
			)
			detail = self._first_detail(data) or (data.get("data") if isinstance(data, dict) else {}) or {}
			label_b64 = detail.get("labelData") or detail.get("label") or ""
		except Exception:
			label_b64 = ""
		if not label_b64:
			frappe.throw(_("Chilexpress no devolvió etiqueta para OT {0}").format(ot))
		content = base64.b64decode(label_b64)
		return {
			"file_name": f"{shipment.name}-{ot}-chilexpress-label.pdf",
			"content": content,
			"content_type": "application/pdf",
		}

	def consultar_tracking(self, shipment, config):
		number = (shipment.awb_number or shipment.shipment_id or "").strip()
		if not number:
			frappe.throw(_("No hay número de tracking/OT para consultar"))
		base = self._endpoint(config, "shipping").rstrip("/")
		# Tracking product lives under /tracking/...; derive host from shipping endpoint.
		host = re.sub(r"/transport-orders/api/v1\.0.*$", "", base)
		if host == base:
			host = "https://testservices.wschilexpress.com"
		url = f"{host}/tracking/api/v1.0/tracking/{number}"
		headers = {
			"Content-Type": "application/json",
			"Ocp-Apim-Subscription-Key": self._api_key(config, "shipping"),
		}
		response = requests.get(url, headers=headers, timeout=30)
		text = response.text or ""
		if response.status_code in (401, 403):
			frappe.throw(_("Chilexpress tracking rechazó la credencial (HTTP {0})").format(response.status_code))
		if response.status_code >= 400:
			frappe.throw(_("Chilexpress tracking error HTTP {0}: {1}").format(response.status_code, text[:180]))
		payload = response.json() if text else {}
		data = payload.get("data") if isinstance(payload, dict) else payload
		if isinstance(data, list) and data:
			data = data[0]
		data = data or {}
		raw_status = (
			data.get("statusDescription")
			or data.get("deliveryStatus")
			or data.get("currentStatus")
			or data.get("status")
			or ""
		)
		events = data.get("trackingEvents") or data.get("events") or []
		last_event = ""
		if events:
			last = events[-1] if isinstance(events, list) else events
			if isinstance(last, dict):
				last_event = last.get("description") or last.get("eventDescription") or str(last)
			else:
				last_event = str(last)
		mapped = "In Progress"
		upper = str(raw_status).upper()
		for key, value in _TRACKING_MAP.items():
			if key in upper:
				mapped = value
				break
		return {
			"tracking_status": mapped,
			"tracking_status_info": (last_event or raw_status or "")[:140],
			"raw_status": raw_status,
		}

	def _resolve_coverages(self, shipment, config):
		pickup = self._load_address(shipment.pickup_address_name)
		delivery = self._load_address(shipment.delivery_address_name)
		origin_city = (pickup.get("city") or "").strip()
		dest_city = (delivery.get("city") or "").strip()
		if not origin_city:
			frappe.throw(_("La dirección de origen no tiene comuna (Address.city)"))
		if not dest_city:
			frappe.throw(_("La dirección de destino no tiene comuna (Address.city)"))
		origin = self._coverage_code_for_city(config, origin_city)
		dest = self._coverage_code_for_city(config, dest_city)
		return origin, dest

	def _coverage_code_for_city(self, config, city_name):
		needle = self._norm(city_name)
		regions = self._request(config, "coverage", "GET", "/regions")
		region_list = (regions or {}).get("regions") or []
		matches = []
		for region in region_list:
			region_id = region.get("regionId")
			if not region_id:
				continue
			areas = self._request(
				config,
				"coverage",
				"GET",
				f"/coverage-areas?RegionCode={region_id}&type=0",
			)
			coverage_areas = (areas or {}).get("coverageAreas") or (areas or {}).get("coverages") or []
			for area in coverage_areas:
				name = area.get("countyName") or area.get("coverageName") or ""
				code = area.get("countyCode") or area.get("coverageCode") or ""
				if self._norm(name) == needle and code:
					matches.append(str(code))
		uniq = sorted(set(matches))
		if not uniq:
			frappe.throw(_("No se resolvió cobertura Chilexpress para comuna '{0}'").format(city_name))
		if len(uniq) > 1:
			frappe.throw(
				_("Cobertura ambigua para comuna '{0}': {1}").format(city_name, ", ".join(uniq))
			)
		return uniq[0]

	def _request(self, config, service, method, path, json_body=None):
		base = self._endpoint(config, service).rstrip("/") + "/"
		url = urljoin(base, path.lstrip("/"))
		headers = {
			"Content-Type": "application/json",
			"Ocp-Apim-Subscription-Key": self._api_key(config, service),
		}
		try:
			if method.upper() == "GET":
				response = requests.get(url, headers=headers, timeout=30)
			else:
				response = requests.post(
					url,
					headers=headers,
					data=json.dumps(json_body or {}),
					timeout=30,
				)
		except requests.RequestException as exc:
			# Caller maps this to Uncertain when creating.
			raise RuntimeError(f"CHILEXPRESS_TRANSPORT_ERROR::{exc}") from exc

		text = response.text or ""
		if response.status_code in (401, 403):
			frappe.throw(_("Chilexpress rechazó la API key de {0} (HTTP {1})").format(service, response.status_code))
		if response.status_code >= 400:
			snippet = text[:220]
			frappe.throw(_("Chilexpress {0} HTTP {1}: {2}").format(service, response.status_code, snippet))
		if not text:
			return {}
		try:
			payload = response.json()
		except Exception:
			frappe.throw(_("Chilexpress devolvió una respuesta no JSON en {0}").format(service))
		status_code = payload.get("statusCode") if isinstance(payload, dict) else None
		if status_code not in (None, 0, "0"):
			desc = payload.get("statusDescription") or payload.get("message") or str(payload)[:180]
			frappe.throw(_("Chilexpress {0}: {1}").format(service, desc))
		return payload

	def _api_key(self, config, service):
		from erpn_custom.chile.courier_endpoints import get_config_api_key

		return get_config_api_key(config, service)

	def _endpoint(self, config, service):
		from erpn_custom.chile.courier_endpoints import get_config_endpoint

		return get_config_endpoint(config, service)

	@staticmethod
	def _load_address(name):
		if not name:
			return None
		return frappe.db.get_value(
			"Address",
			name,
			[
				"name",
				"address_line1",
				"address_line2",
				"city",
				"state",
				"pincode",
				"country",
				"phone",
				"email_id",
			],
			as_dict=True,
		)

	@staticmethod
	def _address_errors(address, section):
		errors = []
		if not (address.get("address_line1") or "").strip():
			errors.append(
				{
					"section": section,
					"field": "address_line1",
					"message": _("Falta calle/número en dirección de {0}").format(section),
				}
			)
		if not (address.get("city") or "").strip():
			errors.append(
				{
					"section": section,
					"field": "city",
					"message": _("Falta comuna (city) en dirección de {0}").format(section),
				}
			)
		return errors

	def _contact_payload(self, shipment, side):
		if side == "pickup":
			name = shipment.pickup_contact_name
			email = shipment.pickup_contact_email
			contact_type = "R"
			fallback_name = shipment.pickup or shipment.pickup_company or "Remitente"
		else:
			name = shipment.delivery_contact_name
			email = shipment.delivery_contact_email
			contact_type = "D"
			fallback_name = shipment.delivery_to or shipment.delivery_customer or "Destinatario"

		phone = ""
		full_name = fallback_name
		mail = email or ""
		if name and frappe.db.exists("Contact", name):
			contact = frappe.get_doc("Contact", name)
			full_name = contact.full_name or fallback_name
			mail = mail or contact.email_id or ""
			phone = contact.mobile_no or contact.phone or ""
		if side == "pickup" and not phone and shipment.pickup_address_name:
			phone = frappe.db.get_value("Address", shipment.pickup_address_name, "phone") or ""
		if side == "delivery" and not phone and shipment.delivery_address_name:
			phone = frappe.db.get_value("Address", shipment.delivery_address_name, "phone") or ""
		return {
			"name": (full_name or "Contacto")[:80],
			"phoneNumber": (phone or "912345678")[:20],
			"mail": (mail or "noreply@example.com")[:80],
			"contactType": contact_type,
		}

	@staticmethod
	def _street_name(address):
		line = (address.get("address_line1") or "").strip()
		parts = line.rsplit(" ", 1)
		if len(parts) == 2 and re.search(r"\d", parts[1]):
			return parts[0][:80] or line[:80]
		return line[:80] or "SIN CALLE"

	@staticmethod
	def _street_number(address):
		line = (address.get("address_line1") or "").strip()
		parts = line.rsplit(" ", 1)
		if len(parts) == 2 and re.search(r"\d", parts[1]):
			digits = re.sub(r"[^\d]", "", parts[1]) or "0"
			return int(digits)
		return 0

	@staticmethod
	def _fmt_num(value):
		return f"{flt(value):.2f}"

	@staticmethod
	def _norm(value):
		text = (value or "").strip().upper()
		replacements = {
			"Á": "A",
			"É": "E",
			"Í": "I",
			"Ó": "O",
			"Ú": "U",
			"Ü": "U",
			"Ñ": "N",
		}
		for src, dst in replacements.items():
			text = text.replace(src, dst)
		return re.sub(r"\s+", " ", text)

	@staticmethod
	def _first_detail(payload):
		if not isinstance(payload, dict):
			return {}
		data = payload.get("data")
		if isinstance(data, list) and data:
			first = data[0]
			return first if isinstance(first, dict) else {}
		if isinstance(data, dict):
			details = data.get("detail") or data.get("details") or data.get("transportOrders")
			if isinstance(details, list) and details:
				first = details[0]
				return first if isinstance(first, dict) else data
			return data
		return {}
