# Makefile with some convenient quick ways to do common things

help:
	@echo ''
	@echo 'ctapipe available make targets:'
	@echo ''
	@echo '  help    -- print this help message (the default)'
	@echo '  init    -- set up shell to use and work on ctapipe'
	@echo '  clean   -- remove temp files'
	@echo '  test    -- run tests'
	@echo '  doc     -- generate Sphinx docs'
	@echo '  docshow -- generate and display docs in browser'
	@echo ''
	@echo '  dist    -- build a conda package for distribution'
	@echo ''

init:
	git submodule init
	git submodule update
	export CTAPIPE_EXTRA_DIR=${PWD}/ctapipe-extra

clean:
	rm -rf build docs/_build docs/api

test:
	CTAPIPE_EXTRA_DIR=${PWD}/ctapipe-extra python setup.py test -V

doc:
	python setup.py build_sphinx

docshow:
	python setup.py build_sphinx --open-docs-in-browser

dist:
	python setup.py bdist_conda

# any other command can be passed to setup.py
%:
	python setup.py $@
