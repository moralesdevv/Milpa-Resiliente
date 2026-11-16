# Objetivos de R2 para fusionar en el Makefile del monorepo.
PY ?= python3
CORE = packages/milpa_core
DAILY ?= data/curated/chiquimula_prueba/daily.parquet

test-science:          ## T-U, T-P, T-G del núcleo + integración mínima
	PYTHONPATH=$(CORE)/src:$(CORE)/tests $(PY) -m pytest -q $(CORE)/tests tests/integration

run-base:              ## corrida base con la serie curada de R1
	$(PY) tools/r2_run.py --daily $(DAILY) --out data/results/base

scenarios:             ## base + grilla de 45 escenarios × lecturas de adaptación
	$(PY) tools/r2_run.py --daily $(DAILY) --grid --out data/results/grid

examples:              ## payloads JSON de ejemplo para R3/R4 (serie sintética rotulada)
	$(PY) tools/r2_run.py --synthetic --grid --out examples

enums-sql:             ## DDL de enums para la migración (paridad T-C)
	PYTHONPATH=$(CORE)/src $(PY) -c "from milpa_core.enums import export_sql; print(export_sql())"
