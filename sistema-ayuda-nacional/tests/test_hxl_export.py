from app import hxl_export, models


def test_generar_sitrep_hxl_incluye_encabezados_hxl(db_session):
    csv_texto = hxl_export.generar_sitrep_hxl(db_session)
    primera_linea = csv_texto.splitlines()[0]
    assert primera_linea == "#loc+name,#affected+num,#need+category,#date+reported"


def test_generar_sitrep_hxl_agrega_por_departamento_y_categoria(db_session):
    centro = models.CentroLocal(id_territorio="choco", nombre="Chocó", departamento="Chocó")
    db_session.add(centro)
    db_session.commit()
    db_session.refresh(centro)

    for _ in range(3):
        db_session.add(models.Solicitud(centro_id=centro.id, categoria=models.CategoriaNecesidad.agua))
    db_session.commit()

    csv_texto = hxl_export.generar_sitrep_hxl(db_session)
    lineas = csv_texto.splitlines()
    assert len(lineas) == 2  # encabezado + 1 fila agregada
    assert "Chocó" in lineas[1]
    assert "3" in lineas[1]
    assert "agua" in lineas[1]
