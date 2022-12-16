
tests:
	python -m unittest discover . -v

clean:
	find . -name '*.pyc' -delete
	find . -name '__pycache__' -delete
	rm -Rf ./build
	rm -Rf ./bespokeasm.egg-info
	rm -Rf ./dist/

flake8:
	flake8 ./bespokeasm/ ./test/ setup.py --count --max-line-length=127 --statistics
