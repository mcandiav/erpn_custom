# Initial list values. The Administrator adjusts them in Desk (Item Attribute).
# Chilean shoe size (CL) is proposed as EU - 1; clothing uses letters in Chile.

import unicodedata

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
	"""(value, departamento, familia) rows; empty departamento/familia applies to all."""
	rows = [("Sin talla", "", ""), ("Talla única", "", "")]
	shoe = "US {} · EU {} · CL {}"
	rows += [(shoe.format(_num(us), _num(eu), _num(eu - 1)), "Mujer", "Calzado") for us, eu in WOMEN_SHOES]
	rows += [(shoe.format(_num(us), _num(eu), _num(eu - 1)), "Hombre", "Calzado") for us, eu in MEN_SHOES]
	rows += [
		(f"M US {_num(us)} · W US {_num(us + 1.5)} · EU {_num(eu)} · CL {_num(eu - 1)}", "Unisex", "Calzado")
		for us, eu in MEN_SHOES
	]
	rows += [(f"{letter} · US {us} · EU {eu}", "Mujer", "Ropa") for letter, us, eu in WOMEN_CLOTHING]
	rows += [(f"{letter} · US {us} · EU {eu}", "Hombre", "Ropa") for letter, us, eu in MEN_CLOTHING]
	rows += [(f"Unisex {letter} · US {us} · EU {eu}", "Unisex", "Ropa") for letter, us, eu in MEN_CLOTHING]
	rows += [(label, "Niño/a", "Ropa") for label in KIDS_CLOTHING]
	return rows


# Diccionario de aduana: (tipo de dato, como viene escrito, valor ERP). Normalized on load.
COLOR_ALIASES = {
	"Black · Negro · Preto": "negro black negra blk blakc preto",
	"White · Blanco · Branco": "blanco white blanca waite branco",
	"Brown · Café · Marrom": "cafe brown marron briwn marrom",
	"Beige": "beige beiga beiger",
	"Blue · Azul": "azul blue",
	"Navy · Azul marino · Azul marinho": "navy|azul marino",
	"Light blue · Celeste · Azul claro": "celeste|light blue|azul claro|celest",
	"Green · Verde": "verde green",
	"Pink · Rosado · Rosa": "rosado pink rosa rosada",
	"Red · Rojo · Vermelho": "rojo red roja",
	"Cream · Crema · Creme": "crema cream crem",
	"Grey · Gris · Cinza": "gris grey gray",
	"Yellow · Amarillo · Amarelo": "amarillo yellow yelllow amaralla",
	"Gold · Dorado · Dourado": "dorado gold oro",
	"Silver · Plateado · Prata": "plateado silver plata",
	"Lilac · Lila · Lilás": "lila",
	"Fuchsia · Fucsia · Fúcsia": "fucsia fuchsia",
	"Orange · Naranjo · Laranja": "naranjo naranja orange",
	"Burgundy · Burdeo · Bordô": "burdeo burgundy",
	"Purple · Morado · Roxo": "morado purpura purple moeado",
	"Khaki · Caqui · Cáqui": "khaki caqui",
	"Multicolor": "multi multicolor mukti",
}

TIPO_ALIASES = {
	"Abrigo": "abrigo",
	"Joyería": "aros|joyeria",
	"Banano": "banano",
	"Base": "base de maquillaje|base",
	"Billetera": "billetera|billetera con monedero",
	"Blazer": "blazer",
	"Corrector": "blur concealer|ojeras|corrector",
	"Rubor": "blush|rubor",
	"Tote": "bolsa|tote",
	"Cartera": "bolso|cartera|caretra",
	"Bota": "botas|bota",
	"Botín": "botin",
	"Brochas y esponjas": "brocha|esponja maquillaje",
	"Bronzer": "bronzer",
	"Bufanda": "bufanda",
	"Calcetines": "calcetin|calcetines|set calcetines",
	"Calza": "calza",
	"Calzado": "calzado",
	"Camisa": "camisa",
	"Cardigan": "cardigans|cardigan",
	"Chaleco": "chaleco",
	"Chaqueta": "chaqueta|chaqueta termica|chiporro",
	"Llavero / Charm": "charms|llavero",
	"Cinturones": "cinturon|set cinturon",
	"Contorno": "contorno|stick contouring",
	"Correa de cartera": "correa de bolso|strap",
	"Neceser": "cosmetiquero|estuche|neceser",
	"Maquillaje": "cosmetica|set maquillaje|pc 3 maquillaje|fijador de maquillaje",
	"Crossbody": "crossbody",
	"Gel": "gel",
	"Gloss": "gloss|lip gloss",
	"Gomitas": "gomitas",
	"Gorra": "gorra",
	"Gorro": "gorro",
	"Guantes": "guante",
	"Tarjetero": "id card|tarjetero",
	"Iluminador": "iluminador|iluminador de ojos",
	"Lentes": "lentes",
	"Labial": "lip|lip kit|lipstick|lapiz labial|pc 2 lipstick",
	"Hogar y otros": "libretas|manta|plancha|toalla|vaso",
	"Melatonina": "melatonina",
	"Mochila": "mochila",
	"Máscara de pestañas": "mascara de pestanas",
	"Organizador de cartera": "organizador de cartera",
	"Sombras": "paleta|sombra de ojos",
	"Pantalón": "pantalon",
	"Paraguas": "paraguas",
	"Parka": "parca|parka",
	"Pastillas": "pastillas|tru niagen",
	"Pañuelo": "panuelo",
	"Polar": "polar|sherpa",
	"Polera": "polera|polera manga larga",
	"Polerón": "poleron|polerones",
	"Polvo": "polvo",
	"Reloj": "reloj",
	"Ropa": "ropa|ropo",
	"Ropa interior": "ropa interior|ropa intima",
	"Sandalia": "sandalias|sandalia|sandalias con tacon",
	"Ashwagandha": "set pc 3 - ashwaganda",
	"Short": "short",
	"Skincare": "skincare set",
	"Clutch": "sobre",
	"Sweater": "sweater",
	"Vestido": "vestido",
	"Zapatilla": "zapatilla",
	"Zapato": "zapatos|zapatos de tacon",
	"Suplementos": "suplemento",
}

DEPARTAMENTO_ALIASES = {
	"Mujer": "mujer",
	"Hombre": "hombre",
	"Juvenil": "juvenil|nina juvenil",
	"Niño/a": "nino|nina|nino/a",
}

MARCA_ALIASES = {
	"Michael Kors": "michael kors",
	"Polo Ralph Lauren": "polo ralph lauren|lauren ralph lauren|polo",
	"Tous": "tous|tou",
	"Karl Lagerfeld": "karl lagerdeld|karl lagerfeld",
	"Victoria Secret": "victiria secret|victoria secret",
	"Steve Madden": "steve medden|steve madden",
	"Huda Beauty": "hudabeauty",
	"Beautyblender": "beauty blender",
}


def normalize_text(text):
	"""Lowercase, no accents, single spaces: the dictionary lookup key."""
	text = unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode()
	return " ".join(text.casefold().split())


def aduana_seed():
	"""(tipo de dato, texto, valor ERP) rows for the initial dictionary."""
	rows = []
	for tipo, aliases in (
		("Color", COLOR_ALIASES),
		("Tipo", TIPO_ALIASES),
		("Departamento", DEPARTAMENTO_ALIASES),
		("Marca", MARCA_ALIASES),
	):
		for value, words in aliases.items():
			# Color aliases are single words split by spaces unless a phrase needs "|".
			texts = words.split() if tipo == "Color" and "|" not in words else words.split("|")
			rows += [(tipo, text, value) for text in texts]
	return rows
