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
from itertools import chain
from typing import List, Union, Iterable

from platypus_qa.database.formula import Term, Select
from platypus_qa.database.owl import Literal, Class, owl_Thing, Entity


class QAInterpretationResult:
    def __init__(self, result: Union[Entity, Literal]):
        self.result = result


class QAInterpretation:
    def __init__(self, interpretation: Term, results: List[QAInterpretationResult]):
        self.interpretation = interpretation
        self.results = results


class FormatterError(Exception):
    pass


class KnowledgeBase:
    def individuals_from_label(self, label: str, language_code: str, type_filter: Class = owl_Thing) -> List[Select]:
        raise NotImplementedError("KnowledgeBase.individuals_from_label is not implemented")

    def relations_from_label(self, label: str, language_code: str) -> List[Select]:
        """
        :return: functions λ s . λ o . X where s is the subject and o the object of the relation
        """
        return self.relations_from_labels((label,), language_code)

    def relations_from_labels(self, labels: Iterable[str], language_code: str) -> List[Select]:
        """
        :return: functions λ s . λ o . X where s is the subject and o the object of the relation
        """
        return list(chain.from_iterable(self.relations_from_label(label, language_code) for label in labels))

    def type_relations(self) -> List[Select]:
        """
        :return: the relations used to state types.
                 Under the format functions λ s . λ t . X where s is the subject and t the type
        """
        raise NotImplementedError("KnowledgeBase.type_properties is not implemented")

    def evaluate_term(self, term: Term) -> List[Union[Entity, Literal]]:
        raise NotImplementedError("KnowledgeBase.evaluate_term is not implemented")

    def format_to_jsonld(self, result: QAInterpretationResult,
                         accept_language: str) -> dict:  # TODO: one or two methods?
        """
        :return: dict ready to serialize in JSON
        :raise FormatterError
        """
        raise NotImplementedError("KnowledgeBase.format_resource is not implemented")
