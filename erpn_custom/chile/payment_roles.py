SELLER_ROLE = "ComercialFRA"
ACCOUNTING_ROLES = ("System Manager", "Accounts Manager", "Accounts User")
PAYMENT_OPERATION_ROLES = ACCOUNTING_ROLES + (SELLER_ROLE,)
KNOWN_PAYER_ADMIN_ROLES = ("System Manager", "Accounts Manager")


def can_operate_payments(roles):
	return bool(set(roles or ()) & set(PAYMENT_OPERATION_ROLES))


def can_admin_known_payers(roles):
	return bool(set(roles or ()) & set(KNOWN_PAYER_ADMIN_ROLES))


def needs_accounting_elevation(roles):
	"""Operational users without accounting roles run the Spec 004 realizer through the controlled backend."""
	return can_operate_payments(roles) and not set(roles or ()) & set(ACCOUNTING_ROLES)
