from radar.normalize import nome_sem_prefixo, normalizar_nome, parse_capacidade


def test_normalizar_nome():
    assert normalizar_nome("Theatro São Pedro") == "teatro sao pedro"


def test_nome_sem_prefixo():
    assert nome_sem_prefixo("Centro Cultural Teatro Guaíra") == "guaira"
    assert nome_sem_prefixo("Theatro da Paz") == "da paz"


def test_parse_capacidade():
    assert parse_capacidade("1.200") == 1200
    assert parse_capacidade("350 lugares") == 350
    assert parse_capacidade("abc") is None
    assert parse_capacidade("5") is None
    assert parse_capacidade(None) is None
