"""Aeroportos conhecidos: nome e palavras que aparecem nas notícias de promoção."""
import re
import unicodedata

# código: (nome curto, palavras-chave para achar o lugar num post de promoção)
AEROPORTOS = {
    "MAO": ("Manaus", ["manaus"]),
    "STM": ("Santarém", ["santarem"]),
    "TMT": ("Porto Trombetas", ["trombetas", "oriximina"]),
    "BEL": ("Belém", ["belem"]),
    "MCP": ("Macapá", ["macapa"]),
    "ITB": ("Itaituba", ["itaituba"]),
    "ATM": ("Altamira", ["altamira"]),
    "MAB": ("Marabá", ["maraba"]),
    "SLZ": ("São Luís", ["sao luis"]),
    "THE": ("Teresina", ["teresina"]),
    "FOR": ("Fortaleza", ["fortaleza"]),
    "NAT": ("Natal", ["natal (rn)", "natal/rn", "para natal", "de natal", "em natal"]),
    "JPA": ("João Pessoa", ["joao pessoa"]),
    "REC": ("Recife", ["recife"]),
    "MCZ": ("Maceió", ["maceio"]),
    "AJU": ("Aracaju", ["aracaju"]),
    "SSA": ("Salvador", ["salvador"]),
    "BPS": ("Porto Seguro", ["porto seguro"]),
    "BSB": ("Brasília", ["brasilia"]),
    "GYN": ("Goiânia", ["goiania"]),
    "CGB": ("Cuiabá", ["cuiaba"]),
    "CGR": ("Campo Grande", ["campo grande"]),
    "PVH": ("Porto Velho", ["porto velho"]),
    "RBR": ("Rio Branco", ["rio branco"]),
    "BVB": ("Boa Vista", ["boa vista"]),
    "PMW": ("Palmas", ["palmas"]),
    "GRU": ("São Paulo (Guarulhos)", ["sao paulo", "guarulhos", "sampa"]),
    "CGH": ("São Paulo (Congonhas)", ["sao paulo", "congonhas", "sampa"]),
    "VCP": ("Campinas", ["campinas", "viracopos"]),
    "GIG": ("Rio (Galeão)", ["rio de janeiro", "galeao"]),
    "SDU": ("Rio (Santos Dumont)", ["rio de janeiro", "santos dumont"]),
    "CNF": ("Belo Horizonte", ["belo horizonte", "confins"]),
    "VIX": ("Vitória", ["vitoria (es)", "vitoria/es", "para vitoria"]),
    "CWB": ("Curitiba", ["curitiba"]),
    "FLN": ("Florianópolis", ["florianopolis", "floripa"]),
    "NVT": ("Navegantes", ["navegantes"]),
    "POA": ("Porto Alegre", ["porto alegre"]),
    "IGU": ("Foz do Iguaçu", ["foz do iguacu"]),
    "VVI": ("Santa Cruz de la Sierra", ["santa cruz de la sierra", "viru viru", "bolivia"]),
    "LPB": ("La Paz", ["la paz", "bolivia"]),
    "CBB": ("Cochabamba", ["cochabamba", "bolivia"]),
    "LIM": ("Lima", ["lima", "peru"]),
    "CUZ": ("Cusco", ["cusco", "cuzco", "machu picchu", "peru"]),
    "BOG": ("Bogotá", ["bogota", "colombia"]),
    "MDE": ("Medellín", ["medellin", "colombia"]),
    "PTY": ("Cidade do Panamá", ["panama"]),
    "UIO": ("Quito", ["quito", "equador"]),
    "EZE": ("Buenos Aires", ["buenos aires", "argentina"]),
    "AEP": ("Buenos Aires", ["buenos aires", "argentina"]),
    "SCL": ("Santiago", ["santiago", "chile"]),
    "MVD": ("Montevidéu", ["montevideu", "uruguai"]),
    "ASU": ("Assunção", ["assuncao", "paraguai"]),
    "CCS": ("Caracas", ["caracas", "venezuela"]),
    "MIA": ("Miami", ["miami"]),
    "MCO": ("Orlando", ["orlando"]),
    "JFK": ("Nova York", ["nova york", "new york"]),
    "CUN": ("Cancún", ["cancun"]),
    "MEX": ("Cidade do México", ["cidade do mexico"]),
    "LIS": ("Lisboa", ["lisboa", "portugal"]),
    "OPO": ("Porto", ["porto (portugal)", "portugal"]),
    "MAD": ("Madri", ["madri", "espanha"]),
    "CDG": ("Paris", ["paris"]),
    "FCO": ("Roma", ["roma", "italia"]),
}


def sem_acento(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", s.lower())


def nome(cod: str) -> str:
    return AEROPORTOS.get(cod, (cod, []))[0]


def palavras(cod: str) -> list[str]:
    nome_, extras = AEROPORTOS.get(cod, (cod, []))
    return sorted({sem_acento(nome_.split(" (")[0])} | set(extras))
