from erpn_custom.catalog.provision import apply_attributes


def execute():
	# v0_0_21 skipped attributes without seed values (Color, Tono).
	apply_attributes()
