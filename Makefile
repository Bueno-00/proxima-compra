PY := .venv/bin/python

.PHONY: instalar baixar preparar avaliar pagina testes

instalar:
	python3 -m venv .venv
	.venv/bin/pip install torch --index-url https://download.pytorch.org/whl/cpu
	.venv/bin/pip install -e ".[dev]"

# Cópia pública da base no Kaggle (precisa do token do Kaggle em ~/.kaggle ou KAGGLE_API_TOKEN).
# Fonte original: CIKM Cup 2016, trilha 2 (DIGINETICA).
baixar:
	mkdir -p data/raw
	kaggle datasets download profalbusdumbledore/diginetica-dataset -p data/raw --unzip

preparar:
	$(PY) -m proxima_compra.cli preparar

avaliar:
	$(PY) -m proxima_compra.cli avaliar

pagina:
	$(PY) -m proxima_compra.cli pagina

testes:
	$(PY) -m pytest -q
	.venv/bin/ruff check src tests
