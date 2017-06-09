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

import itertools
import logging
import re
from collections import defaultdict
from typing import List, Optional, Iterable, Set

from nltk.corpus import wordnet

from platypus_qa.analyzer.case_words import get_case_word_from_str
from platypus_qa.analyzer.literal_parser import parse_literal
from platypus_qa.analyzer.question_words import get_question_word_from_str, OpenQuestionWord, QuestionWord
from platypus_qa.database.formula import VariableFormula, Function, AndFormula, EqualityFormula, ValueFormula, \
    ExistsFormula, Term, Formula, Type, swap_function_arguments
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
        for sentence in self._parser.parse(text, self._language_code):
            return self._analyze(sentence)  # TODO: multiple sentences?
        return []

    def _analyze(self, sentence: Sentence) -> List[Term]:
        results = set()
        for tree in self._sentence_to_trees(sentence):
            _logger.info('tree {}'.format(tree))
            results |= self._analyze_tree(tree)
        _logger.info(
            'Analysis of sentence "{}" lead to terms: {}'.format(sentence, [str(result) for result in results]))
        return [result for result in results if result]

    def _sentence_to_trees(self, sentence: Sentence):
        return self._token_with_dependency_to_trees(sentence.root, None)

    def _token_with_dependency_to_trees(self, token: Token, ud_dependency: Optional[UDDependency]) -> List[Token]:
        """
        Creates trees from NLP toolkits output. We could create more than 1 tree because when we have sentences like
        "a of x of y" we want to try both "a (of x (of y))" and "a (of x) (of y)"
        The most likely trees (e.g. the one returned by NLP tool) are returned first
        """
        left_right_children_possibilities = list(itertools.product(
            self._list_product(
                self._token_with_dependency_to_trees(child, child.main_ud_dependency) for child in token.left_children),
            itertools.chain.from_iterable(self._move_up_nmod_dependencies(children) for children in self._list_product(
                self._token_with_dependency_to_trees(child, child.main_ud_dependency) for child in token.right_children)
                                          )
        ))
        return [SimpleToken(token.word, token.lemma, token.ud_pos, ud_dependency, left_right_children[0],
                            left_right_children[1])
                for left_right_children in left_right_children_possibilities]

    def _move_up_nmod_dependencies(self, nodes) -> List[List[Token]]:
        """
        Moves up rightmost nmod dependencies in order to have all possible interpretation
        (and so resolve ambiguities using the domain knowledge)
        """
        for node in nodes:
            if node.main_ud_dependency <= UDDependency.nmod:
                for child in reversed(node.right_children):  # TODO: what about left children
                    if child.main_ud_dependency <= UDDependency.nmod:
                        # we create new possibilities with this child up and we run again the function on it
                        return [nodes] + self._move_up_nmod_dependencies(
                            self._nodes_before(nodes, node, False) +
                            [SimpleToken(node.word, node.lemma, node.ud_pos, node.main_ud_dependency,
                                         node.left_children,
                                         self._nodes_before(node.right_children, child, False)), child] +
                            self._nodes_after(nodes, node, False)
                        )
                else:
                    break  # we do not want to consider element that are between two dependencies
        return [nodes]

    @staticmethod
    def _list_product(lists: Iterable[list]) -> List[list]:
        results = [[]]
        for list in lists:
            old_results = results
            results = []
            for element in list:
                results.extend([old_list + [element] for old_list in old_results])
        return results

    def _analyze_tree(self, node: Token, expected_type: Type = Type.from_entity(owl_Thing)) -> Set[Function]:
        _logger.info('main {}'.format(node.word))
        possibles = set()

        if expected_type & Type.from_entity(owl_Thing) != Type.bottom():
            possibles |= self._analyze_thing_tree(node)
        if expected_type & Type.from_entity(rdfs_Literal) != Type.bottom():
            possibles |= self._literals_for_node(self._trim(list(node.subtree)), expected_type)

        return possibles

    def _analyze_thing_tree(self, node: Token) -> Set[Function]:
        possibles = set()

        # simple entity
        possibles |= set(self._individuals_for_nodes(list(node.subtree)))

        # question words
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
        if not left_children_to_parse:
            new_question_word = get_question_word_from_str(node.word, self._language_code)
            if new_question_word is not None:
                question_word = new_question_word

        children_to_parse = self._filter_not_main_dependencies(left_children_to_parse + node.right_children)
        _logger.info('question word {}'.format(question_word))
        _logger.info('main children {}'.format(' '.join(str([str(node) for node in children_to_parse]))))

        # meaningless words
        if (self._language_code in _meaningless_roots or question_word and not left_children_to_parse) and \
                        node.word.lower() in _meaningless_roots[self._language_code] and \
                        len(children_to_parse) == 1:
            return set(itertools.chain.from_iterable(
                self._add_data_from_question(node, question_word) for node in self._analyze_tree(children_to_parse[0])))

        # It is just en entity
        individuals = self._individuals_for_nodes(self._trim(list(itertools.chain(
            itertools.chain.from_iterable(child.subtree for child in left_children_to_parse),
            [node],
            itertools.chain.from_iterable(child.subtree for child in node.right_children)
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
                if isinstance(question_word, OpenQuestionWord) and question_word.property_modifiers:
                    nounified_patterns = question_word.property_modifiers
                relations = self._relations_for_nodes(label_nodes)

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

                if relations:
                    for possible in self._build_tree_with_children(children_to_process, label_nodes):
                        possibles |= self._add_data_from_question(possible, question_word)
                if nounified_patterns is not None:
                    possibles |= self._build_tree_with_children(children_to_process, label_nodes, nounified_patterns)

        return possibles

    def _build_tree_with_children(self, children_to_process: Iterable[Token], root_tokens: List[Token],
                                  nounifier_patterns=None) -> Set[Function]:
        output_variable = self._create_variable('result')
        # We iterate on children not used in the predicate
        # We compute first the list of children to process
        to_intersect_elements = []
        for child in children_to_process:
            _logger.info('child: ' + str(child))

            if child.main_ud_dependency <= UDDependency.nsubj or child.main_ud_dependency <= UDDependency.appos:
                # TODO: relevent for appos?
                main_relations = self._relations_for_nodes(root_tokens, nounified_patterns=nounifier_patterns)
                to_intersect_elements.append([function(output_variable) for function in
                                              self._set_argument_to_relations(main_relations, child)])

            elif child.main_ud_dependency <= UDDependency.obj:
                main_relations = self._relations_for_nodes(root_tokens, nounified_patterns=nounifier_patterns)
                to_intersect_elements.append([function(output_variable) for function in
                                              self._set_argument_to_relations(
                                                  (swap_function_arguments(rel) for rel in main_relations),
                                                  child)])

            elif child.main_ud_dependency <= UDDependency.nmod_poss:
                main_relations = self._relations_for_nodes(root_tokens, nounified_patterns=nounifier_patterns)
                to_intersect_elements.append([function(output_variable)
                                              for function in self._set_argument_to_relations(main_relations, child)])

            elif child.main_ud_dependency <= UDDependency.nmod:
                cases = [grandchild.word for grandchild in child.children if
                         grandchild.main_ud_dependency == UDDependency.case]
                if len(cases) > 1:
                    _logger.info('Multiple cases {} in {}'.format(cases, child))
                    to_intersect_elements.append([])  # TODO: what should we do?
                elif len(cases) < 1:
                    _logger.info('No cases in {}'.format(child))
                    # We assume an "of" TODO: is it smart?
                    main_relations = self._relations_for_nodes(root_tokens, nounified_patterns=nounifier_patterns)
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
                            main_relations = self._relations_for_nodes(root_tokens, nounified_patterns=modifiers)
                            relations = [term(relation) for relation in main_relations]
                            results.extend(function(output_variable) for function in
                                           self._set_argument_to_relations(relations, child))
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

        return {Function(output_variable, AndFormula(to_intersect))
                for to_intersect in itertools.product(*to_intersect_elements) if to_intersect}

    def _set_argument_to_relations(self, relations: Iterable[Function[Function[Formula]]], argument: Token):
        relations_by_range = defaultdict(list)
        for relation in relations:
            relations_by_range[relation.argument_type].append(relation)

        results = set()
        variable = self._create_variable('arg')
        result = self._create_variable('result')
        for range, relations in relations_by_range.items():
            results |= {Function(result, ExistsFormula(variable, relation(variable)(result) & arg_relation(variable)))
                        for relation in relations for arg_relation in self._analyze_tree(argument, range)}
        return results

    def _add_data_from_question(self, term: Function, question_word: QuestionWord) -> Set[Function]:
        if not isinstance(question_word, OpenQuestionWord) or not question_word.expected_properties or \
                        term.argument_type <= question_word.expected_type:
            return {term}  # we do not add this triple if the returned type is already the right one

        _logger.info('question word properties {}'.format(question_word.expected_properties))
        relations = list(itertools.chain.from_iterable(
            self._knowledge_base.relations_from_label(label, self._language_code)
            for label in question_word.expected_properties
        ))
        # we do not add this triple if the returned type is already the right one
        result_variable = self._create_variable('result')
        intermediate_variable = self._create_variable('temp')
        return {Function(result_variable, ExistsFormula(intermediate_variable,
                                                        relation(intermediate_variable)(result_variable) &
                                                        term(intermediate_variable)))
                for relation in relations}

    def _individuals_for_nodes(self, nodes, type_filter: Class = owl_Thing) -> List[Function[Formula]]:
        individuals = self.entities_for_nodes(nodes,
                                              lambda label, language_code: self._knowledge_base.individuals_from_label(
                                                  label, language_code, type_filter))
        _logger.info(
            'individual: {} with result {}'.format(self._nodes_to_string(nodes), [str(i) for i in individuals]))
        return individuals

    def _relations_for_nodes(self, nodes, nounified_patterns=None) -> List[Function]:
        properties = self.entities_for_nodes(nodes,
                                             lambda label, language_code: self._knowledge_base.relations_from_label(
                                                 label, language_code), nounified_patterns=nounified_patterns)
        _logger.info(
            'properties: {} and nounifiers {} with result {} '.format(self._nodes_to_string(nodes), nounified_patterns,
                                                                      [str(p) for p in properties]))
        return properties

    def entities_for_nodes(self, nodes, entity_lookup, nounified_patterns=None):
        entities = self._find_entities_with_pattern(self._nodes_to_string(nodes), entity_lookup, nounified_patterns,
                                                    self._language_code)
        if entities or len(nodes) != 1:
            return list(set(entities))

        # lemmatization
        if self._language_code in _wordnet_hardcoded:
            for (pattern, noun) in _wordnet_hardcoded[self._language_code]:
                if pattern.match(nodes[0].word):
                    return list(set(
                        self._find_entities_with_pattern(noun, entity_lookup, nounified_patterns, self._language_code)))

        """TODO: enable again?
        if self._language_code in _wordnet_language_codes and nodes[0].ud_pos in _wordnet_pos_tags:
            try:
                synsets = wordnet.synsets(nodes[0].word, pos=_wordnet_pos_tags[nodes[0].ud_pos],
                                          lang=_wordnet_language_codes[self._language_code])
                nouns = self._nouns_for_synsets(synsets, self._language_code)
                entities = list(itertools.chain.from_iterable(
                    self._find_entities_with_pattern(noun, entity_lookup, nounified_patterns, self._language_code)
                    for noun in nouns))
                if not entities and '{}' in nounified_patterns:
                    # try in english
                    entities = list(itertools.chain.from_iterable(
                        entity_lookup(noun, 'en') for noun in self._nouns_for_synsets(synsets, 'en')))
            except Exception as e:
                logging.getLogger('wornet').warn(e, exc_info=True)
        """

        return list(set(entities))

    def _literals_for_node(self, nodes, expected_type: Type):
        input_str = self._nodes_to_string(nodes)
        literals = parse_literal(input_str, self._language_code, expected_type)
        _logger.info('literals: {} with result {} for type {}'.format(
            self._nodes_to_string(nodes), [str(i) for i in literals], expected_type))

        variable = self._create_variable('value')
        return {Function(variable, EqualityFormula(variable, ValueFormula(literal, input_str))) for literal in literals}

    @staticmethod
    def _find_entities_with_pattern(label, entity_lookup, nounified_patterns, language_code):
        if nounified_patterns is None:
            nounified_patterns = ('{}',)
        return list(itertools.chain.from_iterable(entity_lookup(nounified_pattern.format(label), language_code) for
                                                  nounified_pattern in nounified_patterns))

    @staticmethod
    def _nouns_for_synsets(synsets, language_code: str):
        lemmas = list(
            itertools.chain.from_iterable(synset.lemmas(_wordnet_language_codes[language_code]) for synset in synsets))
        derivationally_related_forms = list(
            itertools.chain(itertools.chain.from_iterable(x.derivationally_related_forms() for x in lemmas), lemmas))
        related_synsets = [lemma.synset() for lemma in derivationally_related_forms]
        return list(itertools.chain.from_iterable(
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
            if self._is_same_entity_dependency(child.main_ud_dependency):  # TODO: other dependencies?
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
