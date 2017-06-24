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

from platypus_qa.database.formula import Select, VariableFormula, EqualityFormula, ValueFormula, TripleFormula, \
    ExistsFormula
from platypus_qa.database.model import KnowledgeBase
from platypus_qa.database.owl import RDFLangStringLiteral, rdf_langString, DatatypeProperty, xsd_decimal, \
    ObjectProperty, owl_NamedIndividual, NamedIndividual

_x = VariableFormula('x')
_y = VariableFormula('y')
_z = VariableFormula('z')
_s = VariableFormula('s')
_p = VariableFormula('p')
_Q2 = ValueFormula(NamedIndividual('wd:Q2', (owl_NamedIndividual,)))
_Q3 = ValueFormula(NamedIndividual('wd:Q3', (owl_NamedIndividual,)))
_foo = ValueFormula(RDFLangStringLiteral('foo', 'fr'))
_P2 = ValueFormula(ObjectProperty('http://www.wikidata.org/prop/direct/P2', owl_NamedIndividual, owl_NamedIndividual))
_P3 = ValueFormula(DatatypeProperty('http://www.wikidata.org/prop/direct/P3', owl_NamedIndividual, rdf_langString))
_P4 = ValueFormula(DatatypeProperty('http://www.wikidata.org/prop/direct/P4', owl_NamedIndividual, xsd_decimal))

_formulas_with_context = [
    (
        Select(_x, TripleFormula(_x, _P2, _Q2)),
        Select(_x, TripleFormula(_x, _P2, _Q2))
    ),
    (
        ExistsFormula(_x, TripleFormula(_x, _P3, _foo)),
        ExistsFormula(_x, TripleFormula(_x, _P3, _foo))
    ),
    (
        Select(_x, TripleFormula(_Q2, _P3, _x)),
        Select((_s, _p, _x), TripleFormula(_s, _p, _x) & EqualityFormula(_s, _Q2) & EqualityFormula(_p, _P3))
    ),
    (
        Select(_x, ExistsFormula(_y, TripleFormula(_y, _P3, _x) & TripleFormula(_Q2, _P2, _y))),
        Select((_s, _p, _x), TripleFormula(_s, _p, _x) & EqualityFormula(_p, _P3) & TripleFormula(_Q2, _P2, _s))
    ),
    (
        Select(_x, ExistsFormula(_y, TripleFormula(_y, _P3, _x) | TripleFormula(_y, _P4, _x))),
        Select((_s, _p, _x), (TripleFormula(_s, _p, _x) & EqualityFormula(_p, _P3)) |
               (TripleFormula(_s, _p, _x) & EqualityFormula(_p, _P4))),
    )
]


class _KnowledgeBaseTest(unittest.TestCase):
    def testBuild(self):
        kb = KnowledgeBase()
        for (input, output) in _formulas_with_context:
            self.assertEqual(output, kb._add_context_variables(input))
