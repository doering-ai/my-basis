# Sphinx Documentation Makefile
############
### HEAD ###
############
SPHINX_OPTS    ?=
SPHINX_PARSE   ?= uv run sphinx-apidoc
SPHINX_BUILD   ?= uv run sphinx-build
SRC_DIR	   		= ./../my/
RST_DIR     	= .
OUT_DIR      	= ./_build/

.PHONY: help docs

############
### BODY ###
############
help:
	@$(SPHINX_BUILD) -M help "$(RST_DIR)" "$(OUT_DIR)" $(SPHINX_OPTS) $(O)

parse:
	@$(SPHINX_PARSE) -o "$(RST_DIR)" "$(SRC_DIR)"

build:
	@$(SPHINX_BUILD) -M html "$(RST_DIR)" "$(OUT_DIR)" $(SPHINX_OPTS) $(O)

docs: parse build


############
### MAIN ###
############
# Catch-all target: route all unknown targets to Sphinx using the new
# "make mode" option.  $(O) is meant as a shortcut for $(SPHINXOPTS).
# %: Makefile
# 	@$(SPHINX_BUILD) -M $@ "$(RST_DIR)" "$(OUT_DIR)" $(SPHINX_OPTS) $(O)
