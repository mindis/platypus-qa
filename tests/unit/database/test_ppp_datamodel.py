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
from itertools import chain

from ppp_datamodel import Exists as E
from ppp_datamodel import Intersection as I
from ppp_datamodel import List as L
from ppp_datamodel import Missing as M
from ppp_datamodel import Resource as R
from ppp_datamodel import Triple as T
from ppp_datamodel import Union as U

from platypus_qa.database.formula import Function, VariableFormula, TripleFormula, ValueFormula, EqualityFormula, \
    ExistsFormula
from platypus_qa.database.owl import ObjectProperty, DatatypeProperty, xsd_dateTime, xsd_decimal, owl_NamedIndividual, \
    Class, NamedIndividual
from platypus_qa.database.ppp_datamodel import ToPPPDataModelConverter, FromPPPDataModelConverter, PlatypusResource
from tests.simple_knowledge_model import SimpleKnowledgeBase

_schema_GeoCoordinates = Class("http://schema.org/GeoCoordinates", (owl_NamedIndividual,))
_schema_Person = Class("http://schema.org/Person", (owl_NamedIndividual,))
_schema_Place = Class("http://schema.org/Place", (owl_NamedIndividual,))
_schema_Movie = Class("http://schema.org/Movie", (owl_NamedIndividual,))

_individuals = {
    'France': [_schema_Place],
    'Homer J. Simpson': [_schema_Person],
    'Bob Marley': [_schema_Person],
    'cheetah': [owl_NamedIndividual],
    'Barack Obama': [_schema_Person],
    'I, Robot': [_schema_Movie],
    'Suzanne Collins': [_schema_Person],
    'John F. Kennedy': [_schema_Person],
    'book': [owl_NamedIndividual],
    'actor': [owl_NamedIndividual]
}

_object_properties = {
    'prime minister': owl_NamedIndividual,
    'president': owl_NamedIndividual,
    'child': owl_NamedIndividual,
    'main actor': owl_NamedIndividual,
    'wife': owl_NamedIndividual,
    'author': owl_NamedIndividual,
    'sister': owl_NamedIndividual,
    'married to': owl_NamedIndividual,
    'location': owl_NamedIndividual,
    'coordinates': _schema_GeoCoordinates,
    'type': owl_NamedIndividual,
    'capital': _schema_Place
}

_data_properties = {
    'birth date': xsd_dateTime,
    'speed': xsd_decimal,
    'age': xsd_decimal
}


def _get_individual(label: str) -> ValueFormula:
    return ValueFormula(NamedIndividual(label, _individuals[label]))


