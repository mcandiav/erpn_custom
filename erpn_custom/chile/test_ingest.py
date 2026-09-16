import unittest

from erpn_custom.chile.ingest import decide_ingest, make_ingest_key


class TestIngestIdempotency(unittest.TestCase):
    def test_key_same_account_and_id(self):
        self.assertEqual(
            make_ingest_key("Banco de Chile - Banco de Chile", "TX-1"),
            make_ingest_key("Banco de Chile - Banco de Chile", "TX-1"),
        )

    def test_same_id_other_account_is_distinct(self):
        self.assertNotEqual(
            make_ingest_key("Account A", "TX-1"),
            make_ingest_key("Account B", "TX-1"),
        )

    def test_missing_transaction_id_has_no_key(self):
        self.assertIsNone(make_ingest_key("Account A", ""))
        self.assertIsNone(make_ingest_key("Account A", None))

    def test_double_import_creates_once(self):
        created = []

        def import_row(account, tid):
            existing = [
                row["name"]
                for row in created
                if make_ingest_key(row["bank_account"], row["transaction_id"])
                == make_ingest_key(account, tid)
            ]
            decision = decide_ingest(account, tid, existing)
            if decision == "create":
                created.append(
                    {
                        "name": f"ACC-BTN-{len(created) + 1}",
                        "bank_account": account,
                        "transaction_id": tid,
                    }
                )
            return decision

        account = "Banco de Chile - Banco de Chile"
        self.assertEqual(import_row(account, "TX-CYNTHIA"), "create")
        self.assertEqual(import_row(account, "TX-CYNTHIA"), "skip_duplicate")
        self.assertEqual(len(created), 1)
        self.assertEqual(import_row("Otra Cuenta", "TX-CYNTHIA"), "create")
        self.assertEqual(len(created), 2)

    def test_reject_empty_transaction_id(self):
        self.assertEqual(
            decide_ingest("Banco de Chile - Banco de Chile", "  ", []),
            "reject_missing_transaction_id",
        )


if __name__ == "__main__":
    unittest.main()
