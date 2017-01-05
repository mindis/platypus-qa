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

import unittest

from platypus_qa.nlp.conllu import CoNLLUParser
from platypus_qa.nlp.tree_matcher import TokenMatcher, TreeMatchingResult
from platypus_qa.nlp.universal_dependencies import UDPOSTag, UDDependency


class _TestTreeTest(unittest.TestCase):
    _conllu_parser = CoNLLUParser()
    _tree1 = _conllu_parser.parse(
        '1	Tom	Tom	NOUN	NN	Number=Sing|fPOS=PROPN++NNP	2	nsubj	_	_\n'
        '2	eats	eat	VERB	VBZ	Mood=Ind|Number=Sing|Person=3|Tense=Pres|VerbForm=Fin|fPOS=VERB++VBZ	0	ROOT	_	_\n'
        '3	an	a	DET	DT	Definite=Ind|PronType=Art|fPOS=DET++DT	4	det	_	_\n'
        '4	apple	apple	NOUN	NN	Number=Sing|fPOS=NOUN++NN	2	dobj	_	_\n'
        '5	.	.	PUNCT	.	fPOS=PUNCT++.	2	punct	_	_', 'en')[0].root

    def test_matcher(self):
        _tree1_matched = TreeMatchingResult(self._tree1, {})
        self.assertSetEqual(TokenMatcher().match(self._tree1), {_tree1_matched})
        self.assertSetEqual(TokenMatcher(word='eats').match(self._tree1), {_tree1_matched})
        self.assertSetEqual(TokenMatcher(lemma='eat').match(self._tree1), {_tree1_matched})
        self.assertSetEqual(TokenMatcher(ud_pos=UDPOSTag.VERB).match(self._tree1), {_tree1_matched})
        self.assertSetEqual(TokenMatcher(word='eats', lemma='eat', ud_pos=UDPOSTag.VERB).match(self._tree1),
                            {_tree1_matched})
        self.assertSetEqual(TokenMatcher(word='eaten').match(self._tree1), set())
        self.assertSetEqual(TokenMatcher(lemma='eats').match(self._tree1), set())
        self.assertSetEqual(TokenMatcher(ud_pos=UDPOSTag.NOUN).match(self._tree1), set())

        self.assertSetEqual((TokenMatcher(word='eats') & TokenMatcher(lemma='eat')).match(self._tree1),
                            {_tree1_matched})
        self.assertSetEqual((TokenMatcher(word='eats') & TokenMatcher(lemma='eats')).match(self._tree1), set())

        self.assertSetEqual((TokenMatcher(word='eats') | TokenMatcher(lemma='eat')).match(self._tree1),
                            {_tree1_matched})
        self.assertSetEqual((TokenMatcher(word='eats') | TokenMatcher(lemma='eats')).match(self._tree1),
                            {_tree1_matched})
        self.assertSetEqual((TokenMatcher(word='eat') | TokenMatcher(lemma='eats')).match(self._tree1), set())

        self.assertSetEqual((TokenMatcher(word='eats') > TokenMatcher(word='Tom')).match(self._tree1), {_tree1_matched})
        self.assertSetEqual((TokenMatcher(word='eats') > TokenMatcher(word='apple')).match(self._tree1),
                            {_tree1_matched})
        self.assertSetEqual((TokenMatcher(word='eats') > TokenMatcher(word='eats')).match(self._tree1), set())

        self.assertSetEqual((TokenMatcher(word='eats') > TokenMatcher(word='Tom')).match(self._tree1), {_tree1_matched})
        self.assertSetEqual((TokenMatcher(word='eats') > TokenMatcher(word='apple')).match(self._tree1),
                            {_tree1_matched})
        self.assertSetEqual((TokenMatcher(word='eats') > TokenMatcher(word='eats')).match(self._tree1), set())
        self.assertSetEqual((TokenMatcher(word='eats') > TokenMatcher(ud_dep=UDDependency.nsubj)).match(self._tree1),
                            {_tree1_matched})

        self.assertSetEqual((TokenMatcher(word='eats') + TokenMatcher(word='an')).match(self._tree1), {_tree1_matched})
        self.assertSetEqual((TokenMatcher(word='Tom') + TokenMatcher(word='eats')).match(self._tree1), {_tree1_matched})
        self.assertSetEqual((TokenMatcher(word='eats') + TokenMatcher(word='apple')).match(self._tree1), set())
        self.assertSetEqual(
            (TokenMatcher(word='eats') > (TokenMatcher(word='an') + TokenMatcher(word='apple'))).match(self._tree1),
            {_tree1_matched})
