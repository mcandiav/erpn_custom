ROOT = "All Item Groups"

# Grupo -> Familia -> Tipos. A family without types is a leaf.
# Item Group names are unique site-wide (accent/case-insensitive in MariaDB).
CLASSIFICATION_TREE = {
	"Vestuario": {
		"Ropa": [
			"Polera",
			"Polerón",
			"Sweater",
			"Cardigan",
			"Camisa",
			"Parka",
			"Chaqueta",
			"Abrigo",
			"Blazer",
			"Polar",
			"Chaleco",
			"Pantalón",
			"Short",
			"Calza",
			"Vestido",
			"Ropa interior",
			"Calcetines",
		],
		"Calzado": ["Bota", "Botín", "Zapatilla", "Zapato", "Sandalia"],
	},
	"Accesorios": {
		"Bolsos": [
			"Cartera",
			"Crossbody",
			"Tote",
			"Banano",
			"Mochila",
			"Clutch",
			"Neceser",
			"Correa de cartera",
			"Organizador de cartera",
		],
		"Pequeña marroquinería": ["Billetera", "Tarjetero", "Llavero / Charm"],
		"Lentes": [],
		"Cinturones": [],
		"Invierno": ["Gorro", "Bufanda", "Guantes", "Pañuelo"],
		"Relojes y joyería": ["Reloj", "Joyería"],
		"Varios": ["Gorra", "Paraguas"],
	},
	"Belleza": {
		"Maquillaje": [
			"Gloss",
			"Labial",
			"Rubor",
			"Bronzer",
			"Contorno",
			"Iluminador",
			"Corrector",
			"Base",
			"Polvo",
			"Sombras",
			"Máscara de pestañas",
			"Brochas y esponjas",
		],
		"Cuidado": ["Skincare", "Gel"],
		"Suplementos": ["Melatonina", "Gomitas", "Pastillas", "Ashwagandha"],
	},
	"Otros": {
		"Hogar y otros": [],
	},
}


def iter_nodes():
	"""Yield (name, parent, is_group) top-down so parents exist before children."""
	for group, families in CLASSIFICATION_TREE.items():
		yield group, ROOT, 1
		for family, types in families.items():
			yield family, group, 1 if types else 0
			for item_type in types:
				yield item_type, family, 0


def family_from_chain(chain):
	"""Familia for an Item Group given its ancestry [node, parent, ..., top] (root excluded)."""
	if len(chain) < 2:
		return None
	group, family = chain[-1], chain[-2]
	if family in CLASSIFICATION_TREE.get(group, {}):
		return family
	return None
