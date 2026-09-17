from erpn_custom.customer_contact_mirror.service import backfill_customer_contact_mirrors


def execute():
	backfill_customer_contact_mirrors(dry_run=False)
