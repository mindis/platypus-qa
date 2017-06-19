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

from typing import Optional

from platypus_qa.database.formula import Type
from platypus_qa.database.owl import platypus_calendar


class QuestionWord:
    def __init__(self, words: str):
        self.words = words

    def __str__(self):
        return self.words


class OpenQuestionWord(QuestionWord):
    def __init__(self, words: str, expected_type: Type = Type.bottom(), expected_properties=(),
                 property_modifiers=('{}',)):
        """
        :param words: The question words
        :param expected_type: The type the question returns
        :param expected_properties: The properties that could be used to retrieve results
        :param property_modifiers: The pattern used to create a property name from the nounified main dependency like 'date de {}' or '{} date'
        """
        super().__init__(words)
        self.expected_type = expected_type
        self.expected_properties = expected_properties
        self.property_modifiers = property_modifiers


class CloseQuestionWord(QuestionWord):
    pass


class ExistsQuestionWord(QuestionWord):
    pass


_time_types = ['xsd:dateTime', 'xsd:date', 'xsd:gMonthYear', 'xsd:gYear', 'xsd:time', 'xsd:gMonthDay', 'xsd:gMonth',
               'xsd:gDay']
_où = OpenQuestionWord('où', expected_properties=['localisation', 'lieu'], property_modifiers=['lieu de {}'])
# TODO expected_type=['Place', 'GeoCoordinates']
_quand = OpenQuestionWord('quand', expected_properties=['date', 'heure'],
                          property_modifiers=['date de {}', 'heure de {}', 'année de {}'],
                          expected_type=Type.from_entity(platypus_calendar))
_dónde = OpenQuestionWord('dónde',
                          expected_properties=['localización', 'lugar', 'sitio', 'plaza', 'posición', 'ubicación',
                                               'coordenadas', 'país'],
                          property_modifiers=['lugar de {}'])
_cuándo = OpenQuestionWord('cuándo', expected_properties=['fecha', 'hora'],
                           property_modifiers=['fecha de {}', 'hora de {}', 'año de {}'],
                           expected_type=Type.from_entity(platypus_calendar))
