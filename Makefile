
tests:
	PYTHONPATH=./src:${PYTHONPATH} python -m unittest discover . -v

clean:
	find . -name '*.pyc' -delete
	find . -name '__pycache__' -delete
	rm -Rf ./build
	rm -Rf ./bespokeasm.egg-info
	rm -Rf ./dist/

flake8:
	flake8 ./src/ ./test/ --count --max-line-length=127 --statistics
