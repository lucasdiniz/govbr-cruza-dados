"""Nenhuma consulta real: valida o ingresso da promoção pelo mesmo CLI do oneshot."""
import sys
from unittest.mock import Mock

import pytest

from web import warm_cache


@pytest.mark.parametrize("estrito", [False, True])
def test_falha_abaixo_de_cinco_porcento(monkeypatch, estrito):
    monkeypatch.setattr(sys, "argv", ["warm_cache", "--daemon", "--mun", "Teste"])
    monkeypatch.setenv("WARM_EXIGIR_COMPLETO", "1" if estrito else "0")
    monkeypatch.setattr(warm_cache.psycopg2, "connect", Mock())
    monkeypatch.setattr(warm_cache, "_get_municipios_pb", lambda *_: ["Teste"])
    monkeypatch.setattr(warm_cache, "warm_cycle_pb", lambda *_: (99, 1))
    monkeypatch.setattr(warm_cache, "_warm_sitemaps_phase", lambda: (1, 0, 0))
    promover = Mock(return_value=(0, 0))
    monkeypatch.setattr(warm_cache, "_swap_all_pending_shadows", promover)
    if estrito:
        with pytest.raises(RuntimeError, match="promoção"):
            warm_cache.main()
        promover.assert_not_called()
    else:
        warm_cache.main()
        promover.assert_called_once()


@pytest.mark.parametrize("sitemap_falho", [False, True])
def test_sitemap_e_swap_precisam_concluir(monkeypatch, sitemap_falho):
    monkeypatch.setattr(sys, "argv", ["warm_cache", "--daemon", "--mun", "Teste"])
    monkeypatch.setenv("WARM_EXIGIR_COMPLETO", "1")
    monkeypatch.setattr(warm_cache.psycopg2, "connect", Mock())
    monkeypatch.setattr(warm_cache, "_get_municipios_pb", lambda *_: ["Teste"])
    monkeypatch.setattr(warm_cache, "warm_cycle_pb", lambda *_: (1, 0))
    monkeypatch.setattr(warm_cache, "_warm_sitemaps_phase", lambda: (1, int(sitemap_falho), 0))
    promover = Mock(return_value=(0, 1))
    monkeypatch.setattr(warm_cache, "_swap_all_pending_shadows", promover)
    with pytest.raises(RuntimeError, match="Sitemap|não confirmada"):
        warm_cache.main()
    assert promover.call_count == (0 if sitemap_falho else 1)
