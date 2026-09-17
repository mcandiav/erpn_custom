from abc import ABC, abstractmethod


class CourierAdapter(ABC):
	"""Common courier contract. Provider-specific adapters implement HTTP details."""

	provider_code = ""

	@abstractmethod
	def validate_shipment(self, shipment, config):
		"""Return {"ok": bool, "errors": [{"section","field","message","parcel_index?"}]}."""

	@abstractmethod
	def cotizar(self, shipment, config):
		"""Return list of normalized quote dicts."""

	@abstractmethod
	def crear_envio(self, shipment, config):
		"""Create external shipment. Return CourierCreateResult dict."""

	@abstractmethod
	def obtener_etiqueta(self, shipment, config):
		"""Return {"file_name": str, "content": bytes, "content_type": str}."""

	@abstractmethod
	def consultar_tracking(self, shipment, config):
		"""Return {"tracking_status","tracking_status_info","raw_status?"}."""
