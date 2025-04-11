CONFIG_DOC_PATH = docs/setup/conf/configuration.md
CONFIG_MODEL_SRC = src/firecrest/config.py

.PHONY: generate-config-docs docs

$(CONFIG_DOC_PATH): $(CONFIG_MODEL_SRC)
	python docs/scripts/generate_config_docs.py

docs: $(CONFIG_DOC_PATH)
	mkdocs build

clean:
	rm -f $(CONFIG_DOC_PATH)
	rm -rf site