_question_words = {
    'de': {
        'wer': OpenQuestionWord('wer'),
        'was': OpenQuestionWord('was'),
        'wann': OpenQuestionWord('wann', expected_properties=['Datum', 'Stunde'], property_modifiers=['{}datum']),
        'wo': OpenQuestionWord('wo', expected_properties=['Lage', 'Ort', 'Platz'], property_modifiers=['{}ort']),
        'wen': OpenQuestionWord('wen'),
        'wem': OpenQuestionWord('wem'),
        'wieso': OpenQuestionWord('wieso'),  # TODO
        'woher': OpenQuestionWord('woher', expected_properties=['Start']),
        'wohin': OpenQuestionWord('wohin', expected_properties=['']),  # TODO
        'warum': OpenQuestionWord('warum', expected_properties=['Ursache', 'Anlass', 'Grund', 'Anfang']),
        'welch': OpenQuestionWord('welch')
    },
    'en': {
        'give': OpenQuestionWord('give'),
        'give me': OpenQuestionWord('give me'),
        'give us': OpenQuestionWord('give us'),
        'list': OpenQuestionWord('list'),
        'what': OpenQuestionWord('what'),
        'what kind': OpenQuestionWord('what kind'),
        'what type': OpenQuestionWord('what type', expected_properties=['type', 'sort']),
        'what sort': OpenQuestionWord('what sort', expected_properties=['type', 'sort']),
        'what time': OpenQuestionWord('what time', expected_properties=['time'], property_modifiers=['{} time']),
        'when': OpenQuestionWord('when', expected_properties=['date', 'time'],
                                 property_modifiers=['{} date', '{} time'],
                                 expected_type=Type.from_entity(platypus_calendar)),
        'why': OpenQuestionWord('why', expected_properties=['reason', 'cause', 'origin'],
                                property_modifiers=['{} reason', '{} cause', '{} origin']),
        'where': OpenQuestionWord('where', expected_properties=['location', 'place', 'city', 'locality'],
                                  property_modifiers=['{} place', '{} location', '{} city']),
        'who': OpenQuestionWord('who'),
        'how': OpenQuestionWord('how', expected_properties=['manner'], property_modifiers=['{} manner']),
        'how much': OpenQuestionWord('how much', expected_properties=['amount', 'quantity', 'number'],
                                     property_modifiers=['{} amount', '{} quantity', '{} number']),
        'how many': OpenQuestionWord('how many', expected_properties=['amount', 'quantity', 'number'],
                                     property_modifiers=['{} amount', '{} quantity', '{} number']),
        'how old': OpenQuestionWord('how old', expected_properties=['age'], property_modifiers=['{} age']),
        'how far': OpenQuestionWord('how far', expected_properties=['distance'], property_modifiers=['{} distance']),
        'how long': OpenQuestionWord('how long', expected_properties=['length', 'duration'],
                                     property_modifiers=['{} length', '{} duration']),
        'how tall': OpenQuestionWord('how tall', expected_properties=['height'], property_modifiers=['{} height']),
        'how deep': OpenQuestionWord('how deep', expected_properties=['depth'], property_modifiers=['{} depth']),
        'how wide': OpenQuestionWord('how wide', expected_properties=['width'], property_modifiers=['{} width']),
        'how fast': OpenQuestionWord('how fast', expected_properties=['speed', 'velocity'],
                                     property_modifiers=['{} speed', '{} velocity']),
        'how often': OpenQuestionWord('how often', expected_properties=['frequency'],
                                      property_modifiers=['{} frequency']),
        'how come': OpenQuestionWord('how come', expected_properties=['reason'], property_modifiers=['{} reason']),
        'which': OpenQuestionWord('which'),
        'whom': OpenQuestionWord('whom'),
        'whose': OpenQuestionWord('whose', expected_properties=['owner'], property_modifiers=['{} owner']),
        'how big': OpenQuestionWord('how big', expected_properties=['size'], property_modifiers=['{} size']),
        'of which': OpenQuestionWord('of which'),
        'in which': OpenQuestionWord('in which', expected_properties=['location', 'place', 'city', 'locality'],
                                     property_modifiers=['{} place', '{} location', '{} city']),
        'from which': OpenQuestionWord('from which',
                                       expected_properties=['place', 'location', 'residence', 'origin', 'citizenship',
                                                            'nationality', 'country of citizenship', 'country', 'city'])
    },
    'es': {
        'cómo': OpenQuestionWord('cómo'),
        'como': OpenQuestionWord('cómo'),
        'cuál': OpenQuestionWord('cuál'),
        'cual': OpenQuestionWord('cuál'),
        'cuáles': OpenQuestionWord('cuáles'),
        'cuales': OpenQuestionWord('cuáles'),
        'cuándo': _cuándo,
        'cuando': _cuándo,
        'cuánto': OpenQuestionWord('cuánto'),
        'cuanto': OpenQuestionWord('cuánto'),
        'cuánta': OpenQuestionWord('cuánto'),
        'cuanta': OpenQuestionWord('cuánto'),
        'cuántos': OpenQuestionWord('cuánto'),
        'cuantos': OpenQuestionWord('cuánto'),
        'cuántas': OpenQuestionWord('cuánto'),
        'cuantas': OpenQuestionWord('cuánto'),
        'dónde': _dónde,
        'donde': _dónde,
        'por qué': OpenQuestionWord('por qué', expected_properties=['causa', 'razón']),
        'por que': OpenQuestionWord('por qué', expected_properties=['causa', 'razón']),
        'qué': OpenQuestionWord('qué'),
        'que': OpenQuestionWord('qué'),
        'quién': OpenQuestionWord('quién'),  # TODO: expected_types=['Person']
        'quien': OpenQuestionWord('quién'),  # TODO: expected_types=['Person']
        'quiénes': OpenQuestionWord('quiénes'),  # TODO: expected_types=['Person']
        'quienes': OpenQuestionWord('quiénes'),  # TODO: expected_types=['Person']
    },
    'fr': {
        'a quoi': OpenQuestionWord('à quoi'),
        'à quoi': OpenQuestionWord('à quoi'),
        'comment': OpenQuestionWord('comment', property_modifiers=(
            'circonstance de {}', 'circonstance du {}', 'cause de {}', 'cause {}', '{} car', '{} à cause de')),
        'combien': OpenQuestionWord('combien'),
        'de quoi': OpenQuestionWord('de quoi'),
        'donne': OpenQuestionWord('donne'),
        'donne moi': OpenQuestionWord('donne moi'),
        'donne nous': OpenQuestionWord('donne nous'),
        'laquelle': OpenQuestionWord('laquelle'),
        'lesquelles': OpenQuestionWord('lesquelles'),
        'lequel': OpenQuestionWord('lequel'),
        'lesquels': OpenQuestionWord('lequels'),
        'liste': OpenQuestionWord('liste'),
        'ou': _où,  # Usual typo
        'où': _où,
        'pourquoi': OpenQuestionWord('pourquoi', expected_properties=['raison', 'cause', 'origine']),
        'qu\'': OpenQuestionWord('qu\''),
        'quand': _quand,
        'quant': _quand,  # Usual typo
        'que': OpenQuestionWord('que'),
        'quel': OpenQuestionWord('quel'),
        'quelle': OpenQuestionWord('quel'),
        'quelles': OpenQuestionWord('quel'),
        'quels': OpenQuestionWord('quel'),
        'qui': OpenQuestionWord('qui'),  # TODO: expected_types=['Person']
        'quoi': OpenQuestionWord('quoi')
    }
}


def get_question_word_from_str(words: str, language_code: str) -> Optional[QuestionWord]:
    words = words.lower().strip()
    if language_code not in _question_words or words not in _question_words[language_code]:
        return None

    return _question_words[language_code][words]
