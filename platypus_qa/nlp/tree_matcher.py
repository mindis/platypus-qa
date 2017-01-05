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

from _operator import or_, and_
from functools import reduce
from typing import Set, Callable, Dict

from platypus_qa.nlp.model import Token
from platypus_qa.nlp.universal_dependencies import UDPOSTag, UDDependency


class TreeMatchingResult:
    def __init__(self, root: Token, matched: Dict[str, Token]):
        self._root = root
        self._matched = matched

    @property
    def root(self) -> Token:
        return self._root

    def token(self, name: str) -> Token:
        return self._matched[name]

    def __eq__(self, other):
        return isinstance(other, TreeMatchingResult) and other._root == self._root and other._matched == self._matched

    def __hash__(self):
        return hash(self.root)


class TreeMatcher:
    """
    To match tokens TokenMatcher(word: 'eaten', lemma: 'eat', ud_pos: UDPOSTag.VERB)
    To do intersection use & operator, to do union |.
    For direct descendant use A > B to filter As that are the parent of Bs and A < B to filter As that are the children of Bs
    """

    def __and__(self, other: 'TreeMatcher') -> 'TreeMatcher':
        return _OperatorTreeMatcher(self, other, and_)

    def __or__(self, other: 'TreeMatcher') -> 'TreeMatcher':
        return _OperatorTreeMatcher(self, other, or_)

    def __gt__(self, other: 'TreeMatcher') -> 'TreeMatcher':
        return _GovernorOfTreeMatcher(self, other)

    def __lt__(self, other: 'TreeMatcher') -> 'TreeMatcher':
        return _ChildOfTreeMatcher(self, other)

    def __add__(self, other: 'TreeMatcher') -> 'TreeMatcher':
        return _NextTreeMatcher(self, other)

    def match(self, token: Token) -> Set[TreeMatchingResult]:
        raise NotImplementedError('TreeMatcher.match is not implemented')


class TokenMatcher(TreeMatcher):
    """
    {word: word, lemma: lemma, tag: tag}
    """

    def __init__(self, word: str = None, lemma: str = None, ud_pos: UDPOSTag = None, ud_dep: UDDependency = None):
        self._word = word
        self._lemma = lemma
        self._ud_pos = ud_pos
        self._ud_dep = ud_dep

    def match(self, token: Token) -> Set[TreeMatchingResult]:
        if (self._word is None or self._word == token.word) and \
                (self._lemma is None or self._lemma == token.lemma) and \
                (self._ud_pos is None or self._ud_pos == token.ud_pos) and \
                (self._ud_dep is None or self._ud_dep == token.main_ud_dependency):
            return {TreeMatchingResult(token, {})}
        return set()


class _OperatorTreeMatcher(TreeMatcher):
    """
    left | right, left & right
    """

    def __init__(self, left: TreeMatcher, right: TreeMatcher,
                 operator: Callable[[Set[TreeMatchingResult], Set[TreeMatchingResult]], Set[TreeMatchingResult]]):
        self._left = left
        self._right = right
        self._operator = operator

    def match(self, token: Token) -> Set[TreeMatchingResult]:
        return self._operator(self._left.match(token), self._right.match(token))


class _GovernorOfTreeMatcher(TreeMatcher):
    """
    left > right
    """

    def __init__(self, left: TreeMatcher, right: TreeMatcher):
        self._left = left
        self._right = right

    def match(self, token: Token) -> Set[TreeMatchingResult]:
        return {parent_match for parent_match in self._left.match(token) if
                reduce(or_, [self._right.match(child) for child in parent_match.root.children])}


class _ChildOfTreeMatcher(TreeMatcher):
    """
    left < right
    """

    def __init__(self, left: TreeMatcher, right: TreeMatcher):
        self._left = left
        self._right = right

    def match(self, token: Token) -> Set[TreeMatchingResult]:
        return {child for child in self._left.match(token) if self._right.match(child.head)}


class _NextTreeMatcher(TreeMatcher):
    """
    left + right
    """

    def __init__(self, left: TreeMatcher, right: TreeMatcher):
        self._left = left
        self._right = right

    def match(self, token: Token) -> Set[TreeMatchingResult]:
        return {left_match for left_match in self._left.match(token)
                if left_match.root.next is not None and self._right.match(left_match.root.next)} | \
               {right_match for right_match in self._right.match(token)
                if right_match.root.next is not None and self._left.match(right_match.root.prev)}
