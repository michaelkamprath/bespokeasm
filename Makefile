
tests:
	python -m unittest discover . -v

clean:
	find . -name '*.pyc' -delete