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
import re
from collections import defaultdict
from itertools import chain, product
from typing import List, Iterable, Set

from nltk.corpus import wordnet

from platypus_qa.analyzer.case_words import get_case_word_from_str
from platypus_qa.analyzer.literal_parser import parse_literal
from platypus_qa.analyzer.question_words import get_question_word_from_str, OpenQuestionWord, QuestionWord
from platypus_qa.database.formula import VariableFormula, Select, AndFormula, EqualityFormula, ValueFormula, \
    ExistsFormula, Term, Type
from platypus_qa.database.model import KnowledgeBase
from platypus_qa.database.owl import Class, owl_Thing, rdfs_Literal
from platypus_qa.nlp.model import Sentence, NLPParser, Token, SimpleToken
from platypus_qa.nlp.universal_dependencies import UDDependency, UDPOSTag

_logger = logging.getLogger('grammatical_analyzer')

_wordnet_language_codes = {
    'en': 'eng',
    'ar': 'arb',
    'bg': 'bul',
    'ca': 'cat',
    'da': 'dan',
    'el': 'ell',
    'eu': 'eus',
    'fa': 'fas',
    'fi': 'fin',
    'fr': 'fra',
    'gl': 'glg',
    'he': 'heb',
    'hr': 'hrv',
    'id': 'ind',
    'it': 'ita',
    'ja': 'jpn',
    'nn': 'nno',
    'nb': 'nob',
    'pl': 'pol',
    'pt': 'por',
    'sl': 'slv',
    'es': 'spa',
    'sv': 'swe'
}

_wordnet_pos_tags = {
    UDPOSTag.VERB: wordnet.VERB,
    UDPOSTag.NOUN: wordnet.NOUN,
    UDPOSTag.ADJ: wordnet.ADJ,
    UDPOSTag.ADV: wordnet.ADV
}

_wordnet_hardcoded = {
    'fr': [
        (re.compile('^née?s?$'), 'naissance'),
        (re.compile('^morte?s?$'), 'décès'),
        (re.compile('^décédée?s?$'), 'décès')
    ]
}

_ignored_dependencies = [
    UDDependency.aux,
    UDDependency.compound,
    UDDependency.case,
    UDDependency.conj,
    UDDependency.cop,
    UDDependency.det,
    UDDependency.discourse,
    UDDependency.flat,
    UDDependency.fixed,
    UDDependency.parataxis,
    UDDependency.punct,
    UDDependency.reparandum,
]

_dependencies_trimmed_for_label = [
    UDDependency.aux,
    UDDependency.case,
    UDDependency.cop,
    UDDependency.det,
    UDDependency.discourse,
    UDDependency.parataxis,
    UDDependency.punct,
    UDDependency.reparandum,
]

_pos_trimmed_for_label = [UDPOSTag.ADP, UDPOSTag.AUX, UDPOSTag.CCONJ, UDPOSTag.DET, UDPOSTag.INTJ, UDPOSTag.PUNCT,
                          UDPOSTag.SCONJ]

_meaningless_roots = {
    # moi, nous : hack because bad CoreNLP parsing
    'en': ['list', 'is', 'are', 'was', 'were', 'who', 'what', 'give', 'me', 'us'],
    'es': ['dame', 'danos', 'daños', 'lista', 'está', 'esta', 'es', 'eres', 'eras', 'son', 'quien', 'qué', 'dar', 'me',
           'mí'],
    'fr': ['liste', 'donne', 'retourne', 'dit', 'explique', 'moi', 'nous', 'a', 'ont', 'avait', 'avaient', '-ce',
           'qu\'', 'qui', 'quel', 'quels', 'quelle', 'quelles', 'est', 'sont'],
}


