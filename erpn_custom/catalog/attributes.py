import re
import unicodedata

from erpn_custom.catalog.seed import COLOR_VALUES, CONTENIDO_VALUES, TONO_VALUES, talla_values

DEPARTMENTS = ("Mujer", "Hombre", "Unisex", "Juvenil", "Niño/a")

# Item Attribute -> Item custom field. Lists are maintained by the Administrator in Desk.
ATTRIBUTE_FIELDS = {
	"Color": "custom_color",
	"Talla": "custom_talla",
	"Taco": "custom_taco",
	"Manga": "custom_manga",
	"Tamaño": "custom_tamano",
	"Tono": "custom_tono",
	"Contenido": "custom_contenido",
}

# Attributes that only apply to some families; the rest (Color) apply to every product.
FAMILY_ATTRIBUTES = {
	"Calzado": ("Talla", "Taco"),
	"Ropa": ("Talla", "Manga"),
	"Bolsos": ("Tamaño",),
	"Maquillaje": ("Tono", "Contenido"),
	"Cuidado": ("Contenido",),
	"Suplementos": ("Contenido",),
}

# Values seeded on install: plain strings or (value, departamento).
SEED_VALUES = {
	"Color": COLOR_VALUES,
	"Talla": talla_values(),
	"Taco": ["Sin taco", "Bajo", "Medio", "Alto"],
	"Manga": ["Corta", "Larga", "Sin manga"],
	"Tamaño": ["Mini", "Small", "Medium", "Large"],
	"Tono": TONO_VALUES,
	"Contenido": CONTENIDO_VALUES,
}


def seed_rows(attribute):
	"""Seed values of an attribute as (value, departamento, familia)."""
	return [row if isinstance(row, tuple) else (row, "", "") for row in SEED_VALUES[attribute]]


def family_scoped_attributes():
	return {attribute for attributes in FAMILY_ATTRIBUTES.values() for attribute in attributes}


def allowed_attributes(family):
	"""Attributes a product of this family may carry."""
	scoped = family_scoped_attributes()
	own = set(FAMILY_ATTRIBUTES.get(family, ()))
	return [attribute for attribute in ATTRIBUTE_FIELDS if attribute not in scoped or attribute in own]


def make_abbr(value, taken):
	"""Short unique abbreviation (ERPNext requires one per attribute value)."""
	ascii_value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
	base = re.sub(r"[^A-Za-z0-9]", "", ascii_value).upper()[:10] or "V"
	taken_lower = {abbr.lower() for abbr in taken}
	abbr, counter = base, 2
	while abbr.lower() in taken_lower:
		suffix = str(counter)
		abbr = base[: 10 - len(suffix)] + suffix
		counter += 1
	return abbr
