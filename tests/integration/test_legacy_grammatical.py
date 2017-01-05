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

import sys
import unittest
from itertools import chain

from platypus_qa.analyzer.legacy_grammatical_analyzer import LegacyGrammaticalAnalyzer
from platypus_qa.database.formula import Function, VariableFormula, TripleFormula, ValueFormula, EqualityFormula, \
    ExistsFormula
from platypus_qa.database.owl import ObjectProperty, DataProperty, xsd_decimal, owl_NamedIndividual, Class, \
    NamedIndividual
from tests.simple_knowledge_model import SimpleKnowledgeBase

_schema_Person = Class('http://schema.org/Person', (owl_NamedIndividual,))
_schema_Place = Class('http://schema.org/Place', (owl_NamedIndividual,))
_schema_Country = Class('http://schema.org/Place', (owl_NamedIndividual, _schema_Place))
_schema_Movie = Class('http://schema.org/Movie', (owl_NamedIndividual,))
_schema_CreativeWork = Class('http://schema.org/CreativeWork', (owl_NamedIndividual,))
_schema_Book = Class('http://schema.org/Book', (owl_NamedIndividual, _schema_CreativeWork))

_individuals = {
    'France': [_schema_Country],
    'Homer J. Simpson': [_schema_Person],
    'I, Robot': [_schema_Movie],
    'United States': [_schema_Country],
    'Le Petit Prince': [_schema_Book],
    'Vol de Nuit': [_schema_Book]
}

_object_properties = {
    'prime minister': _schema_Person,
    'president': _schema_Person,
    'son': _schema_Person,
    'main actor': _schema_Person,
    'daughter': _schema_Person,
    'wife': _schema_Person,
    'husband': _schema_Person,
    'author': _schema_Person,
    'capital': _schema_Place
}

_data_properties = {
    'age': xsd_decimal
}


def _get_individual(label: str) -> ValueFormula:
    return ValueFormula(NamedIndividual(label, _individuals[label]))


def _get_property(label: str) -> ValueFormula:
    if label in _object_properties:
        return ValueFormula(ObjectProperty(label, range=_object_properties[label]))
    if label in _data_properties:
        return ValueFormula(DataProperty(label, range=_data_properties[label]))


_knowledge_base = SimpleKnowledgeBase(
    {label: [_get_individual(label).term] for label in _individuals.keys()},
    {label: [_get_property(label).term] for label in chain(_data_properties.keys(), _object_properties.keys())},
    [ObjectProperty('type', range=owl_NamedIndividual)]
)

_x = VariableFormula('x')
_y = VariableFormula('y')
_z = VariableFormula('z')
_t = VariableFormula('t')
_u = VariableFormula('u')

_parsed_sentences = {
    'Who is the prime minister of France?':
        Function(_x, TripleFormula(_get_individual('France'), _get_property('prime minister'), _x)),

    'Who is Homer J. Simpson?':
        Function(_x, EqualityFormula(_x, _get_individual('Homer J. Simpson'))),

    'Who is the president of France':
        Function(_x, TripleFormula(_get_individual('France'), _get_property('president'), _x)),

    'How old is the son of the main actor of "I, Robot"?':
        Function(_x, ExistsFormula(_y, ExistsFormula(_z,
                                                     TripleFormula(_get_individual('I, Robot'),
                                                                   _get_property('main actor'), _z) &
                                                     TripleFormula(_z, _get_property('son'), _y)) &
                                   TripleFormula(_y, _get_property('age'), _x))),

    'Who are the daughters of the wife of the husband of the wife of the president of the United States?':
        Function(_x, ExistsFormula(_y, ExistsFormula(_z, ExistsFormula(_t, ExistsFormula(_u,
                                                                                         TripleFormula(_get_individual(
                                                                                             'United States'),
                                                                                             _get_property(
                                                                                                 'president'),
                                                                                             _u) &
                                                                                         TripleFormula(_u,
                                                                                                       _get_property(
                                                                                                           'wife'),
                                                                                                       _t)) &
                                                                       TripleFormula(_t, _get_property('husband'),
                                                                                     _z)) &
                                                     TripleFormula(_z, _get_property('wife'), _y)) &
                                   TripleFormula(_y, _get_property('daughter'), _x))),

    'Who wrote \"Le Petit Prince\" and \"Vol de Nuit\"':
        Function(_x, TripleFormula(_get_individual('Le Petit Prince'), _get_property('author'), _x) &
                 TripleFormula(_get_individual('Vol de Nuit'), _get_property('author'), _x)),

    'Is there a capital of France?':
        ExistsFormula(_x, TripleFormula(_get_individual('France'), _get_property('capital'), _x)),
}


class LegacyGrammaticalAnalyzerTest(unittest.TestCase):
    @classmethod
    def setUpClass(self):
        self._analyzer = LegacyGrammaticalAnalyzer(_knowledge_base)

    def testParsing(self):
        bad_count = 0
        for (sentence, expected_formula) in _parsed_sentences.items():
            returned_formulas = self._analyzer.analyze(sentence, 'en')
            correct_count = len(returned_formulas)
            for formula in returned_formulas:
                try:
                    self.assertEqual(formula, expected_formula)
                except AssertionError:
                    correct_count -= 1
            if not correct_count:
                print(
                    '[fr_grammatical_analyzer test] The following question check failed: {}\nExpected: {}\nActual: {}'.format(
                        sentence, expected_formula, ', '.join(str(formula) for formula in returned_formulas)),
                    file=sys.stderr)
                bad_count += 1
        if bad_count > 0:
            raise AssertionError('{} on {} tests failed'.format(bad_count, len(_parsed_sentences)))
