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
import time
import unittest

from ppp_datamodel import Sentence, Resource, List, Request

from platypus_qa.request_handler import PPPRequestHandler

_questions = {
    'en': [
        'What is the birth date of George Washington?',
        'Who is the president of France?',
        'What is the capital of Australia?',
        'Who is the author of Foundation?',
        'Who is the director of "Pulp Fiction"?',
        'Who is the director of "A Clockwork Orange"?',
        'Sherlock Holmes',
        'Guatemala',
        'Who is Bach?',
        'What is “P=NP”?',
        'Who is the author of “Le Petit Prince”?',
        'What is the capital of India?',
        'Who is the prime minister of France?',
        'What is the birth date of the president of the United States?',
        'Who are the Beatles\' members?',
        'sqrt(180)',
        'N[Pi, 42]',
        'Limit[Sum[1/i, {i,1,n}]-Log[n], n->Infinity]',
        'Sum[x^n/n!, {n,0,Infinity}]',
        'Solve[Exp[x]/2+Exp[-x]/2==y,x]',
        'dsolve(f\'(x) + f(x) = 0, f(x))',
        'Who are the daughters of the wife of the husband of the wife of the president of the United States?',
        'Where was Ulysses S. Grant born?',
        'Where was George Washington born?',
        'Where is the Taj Mahal?',
        'Who is the President of Ghana?',
        'What is Head Start?',
        'Who wrote "Dubliners"?',
        'Who wrote Hamlet?',
        'What is the population of Japan?',
        'What is the population of France?',
        'What is a caldera?',
        'What is the nationality of Jackson Pollock?',
        'What is the zip code for Lyon?',
        'What is the atomic number of oxygen?',
        'What is the atomic number of polonium?',
        'What is Boston Strangler\'s name?',
        'When was D-Day?',
        'What is an annotated bibliography?',
        'Who is the mayor of Paris?',
        'Who is the mayor of London?',
        'Where is the Sagrada Familia?',
        'Where is "Notre-Dame de Paris"?',
        'Where is the Everest?',
        'Where is the parliament of China?',
        'Where is the Panama canal?',
        'What is the location of the Alps?',
        'What is the location of the Great Barrier Reef?',
        'What are the official names of the European Union?',
        'What are the official languages of the European Union?',
        'What is the flag of the European Union?',
        'What are the capitals of the European Union?',
        'Where are the capitals of the European Union?',
        'What are the borders of Mexico?',
        'What is the time zone of France?',
        'What is the time zone of San Francisco?',
        'Where is the Bay Area?',
        'What is the music genre of the Beatles?',
        'What is the music genre of Bob Marley?',
        'What is the film genre of Full Metal Jacket?',
        'film genre of Full Metal Jacket',
        'atomic number of polonium',
        'population of France',
        'president of Ghana?',
        'When is Julius Caesar born?',
        'When is Ramesses II born?',
        'Where is the inventor of dynamite born?'
    ],
    'fr': [
        'Quelle est la date de naissance de George Washington?',
        'Quand est né George Washington ?',
        'Où est né Jules César ?',
        'Quand était la bataille d\'Actium ?',
        'Quand est né le premier ministre du Royaume-Unis ?',
        'Quand est né le président de la France ?',
        'Qui est le président de la France ?',
        'Quelle est la capitale de l\'Australie ?',
        'Qui est l\'auteur de Fondation ?',
        'Qui est le réalisateur de Pulp Fiction ?',
        'Qui est le PDG de Google ?',
        'Sherlock Holmes',
        'Guatemala',
        'Qui est Bach?',
        'Qu\'est-ce que “P=NP”?',
        'Qui est l\'auteur du Petit Prince ?',
        'Quel est la capitale de l\'Inde ?',
        'Qui est le premier ministre de la France ?',
        'Qui sont les membres des Beatles ?',
        'sqrt(180)',
        'N[Pi, 42]',
        'Limit[Sum[1/i, {i,1,n}]-Log[n], n->Infinity]',
        'Sum[x^n/n!, {n,0,Infinity}]',
        'Solve[Exp[x]/2+Exp[-x]/2==y,x]',
        'dsolve(f\'(x) + f(x) = 0, f(x))',
        'Quand est né Louis XIV ?',
        'Où est né le général De Gaulle ?',
        'Où est le musée de Louvre ?',
        'Qui est le président du Ghana ?',
        # TODO 'Qui a écrit Hamlet ?', "écrit" as amod of Hamlet
        # TODO 'Qui a écrit La Princesse de Clèves ?', idem
        'Quelle est la population de la France ?',
        'Quelle est la population du Japon ?',
        'Qu\'est-ce qu\'une  caldera ?',
        'Quelle est la nationalité de Jackson Pollock ?',
        'Quel est le code postal de Lyon ?',
        'Quel est le numéro atomique de l\'oxygène ?',
        'Quel est le numéro atomique du Polonium ?',
        'Quand était la prise de la Bastille ?',
        'Qu\'est-ce qu\'une bibliographie ?',
        'Qui est le maire de Paris ?',
        'Qui est le maire de Londre ?',
        'Où est la Sagrada Familia ?',
        'Où est "Notre-Dame de Paris" ?',
        'Ou est l\'Everest ?',
        'Où est le sénat français ?',
        'Où est le canal de Panama ?',
        'Quelle est la localisation des Alpes ?',
        'Quelle est la localisation de la Grande barrière de corail ?',
        'Quels sont les noms officiels de l\'Union Européenne ?',
        'Quels sont les langues officielles de l\'UE ?',
        'Quel est le drapeau de l\'Union Européenne ?',
        'Quels sont les capitales de l\'Union Européenne ?',
        'Où sont les capitales de l\'Union Européenne ?',
        'Quels sont les frontières de Mexico ?',
        'Quel est le fuseau horaire de la France ?',
        'Quel est le fuseau horaire de San Francisco ?',
        'Où est le bassin d\'Arcachon ?',
        'numéro atomique du polonium',
        'population de la France',
        'président du Ghana',
        'Où est né l\'inventeur de la dynamite ?',
        'Qui est né à Paris ?'
    ]
}


class RequestHandlerTest(unittest.TestCase):
    """
    Warning: very slow tests to don't overload servers
    """

    def testQuestions(self):
        bad_count = 0
        for (language_code, questions) in _questions.items():
            for question in questions:
                results = PPPRequestHandler(Request(
                    'foo', language_code, Sentence(question), {}, [], language_code
                )).answer()
                resource_results = [result for result in results
                                    if isinstance(result.tree, Resource) or
                                    (isinstance(result.tree, List) and result.tree.list)]
                if not resource_results:
                    print(
                        '[ppp_module_test] No resources found for the {} question {}.\nReturned results: {}'.format(
                            language_code, question, results), file=sys.stderr)
                    bad_count += 1
                time.sleep(5)  # to don't overload servers
        if bad_count > 0:
            raise AssertionError(
                '{} on {} tests failed'.format(bad_count, sum(len(questions) for questions in _questions.values())))
