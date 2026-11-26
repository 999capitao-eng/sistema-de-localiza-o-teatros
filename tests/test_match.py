from radar.consolidate import avaliar
from radar.match import agrupar, haversine_m, sao_o_mesmo


def reg(nome, lat=None, lon=None, cidade=None):
    return {"nome": nome, "lat": lat, "lon": lon, "cidade": cidade}


def test_distancia_zero():
    assert haversine_m(-23.5, -46.6, -23.5, -46.6) == 0


def test_mesmo_teatro_com_grafias_diferentes():
    a = reg("Theatro da Paz", -1.4558, -48.5039)
    b = reg("Teatro da Paz", -1.4559, -48.5040)
    assert sao_o_mesmo(a, b)


def test_teatros_diferentes_vizinhos():
    a = reg("Teatro Alfa", -23.5500, -46.6300)
    b = reg("Teatro Beta", -23.5501, -46.6301)
    assert not sao_o_mesmo(a, b)


def test_sem_coordenada_exige_mesma_cidade():
    a = reg("Teatro Horizonte", cidade="Teresina")
    b = reg("Teatro Horizonte", cidade="Teresina")
    c = reg("Teatro Horizonte", cidade="Recife")
    assert sao_o_mesmo(a, b)
    assert not sao_o_mesmo(a, c)


def test_agrupar():
    regs = [reg("Teatro Alfa", -5.0, -42.8), reg("Theatro Alfa", -5.0001, -42.8001),
            reg("Teatro Beta", -9.0, -40.0)]
    assert len(agrupar(regs)) == 2


def test_avaliar_conflito_e_confianca():
    assert avaliar([]) == (None, None, "sem_dado", 0)
    assert avaliar([(900, "osm"), (910, "wikidata")])[2] == "alta"
    valor, fonte, confianca, conflito = avaliar([(906, "wikidata"), (1100, "wikidata")])
    assert (confianca, conflito) == ("baixa", 1)
    assert avaliar([(500, "osm"), (800, "manual")])[0:3] == (800, "manual", "alta")
