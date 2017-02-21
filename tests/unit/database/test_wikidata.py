# coding=utf-8
"""
Copyright (c) 2017 Lexistems SAS and École normale supérieure de Lyon

This file is part of Platypus.

Platypus is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as
published by the Free Software Foundation, either version 3 of the
License, or (at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program. If not, see <http://www.gnu.org/licenses/>.
"""

import unittest
from decimal import Decimal

from platypus_qa.database.formula import Function, VariableFormula, EqualityFormula, ValueFormula, TripleFormula, \
    ExistsFormula
from platypus_qa.database.owl import RDFLangStringLiteral, XSDDecimalLiteral, XSDIntegerLiteral
from platypus_qa.database.wikidata import _WikidataItem, _WikidataQuerySparqlBuilder, _WikidataObjectProperty, \
    _WikidataDataProperty

_x = VariableFormula('x')
_y = VariableFormula('y')
_z = VariableFormula('z')
_Q2 = ValueFormula(_WikidataItem({'@id': 'wd:Q2'}))
_Q3 = ValueFormula(_WikidataItem({'@id': 'wd:Q3'}))
_foo = ValueFormula(RDFLangStringLiteral('foo', 'fr'))
_1 = ValueFormula(XSDIntegerLiteral(1))
_2 = ValueFormula(XSDDecimalLiteral(Decimal(2)))
_P2 = ValueFormula(_WikidataObjectProperty({'@id': 'wdt:P2', 'range': 'NamedIndividual'}))
_P3 = ValueFormula(_WikidataDataProperty({'@id': 'wdt:P3', 'range': 'rdf:langString'}))
_P4 = ValueFormula(_WikidataDataProperty({'@id': 'wdt:P4', 'range': 'xsd:decimal'}))

_sparql_to_tree_without_context = [
    (
        'SELECT DISTINCT ?r WHERE {\n\tBIND(wd:Q2 AS ?r)\n\tOPTIONAL { ?r wikibase:sitelinks ?sitelinksCount . }\n} ORDER BY DESC(?sitelinksCount) LIMIT 100',
        Function(_x, EqualityFormula(_x, _Q2))
    ),
    (
        'SELECT DISTINCT ?r WHERE {\n\t{\n\t\tBIND("foo"@fr AS ?r)\n\t} UNION {\n\t\tBIND(wd:Q2 AS ?r)\n\t}\n\tOPTIONAL { ?r wikibase:sitelinks ?sitelinksCount . }\n} ORDER BY DESC(?sitelinksCount) LIMIT 100',
        Function(_x, EqualityFormula(_x, _foo) | EqualityFormula(_x, _Q2))
    ),
    (
        'SELECT DISTINCT ?r WHERE {\n\t?r wdt:P2 wd:Q2 .\n\tOPTIONAL { ?r wikibase:sitelinks ?sitelinksCount . }\n} ORDER BY DESC(?sitelinksCount) LIMIT 100',
        Function(_x, TripleFormula(_x, _P2, _Q2))
    ),
    (
        'SELECT DISTINCT ?r WHERE {\n\twd:Q2 wdt:P2 ?r .\n\tOPTIONAL { ?r wikibase:sitelinks ?sitelinksCount . }\n} ORDER BY DESC(?sitelinksCount) LIMIT 100',
        Function(_x, TripleFormula(_Q2, _P2, _x))
    ),
    (
        'SELECT DISTINCT ?r WHERE {\n\t?r wdt:P3 "foo"@fr .\n\tOPTIONAL { ?r wikibase:sitelinks ?sitelinksCount . }\n} ORDER BY DESC(?sitelinksCount) LIMIT 100',
        Function(_x, TripleFormula(_x, _P3, _foo))
    ),
    (
        'SELECT DISTINCT ?r WHERE {\n\t{\n\t\twd:Q2 wdt:P2 ?r .\n\t} UNION {\n\t\twd:Q2 wdt:P3 ?r .\n\t}\n\tOPTIONAL { ?r wikibase:sitelinks ?sitelinksCount . }\n} ORDER BY DESC(?sitelinksCount) LIMIT 100',
        Function(_x, TripleFormula(_Q2, _P2, _x) | TripleFormula(_Q2, _P3, _x))
    ),
    (
        'SELECT DISTINCT ?r WHERE {\n\t{\n\t\twd:Q2 wdt:P2 ?r .\n\t} UNION {\n\t\twd:Q2 wdt:P3 ?r .\n\t}\n\tOPTIONAL { ?r wikibase:sitelinks ?sitelinksCount . }\n} ORDER BY DESC(?sitelinksCount) LIMIT 100',
        Function(_x, ExistsFormula(_y, (TripleFormula(_y, _P2, _x) | TripleFormula(_y, _P3, _x)) &
                                   EqualityFormula(_y, _Q2)))
    ),
    (
        'SELECT DISTINCT ?r WHERE {\n\tFILTER(?r = ((2. * ?y) - 1))\n\twd:Q2 wdt:P4 ?y .\n\tOPTIONAL { ?r wikibase:sitelinks ?sitelinksCount . }\n} ORDER BY DESC(?sitelinksCount) LIMIT 100',
        Function(_x, ExistsFormula(_y, TripleFormula(_Q2, _P4, _y) & EqualityFormula(_x, _2 * _y - _1)))
    ),
    (
        'SELECT DISTINCT ?r WHERE {\n\tFILTER(?y < ?z)\n\twd:Q2 wdt:P4 ?y .\n\twd:Q3 wdt:P4 ?z .\n\tOPTIONAL { ?r wikibase:sitelinks ?sitelinksCount . }\n} ORDER BY DESC(?sitelinksCount) LIMIT 100',
        Function(_x, ExistsFormula(_y, ExistsFormula(_z, TripleFormula(_Q2, _P4, _y) & TripleFormula(_Q3, _P4, _z) & (
            _y < _z))))
    ),
    (
        'ASK {\n\t?x wdt:P3 "foo"@fr .\n}',
        ExistsFormula(_x, TripleFormula(_x, _P3, _foo))
    )
]

