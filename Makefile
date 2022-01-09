
tests:
	python -m unittest discover . -v

clean:
	find . -name '*.pyc' -delete
	rm -Rf ./build
	rm -Rf ./bespokeasm.egg-info

flake8:
	flake8 ./bespokeasm/ ./test/ setup.py --count --exit-zero --max-complexity=10 --max-line-length=127 --statistics
