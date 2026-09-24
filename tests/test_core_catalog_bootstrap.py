from app.db.init_db import bootstrap_sanaa_university, bootstrap_tofan_academy


def test_core_catalog_bootstrap_functions_are_wired():
    assert callable(bootstrap_sanaa_university)
    assert callable(bootstrap_tofan_academy)
