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

from typing import List, Dict

from platypus_qa.database.formula import Select, VariableFormula, TripleFormula, ValueFormula, EqualityFormula
from platypus_qa.database.model import KnowledgeBase
from platypus_qa.database.owl import Property, NamedIndividual, owl_Thing, Class

_s = VariableFormula('s')
_o = VariableFormula('o')


class SimpleKnowledgeBase(KnowledgeBase):
    def __init__(self, individuals_by_label: Dict[str, List[NamedIndividual]],
                 properties_by_label: Dict[str, List[Property]], type_properties: List[Property]):
        self._individuals_by_label = individuals_by_label
        self._properties_by_label = properties_by_label
        self._type_properties = type_properties

    def individuals_from_label(self, label: str, language_code: str, type_filter: Class = owl_Thing) -> List[Select]:
        if label not in self._individuals_by_label:
            return []
        individuals = self._individuals_by_label[label]
        if type_filter != owl_Thing:
            individuals = [individual for individual in individuals if type in individual.types]
        return [Select(_s, EqualityFormula(_s, ValueFormula(individual, label))) for individual in individuals]

    def relations_from_label(self, label: str, language_code: str) -> List[Select]:
        if label not in self._properties_by_label:
            return []
        return [Select((_s, _o), TripleFormula(_s, ValueFormula(p, label), _o)) for p in
                self._properties_by_label[label]]

    def type_relations(self) -> List[Select]:
        return [Select((_s, _o), TripleFormula(_s, ValueFormula(p), _o)) for p in self._type_properties]
