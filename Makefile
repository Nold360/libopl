default: build

build:
	python3 setup.py sdist bdist_wheel

clean:
	rm -rf dist/* build/* libopl.egg-info/

release:
	python3 -m twine upload dist/*

test:
	python3 -m twine upload --repository-url https://test.pypi.org/legacy/ dist/*
