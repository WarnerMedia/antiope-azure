

# Static, not sure if needed??
PYTHON=python3
PIP=pip3

FILES =	inventory-vm.py \
		inventory-subs.py \
		trigger_sub_actions.py \
		report-subs.py \
		sub_handler.py \
		common.py \
		subscription.py

DEPENDENCIES=

package: test clean zipfile

#
# Lambda function management
#

clean:
	rm -rf __pycache__ *.zip *.dist-info $(DEPENDENCIES)

# # Create the package Zip. Assumes all tests were done
zipfile: deps $(FILES) $(DEPENDENCIES) html_templates
	zip -r $(LAMBDA_PACKAGE) $^

test: $(FILES)
	for f in $^; do $(PYTHON) -m py_compile $$f; if [ $$? -ne 0 ] ; then echo "$$f FAILS" ; exit 1; fi done

deps:
	$(PIP) install -r requirements.txt -t . --upgrade

pep8: $(FILES)
	pycodestyle $^
