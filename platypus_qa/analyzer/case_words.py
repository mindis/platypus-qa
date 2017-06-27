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

from typing import Callable, Optional, Dict, Iterable, List

from platypus_qa.database.formula import Select, VariableFormula, LowerFormula, ExistsFormula, GreaterFormula


class CaseWord:
    def __init__(self, words: str,
                 terms_by_modifiers: Dict[Iterable[str], Callable[[Select], Select]], properties: List[str] = ()):
        self.words = words
        self.terms_by_modifiers = terms_by_modifiers
        self.properties = properties

    def __str__(self):
        return self.words


def _predicate_subject_term(relation: Select):
    return relation


def _predicate_object_term(relation: Select):
    return relation.swap_arguments()


def _predicate_lower_object_term(relation: Select):
    subject = VariableFormula('subject')
    object = VariableFormula('object')
    lower = VariableFormula('lower')
    return Select((object, subject), ExistsFormula(lower, relation(subject)(lower) & LowerFormula(lower, object)))


def _predicate_greater_object_term(relation: Select):
    subject = VariableFormula('subject')
    object = VariableFormula('object')
    greater = VariableFormula('greater')
    return Select((object, subject),
                  ExistsFormula(greater, relation(subject)(greater) & GreaterFormula(greater, object)))


_case_words = {
    'de': {
        'auf': CaseWord('auf', {('{} auf',): _predicate_object_term}),
        'aus': CaseWord('aus', {('{} aus',): _predicate_object_term}),
        'durch': CaseWord('durch', {('{} durch',): _predicate_object_term}),
        'für': CaseWord('für', {('{} für',): _predicate_object_term}),
        'fur': CaseWord('für', {('{} für',): _predicate_object_term}),
        'nach': CaseWord('nach', {('{} nach',): _predicate_object_term}),
        'mit': CaseWord('mit', {('{} mit',): _predicate_object_term}),
        'von': CaseWord('von', {('{} von',): _predicate_object_term, ('{}',): _predicate_subject_term}),
        'zu': CaseWord('zu', {('{} zu',): _predicate_object_term}),
    },
    'en': {
        'after': CaseWord('after', {('{} after',): _predicate_object_term, ('{} in',): _predicate_greater_object_term}),
        'before': CaseWord('before',
                           {('{} before',): _predicate_object_term, ('{} in',): _predicate_lower_object_term}),
        'by': CaseWord('by', {('{} by',): _predicate_object_term}),
        'for': CaseWord('for', {('{} for',): _predicate_object_term, ('{}',): _predicate_subject_term}),
        'from': CaseWord('on', {('{} from',): _predicate_object_term}),
        'in': CaseWord('for', {('{} in',): _predicate_object_term}),
        'of': CaseWord('of', {('{} of',): _predicate_object_term, ('{}',): _predicate_subject_term}),
        'on': CaseWord('on', {('{} on',): _predicate_object_term}),
        'with': CaseWord('with', {('{} with',): _predicate_object_term}, ('actor',)),
    },
    'es': {
        'de': CaseWord('de', {('{} de',): _predicate_object_term, ('{}',): _predicate_subject_term}),
        'en': CaseWord('en', {('{} en',): _predicate_object_term}),
    },
    'fr': {
        'à': CaseWord('à', {('{} à',): _predicate_object_term}),
        'à partir de': CaseWord('à partir de', {('{} à partir de',): _predicate_object_term}),
        'à cause de': CaseWord('à cause de', {('{} à cause de',): _predicate_object_term}),
        'après': CaseWord('après', {('{} après',): _predicate_object_term, ('{} en',): _predicate_greater_object_term}),
        'avant': CaseWord('avant', {('{} avant',): _predicate_object_term, ('{} en',): _predicate_lower_object_term}),
        'avec': CaseWord('avec', {('{} avec',): _predicate_object_term}),
        'chez': CaseWord('chez', {('{} chez',): _predicate_object_term}),
        'contre': CaseWord('contre', {('{} contre',): _predicate_object_term}),
        'd\'': CaseWord('de', {('{} de',): _predicate_object_term, ('{}',): _predicate_subject_term}),
        'd’': CaseWord('de', {('{} de',): _predicate_object_term, ('{}',): _predicate_subject_term}),
        'dans': CaseWord('dans', {('{} dans',): _predicate_object_term}),
        'de': CaseWord('de', {('{} de',): _predicate_object_term, ('{}',): _predicate_subject_term}),
        'depuis': CaseWord('depuis', {('{} depuis',): _predicate_object_term}),
        'derrière': CaseWord('derrière', {('{} derrière',): _predicate_object_term}),
        'des': CaseWord('des', {('{} de',): _predicate_object_term, ('{}',): _predicate_subject_term}),
        'devant': CaseWord('devant', {('{} devant',): _predicate_object_term}),
        'du': CaseWord('du', {('{} de',): _predicate_object_term, ('{}',): _predicate_subject_term}),
        'en': CaseWord('en', {('{} en',): _predicate_object_term}),
        'envers': CaseWord('envers', {('{} envers',): _predicate_object_term}),
        'jusqu\'à': CaseWord('jusqu\'à', {('{} jusqu\'à',): _predicate_object_term}),
        'jusqu’à': CaseWord('jusqu\'à', {('{} jusqu\'à',): _predicate_object_term}),
        'malgré': CaseWord('malgré', {('{} malgré',): _predicate_object_term}),
        'pendant': CaseWord('pendant', {('{} pendant',): _predicate_object_term}),
        'par': CaseWord('par', {('{} par',): _predicate_object_term}),
        'pour': CaseWord('pour', {('{} pour',): _predicate_object_term}),
        'sans': CaseWord('sans', {('{} sans',): _predicate_object_term}),
        'sauf': CaseWord('sauf', {('{} sauf',): _predicate_object_term}),
        'selon': CaseWord('selon', {('{} selon',): _predicate_object_term}),
        'sous': CaseWord('sous', {('{} sous',): _predicate_object_term}),
        'sur': CaseWord('sur', {('{} sur',): _predicate_object_term}),
        'vers': CaseWord('vers', {('{} vers',): _predicate_object_term}),
    }  # TODO: entre
}


def get_case_word_from_str(words: str, language_code: str) -> Optional[CaseWord]:
    words = words.lower().strip()
    if language_code not in _case_words or words not in _case_words[language_code]:
        return None

    return _case_words[language_code][words]
