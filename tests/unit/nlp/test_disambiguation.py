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

from platypus_qa.analyzer.disambiguation import DisambiguationStep, find_process
from platypus_qa.database.formula import VariableFormula, ValueFormula, Function, TripleFormula
from platypus_qa.database.owl import XSDStringLiteral, owl_NamedIndividual, xsd_string, DatatypeProperty

_x = VariableFormula('x')
_foo = ValueFormula(XSDStringLiteral("foo"), "foo")
_foo2 = ValueFormula(XSDStringLiteral("foo2"), "foo")
_bar = ValueFormula(XSDStringLiteral("bar"), "bar")
_schema_name = ValueFormula(DatatypeProperty('http://schema.org/name', owl_NamedIndividual, xsd_string), "name")
_schema_name2 = ValueFormula(DatatypeProperty('http://schema.org/name2', owl_NamedIndividual, xsd_string), "name")
_schema_name3 = ValueFormula(DatatypeProperty('http://schema.org/name3', owl_NamedIndividual, xsd_string), "name")


class _TestDisambiguation(unittest.TestCase):
    def test_find_process(self):
        formulas = [
            Function(_x, TripleFormula(_x, _schema_name, _foo) & TripleFormula(_x, _schema_name, _bar)),
            Function(_x, TripleFormula(_x, _schema_name2, _foo) & TripleFormula(_x, _schema_name2, _bar)),
            Function(_x, TripleFormula(_x, _schema_name3, _foo) & TripleFormula(_x, _schema_name3, _bar)),
            Function(_x, TripleFormula(_x, _schema_name, _foo2) & TripleFormula(_x, _schema_name, _bar)),
            Function(_x, TripleFormula(_x, _schema_name2, _foo2) & TripleFormula(_x, _schema_name2, _bar)),
            Function(_x, TripleFormula(_x, _schema_name3, _foo2) & TripleFormula(_x, _schema_name3, _bar))
        ]
        expected = DisambiguationStep('name', {
            _schema_name: DisambiguationStep('foo', {
                _foo: [Function(_x, TripleFormula(_x, _schema_name, _foo) & TripleFormula(_x, _schema_name, _bar))],
                _foo2: [Function(_x, TripleFormula(_x, _schema_name, _foo2) & TripleFormula(_x, _schema_name, _bar))]
            }),
            _schema_name2: DisambiguationStep('foo', {
                _foo: [Function(_x, TripleFormula(_x, _schema_name2, _foo) & TripleFormula(_x, _schema_name3, _bar))],
                _foo2: [Function(_x, TripleFormula(_x, _schema_name2, _foo2) & TripleFormula(_x, _schema_name3, _bar))]
            }),
            _schema_name3: DisambiguationStep('foo', {
                _foo: [Function(_x, TripleFormula(_x, _schema_name3, _foo) & TripleFormula(_x, _schema_name3, _bar))],
                _foo2: [Function(_x, TripleFormula(_x, _schema_name3, _foo2) & TripleFormula(_x, _schema_name3, _bar))]
            })
        })
        self.assertEqual(len(str(expected)), len(str(find_process(formulas))))  # TODO: we should implement __eq__
