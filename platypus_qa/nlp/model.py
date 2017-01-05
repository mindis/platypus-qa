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
from typing import Optional, List, Iterator, Sequence

from platypus_qa.nlp.universal_dependencies import UDPOSTag, UDDependency


class Form:
    @property
    def ud_pos(self) -> UDPOSTag:
        """
        :return: An universal dependencies POS tag http://universaldependencies.org/u/pos/index.html
        """
        raise NotImplementedError('Lexeme.ud_pos is not implemented')

    @property
    def word(self) -> str:
        raise NotImplementedError('Lexeme.word is not implemented')

    @property
    def lemma(self) -> str:
        raise NotImplementedError('Lexeme.lemma is not implemented')

    @property
    def nouns(self) -> Sequence[str]:
        return ()

    def __str__(self) -> str:
        return '{}/{}'.format(self.word, self.ud_pos)

    def __eq__(self, other):
        return isinstance(other, Form) and \
               self.word == other.word and self.ud_pos == other.ud_pos and self.lemma == other.lemma

    def __hash__(self):
        return hash(self.word)


class Token(Form):
    @property
    def id(self) -> int:
        """
        :return: The id of the token in the sentence starting at 1
        """
        raise NotImplementedError('Token.id is not implemented')

    @property
    def ud_pos(self) -> UDPOSTag:
        raise NotImplementedError('Token.ud_pos is not implemented')

    @property
    def word(self) -> str:
        raise NotImplementedError('Token.word is not implemented')

    @property
    def lemma(self) -> str:
        raise NotImplementedError('Token.lemma is not implemented')

    @property
    def main_ud_dependency(self) -> UDDependency:
        raise NotImplementedError('Token.main_ud_dependency is not implemented')

    @property
    def head(self) -> Optional['Token']:
        raise NotImplementedError('Token.head is not implemented')

    @property
    def left_children(self) -> List['Token']:
        """
        :return: The left children with the same order as in the original sentence
        """
        raise NotImplementedError('Token.children is not implemented')

    @property
    def right_children(self) -> List['Token']:
        """
        :return: The right children with the same order as in the original sentence
        """
        raise NotImplementedError('Token.children is not implemented')

    @property
    def children(self) -> List['Token']:
        """
        :return: The children with the same order as in the original sentence
        """
        return self.left_children + self.right_children

    def children_by_ud_dependency(self, ud_dependency: UDDependency) -> List['Token']:
        return [dependency for dependency in self.children if dependency.main_ud_dependency == ud_dependency]

    @property
    def prev(self) -> Optional['Token']:
        raise NotImplementedError('Token.prev is not implemented')

    @property
    def next(self) -> Optional['Token']:
        raise NotImplementedError('Token.next is not implemented')

    @staticmethod
    def _leftmost_token(token: 'Token') -> 'Token':
        if token.left_children:
            return Token._leftmost_token(token.left_children[0])
        else:
            return token

    @staticmethod
    def _rightmost_token(token: 'Token') -> 'Token':
        if token.right_children:
            return Token._rightmost_token(token.right_children[-1])
        else:
            return token

    @property
    def subtree(self) -> Iterator['Token']:
        return itertools.chain(
            itertools.chain.from_iterable(dependency.subtree for dependency in self.left_children),
            [self],
            itertools.chain.from_iterable(dependency.subtree for dependency in self.right_children)
        )

    def __str__(self) -> str:
        return '{} {} {}'.format(
            ' '.join(['{}({})'.format(child.main_ud_dependency, child) for child in self.left_children]),
            super().__str__(),
            ' '.join(['{}({})'.format(child.main_ud_dependency, child) for child in self.right_children])
        )

    def __eq__(self, other):
        if not isinstance(other, Token) or self.word != other.word or self.ud_pos != other.ud_pos or \
                        self.main_ud_dependency != other.main_ud_dependency or \
                        len(self.left_children) != len(other.left_children) or \
                        len(self.right_children) != len(other.right_children):
            return False
        for i in range(len(self.left_children)):
            if self.left_children[i] != other.left_children[i]:
                return False
        for i in range(len(self.right_children)):
            if self.right_children[i] != other.right_children[i]:
                return False
        return True

    def __hash__(self):
        return super().__hash__()


class Sentence:
    """
    A sentence: a bag of tokens
    """

    def __getitem__(self, i: int) -> Token:
        raise NotImplementedError('Sentence.__getitem__(i: int) is not implemented')

    def __iter__(self):
        raise NotImplementedError('Sentence.__iter__() is not implemented')

    def __len__(self) -> int:
        raise NotImplementedError('Sentence.__len__() is not implemented')

    @property
    def root(self) -> Token:
        raise NotImplementedError('Sentence.root is not implemented')

    @property
    def language_code(self) -> str:
        raise NotImplementedError('Sentence.language_code is not implemented')

    def __str__(self) -> str:
        return str(self.root)


class NLPParser:
    def parse(self, text: str, language_code: str) -> List[Sentence]:
        """
        :param text: the text to parse
        :param language_code: the text language like 'en' and 'fr'.
        """
        raise NotImplementedError('NLPParser.parse is not implemented')


class Dictionary:
    def get_form(self, word: str, ud_pos: UDPOSTag = None) -> Form:
        raise NotImplementedError('Dictionnary.get_form is not implemented')

    @property
    def language_code(self) -> str:
        raise NotImplementedError('Dictionary.language_code is not implemented')


class SimpleForm(Form):
    def __init__(self, word: str, lemma: str, ud_pos: UDPOSTag, nouns: Sequence[str] = ()):
        self._word = word
        self._lemma = lemma
        self._ud_pos = ud_pos
        self._nous = nouns

    @property
    def word(self) -> str:
        return self._word

    @property
    def lemma(self) -> str:
        return self._lemma

    @property
    def nouns(self) -> Sequence[str]:
        return self._nous

    @property
    def ud_pos(self) -> UDPOSTag:
        return self._ud_pos


class SimpleToken(SimpleForm, Token):
    def __init__(self, word: str, lemma: str, ud_pos: UDPOSTag, ud_dependency: Optional[UDDependency],
                 left_children: List[Token], right_children: List[Token]):
        super().__init__(word, lemma, ud_pos)
        self._ud_dependency = ud_dependency
        self._left_children = left_children
        self._right_children = right_children

    @property
    def id(self) -> int:
        raise NotImplementedError('Token.id is not implemented')

    @property
    def left_children(self) -> List[Token]:
        return self._left_children

    @property
    def right_children(self) -> List[Token]:
        return self._right_children

    @property
    def main_ud_dependency(self) -> UDDependency:
        return self._ud_dependency

    @property
    def head(self) -> Optional[Token]:
        raise NotImplementedError('SimpleToken.head is not implemented')

    @property
    def prev(self) -> Optional['Token']:
        raise NotImplementedError('SimpleToken.prev is not implemented')

    @property
    def next(self) -> Optional['Token']:
        raise NotImplementedError('SimpleToken.next is not implemented')


class EmptyDictionary(Dictionary):
    def __init__(self, language_code: str):
        self._language_code = language_code

    @property
    def language_code(self) -> str:
        return self._language_code

    def get_form(self, word: str, ud_pos: UDPOSTag = None) -> Form:
        return SimpleForm(word, word, ud_pos or UDPOSTag.X)
