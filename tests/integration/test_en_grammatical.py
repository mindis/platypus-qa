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

from platypus_qa.analyzer.grammatical_analyzer import GrammaticalAnalyzer
from platypus_qa.database.formula import Function, VariableFormula, TripleFormula, ValueFormula, EqualityFormula, \
    ExistsFormula, GreaterFormula
from platypus_qa.database.owl import ObjectProperty, DataProperty, xsd_decimal, owl_NamedIndividual, Class, \
    NamedIndividual, \
    XSDDateTimeLiteral, xsd_dateTime
from platypus_qa.nlp.core_nlp import CoreNLPParser
from tests.simple_knowledge_model import SimpleKnowledgeBase

_schema_GeoCoordinates = Class('http://schema.org/GeoCoordinates', (owl_NamedIndividual,))
_schema_Person = Class('http://schema.org/Person', (owl_NamedIndividual,))
_schema_Place = Class('http://schema.org/Place', (owl_NamedIndividual,))
_schema_Country = Class('http://schema.org/Place', (owl_NamedIndividual, _schema_Place))
_schema_Movie = Class('http://schema.org/Movie', (owl_NamedIndividual,))
_schema_CreativeWork = Class('http://schema.org/CreativeWork', (owl_NamedIndividual,))
_schema_Book = Class('http://schema.org/Book', (owl_NamedIndividual, _schema_CreativeWork))

_individuals = {
    'France': [_schema_Country],
    'United Kingdom': [_schema_Country],
    'Homer J. Simpson': [_schema_Person],
    'Bob Marley': [_schema_Person],
    'cheetah': [owl_NamedIndividual],
    'Barack Obama': [_schema_Person],
    'Big Ben': [_schema_Place],
    'I, Robot': [_schema_Movie],
    'Robin Woods': [_schema_Movie],
    'John': [_schema_Person],
    'flight': [owl_NamedIndividual],
    'male': [owl_NamedIndividual],
    'Lyon': [_schema_Place],
    'Paris': [_schema_Place],
    'fork': [owl_NamedIndividual],
    'city': [owl_NamedIndividual],
    'Le Petit Prince': [_schema_Book],
    'Vol de Nuit': [_schema_Book],
    'Douglas': [owl_NamedIndividual],
    'apple': [owl_NamedIndividual]
}

_object_properties = {
    'prime minister': _schema_Person,
    'president': _schema_Person,
    'children': _schema_Person,
    'birth place': _schema_Place,
    'wife': _schema_Person,
    'husband': _schema_Person,
    'main actor': _schema_Person,
    'capital': _schema_Place,
    'pilote': _schema_Person,
    'books': owl_NamedIndividual,
    'location': _schema_GeoCoordinates,
    'written by': _schema_Person,
    'origin': owl_NamedIndividual,
    'author': _schema_Person,
    'type': owl_NamedIndividual,
    'last name': owl_NamedIndividual,
    'eats': owl_NamedIndividual,
    'heir of': _schema_Person
}

