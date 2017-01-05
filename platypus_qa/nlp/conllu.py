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

from collections import OrderedDict
from collections import defaultdict
from typing import Optional, List

from platypus_qa.nlp.model import Token, Sentence
from platypus_qa.nlp.universal_dependencies import UDDependency, UDPOSTag


class _CoNLLUToken(Token):
    def __init__(self, conll_token, sentence):
        """
        :param sentence _CoNLLUSentence
        """
        self._conll_token = conll_token
        self._sentence = sentence

    @property
    def id(self) -> int:
        if not self._conll_token['ID'].isdecimal():
            raise ValueError('This CONLLU token has not an integer id {}'.format(self._conll_token))
        return int(self._conll_token['ID'])

    @property
    def ud_pos(self) -> UDPOSTag:
        return UDPOSTag.from_str(self._conll_token['UPOSTAG'])

    @property
    def word(self) -> str:
        return self._conll_token['FORM']

    @property
    def lemma(self) -> str:
        return self._conll_token['LEMMA']

    @property
    def main_ud_dependency(self) -> UDDependency:
        return UDDependency.from_str(self._conll_token['DEPREL'])

    @property
    def head(self) -> Optional[Token]:
        if self._conll_token['HEAD'] == '0' or self._conll_token['HEAD'] == '_':
            return None
        else:
            return self._sentence.token_for_id(self._conll_token['HEAD'])

    @property
    def left_children(self) -> List[Token]:
        return self._sentence.left_children_for_id(self._conll_token['ID'])

    @property
    def right_children(self) -> List[Token]:
        return self._sentence.right_children_for_id(self._conll_token['ID'])

    @property
    def prev(self) -> Optional[Token]:
        if not self._conll_token['ID'].isdecimal():
            return None
        return self._sentence[int(self._conll_token['ID']) - 2]

    @property
    def next(self) -> Optional[Token]:
        if not self._conll_token['ID'].isdecimal():
            return None
        return self._sentence[int(self._conll_token['ID'])]


class _CoNLLUSentence(Sentence):
    def __init__(self, conll_sentence, language_code: str):
        self._language_code = language_code
        self._tokens = []
        self._token_by_id = {}
        self._left_children_ids = defaultdict(list)
        self._right_children_ids = defaultdict(list)
        self._root = None

        for conll_token in conll_sentence:
            token = _CoNLLUToken(conll_token, self)

            self._token_by_id[conll_token['ID']] = token
            if conll_token['ID'].isdecimal():
                self._tokens.insert(int(conll_token['ID']), token)

            if conll_token['HEAD'] == '0':
                self._root = token
            else:
                if conll_token['HEAD'] in self._token_by_id:
                    self._right_children_ids[conll_token['HEAD']].append(conll_token['ID'])
                else:
                    self._left_children_ids[conll_token['HEAD']].append(conll_token['ID'])

    @property
    def language_code(self) -> str:
        return self._language_code

    def __getitem__(self, i: int) -> Token:
        return self._tokens[i]

    def __iter__(self):
        return self._tokens.__iter__()

    def __len__(self) -> int:
        return len(self._tokens)

    @property
    def root(self):
        return self._root

    def token_for_id(self, id: str) -> Token:
        """
        Private function. Unstable.
        """
        return self._token_by_id[id]

    def left_children_for_id(self, id: str):
        """
        Private function. Unstable.
        """
        if id in self._left_children_ids:
            return [self._token_by_id[child_id] for child_id in self._left_children_ids[id]]
        else:
            return []

    def right_children_for_id(self, id: str):
        """
        Private function. Unstable.
        """
        if id in self._right_children_ids:
            return [self._token_by_id[child_id] for child_id in self._right_children_ids[id]]
        else:
            return []


class CoNLLUParser:
    def parse(self, file_text: str, language_code: str):
        """
        :return: List[Sentence]
        """
        sentences = []
        current_sentence_conll = []
        for line in file_text.split('\n'):
            if not line:
                if current_sentence_conll:
                    sentences.append(_CoNLLUSentence(current_sentence_conll, language_code))
                    current_sentence_conll = []
            elif line[0] == '#':
                continue
            else:
                current_sentence_conll.append(OrderedDict(zip(
                    ['ID', 'FORM', 'LEMMA', 'UPOSTAG', 'XPOSTAG', 'FEATS', 'HEAD', 'DEPREL', 'DEPS', 'MISC'],
                    line.split('\t')
                )))
        if current_sentence_conll:
            sentences.append(_CoNLLUSentence(current_sentence_conll, language_code))
        return sentences
