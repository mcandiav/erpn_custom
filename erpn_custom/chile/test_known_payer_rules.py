import unittest

from erpn_custom.chile import known_payer_rules as rules
from erpn_custom.chile.matching import CONFLICT, EXACT_TAX_ID, NO_MATCH, index_customers_by_normalized_tax_id
from erpn_custom.chile.rut import normalize_chilean_tax_id

MARIA_RUT = "13698154-4"
PAYER_RUT = "12345678-5"


class TestResolvePayer(unittest.TestCase):
	def setUp(self):
		self.customers = index_customers_by_normalized_tax_id(
			[
				{"name": "Maria Perez", "tax_id": MARIA_RUT},
				{"name": "Dup A", "tax_id": "11.111.111-1"},
				{"name": "Dup B", "tax_id": "11111111-1"},
			],
			normalize_chilean_tax_id,
		)
		self.lookups = []

	def lookup(self, active):
		def _lookup(normalized):
			self.lookups.append(normalized)
			return active.get(normalized)

		return _lookup

	def test_customer_tax_id_has_priority(self):
		active = {MARIA_RUT: ("KP-00001", "Carolina Soto")}
		rule, names, known_payer = rules.resolve_payer(MARIA_RUT, self.customers, self.lookup(active))
		self.assertEqual((rule, names, known_payer), (EXACT_TAX_ID, ["Maria Perez"], None))
		self.assertEqual(self.lookups, [])

	def test_resolves_by_active_known_payer(self):
		active = {PAYER_RUT: ("KP-00001", "Maria Perez")}
		rule, names, known_payer = rules.resolve_payer(PAYER_RUT, self.customers, self.lookup(active))
		self.assertEqual((rule, names, known_payer), (rules.KNOWN_PAYER, ["Maria Perez"], "KP-00001"))

	def test_inactive_known_payer_does_not_resolve(self):
		rule, names, known_payer = rules.resolve_payer(PAYER_RUT, self.customers, self.lookup({}))
		self.assertEqual((rule, names, known_payer), (NO_MATCH, [], None))

	def test_tax_id_conflict_is_not_bypassed(self):
		key = normalize_chilean_tax_id("11111111-1")
		active = {key: ("KP-00001", "Maria Perez")}
		rule, names, known_payer = rules.resolve_payer(key, self.customers, self.lookup(active))
		self.assertEqual(rule, CONFLICT)
		self.assertIsNone(known_payer)

	def test_invalid_rut_is_orphan(self):
		rule, names, known_payer = rules.resolve_payer(None, self.customers, self.lookup({}))
		self.assertEqual((rule, names, known_payer), (NO_MATCH, [], None))
		self.assertEqual(self.lookups, [])

	def test_payer_rut_formats_share_key(self):
		keys = {normalize_chilean_tax_id(v) for v in ("12.345.678-5", "12345678-5", "12 345 678-5")}
		self.assertEqual(keys, {PAYER_RUT})


class TestLocks(unittest.TestCase):
	def test_free_rut(self):
		self.assertEqual(rules.lock_violation("Maria Perez", [], None), (None, None))

	def test_same_rut_active_for_other_customer_blocked(self):
		self.assertEqual(
			rules.lock_violation("Carolina Soto", [], "Maria Perez"),
			(rules.OTHER_ACTIVE, "Maria Perez"),
		)

	def test_primary_rut_of_other_customer_blocked(self):
		self.assertEqual(
			rules.lock_violation("Maria Perez", ["Juan Rojas"], None),
			(rules.OTHER_PRIMARY, "Juan Rojas"),
		)

	def test_primary_rut_checked_before_active(self):
		code, _ = rules.lock_violation("Maria Perez", ["Juan Rojas"], "Carolina Soto")
		self.assertEqual(code, rules.OTHER_PRIMARY)

	def test_own_primary_rut_blocked(self):
		self.assertEqual(
			rules.lock_violation("Maria Perez", ["Maria Perez"], None),
			(rules.OWN_PRIMARY, "Maria Perez"),
		)

	def test_exact_duplicate_detected(self):
		self.assertEqual(
			rules.lock_violation("Maria Perez", [], "Maria Perez"),
			(rules.SAME_ACTIVE, "Maria Perez"),
		)

	def test_active_key_allows_history_after_deactivation(self):
		self.assertEqual(rules.active_rut_key(1, PAYER_RUT), PAYER_RUT)
		self.assertIsNone(rules.active_rut_key(0, PAYER_RUT))
		self.assertIsNone(rules.active_rut_key(1, None))

	def test_messages(self):
		self.assertEqual(
			rules.violation_message(rules.OTHER_ACTIVE, PAYER_RUT, "Maria Perez"),
			"El RUT pagador 12345678-5 ya está asociado a Maria Perez. Debe desactivar primero esa "
			"asociación antes de asignarlo a otro cliente.",
		)
		self.assertEqual(
			rules.violation_message(rules.OTHER_PRIMARY, PAYER_RUT, "Juan Rojas"),
			"El RUT 12345678-5 corresponde al RUT principal del cliente Juan Rojas y no puede "
			"registrarse como pagador de otro cliente.",
		)
		self.assertEqual(
			rules.learning_conflict_message("Maria Perez", "Carolina Soto"),
			"Este RUT de origen ya está registrado como pagador de Maria Perez. El depósito actual "
			"fue asignado a Carolina Soto, pero la relación permanente no fue modificada.",
		)


class TestLearningOffer(unittest.TestCase):
	def test_offer_when_payer_differs(self):
		self.assertTrue(rules.should_offer_learning(PAYER_RUT, MARIA_RUT, None, "Maria Perez"))

	def test_no_offer_for_customer_own_rut(self):
		self.assertFalse(rules.should_offer_learning(MARIA_RUT, MARIA_RUT, None, "Maria Perez"))

	def test_no_offer_when_relation_already_exists(self):
		self.assertFalse(rules.should_offer_learning(PAYER_RUT, MARIA_RUT, "Maria Perez", "Maria Perez"))

	def test_offer_when_rut_belongs_to_other_customer(self):
		self.assertTrue(rules.should_offer_learning(PAYER_RUT, MARIA_RUT, "Carolina Soto", "Maria Perez"))

	def test_no_offer_without_valid_rut(self):
		self.assertFalse(rules.should_offer_learning(None, MARIA_RUT, None, "Maria Perez"))
