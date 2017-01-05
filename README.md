Platypus QA
===========

[![Build Status](https://travis-ci.org/askplatypus/platypus-qa.svg?branch=master)](https://travis-ci.org/askplatypus/platypus-qa)

Platypus QA is the question answering service of Platypus.
You could see it live at [qa.dev.askplatyp.us](http://qa.dev.askplatyp.us)

## Install and run

Platypus QA relies on python 3.5+ and packages available using pip. It also uses
other Platypus services. The source code is setup in order to use production
version of these services automatically.

To install run:
```
python3 setup.py install
```

To run the Platypus QA server on port 8000:
```
python3 flask_server.py
```


## Quick introduction

Platypus QA is built from:

* Natural Language Processing tools available in the `nlp` package. It
provides a common interface (`model` file) and wrapper for CoreNLP and
SyntaxNet.
* A model for representing knowledge defined in `database.formula` and
based on RDF and OWL specifications (`database.owl` file).
* Wrapper for knowledge base allowing to retrieve entities and relations and
execute queries. Currently only Wikidata is supported
(`database.wikidata` file).
* A grammatical analyzer for questions, mainly implemented in
`analyzer.grammatical_anlyzer`.
* `request_handler` that puts all pieces together.