_data_properties = {
    'birth date': xsd_dateTime,
    'speed': xsd_decimal,
    'age': xsd_decimal,
    'width': xsd_decimal,
    'height': xsd_decimal,
    'born in': xsd_dateTime,
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
logging.basicConfig(level=logging.INFO)

_parsed_sentences = {
    'Bob Marley?':
        Function(_x, EqualityFormula(_x, _get_individual('Bob Marley'))),

    'The Bob Marley?':
        Function(_x, EqualityFormula(_x, _get_individual('Bob Marley'))),

    'Who is Bob Marley?':
        Function(_x, EqualityFormula(_x, _get_individual('Bob Marley'))),

    'Who is Homer J. Simpson?':
        Function(_x, EqualityFormula(_x, _get_individual('Homer J. Simpson'))),

    'prime minister of France':
        Function(_x, TripleFormula(_get_individual('France'), _get_property('prime minister'), _x)),

    'Who is the prime minister of France?':
        Function(_x, TripleFormula(_get_individual('France'), _get_property('prime minister'), _x)),

    'Who is the president of the United Kingdom':
        Function(_x, TripleFormula(_get_individual('United Kingdom'), _get_property('president'), _x)),

    'Who is the president of France':
        Function(_x, TripleFormula(_get_individual('France'), _get_property('president'), _x)),

    'What is the birth date of Bob Marley?':
        Function(_x, TripleFormula(_get_individual('Bob Marley'), _get_property('birth date'), _x)),

    'What is the speed of cheetah?':
        Function(_x, TripleFormula(_get_individual('cheetah'), _get_property('speed'), _x)),

    'Who are the children of the wife of Barack Obama?':
        Function(_x, ExistsFormula(_y, TripleFormula(_get_individual('Barack Obama'), _get_property('wife'), _y) &
                                   TripleFormula(_y, _get_property('children'), _x))),

    'What is the width of a cheetah?':
        Function(_x, TripleFormula(_get_individual('cheetah'), _get_property('width'), _x)),

    'How old is Big Ben?':
        Function(_x, TripleFormula(_get_individual('Big Ben'), _get_property('age'), _x)),

    'What is the height of Big Ben?':
        Function(_x, TripleFormula(_get_individual('Big Ben'), _get_property('height'), _x)),

    'What is a fork?':
        Function(_x, EqualityFormula(_x, _get_individual('fork'))),

    'What is Robin Woods?':
        Function(_x, EqualityFormula(_x, _get_individual('Robin Woods'))),

    'books of John':
        Function(_x, TripleFormula(_get_individual('John'), _get_property('books'), _x)),

    'Who are the male children of Barack Obama?':
        Function(_x, TripleFormula(_get_individual('Barack Obama'), _get_property('children'), _x) &
                 TripleFormula(_x, _get_property('type'), _get_individual('male'))),

    'What is the location of Big Ben?':
        Function(_x, TripleFormula(_get_individual('Big Ben'), _get_property('location'), _x)),

    'Where is Big Ben?':
        Function(_x, TripleFormula(_get_individual('Big Ben'), _get_property('location'), _x)),

    'Where is Lyon?':
        Function(_x, TripleFormula(_get_individual('Lyon'), _get_property('location'), _x)),

    'Who eats an apple?':
        Function(_x, TripleFormula(_x, _get_property('eats'), _get_individual('apple'))),

    'Who is born in 1960?':
        Function(_x,
                 TripleFormula(_x, _get_property('born in'), ValueFormula(XSDDateTimeLiteral(1960, 0, 0, 0, 0, 0)))),

    'WHo is born after 2016?':
        Function(_x, ExistsFormula(_y, TripleFormula(_x, _get_property('born in'), _y) &
                                   GreaterFormula(_y, ValueFormula(XSDDateTimeLiteral(2016, 0, 0, 0, 0, 0))))),
}
'''
'Give us the France\'s prime minister.':
    Function(_x, TripleFormula(_get_individual('France'), _get_property('prime minister'), _x)),
'Give me the capital of the United Kingdom.':
    Function(_x, TripleFormula(_get_individual('United Kingdom'), _get_property('capital'), _x)),
'When is the president of France born?':
    Function(_x, ExistsFormula(_y, TripleFormula(_get_individual('France'), _get_property('president'), _y) &
                                   TripleFormula(_y, _get_property('birth date'), _x))),
'When are the children of the president of France born?':
        Function(_x, ExistsFormula(_y, ExistsFormula(_z,
                                                     TripleFormula(_get_individual('France'),
                                                                   _get_property('president'), _z) &
                                                     TripleFormula(_z, _get_property('children'), _y)) &
                                   TripleFormula(_y, _get_property('birth date'), _x))),
'Who is the heir of Barack Obama?':
    Function(_x, TripleFormula(_x, _get_property('heir of'), _get_individual('Barack Obama'))),

'''


class EnglishGrammaticalAnalyzerTest(unittest.TestCase):
    @classmethod
    def setUpClass(self):
        self._analyzer = GrammaticalAnalyzer(CoreNLPParser(['http://163.172.54.30:9000']), _knowledge_base, 'en')

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
                    '[fr_grammatical_analyzer test] The following question check failed: {}\nExpected: {}\nActual: {}'.format(
                        sentence, expected_formula, ', '.join(str(formula) for formula in returned_formulas)),
                    file=sys.stderr)
                bad_count += 1
        if bad_count > 0:
            raise AssertionError('{} on {} tests failed'.format(bad_count, len(_parsed_sentences)))
