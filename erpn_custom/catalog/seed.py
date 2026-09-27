# Initial list values. The Administrator adjusts them in Desk (Item Attribute).
# Chilean shoe size (CL) is proposed as EU - 1; clothing uses letters in Chile.

COLOR_VALUES = [
	"Black · Negro · Preto",
	"White · Blanco · Branco",
	"Brown · Café · Marrom",
	"Beige",
	"Blue · Azul",
	"Navy · Azul marino · Azul marinho",
	"Light blue · Celeste · Azul claro",
	"Green · Verde",
	"Pink · Rosado · Rosa",
	"Red · Rojo · Vermelho",
	"Cream · Crema · Creme",
	"Grey · Gris · Cinza",
	"Yellow · Amarillo · Amarelo",
	"Gold · Dorado · Dourado",
	"Silver · Plateado · Prata",
	"Lilac · Lila · Lilás",
	"Fuchsia · Fucsia · Fúcsia",
	"Orange · Naranjo · Laranja",
	"Burgundy · Burdeo · Bordô",
	"Purple · Morado · Roxo",
	"Khaki · Caqui · Cáqui",
	"Multicolor",
]

TONO_VALUES = [
	"Light Medium", "Rose Amber", "Brown Sugar", "Light", "Miss Jellyfish", "Enamel", "1 Birch",
	"Pillow Talk", "Pillow Talk Medium", "001 Pink Juicy", "018 Intense Spice", "Fair", "Soft Fair",
	"015 Fair Warm", "Neutral", "Golden Neutral", "Medium Neutral", "Light Golden", "6.5 Medium",
	"7 Medium", "Cool Mauve", "Intense Mauve", "Toasty", "1.3 Stone", "Caramel", "Blushed Rose",
	"110 Frosted Opal", "Mixed Berries", "Desert Rose", "Lip Cheat / Kissing", "Shimmer Rose",
	"Peachmania", "Glowmania", "Bluemania", "Cupcake Sparkly", "Strawberry", "Soft Pinch",
	"She Goes To The Gym", "Happy", "Mildred", "Pure Hollywood", "Sweet Mouth", "Pomegranate",
	"Serenity", "Matilda", "Wattabrat", "Fussy", "Rose Crush", "Bronzed Umber", "Love Trap",
	"Rosewood", "Translucent", "Crazy In Love", "Hot Chocolit", "Pearly Peach", "Soft Launch",
	"When The Sun Sets", "Slow Burn", "Rose Nude",
]

CONTENIDO_VALUES = [
	"1.5 ml", "2.7 ml", "3 ml", "6 ml", "9 ml", "30 ml",
	"0.05 g", "0.5 g", "3.5 g", "11 g",
	"0.03 oz", "0.13 oz",
	"30 cápsulas", "90 cápsulas",
	"60 unidades", "100 unidades",
]


def _num(value):
	return f"{value:g}"


# (US, EU) pairs
WOMEN_SHOES = [
	(5, 35.5), (5.5, 36), (6, 36.5), (6.5, 37.5), (7, 38), (7.5, 38.5), (8, 39),
	(8.5, 40), (9, 40.5), (9.5, 41), (10, 42), (10.5, 42.5), (11, 43),
]
MEN_SHOES = [
	(6, 38.5), (6.5, 39), (7, 40), (7.5, 40.5), (8, 41), (8.5, 42), (9, 42.5),
	(9.5, 43), (10, 44), (10.5, 44.5), (11, 45), (11.5, 45.5), (12, 46), (13, 47.5),
]
# (letter, US, EU)
WOMEN_CLOTHING = [
	("XXS", "00", "30"), ("XS", "0-2", "32-34"), ("S", "4-6", "36-38"), ("M", "8-10", "40-42"),
	("L", "12-14", "44-46"), ("XL", "16", "48"), ("XXL", "18", "50"),
]
MEN_CLOTHING = [
	("XS", "32-34", "44"), ("S", "34-36", "46"), ("M", "38-40", "48-50"),
	("L", "42-44", "52-54"), ("XL", "46-48", "56"), ("XXL", "50-52", "58"),
]
KIDS_CLOTHING = ["XS (4-5)", "S (6-7)", "M (8-10)", "M (10-12)", "L (12-14)", "L (14-16)", "XL (16)", "XL (18-20)"]


def talla_values():
	"""(value, departamento) rows; empty departamento applies to every department."""
	rows = [("Sin talla", ""), ("Talla única", "")]
	rows += [(f"US {_num(us)} · EU {_num(eu)} · CL {_num(eu - 1)}", "Mujer") for us, eu in WOMEN_SHOES]
	rows += [(f"US {_num(us)} · EU {_num(eu)} · CL {_num(eu - 1)}", "Hombre") for us, eu in MEN_SHOES]
	rows += [
		(f"M US {_num(us)} · W US {_num(us + 1.5)} · EU {_num(eu)} · CL {_num(eu - 1)}", "Unisex")
		for us, eu in MEN_SHOES
	]
	rows += [(f"{letter} · US {us} · EU {eu}", "Mujer") for letter, us, eu in WOMEN_CLOTHING]
	rows += [(f"{letter} · US {us} · EU {eu}", "Hombre") for letter, us, eu in MEN_CLOTHING]
	rows += [(f"Unisex {letter} · US {us} · EU {eu}", "Unisex") for letter, us, eu in MEN_CLOTHING]
	rows += [(label, "Niño/a") for label in KIDS_CLOTHING]
	return rows