_sparql_to_tree_with_context = [
    (
        'SELECT DISTINCT ?r ?s ?p WHERE {\n\t?s ?p ?r .\n\tBIND(wd:Q2 AS ?s)\n\tBIND(wdt:P3 AS ?p)\n\tOPTIONAL { ?s wikibase:sitelinks ?sitelinksCount . }\n} ORDER BY DESC(?sitelinksCount) LIMIT 100',
        Function(_x, TripleFormula(_Q2, _P3, _x))
    ),
    (
        'SELECT DISTINCT ?r ?s ?p WHERE {\n\t?s ?p ?r .\n\tBIND(wdt:P3 AS ?p)\n\twd:Q2 wdt:P2 ?s .\n\tOPTIONAL { ?s wikibase:sitelinks ?sitelinksCount . }\n} ORDER BY DESC(?sitelinksCount) LIMIT 100',
        Function(_x, ExistsFormula(_y, TripleFormula(_y, _P3, _x) & TripleFormula(_Q2, _P2, _y)))
    ),
    (
        'SELECT DISTINCT ?r ?s ?p WHERE {\n\t{\n\t\t?s ?p ?r .\n\t\tBIND(wdt:P3 AS ?p)\n\t} UNION {\n\t\t?s ?p ?r .\n\t\tBIND(wdt:P4 AS ?p)\n\t}\n\tOPTIONAL { ?s wikibase:sitelinks ?sitelinksCount . }\n} ORDER BY DESC(?sitelinksCount) LIMIT 100',
        Function(_x, ExistsFormula(_y, TripleFormula(_y, _P3, _x) | TripleFormula(_y, _P4, _x)))
    ),
    (
        'ASK {\n\t?x wdt:P3 "foo"@fr .\n}',
        ExistsFormula(_x, TripleFormula(_x, _P3, _foo))
    )
]


class _WikidataQuerySparqlBuilderTest(unittest.TestCase):
    _builder = _WikidataQuerySparqlBuilder()

    def testBuild(self):
        for (sparql, tree) in _sparql_to_tree_without_context:
            self.assertEqual(sparql, self._builder.build(tree))
        for (sparql, tree) in _sparql_to_tree_with_context:
            self.assertEqual(sparql, self._builder.build(tree, retrieve_context=True))