class GrammaticalAnalyzer:
    def __init__(self, parser: NLPParser, knowledge_base: KnowledgeBase, language_code: str):
        self._parser = parser
        self._knowledge_base = knowledge_base
        self._language_code = language_code
        self._variable_counter = 0

    def analyze(self, text: str) -> List[Term]:
        sentences = self._parser.parse(text, self._language_code)
        if len(sentences) != 1:
            _logger.warning('GrammaticalAnalyzer only supports single sentences: '.format(sentences))
            return []
        for sentence in self._parser.parse(text, self._language_code):
            return self._analyze(sentence)
        return []

    def _analyze(self, sentence: Sentence) -> List[Term]:
        results = self._analyze_tree(sentence.root)
        _logger.info(
            'Analysis of sentence "{}" lead to terms: {}'.format(sentence, [str(result) for result in results]))
        return [result for result in results if result]

    def _analyze_tree(self, node: Token, expected_type: Type = Type.from_entity(owl_Thing)) -> Set[Select]:
        _logger.info('main {}'.format(node.word))
        possibles = set()

        if expected_type & Type.from_entity(owl_Thing) != Type.bottom():
            possibles |= self._analyze_thing_tree(node)
        if expected_type & Type.from_entity(rdfs_Literal) != Type.bottom():
            possibles |= self._literals_for_node(self._trim(list(node.subtree)), expected_type)

        return possibles

    def _analyze_thing_tree(self, node: Token) -> Set[Select]:
        possibles = set()

        # simple entity
        possibles |= set(self._individuals_for_nodes(list(node.subtree)))

        # question words
        # We try the root if it is the leftest node
        if not node.left_children:
            question_word = get_question_word_from_str(node.word, self._language_code)
            if question_word is not None:  # The root is a question word
                children_to_parse = self._filter_not_main_dependencies(node.children)
                if len(children_to_parse) != 1:
                    return set()  # TODO: what should we do?
                return set(chain.from_iterable(
                    self._add_data_from_question(node, question_word)
                    for node in self._analyze_tree(children_to_parse[0])))

        # We try other nodes
        question_word = None
        left_children_to_parse = node.left_children
        question_nodes = []
        for child in node.left_children:
            question_nodes.extend(child.subtree)
            question_nodes_trimmed = self._trim(question_nodes)
            if not question_nodes_trimmed:
                question_nodes_trimmed = question_nodes
            new_question_word = get_question_word_from_str(self._nodes_to_string(question_nodes_trimmed),
                                                           self._language_code)
            if new_question_word is not None:
                question_word = new_question_word
                left_children_to_parse = self._nodes_after(left_children_to_parse, child)

        children_to_parse = self._filter_not_main_dependencies(left_children_to_parse + node.right_children)
        _logger.info('question word {}'.format(question_word))
        _logger.info('main children {}'.format(' '.join(str([str(node) for node in children_to_parse]))))

        # meaningless words
        # ...at the beggining of sentence
        skip_number = 0
        for child in left_children_to_parse:
            if self._nodes_to_string(child.subtree).lower() in _meaningless_roots.get(self._language_code, ()):
                skip_number += 1
            else:
                break
        left_children_to_parse = left_children_to_parse[skip_number:]

        # ...at the root
        if (self._language_code in _meaningless_roots or question_word and not left_children_to_parse) and \
                        node.word.lower() in _meaningless_roots[self._language_code] and \
                        len(children_to_parse) == 1:
            return set(chain.from_iterable(
                self._add_data_from_question(node, question_word) for node in self._analyze_tree(children_to_parse[0])))

        # It is just en entity
        individuals = self._individuals_for_nodes(self._trim(list(chain(
            chain.from_iterable(child.subtree for child in left_children_to_parse),
            [node],
            chain.from_iterable(child.subtree for child in node.right_children)
        ))))
        for individual in individuals:
            possibles |= self._add_data_from_question(individual, question_word)
            # TODO: return here?

        # parse tree
        for left_child in left_children_to_parse + [None]:
            # We consider as predicate [left_child ... token ... right_child]
            for right_child in self._filter_not_main_dependencies(node.right_children) + [None]:

                # find properties
                label_nodes = self._extract_label_nodes_from_node(node, left_child, right_child)
                nounified_patterns = None
                expected_type = Type.top()
                if isinstance(question_word, OpenQuestionWord) and question_word.property_modifiers:
                    nounified_patterns = question_word.property_modifiers
                    expected_type = question_word.expected_type

                # We iterate on children not used in the predicate
                # We compute first the list of children to process
                children_to_process = []
                for child in self._filter_not_main_dependencies(left_children_to_parse):
                    if child == left_child:
                        break
                    children_to_process.append(child)
                for child in reversed(self._filter_not_main_dependencies(node.right_children)):
                    if child == right_child:
                        break
                    children_to_process.append(child)

                for possible in self._build_tree_with_children(children_to_process, label_nodes, expected_type):
                    possibles |= self._add_data_from_question(possible, question_word)
                if nounified_patterns is not None:
                    possibles |= self._build_tree_with_children(children_to_process, label_nodes, expected_type,
                                                                nounified_patterns)

        return possibles

    def _build_tree_with_children(self, children_to_process: Iterable[Token], root_tokens: List[Token],
                                  expected_type: Type, nounifier_patterns=None) -> Set[Select]:
        output_variable = self._create_variable('result')
        # We iterate on children not used in the predicate
        # We compute first the list of children to process
        to_intersect_elements = []
        for child in children_to_process:
            _logger.info('child: ' + str(child))

            if child.main_ud_dependency <= UDDependency.nsubj or child.main_ud_dependency <= UDDependency.appos:
                # TODO: relevent for appos?
                main_relations = self._relations_for_nodes(root_tokens, nounifier_patterns, expected_type)
                to_intersect_elements.append([function(output_variable) for function in
                                              self._set_argument_to_relations(main_relations, child)])

            elif child.main_ud_dependency <= UDDependency.obj:
                main_relations = self._relations_for_nodes(root_tokens, nounifier_patterns, expected_type)
                to_intersect_elements.append([function(output_variable) for function in
                                              self._set_argument_to_relations(
                                                  (rel.swap_arguments() for rel in main_relations),
                                                  child)])

            elif child.main_ud_dependency <= UDDependency.nmod_poss:
                main_relations = self._relations_for_nodes(root_tokens, nounifier_patterns, expected_type)
                to_intersect_elements.append([function(output_variable)
                                              for function in self._set_argument_to_relations(main_relations, child)])

            elif child.main_ud_dependency <= UDDependency.nmod or child.main_ud_dependency <= UDDependency.obl:
                # We extract cases and remove them from the child
                cases = [grandchild.word for grandchild in child.children
                         if grandchild.main_ud_dependency == UDDependency.case]
                child = SimpleToken(child.word, child.lemma, child.ud_pos, child.main_ud_dependency,
                                    [grandchild for grandchild in child.left_children
                                     if grandchild.main_ud_dependency != UDDependency.case],
                                    [grandchild for grandchild in child.right_children
                                     if grandchild.main_ud_dependency != UDDependency.case])

                if len(cases) > 1:
                    _logger.info('Multiple cases {} in {}'.format(cases, child))
                    to_intersect_elements.append([])  # TODO: what should we do?
                elif len(cases) < 1:
                    _logger.info('No cases in {}'.format(child))
                    # We assume an "of" TODO: is it smart?
                    main_relations = self._relations_for_nodes(root_tokens, nounifier_patterns, expected_type)
                    to_intersect_elements.append([function(output_variable) for function in
                                                  self._set_argument_to_relations(main_relations, child)])
                else:
                    case = get_case_word_from_str(cases[0], self._language_code)
                    if case is None:
                        _logger.info('Case {} in {} is not supported'.format(cases[0], self._language_code))
                        to_intersect_elements.append([])  # TODO: what should we do?
                    else:
                        results = []
                        for modifiers, term in case.terms_by_modifiers.items():
                            if nounifier_patterns is not None:
                                modifiers = [nounified_pattern.format(modifier)
                                             for nounified_pattern in nounifier_patterns for modifier in modifiers]
                            main_relations = self._relations_for_nodes(root_tokens, modifiers)
                            # TODO: expected range (deal with modifiers)
                            relations = [term(relation) for relation in main_relations]
                            results.extend(function(output_variable) for function in
                                           self._set_argument_to_relations(relations, child))
                        for property in case.properties:
                            main_relations = [r.swap_arguments() for r in
                                              self._find_relations_with_pattern(property, range=expected_type)]
                            results.extend(function(output_variable)
                                           for function in self._set_argument_to_relations(main_relations, child))
                        to_intersect_elements.append(results)

            elif child.main_ud_dependency <= UDDependency.amod:
                if nounifier_patterns is not None:
                    # We do not support nounifiers here
                    to_intersect_elements.append([])
                else:
                    types = self._analyze_tree(child)
                    type_variable = self._create_variable('type')
                    to_intersect_elements.append(
                        [ExistsFormula(type_variable, relation(output_variable)(type_variable) & \
                                       type_function(type_variable))
                         for type_function in types
                         for relation in self._knowledge_base.type_relations()])

            else:
                _logger.warning('Unsupported dependency {} in {}'.format(
                    child.main_ud_dependency, [str(s) for s in children_to_process]
                ))
                return set()

        return {Select(output_variable, AndFormula(to_intersect))
                for to_intersect in product(*to_intersect_elements) if to_intersect}

    def _set_argument_to_relations(self, relations: Iterable[Select], argument: Token):
        relations_by_domain = defaultdict(list)
        for relation in relations:
            relations_by_domain[relation.type[0]].append(relation)

        results = set()
        variable = self._create_variable('arg')
        result = self._create_variable('result')
        for domain, relations in relations_by_domain.items():
            results |= {Select(result, ExistsFormula(variable, relation(variable)(result) & arg_relation(variable)))
                        for relation in relations for arg_relation in self._analyze_tree(argument, domain)}
        return results

    def _add_data_from_question(self, term: Select, question_word: QuestionWord) -> Set[Select]:
        if not isinstance(question_word, OpenQuestionWord):
            return {term}
        if not question_word.expected_properties or term.type <= Type.from_entity(rdfs_Literal):
            if term.type & question_word.expected_type == Type.bottom():
                return set()  # Typing does not works
            else:
                return {term}  # the return type is already a literal of the right type or we have no expected property

        _logger.info('question word properties {}'.format(question_word.expected_properties))
        relations = list(chain.from_iterable(
            self._find_relations_with_pattern(label)
            for label in question_word.expected_properties
        ))
        result_variable = self._create_variable('result')
        intermediate_variable = self._create_variable('temp')
        return {Select(result_variable, ExistsFormula(intermediate_variable,
                                                      relation(intermediate_variable)(result_variable) &
                                                      term(intermediate_variable)))
                for relation in relations}

    def _individuals_for_nodes(self, nodes, type_filter: Class = owl_Thing) -> List[Select]:
        individuals = self._knowledge_base.individuals_from_label(
            self._nodes_to_string(nodes), self._language_code, type_filter)
        _logger.info(
            'individual: {} with result {}'.format(self._nodes_to_string(nodes), [str(i) for i in individuals]))
        return individuals

    def _relations_for_nodes(self, nodes, nounified_patterns=None, range: Type = Type.top()) -> List[Select]:
        label = self._nodes_to_string(nodes)
        relations = self._find_relations_with_pattern(label, nounified_patterns, range)
        if not relations and len(nodes) == 1:
            # lemmatization
            if self._language_code in _wordnet_hardcoded:
                for (pattern, noun) in _wordnet_hardcoded[self._language_code]:
                    if pattern.match(label):
                        relations = self._find_relations_with_pattern(noun, nounified_patterns, range)

        """TODO: enable again?
        if self._language_code in _wordnet_language_codes and nodes[0].ud_pos in _wordnet_pos_tags:
            try:
                synsets = wordnet.synsets(nodes[0].word, pos=_wordnet_pos_tags[nodes[0].ud_pos],
                                          lang=_wordnet_language_codes[self._language_code])
                nouns = self._nouns_for_synsets(synsets, self._language_code)
                entities = list(chain.from_iterable(
                    self._find_entities_with_pattern(noun, entity_lookup, nounified_patterns, self._language_code)
                    for noun in nouns))
                if not entities and '{}' in nounified_patterns:
                    # try in english
                    entities = list(chain.from_iterable(
                        entity_lookup(noun, 'en') for noun in self._nouns_for_synsets(synsets, 'en')))
            except Exception as e:
                logging.getLogger('wornet').warn(e, exc_info=True)
        """
        return list(set(relations))

    def _find_relations_with_pattern(self, label, nounified_patterns=None, range: Type = Type.top()) -> List[Select]:
        if nounified_patterns is None:
            nounified_patterns = ('{}',)
        # TODO apply range
        relations = self._knowledge_base.relations_from_labels(
            (nounified_pattern.format(label) for nounified_pattern in nounified_patterns), self._language_code)
        _logger.info(
            'relation "{}" with nounifiers {} and range {} give a result result {} '.format(
                label, nounified_patterns, range, [str(p) for p in relations]))
        return relations

    def _literals_for_node(self, nodes, expected_type: Type):
        input_str = self._nodes_to_string(nodes)
        literals = parse_literal(input_str, self._language_code, expected_type)
        _logger.info('literals: {} with result {} for type {}'.format(
            self._nodes_to_string(nodes), [str(i) for i in literals], expected_type))

        variable = self._create_variable('value')
        return {Select(variable, EqualityFormula(variable, ValueFormula(literal, input_str))) for literal in literals}

    @staticmethod
    def _nouns_for_synsets(synsets, language_code: str):
        lemmas = list(
            chain.from_iterable(synset.lemmas(_wordnet_language_codes[language_code]) for synset in synsets))
        derivationally_related_forms = list(
            chain(chain.from_iterable(x.derivationally_related_forms() for x in lemmas), lemmas))
        related_synsets = [lemma.synset() for lemma in derivationally_related_forms]
        return list(chain.from_iterable(
            synset.lemma_names(_wordnet_language_codes[language_code]) for synset in related_synsets if
            synset.pos() == wordnet.NOUN)
        )

    @staticmethod
    def _filter_not_main_dependencies(nodes):
        """
        Filters dependencies that are not main component of the dependency tree (determiners, auxiliaries...)
        """
        return [node for node in nodes if node.main_ud_dependency.root_dep not in _ignored_dependencies]

    def _extract_label_nodes_from_node(self, main_node: Token, should_start_at_least: Token = None,
                                       should_end_at_least: Token = None) -> List[Token]:
        start_node = None
        end_node = None
        for child in main_node.left_children:
            if self._is_same_entity_dependency(child.main_ud_dependency) and \
                            child.word.lower() not in _meaningless_roots.get(self._language_code,
                                                                             ()):  # TODO: other dependencies?
                start_node = child
                break
            elif child == should_start_at_least:
                start_node = child
                break
        for child in reversed(main_node.right_children):
            if self._is_same_entity_dependency(child.main_ud_dependency):  # TODO: other dependencies?
                end_node = child
                break
            elif child == should_end_at_least:
                end_node = child
                break

        entity_nodes = []
        if start_node is not None:
            for child in self._nodes_after(main_node.left_children, start_node, True):
                entity_nodes.extend(child.subtree)
        entity_nodes.append(main_node)
        if end_node is not None:
            for child in self._nodes_before(main_node.right_children, end_node, True):
                entity_nodes.extend(child.subtree)
        return self._trim(entity_nodes)

    @staticmethod
    def _trim_left(subtree):
        start = 0
        while start < len(subtree):
            if subtree[start].ud_pos in _pos_trimmed_for_label or (subtree[start].main_ud_dependency is not None and
                                                                           subtree[
                                                                               start].main_ud_dependency.root_dep in _dependencies_trimmed_for_label):
                start += 1
            else:
                break
        return subtree[start:]

    @staticmethod
    def _trim_right(subtree):
        end = len(subtree) - 1
        while end >= 0:
            if subtree[end].ud_pos in _pos_trimmed_for_label or (subtree[end].main_ud_dependency is not None and
                                                                         subtree[
                                                                             end].main_ud_dependency.root_dep in _dependencies_trimmed_for_label):
                end -= 1
            else:
                break
        return subtree[:end + 1]

    def _trim(self, subtree):
        return self._trim_right(self._trim_left(subtree))

    @staticmethod
    def _nodes_before(nodes, node, include: bool = False):
        """
        Returns the nodes in nodes before node (node is included if, and only if, include = True)
        """
        result = []
        for current in nodes:
            if current == node:
                if include:
                    result.append(current)
                break
            else:
                result.append(current)
        return result

    @staticmethod
    def _nodes_after(nodes, node, include: bool = False):
        """
        Returns the nodes in nodes after node (node is included if, and only if, include = True)
        """
        return list(reversed(GrammaticalAnalyzer._nodes_before(reversed(nodes), node, include)))

    @staticmethod
    def _is_same_entity_dependency(dependency_tag: UDDependency) -> bool:
        return dependency_tag <= UDDependency.compound or \
               dependency_tag <= UDDependency.flat or \
               dependency_tag <= UDDependency.fixed

    @staticmethod
    def _nodes_to_string(nodes):
        return ' '.join([node.word for node in nodes]) \
            .replace(' -', '-').replace('\' ', '\'').replace(' ,', ',').replace(' .', '.')
        # TODO: implement it nicely in NLP classes.

    def _create_variable(self, prefix: str = 'var') -> VariableFormula:
        self._variable_counter += 1
        return VariableFormula('{}{}'.format(prefix, self._variable_counter))
