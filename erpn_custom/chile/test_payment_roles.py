import unittest

from erpn_custom.chile.payment_roles import (
	can_admin_known_payers,
	can_operate_payments,
	needs_accounting_elevation,
)


class TestPaymentRoles(unittest.TestCase):
	def test_comercialfra_operates_without_admin(self):
		roles = ["ComercialFRA", "Guest", "All"]
		self.assertTrue(can_operate_payments(roles))
		self.assertFalse(can_admin_known_payers(roles))
		self.assertTrue(needs_accounting_elevation(roles))

	def test_accounts_user_operates_without_admin(self):
		roles = ["Accounts User"]
		self.assertTrue(can_operate_payments(roles))
		self.assertFalse(can_admin_known_payers(roles))
		self.assertFalse(needs_accounting_elevation(roles))

	def test_admin_roles(self):
		for role in ("Accounts Manager", "System Manager"):
			self.assertTrue(can_operate_payments([role]))
			self.assertTrue(can_admin_known_payers([role]))
			self.assertFalse(needs_accounting_elevation([role]))

	def test_comercialfra_with_accounting_role_is_not_elevated(self):
		self.assertFalse(needs_accounting_elevation(["ComercialFRA", "Accounts User"]))

	def test_unrelated_roles_have_no_access(self):
		roles = ["Sales User", "ShopperFRA"]
		self.assertFalse(can_operate_payments(roles))
		self.assertFalse(can_admin_known_payers(roles))
		self.assertFalse(needs_accounting_elevation(roles))
		self.assertFalse(can_operate_payments(None))


if __name__ == "__main__":
	unittest.main()
