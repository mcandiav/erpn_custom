import sys
import unittest
from unittest.mock import MagicMock, patch


def _row(role, **perms):
	row = {"role": role, "permlevel": 0, "if_owner": 0, "read": 1}
	row.update(perms)
	return row


class TestRestoreStandardPerms(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		sys.modules.setdefault("frappe", MagicMock())

	def _run(self, custom, standard):
		from erpn_custom.patches import v0_0_45_restore_standard_perms as module

		inserted = []
		fake = MagicMock()
		fake.get_all.side_effect = lambda doctype, **kw: custom if doctype == "Custom DocPerm" else standard
		fake.get_meta.return_value.fields = [
			MagicMock(fieldname=name)
			for name in ("name", "parent", "role", "permlevel", "if_owner", "read", "write", "delete")
		]
		fake.get_doc.side_effect = lambda doc: MagicMock(insert=lambda **kw: inserted.append(doc))
		with patch.object(module, "frappe", fake):
			added = module.restore_standard_rows("Shipment")
		return added, inserted

	def test_adds_only_missing_standard_roles(self):
		custom = [{"role": "ComercialFRA", "permlevel": 0, "if_owner": 0}]
		standard = [_row("Stock Manager", write=1, delete=1), _row("System Manager", write=1, delete=1)]
		added, inserted = self._run(custom, standard)
		self.assertEqual(added, 2)
		self.assertEqual([doc["role"] for doc in inserted], ["Stock Manager", "System Manager"])
		self.assertTrue(all(doc["doctype"] == "Custom DocPerm" for doc in inserted))
		self.assertTrue(all(doc["parent"] == "Shipment" for doc in inserted))
		self.assertEqual(inserted[0]["delete"], 1)
		self.assertNotIn("name", inserted[0])

	def test_idempotent_when_standard_already_present(self):
		custom = [
			{"role": "ComercialFRA", "permlevel": 0, "if_owner": 0},
			{"role": "System Manager", "permlevel": 0, "if_owner": 0},
		]
		added, inserted = self._run(custom, [_row("System Manager")])
		self.assertEqual((added, inserted), (0, []))

	def test_no_custom_rows_means_standard_already_applies(self):
		added, inserted = self._run([], [_row("System Manager")])
		self.assertEqual((added, inserted), (0, []))


if __name__ == "__main__":
	unittest.main()
