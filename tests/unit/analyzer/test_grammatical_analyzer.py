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

from platypus_qa.analyzer.grammatical_analyzer import GrammaticalAnalyzer
from platypus_qa.nlp.core_nlp import CoreNLPParser
from platypus_qa.nlp.model import SimpleToken
from platypus_qa.nlp.universal_dependencies import UDDependency, UDPOSTag
from tests.simple_knowledge_model import SimpleKnowledgeBase


class _GrammaticalAnalyzerTest(unittest.TestCase):
    _analyzer = GrammaticalAnalyzer(CoreNLPParser(['http://163.172.54.30:9000']), SimpleKnowledgeBase({}, {}, []), 'fr')

    def test_node_eq(self):
        foo_adj = SimpleToken('foo', 'foo', UDPOSTag.ADJ, UDDependency.amod, [], [])
        foo_adj2 = SimpleToken('foo', 'foo', UDPOSTag.ADJ, UDDependency.amod, [], [])
        foo_verb = SimpleToken('foo', 'foo', UDPOSTag.VERB, UDDependency.amod, [], [])
        foo_dep = SimpleToken('foo', 'foo', UDPOSTag.ADJ, UDDependency.amod, [foo_adj], [foo_verb]),
        foo_dep2 = SimpleToken('foo', 'foo', UDPOSTag.ADJ, UDDependency.amod, [foo_verb], [foo_verb]),

        self.assertEquals(foo_adj, foo_adj2)
        self.assertNotEquals(foo_adj, foo_verb)
        self.assertEquals(foo_dep, foo_dep)
        self.assertNotEqual(foo_dep, foo_dep2)
        self.assertNotEqual(foo_dep, foo_adj)

    def test_nodes_before(self):
        foo = SimpleToken('foo', 'foo', UDPOSTag.ADJ, UDDependency.amod, [], [])
        bar = SimpleToken('bar', 'bar', UDPOSTag.ADJ, UDDependency.amod, [], [])
        baz = SimpleToken('baz', 'baz', UDPOSTag.ADJ, UDDependency.amod, [], [])

        self.assertListEqual([foo, bar], self._analyzer._nodes_before([foo, bar, baz], bar, include=True))
        self.assertListEqual([foo], self._analyzer._nodes_before([foo, bar, baz], bar, include=False))

    def test_nodes_after(self):
        foo = SimpleToken('foo', 'foo', UDPOSTag.ADJ, UDDependency.amod, [], [])
        bar = SimpleToken('bar', 'bar', UDPOSTag.ADJ, UDDependency.amod, [], [])
        baz = SimpleToken('baz', 'baz', UDPOSTag.ADJ, UDDependency.amod, [], [])

        self.assertListEqual([bar, baz], self._analyzer._nodes_after([foo, bar, baz], bar, include=True))
        self.assertListEqual([baz], self._analyzer._nodes_after([foo, bar, baz], bar, include=False))