def _get_resource(label: str) -> R:
    return PlatypusResource(value=label, graph={'@id': label})


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
_term_for_tree = [
    (
        T(R('France'), R('prime minister'), M()),
        [Function(_x, TripleFormula(_get_individual('France'), _get_property('prime minister'), _x))]
    ),
    (
        T(R('Homer J. Simpson'), R('identity'), M()),
        [Function(_x, EqualityFormula(_x, _get_individual('Homer J. Simpson')))]
    ),
    (
        T(R('cheetah'), R('speed'), M()),
        [Function(_x, TripleFormula(_get_individual('cheetah'), _get_property('speed'), _x))]
    ),
    (
        T(R('France'), L([R('location'), R('coordinates')]), M()),
        [Function(_x, TripleFormula(_get_individual('France'), _get_property('location'), _x)),
         Function(_x, TripleFormula(_get_individual('France'), _get_property('coordinates'), _x))]
    ),
    (
        T(
            T(R('I, Robot'), R('main actor'), M()),
            R('child'),
            M()
        ),
        [Function(_x, ExistsFormula(_y, TripleFormula(_y, _get_property('child'), _x) &
                                    TripleFormula(_get_individual('I, Robot'), _get_property('main actor'), _y)))]
    ),
    (
        T(
            T(
                T(R('I, Robot'), R('main actor'), M()),
                R('child'),
                M()
            ),
            R('age'),
            M()
        ),
        [Function(_x, ExistsFormula(_y,
                                    TripleFormula(_y, _get_property('age'), _x) &
                                    ExistsFormula(_z, TripleFormula(_z, _get_property('child'), _y) &
                                                  TripleFormula(_get_individual('I, Robot'),
                                                                _get_property('main actor'),
                                                                _z))))]
    ),
    (
        T(R('World'), L([R('car')]), M()),
        []
    ),
    (
        I([
            T(M(), R('instance of'), R('book')),
            T(R('Suzanne Collins'), R('bibliography'), M(), R('author'))
        ]),
        [Function(_x, TripleFormula(_x, _get_property('type'), _get_individual('book')) &
                  TripleFormula(_x, _get_property('author'), _get_individual('Suzanne Collins')))]
    ),
    (
        U([T(R('Barack Obama'), R('child'), M()), T(R('John F. Kennedy'), R('child'), M())]),
        [Function(_x, TripleFormula(_get_individual('Barack Obama'), _get_property('child'), _x) | TripleFormula(
            _get_individual('John F. Kennedy'), _get_property('child'), _x))]
    ),
    (
        I([
            T(M(), L([R('instance of')]), R('actor')),
            T(
                M(),
                R('wife'),
                T(R('John F. Kennedy'), R('sister'), M()),
                R('married to')
            )
        ]),
        [
            Function(_x, TripleFormula(_x, _get_property('type'), _get_individual('actor')) &
                     ExistsFormula(_y, TripleFormula(_x, _get_property('wife'), _y) &
                                   TripleFormula(_get_individual('John F. Kennedy'), _get_property('sister'), _y))),
            Function(_x, TripleFormula(_x, _get_property('type'), _get_individual('actor')) &
                     ExistsFormula(_y, (TripleFormula(_y, _get_property('married to'), _x)) &
                                   TripleFormula(_get_individual('John F. Kennedy'), _get_property('sister'), _y)))
        ]
    ),
    (
        E(T(R('France'), R('capital'), M())),
        [ExistsFormula(_x, TripleFormula(_get_individual('France'), _get_property('capital'), _x))]
    ),
]

_tree_for_term = [
    (
        Function(_x, EqualityFormula(_x, _get_individual('France'))),
        _get_resource('France')
    ),
    (
        Function(_x, TripleFormula(_get_individual('France'), _get_property('prime minister'), _x)),
        T(_get_resource('France'), _get_resource('prime minister'), M()),
    ),
    (
        Function(_x, TripleFormula(_get_individual('France'), _get_property('location'), _x) |
                 TripleFormula(_get_individual('France'), _get_property('coordinates'), _x)),
        U([T(_get_resource('France'), _get_resource('coordinates'), M()),
           T(_get_resource('France'), _get_resource('location'), M())])
    ),
    (
        Function(_x, TripleFormula(_get_individual('France'), _get_property('location'), _x) &
                 TripleFormula(_get_individual('France'), _get_property('coordinates'), _x)),
        I([T(_get_resource('France'), _get_resource('coordinates'), M()),
           T(_get_resource('France'), _get_resource('location'), M())])
    ),
    (
        Function(_x, ExistsFormula(_y, TripleFormula(_y, _get_property('child'), _x) &
                                   TripleFormula(_get_individual('I, Robot'), _get_property('main actor'), _y))),
        T(
            T(_get_resource('I, Robot'), _get_resource('main actor'), M()),
            _get_resource('child'),
            M()
        ),
    ),
]


class _PPPDataModelConverterTest(unittest.TestCase):
    _convert_from = FromPPPDataModelConverter(_knowledge_base, 'en')
    _convert_to = ToPPPDataModelConverter()

    def testTreeToFormula(self):
        for (input, output) in _term_for_tree:
            results = self._convert_from.node_to_terms(input)
            self.assertListEqual(output, results)

    def testFormulaToTree(self):
        for (input, output) in _tree_for_term:
            result = self._convert_to.term_to_node(input)
            self.assertEqual(output, result)
