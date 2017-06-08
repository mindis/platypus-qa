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
from platypus_qa.database.owl import ObjectProperty, DatatypeProperty, xsd_decimal, owl_NamedIndividual, Class, \
    NamedIndividual, XSDDateTimeLiteral, xsd_dateTime
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
    'Royaume-Uni': [_schema_Country],
    'Homer J. Simpson': [_schema_Person],
    'Bob Marley': [_schema_Person],
    'guépard': [owl_NamedIndividual],
    'Barack Obama': [_schema_Person],
    'Big Ben': [_schema_Place],
    'I, Robot': [_schema_Movie],
    'Robin des Bois': [_schema_Movie],
    'avion': [owl_NamedIndividual],
    'masculin': [owl_NamedIndividual],
    'Lyon': [_schema_Place],
    'Paris': [_schema_Place],
    'fourchette': [owl_NamedIndividual],
    'ville': [owl_NamedIndividual],
    'Le Petit Prince': [_schema_Book],
    'Vol de Nuit': [_schema_Book],
    'Strasbourg': [_schema_Place],
    'service civique': [owl_NamedIndividual],
    'civique': [owl_NamedIndividual],
    'service': [owl_NamedIndividual],
    'Douglas': [owl_NamedIndividual],
    'fraise': [owl_NamedIndividual]
}

_object_properties = {
    'premier ministre': _schema_Person,
    'président': _schema_Person,
    'enfants': _schema_Person,
    'lieu de naissance': _schema_Place,
    'femme': _schema_Person,
    'mari': _schema_Person,
    'acteur principal': _schema_Person,
    'capitale': _schema_Place,
    'pilote': _schema_Person,
    'livres': owl_NamedIndividual,
    'localisation': _schema_GeoCoordinates,
    'né à': _schema_Place,
    'écrits par': _schema_Person,
    'origine': owl_NamedIndividual,
    'auteur': _schema_Person,
    'type': owl_NamedIndividual,
    'prénom': owl_NamedIndividual,
    'mange': owl_NamedIndividual,
    'héritier de': _schema_Person
}

