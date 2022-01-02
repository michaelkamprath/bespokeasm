
tests:
	python -m unittest discover . -v

clean:
	find . -name '*.pyc' -delete
	rm -Rf ./build
	rm -Rf ./bespokeasm.egg-info