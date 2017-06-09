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

import logging
import sys
import unittest
from itertools import chain

from nlp.core_nlp import CoreNLPParser
from platypus_qa.analyzer.grammatical_analyzer import GrammaticalAnalyzer
from platypus_qa.database.formula import Function, VariableFormula, ValueFormula, EqualityFormula, TripleFormula
from platypus_qa.database.owl import ObjectProperty, DatatypeProperty, owl_NamedIndividual, Class, NamedIndividual
from tests.simple_knowledge_model import SimpleKnowledgeBase

_schema_GeoCoordinates = Class('http://schema.org/GeoCoordinates', (owl_NamedIndividual,))
_schema_Person = Class('http://schema.org/Person', (owl_NamedIndividual,))
_schema_Place = Class('http://schema.org/Place', (owl_NamedIndividual,))
_schema_Country = Class('http://schema.org/Place', (owl_NamedIndividual, _schema_Place))
_schema_Movie = Class('http://schema.org/Movie', (owl_NamedIndividual,))
_schema_CreativeWork = Class('http://schema.org/CreativeWork', (owl_NamedIndividual,))
_schema_Book = Class('http://schema.org/Book', (owl_NamedIndividual, _schema_CreativeWork))

_individuals = {
    'Barack Obama': [_schema_Person],
    'Bob Marley': [_schema_Person],
}

_object_properties = {
    'Töchter': _schema_Person
}

_data_properties = {
}


def _get_individual(label: str) -> ValueFormula:
    return ValueFormula(NamedIndividual(label, _individuals[label]))


def _get_property(label: str) -> ValueFormula:
    if label in _object_properties:
        return ValueFormula(ObjectProperty(label, range=_object_properties[label]))
    if label in _data_properties:
        return ValueFormula(DatatypeProperty(label, range=_data_properties[label]))


_knowledge_base = SimpleKnowledgeBase(
    {label: [_get_individual(label).term] for label in _individuals.keys()},
    {label: [_get_property(label).term] for label in chain(_data_properties.keys(), _object_properties.keys())},
    [ObjectProperty('type', range=owl_NamedIndividual)]
)

_x = VariableFormula('x')
_y = VariableFormula('y')
_z = VariableFormula('z')
logging.basicConfig(level=logging.DEBUG)

_parsed_sentences = {
    'Barack Obama':
        Function(_x, EqualityFormula(_x, _get_individual('Barack Obama'))),

    'Der Bob Marley?':
        Function(_x, EqualityFormula(_x, _get_individual('Bob Marley'))),

    'Wer ist Barack Obama?':
        Function(_x, EqualityFormula(_x, _get_individual('Barack Obama'))),

    'Töchter von Barack Obama':
        Function(_x, TripleFormula(_get_individual('Barack Obama'), _get_property('Töchter'), _x))
}


class GermanGrammaticalAnalyzerTest(unittest.TestCase):
    @classmethod
    def setUpClass(self):
        self._analyzer = GrammaticalAnalyzer(
            CoreNLPParser(['https://corenlp.askplatyp.us/1.7/']), _knowledge_base, 'de')

    def testParsing(self):
        bad_count = 0
        for (sentence, expected_formula) in _parsed_sentences.items():
            returned_formulas = self._analyzer.analyze(sentence)
            correct_count = len(returned_formulas)
            for formula in returned_formulas:
                try:
                    self.assertEqual(formula, expected_formula)
                except AssertionError:
                    correct_count -= 1
            if not correct_count:
                print(
                    '[de_grammatical_analyzer test] The following question check failed: {}\nExpected: {}\nActual: {}'.format(
                        sentence, expected_formula, ', '.join(str(formula) for formula in returned_formulas)),
                    file=sys.stderr)
                bad_count += 1
        if bad_count > 0:
            raise AssertionError('{} on {} tests failed'.format(bad_count, len(_parsed_sentences)))
