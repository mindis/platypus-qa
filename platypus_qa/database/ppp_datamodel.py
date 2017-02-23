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

import typing
from collections import defaultdict
from itertools import chain, product

from ppp_datamodel import AbstractNode, StringResource, Missing, List, Resource, Union, Intersection, Exists, Triple
from ppp_datamodel.nodes.resource import register_valuetype
from ppp_libmodule.simplification import simplify

from platypus_qa.analyzer.literal_parser import parse_literal
from platypus_qa.database.formula import ValueFormula, Function, OrFormula, VariableFormula, EqualityFormula, Term, \
    AndFormula, TripleFormula, Formula, ExistsFormula, Type, true_formula
from platypus_qa.database.model import KnowledgeBase
from platypus_qa.database.owl import owl_Thing, Entity, Literal, rdfs_Literal
from platypus_qa.database.wikidata import _WikidataObjectProperty, _WikidataItem

_wikidata_property_child = _WikidataObjectProperty({'@id': 'wdt:P40', 'range': 'NamedIndividual'})
_wikidata_property_sex = _WikidataObjectProperty({'@id': 'wdt:P21', 'range': 'NamedIndividual'})
_wikidata_item_male = _WikidataItem({'@id': 'wd:Q6581097', '@type': ['NamedIndividual']})
_wikidata_item_female = _WikidataItem({'@id': 'wd:Q6581072', '@type': ['NamedIndividual']})


@register_valuetype
class PlatypusResource(Resource):
    _value_type = 'resource-jsonld'
    _possible_attributes = Resource._possible_attributes + ('graph',)

    @classmethod
    def deserialize_attribute(cls, key, value):
        if key == 'graph':
            return value
        else:
            super().deserialize_attribute(key, value)

    def __hash__(self):
        return hash(self.value)

    def __eq__(self, other):
        if not isinstance(other, PlatypusResource):
            return False
        if '@id' in self.graph and '@id' in other.graph:
            return self.graph['@id'] == other.graph['@id']
        return self.graph == other.graph


class FromPPPDataModelConverter:
    _variable_counter = 0

    def __init__(self, knowledge_base: KnowledgeBase, language_code: str):
        self._knowledge_base = knowledge_base
        self._language_code = language_code

    def node_to_terms(self, node: AbstractNode, expected_type: Type = Type.from_entity(owl_Thing)) -> \
            typing.List[Term]:
        if isinstance(node, Resource):
            variable = self._create_variable('value')
            if expected_type <= owl_Thing:
                return self._knowledge_base.individuals_from_label(node.value, self._language_code)  # TODO: type?
            elif expected_type <= rdfs_Literal:
                return [Function(variable, EqualityFormula(variable, ValueFormula(value, node.value)))
                        for value in parse_literal(node.value, self._language_code, expected_type)]
            else:
                raise ValueError('Unsupported expected type {}'.format(expected_type))

        elif isinstance(node, Missing):
            return [Function(self._create_variable('everything'), true_formula)]

        elif isinstance(node, Triple):
            variable = self._create_variable('result')
            # TODO:bad, we should parse predicate et inverse_predicate with formulas \x \y .... and do composition
            return [Function(variable, triple) for triple in chain(
                self._triple_to_formulas(node.subject, node.predicate, node.object, variable) +
                self._triple_to_formulas(node.object, node.inverse_predicate, node.subject, variable)
            )]

        elif isinstance(node, Union):
            variable = self._create_variable('unified')
            return [Function(variable, OrFormula([child_term(variable) for child_term in child_terms]))
                    for child_terms in product(*(self.node_to_terms(child, expected_type) for child in node.list))]

        elif isinstance(node, Intersection):
            variable = self._create_variable('intersected')
            return [Function(variable, AndFormula([child_term(variable) for child_term in child_terms]))
                    for child_terms in product(*(self.node_to_terms(child, expected_type) for child in node.list))]

        elif isinstance(node, Exists):
            variable = self._create_variable('exists')
            return [ExistsFormula(variable, argument(variable)) for argument
                    in self.node_to_terms(node.list, expected_type)]

        else:
            raise ValueError('Unsupported node {}'.format(node))

    def _triple_to_formulas(self, subject: AbstractNode, predicate: AbstractNode, object: AbstractNode,
                            output_variable: VariableFormula) -> typing.List[Formula]:
        subject_variable = self._create_variable('subject')
        object_variable = self._create_variable('object')
        subject_functions = self.node_to_terms(subject)  # the only possible domain is owl:Thing

        possibles = []
        relations = []
        for predicate_resource in self._unpack_list(predicate):
            if predicate_resource == StringResource('instance of') and self._language_code == 'en':
                relations.extend(self._knowledge_base.type_relations())
            elif predicate_resource in [StringResource('name'), StringResource('identity'),
                                        StringResource('definition')] and self._language_code == 'en':
                possibles.extend(subject_function(output_variable) for subject_function in subject_functions)
            elif isinstance(predicate_resource, Resource):
                relations.extend(
                    self._knowledge_base.relations_from_label(predicate_resource.value, self._language_code))
            else:
                raise ValueError('Unexpected predicate {}'.format(predicate_resource))

        if not relations:
            return possibles

        # general case
        if isinstance(object, Missing):  # no need of classification by range
            possibles.extend(
                ExistsFormula(subject_variable, relation(subject_variable)(output_variable) &
                              subject_function(subject_variable))
                for relation in relations for subject_function in subject_functions)
        elif isinstance(subject, Missing):
            relations_by_range = defaultdict(list)
            for relation in relations:
                relations_by_range[relation.body.argument_type].append(relation)

            for range, relations in relations_by_range.items():
                possibles.extend(
                    ExistsFormula(object_variable, relation(output_variable)(object_variable) &
                                  object_function(object_variable))
                    for relation in relations for object_function in self.node_to_terms(object, range))

        else:
            raise ValueError('Full triple are not supported ({}, {}, {})'.format(subject, predicate, object))

        return possibles

    def _create_variable(self, prefix: str = 'var') -> VariableFormula:
        self._variable_counter += 1
        return VariableFormula('{}{}'.format(prefix, self._variable_counter))

    @staticmethod
    def _unpack_list(node):
        if isinstance(node, List):
            return node.list
        else:
            return [node]