_data_properties = {
    'date de naissance': xsd_dateTime,
    'vitesse': xsd_decimal,
    'âge': xsd_decimal,
    'largeur': xsd_decimal,
    'hauteur': xsd_decimal,
    'date': xsd_dateTime,
    'né en': xsd_dateTime,
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
logging.basicConfig(level=logging.WARNING)

_parsed_sentences = {
    'Bob Marley ?':
        Function(_x, EqualityFormula(_x, _get_individual('Bob Marley'))),

    'Le Bob Marley ?':
        Function(_x, EqualityFormula(_x, _get_individual('Bob Marley'))),

    'Qui est Bob Marley ?':
        Function(_x, EqualityFormula(_x, _get_individual('Bob Marley'))),

    'Qui est Homer J. Simpson ?':
        Function(_x, EqualityFormula(_x, _get_individual('Homer J. Simpson'))),

    'premier ministre de la France':
        Function(_x, TripleFormula(_get_individual('France'), _get_property('premier ministre'), _x)),

    'Qui est le premier ministre de la France ?':
        Function(_x, TripleFormula(_get_individual('France'), _get_property('premier ministre'), _x)),

    'Qui est le président du Royaume-Uni':
        Function(_x, TripleFormula(_get_individual('Royaume-Uni'), _get_property('président'), _x)),

    'Quel est le président de la France':
        Function(_x, TripleFormula(_get_individual('France'), _get_property('président'), _x)),

    'Quel est la date de naissance de Bob Marley?':
        Function(_x, TripleFormula(_get_individual('Bob Marley'), _get_property('date de naissance'), _x)),

    'Quel est la vitesse du guépard ?':
        Function(_x, TripleFormula(_get_individual('guépard'), _get_property('vitesse'), _x)),

    'Quels sont les enfants de la femme de Barack Obama ?':
        Function(_x, ExistsFormula(_y, TripleFormula(_get_individual('Barack Obama'), _get_property('femme'), _y) &
                                   TripleFormula(_y, _get_property('enfants'), _x))),

    'Quel est la largeur d\'un guépard ?':
        Function(_x, TripleFormula(_get_individual('guépard'), _get_property('largeur'), _x)),

    'De quand date Big Ben ?':
        Function(_x, TripleFormula(_get_individual('Big Ben'), _get_property('date'), _x)),

    'De combien est la hauteur de Big Ben ?':
        Function(_x, TripleFormula(_get_individual('Big Ben'), _get_property('hauteur'), _x)),

    'Qu\'est-ce qu\'une fourchette ?':
        Function(_x, EqualityFormula(_x, _get_individual('fourchette'))),

    'Qu\'est-ce qu\'"I, Robot" ?':
        Function(_x, EqualityFormula(_x, _get_individual('I, Robot'))),

    'Qu\'est-ce que Robin des Bois ?':
        Function(_x, EqualityFormula(_x, _get_individual('Robin des Bois'))),

    'Donne moi la capitale du Royaume-Uni.':
        Function(_x, TripleFormula(_get_individual('Royaume-Uni'), _get_property('capitale'), _x)),

    'Donne nous le premier ministre de la France.':
        Function(_x, TripleFormula(_get_individual('France'), _get_property('premier ministre'), _x)),

    'livres de Barack Obama':
        Function(_x, TripleFormula(_get_individual('Barack Obama'), _get_property('livres'), _x)),

    'Liste des livres de Barack Obama':
        Function(_x, TripleFormula(_get_individual('Barack Obama'), _get_property('livres'), _x)),

    'Quels sont les enfants masculin de Barack Obama ?':
        Function(_x, TripleFormula(_get_individual('Barack Obama'), _get_property('enfants'), _x) &
                 TripleFormula(_x, _get_property('type'), _get_individual('masculin'))),

    'Quel est la localisation de Big Ben ?':
        Function(_x, TripleFormula(_get_individual('Big Ben'), _get_property('localisation'), _x)),

    'Où est Big Ben ?':
        Function(_x, TripleFormula(_get_individual('Big Ben'), _get_property('localisation'), _x)),

    'Où est Lyon ?':
        Function(_x, TripleFormula(_get_individual('Lyon'), _get_property('localisation'), _x)),

    'Où est Paris ?':
        Function(_x, TripleFormula(_get_individual('Paris'), _get_property('localisation'), _x)),

    'Où est Strasbourg ?':
        Function(_x, TripleFormula(_get_individual('Strasbourg'), _get_property('localisation'), _x)),

    'Quand est né le président de la France ?':
        Function(_x, ExistsFormula(_y, TripleFormula(_get_individual('France'), _get_property('président'), _y) &
                                   TripleFormula(_y, _get_property('date de naissance'), _x))),

    'Quand sont nés les enfants du président de la France ?':
        Function(_x, ExistsFormula(_y, ExistsFormula(_z,
                                                     TripleFormula(_get_individual('France'),
                                                                   _get_property('président'), _z) &
                                                     TripleFormula(_z, _get_property('enfants'), _y)) &
                                   TripleFormula(_y, _get_property('date de naissance'), _x))),

    'service civique':
        Function(_x, EqualityFormula(_x, _get_individual('service civique'))),

    'Qui mange une fraise ?':
        Function(_x, TripleFormula(_x, _get_property('mange'), _get_individual('fraise'))),

    'Qui est né en 1960 ?':
        Function(_x, TripleFormula(_x, _get_property('né en'), ValueFormula(XSDDateTimeLiteral(1960, 0, 0, 0, 0, 0)))),

    'Qui est né à Paris ?':
        Function(_x, TripleFormula(_x, _get_property('né à'), _get_individual('Paris'))),

    'Qui est né à Paris en 1960 ?':
        Function(_x, TripleFormula(_x, _get_property('né à'), _get_individual('Paris')) &
                 TripleFormula(_x, _get_property('né en'), ValueFormula(XSDDateTimeLiteral(1960, 0, 0, 0, 0, 0)))),

    'Qui sont les héritier de Barack Obama ?':
        Function(_x, TripleFormula(_x, _get_property('héritier de'), _get_individual('Barack Obama'))),

    'Qui est né après 2016 ?':
        Function(_x, ExistsFormula(_y, TripleFormula(_x, _get_property('né en'), _y) &
                                   GreaterFormula(_y, ValueFormula(XSDDateTimeLiteral(2016, 0, 0, 0, 0, 0))))),
}
'''
    'Qui a pour prénom Douglas':
        Function(_x, TripleFormula(_x, _get_property('prénom'), _get_individual('Douglas'))),

    'Où est né Barack Obama ?':
        Function(_x, TripleFormula(_get_individual('Barack Obama'), _get_property('lieu de naissance'), _x)),

    'Qui a écrit Le Petit Prince ?':
        T(_Le_Petit_Prince, _auteur, M()),

    'La France a-t-elle une capitale ?':
        E(T(_France, _capitale, M())),

    'Il y a-t-il un pilote dans l\'avion ?':
        E(T(_avion, _pilote, M())),

    'Quels sont les livres écrits par Barack Obama ?':
        I([
            T(M(), L(_type_properties), _livre),
            T(M(), _ecrits_par, _Barack_Obama)
        ])),

    'Quels livres Barack Obama a-t-il écrits ?':
        I([
            T(M(), L(_type_properties), _livre),
            T(M(), _ecrits_par, _Barack_Obama)
        ])),

    'Qui a écrit Le Petit Prince et Vol de Nuit ?':
        I([
            T(_Le_Petit_Prince, _auteur, M()),
            T(_Vol_de_Nuit, _auteur, M()),
        ]))


    'Qui est l\'acteur principal de Robin des Bois ?':
        T(_Robin_des_Bois, _acteur_principal, M()),

    'Qui sont les enfants de l\'acteur principal de Robin des Bois ?':
        T(
            T(_Robin_des_Bois, _acteur_principal, M()),
            _enfant,
            M()
        ),

    'Quel âge ont les enfants de l\'acteur principal de Robin des Bois ?':
        T(
            T(
                T(_Robin_des_Bois, _acteur_principal, M()),
                _enfant,
                M()
            ),
            _age,
            M()
        ),

    TODO: question avec adjectifs
'Qui est le président français ?':
    T(_France, _president, M()),

'Quel est le premier ministre français ?':
    T(_France, _premier_ministre, M()),

'Quel est la vitesse de la voiture la plus rapide du monde ?':
    T(
        L(
            S(
                T(_M, R('car'), M()),
                R('cost')
            ),
        ),
        R('speed'),
        M()
    ),
'''


class FrenchGrammaticalAnalyzerTest(unittest.TestCase):
    @classmethod
    def setUpClass(self):
        self._analyzer = GrammaticalAnalyzer(CoreNLPParser(['https://corenlp.askplatyp.us/1.7/']), _knowledge_base,
                                             'fr')

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
