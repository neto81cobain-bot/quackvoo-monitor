"""Teste do Radar do Norte de verdade (não manda nada)."""
import os, radar
est = {}
boas = radar.rodar(est, ["MAO", "BEL"], "2026-11-24T07:00:00+00:00", 1, os.getenv("SERPAPI_KEY", ""))
print("destinos:", len(est["radar"]["ultimos"]))
print(radar.texto_resumo(est))