class ToPPPDataModelConverter:
    def term_to_node(self, term: Term) -> AbstractNode:
        if isinstance(term, Function):
            return simplify(self._term_to_node(term.body, term.argument))
        else:
            raise ValueError('Could not convert this formula: {}'.format(term))

    def _term_to_node(self, term: Term, main_variable: VariableFormula,
                      context_term: Term = true_formula) -> AbstractNode:
        if term == true_formula:
            return Missing()
        elif isinstance(term, AndFormula):
            params_with_main_variable = []
            params_with_other_variables = []
            for arg in term.args:
                if self._contains_variable(arg, main_variable):
                    params_with_main_variable.append(arg)
                else:
                    params_with_other_variables.append(arg)
            return Intersection(sorted([
                                           self._term_to_node(arg, main_variable,
                                                              AndFormula(params_with_other_variables))
                                           for arg in params_with_main_variable], key=str))
        elif isinstance(term, OrFormula):
            return Union(
                sorted([self._term_to_node(child, main_variable, context_term) for child in term.args], key=str))
        elif isinstance(term, EqualityFormula):
            if term.left == main_variable and isinstance(term.right, ValueFormula):
                return self._term_to_resource(term.right.term)
            elif term.right == main_variable and isinstance(term.left, ValueFormula):
                return self._term_to_resource(term.left.term)
            else:
                raise ValueError('Could not convert this term: {}'.format(term))
        elif isinstance(term, TripleFormula):
            if not isinstance(term.predicate, ValueFormula):
                raise ValueError('Could not convert this term: {}'.format(term))
            if term.subject == main_variable:
                if isinstance(term.object, VariableFormula):
                    return Triple(Missing(), self._term_to_resource(term.predicate.term),
                                  self._term_to_node(context_term, term.object))
                elif isinstance(term.object, ValueFormula):
                    return Triple(Missing(), self._term_to_resource(term.predicate.term),
                                  self._term_to_resource(term.object.term))
                else:
                    raise ValueError('Invalid triple {}'.format(term))
            elif term.object == main_variable:
                if isinstance(term.subject, VariableFormula):
                    return Triple(self._term_to_node(context_term, term.subject),
                                  self._term_to_resource(term.predicate.term), Missing())
                elif isinstance(term.subject, ValueFormula):
                    return Triple(self._term_to_resource(term.subject.term),
                                  self._term_to_resource(term.predicate.term),
                                  Missing())
                else:
                    raise ValueError('Invalid triple {}'.format(term))
        elif isinstance(term, ExistsFormula):
            return self._term_to_node(term.body, main_variable, context_term)
        else:
            raise ValueError('Could not convert this term: {}'.format(term))

    def _term_to_resource(self, term: typing.Union[Entity, Literal]) -> Resource:
        return PlatypusResource(value=str(term), graph=term.to_jsonld())

    def _contains_variable(self, term: Term, variable: VariableFormula) -> bool:
        if isinstance(term, EqualityFormula):
            return term.left == variable or term.right == variable
        elif isinstance(term, TripleFormula):
            return term.subject == variable or term.predicate == variable or term.object == variable
        elif isinstance(term, OrFormula):
            return any(self._contains_variable(arg, variable) for arg in term.args)
        elif isinstance(term, AndFormula):
            return any(self._contains_variable(arg, variable) for arg in term.args)
        elif isinstance(term, ExistsFormula):
            return term.argument != variable and self._contains_variable(term.body, variable)
        else:
            raise ValueError('Unsupported term in ToPPPDataModelConverter._contains_variable: {}'.format(term))
