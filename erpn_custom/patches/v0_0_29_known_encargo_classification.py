from erpn_custom.patches.v0_0_28_known_encargo_item_fields import execute as refresh_known_encargos


def execute():
	# Encargo now carries the Item classification fields; copy them onto known-item Encargos.
	refresh_known_encargos()
