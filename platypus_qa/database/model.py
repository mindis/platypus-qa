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
from typing import List, Union, Iterable, Optional, Tuple

from platypus_qa.database.formula import Term, Select, Tuple, VariableFormula, TripleFormula, AndFormula, OrFormula, \
    ExistsFormula, EqualityFormula
from platypus_qa.database.owl import Literal, Class, owl_Thing, Entity, Property


class QAInterpretationResult:
    def __init__(self, result: Union[Entity, Literal],
                 context_subject: Optional[Entity] = None, context_predicate: Optional[Property] = None):
        self.result = result
        self.context_subject = context_subject
        self.context_predicate = context_predicate


class QAInterpretation:
    def __init__(self, interpretation: Term, results: List[QAInterpretationResult]):
        self.interpretation = interpretation
        self.results = results


class FormatterError(Exception):
    pass


class EvaluationError(Exception):
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

    def evaluate_term(self, term: Term) -> List[Tuple]:
        """
        :raise EvaluationError
        """
        raise NotImplementedError("KnowledgeBase.evaluate_term is not implemented")

    def build_interpretation(self, term: Term) -> QAInterpretation:
        """
        :raise EvaluationError
        """
        results = self.evaluate_term(self._add_context_variables(term))
        return QAInterpretation(term, [self._tuple_to_result(result) for result in results])

    @staticmethod
    def _add_context_variables(term: Term) -> Term:
        if not isinstance(term, Select):
            return term

        result = term.args[0]
        subject_var = VariableFormula('s')
        predicate_var = VariableFormula('p')

        def explore(term: Term):
            if isinstance(term, TripleFormula):
                if term.object == result:
                    return TripleFormula(subject_var, predicate_var, result) & \
                           EqualityFormula(subject_var, term.subject) & EqualityFormula(predicate_var, term.predicate), \
                           True
                return term, False
            elif isinstance(term, AndFormula):
                found = False
                modified = []
                for arg in term.args:
                    if found:
                        modified.append(arg)  # The value is already set, we do not modify anything
                    else:
                        arg, found_ = explore(arg)
                        modified.append(arg)
                        found = found or found_
                return AndFormula(modified), found
            elif isinstance(term, OrFormula):
                modified = []
                found = False
                for arg in term.args:
                    arg, found_ = explore(arg)
                    modified.append(arg)
                    found = found or found_
                return OrFormula(modified), found
            elif isinstance(term, ExistsFormula):
                out, found = explore(term.body)
                return ExistsFormula(term.argument, out), found
            else:
                return term, False

        body, found = explore(term.body)

        if found:
            return Select((subject_var, predicate_var, result), body)
        else:
            return term

    @staticmethod
    def _tuple_to_result(result: Tuple) -> QAInterpretationResult:
        if len(result) == 1:
            return QAInterpretationResult(result[0])
        elif len(result) == 3:
            return QAInterpretationResult(result[2], result[0], result[1])
        else:
            raise EvaluationError('Unexpected result tuple: {}'.format(result))

    def format_to_jsonld(self, result: QAInterpretationResult,
                         accept_language: str) -> dict:  # TODO: one or two methods?
        """
        :return: dict ready to serialize in JSON
        :raise FormatterError
        """
        raise NotImplementedError("KnowledgeBase.format_resource is not implemented")
