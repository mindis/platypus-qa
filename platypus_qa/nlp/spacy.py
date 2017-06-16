# coding=utf-8
from typing import List
from typing import Optional

import spacy
from spacy.tokens.span import Span

from platypus_qa.nlp.model import Sentence, Token, NLPParser
from platypus_qa.nlp.universal_dependencies import UDPOSTag, UDDependency


class _SpacyToken(Token):
    def __init__(self, token):
        self._token = token

    @property
    def id(self) -> int:
        return self._token.i

    @property
    def ud_pos(self) -> UDPOSTag:
        return UDPOSTag.from_str(self._token.pos_)

    @property
    def word(self) -> str:
        return self._token.text

    @property
    def lemma(self) -> str:
        return self._token.lemma_

    @property
    def main_ud_dependency(self) -> UDDependency:
        return UDDependency.from_str(self._token.dep_)

    @property
    def head(self) -> Optional[Token]:
        return _SpacyToken(self._token.head)

    @property
    def left_children(self) -> List[Token]:
        return [_SpacyToken(token) for token in self._token.children if token.i < self._token.i]

    @property
    def right_children(self) -> List[Token]:
        return [_SpacyToken(token) for token in self._token.children if token.i > self._token.i]

    @property
    def prev(self) -> Optional[Token]:
        return _SpacyToken(self._token.nbor[-1])

    @property
    def next(self) -> Optional[Token]:
        return _SpacyToken(self._token.nbor[1])

    @property
    def language_code(self) -> str:
        return self._token.lang_


class _SpacySentence(Sentence):
    def __init__(self, span: Span):
        self._tokens = [_SpacyToken(token) for token in span]

    def __getitem__(self, i: int) -> Token:
        return self._tokens[i]

    def __iter__(self):
        return self._tokens.__iter__()

    def __len__(self) -> int:
        return len(self._tokens)

    @property
    def root(self):
        for token in self._tokens:
            if token.main_ud_dependency == UDDependency.root:
                return token
        raise ValueError('Sentence without root')

    @property
    def language_code(self) -> str:
        return self.root.language_code


class SpacyParser(NLPParser):
    _models_by_language = {}

    @property
    def supported_languages(self) -> List[str]:
        return ['es', 'fr']

    def parse(self, text: str, language_code: str) -> List[Sentence]:
        # models lazy loading
        if language_code not in self._models_by_language:
            try:
                self._models_by_language[language_code] = spacy.load(language_code)
            except RuntimeError as e:
                self._models_by_language[language_code] = None
                raise ValueError('{} is not supported yet by Spacy'.format(language_code)).with_traceback(e)

        if self._models_by_language[language_code] is None or self._models_by_language[language_code].parser is None:
            raise ValueError('{} is not supported yet by Spacy'.format(language_code))

        return [_SpacySentence(sentence) for sentence in self._models_by_language[language_code](text).sents]
