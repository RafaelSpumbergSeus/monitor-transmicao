.PHONY: demo test real
demo:  ## pipeline completo com dados sintéticos
	python -m src.pipeline.run --fonte sintetico --n 3000 --reset
test:
	python -m unittest discover -s tests -t . -v
real:  ## requer DATAJUD_API_KEY; comece com --max-docs pequeno
	python -m src.pipeline.run --fonte datajud --tribunais tjrs trt4 --classes 7 1116 985 --max-docs 500 --reset
