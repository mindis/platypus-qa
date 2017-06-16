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

import json
import random
from functools import lru_cache
from json import JSONDecodeError
from typing import List
from typing import Optional

import requests

from platypus_qa.nlp.model import Sentence, Token, NLPParser
from platypus_qa.nlp.universal_dependencies import UDPOSTag, UDDependency


class _CoreNLPToken(Token):
    def __init__(self, data, sentence):
        """
        :param sentence _CoreNLPSentence
        """
        self._data = data
        self._sentence = sentence

    @property
    def id(self) -> int:
        return self._data['dep_id']

    @property
    def ud_pos(self) -> UDPOSTag:
        return UDPOSTag.from_str(self._data['pos'])

    @property
    def word(self) -> str:
        return self._data['word']

    @property
    def lemma(self) -> str:
        return self._data['lemma']

    @property
    def main_ud_dependency(self) -> UDDependency:
        return UDDependency.from_str(self._data['dep'])

    @property
    def head(self) -> Optional[Token]:
        return self._sentence.token_for_dep_position(self._data['governor'])

    @property
    def left_children(self) -> List[Token]:
        return self._sentence.left_children_for_dep_position(self._data['dep_id'])

    @property
    def right_children(self) -> List[Token]:
        return self._sentence.right_children_for_dep_position(self._data['dep_id'])

    @property
    def prev(self) -> Optional[Token]:
        return self._sentence.token_for_dep_position(self._data['dep_id'] - 1)

    @property
    def next(self) -> Optional[Token]:
        return self._sentence.token_for_dep_position(self._data['dep_id'] + 1)


# TODO improve with http://universaldependencies.org/tagset-conversion/en-penn-uposf.html or better http://universaldependencies.org/en/overview/morphology.html
_upen_pos_tag_to_ud = {
    'NN|SYM': UDPOSTag.NOUN,
    'WRB': UDPOSTag.ADV,
    'DT': UDPOSTag.DET,
    'WDT': UDPOSTag.DET,
    '!': UDPOSTag.SYM,
    'VB': UDPOSTag.VERB,
    'NNS': UDPOSTag.NOUN,
    '?': UDPOSTag.SYM,
    'VP': UDPOSTag.VERB,
    'VBN': UDPOSTag.VERB,
    '-LRB-': UDPOSTag.SYM,
    'PRP': UDPOSTag.PRON,
    'RBR': UDPOSTag.ADV,
    'JJR': UDPOSTag.ADJ,
    'FW': UDPOSTag.X,
    'VBZ': UDPOSTag.VERB,
    'JJRJR': UDPOSTag.ADJ,
    'NNPS': UDPOSTag.NOUN,
    'NP': UDPOSTag.NOUN,
    'VBP|TO': UDPOSTag.VERB,
    '$': UDPOSTag.SYM,
    'RB|RP': UDPOSTag.ADV,
    'RB|VBG': UDPOSTag.ADV,
    'WH': UDPOSTag.X,
    'VBD': UDPOSTag.VERB,
    'JJ': UDPOSTag.ADJ,
    'TO': UDPOSTag.PART,
    'JJS': UDPOSTag.ADJ,
    'IN|RP': UDPOSTag.ADP,
    'NN|VBG': UDPOSTag.NOUN,
    '.': UDPOSTag.SYM,
    'VBP': UDPOSTag.VERB,
    'MD': UDPOSTag.VERB,
    '#': UDPOSTag.SYM,
    'UH': UDPOSTag.X,
    'JJ|RB': UDPOSTag.ADJ,
    'CC': UDPOSTag.CCONJ,
    '(': UDPOSTag.SYM,
    'LS': UDPOSTag.X,
    'WP': UDPOSTag.PRON,
    'VBD|VBN': UDPOSTag.VERB,
    'NN': UDPOSTag.NOUN,
    'PRT': UDPOSTag.PART,
    'VBG|NN': UDPOSTag.VERB,
    'RBS': UDPOSTag.ADV,
    'PRP$': UDPOSTag.PRON,
    ':': UDPOSTag.SYM,
    'NN|NNS': UDPOSTag.NOUN,
    'VBG': UDPOSTag.VERB,
    'RN': UDPOSTag.X,
    'RP': UDPOSTag.PART,
    'IN': UDPOSTag.ADP,
    'NNP': UDPOSTag.NOUN,
    'JJ|VBG': UDPOSTag.ADJ,
    'POS': UDPOSTag.PART,
    'WP$': UDPOSTag.PRON,
    '``': UDPOSTag.SYM,
    'SYM': UDPOSTag.X,
    'PRP|VBP': UDPOSTag.PRON,
    ',': UDPOSTag.SYM,
    ')': UDPOSTag.SYM,
    'EX': UDPOSTag.DET,
    "''": UDPOSTag.SYM,
    'CD|RB': UDPOSTag.X,
    'CD': UDPOSTag.NUM,
    '-RRB-': UDPOSTag.SYM,
    'PDT': UDPOSTag.DET,
    'RB': UDPOSTag.ADV
}

_de_pos_tag_to_ud = {  # From Spacy mapping: https://github.com/explosion/spaCy/blob/master/spacy/de/tag_map.py
    '$(': UDPOSTag.PUNCT,
    '$,': UDPOSTag.PUNCT,
    '$.': UDPOSTag.PUNCT,
    'ADJA': UDPOSTag.ADJ,
    'ADJD': UDPOSTag.ADJ,
    'ADV': UDPOSTag.ADV,
    'APPO': UDPOSTag.ADP,
    'APPR': UDPOSTag.ADP,
    'APPRART': UDPOSTag.ADP,
    'APZR': UDPOSTag.ADP,
    'ART': UDPOSTag.DET,
    'CARD': UDPOSTag.NUM,
    'FM': UDPOSTag.X,
    'ITJ': UDPOSTag.INTJ,
    'KOKOM': UDPOSTag.CCONJ,
    'KON': UDPOSTag.CCONJ,
    'KOUI': UDPOSTag.SCONJ,
    'KOUS': UDPOSTag.SCONJ,
    'NE': UDPOSTag.PROPN,
    'NNE': UDPOSTag.PROPN,
    'NN': UDPOSTag.NOUN,
    'PAV': UDPOSTag.ADV,
    'PROAV': UDPOSTag.ADV,
    'PDAT': UDPOSTag.DET,
    'PDS': UDPOSTag.PRON,
    'PIAT': UDPOSTag.DET,
    'PIDAT': UDPOSTag.DET,
    'PIS': UDPOSTag.PRON,
    'PPER': UDPOSTag.PRON,
    'PPOSAT': UDPOSTag.DET,
    'PPOSS': UDPOSTag.PRON,
    'PRELAT': UDPOSTag.DET,
    'PRELS': UDPOSTag.PRON,
    'PRF': UDPOSTag.PRON,
    'PTKA': UDPOSTag.PART,
    'PTKANT': UDPOSTag.PART,
    'PTKNEG': UDPOSTag.PART,
    'PTKVZ': UDPOSTag.PART,
    'PTKZU': UDPOSTag.PART,
    'PWAT': UDPOSTag.DET,
    'PWAV': UDPOSTag.ADV,
    'PWS': UDPOSTag.PRON,
    'TRUNC': UDPOSTag.X,
    'VAFIN': UDPOSTag.AUX,
    'VAIMP': UDPOSTag.AUX,
    'VAINF': UDPOSTag.AUX,
    'VAPP': UDPOSTag.AUX,
    'VMFIN': UDPOSTag.VERB,
    'VMINF': UDPOSTag.VERB,
    'VMPP': UDPOSTag.VERB,
    'VVFIN': UDPOSTag.VERB,
    'VVIMP': UDPOSTag.VERB,
    'VVINF': UDPOSTag.VERB,
    'VVIZU': UDPOSTag.VERB,
    'VVPP': UDPOSTag.VERB,
    'XY': UDPOSTag.X
}

_ancora_pos_tag_to_ud = {  # See https://nlp.stanford.edu/software/spanish-faq.shtml#tagset
    'ao0000': UDPOSTag.ADJ,
    'aq0000': UDPOSTag.ADJ,
    'cc': UDPOSTag.CCONJ,
    'cs': UDPOSTag.SCONJ,
    'da0000': UDPOSTag.DET,
    'dd0000': UDPOSTag.DET,
    'de0000': UDPOSTag.DET,
    'di0000': UDPOSTag.DET,
    'dn0000': UDPOSTag.NUM,
    'do0000': UDPOSTag.NUM,
    'dp0000': UDPOSTag.DET,
    'dt0000': UDPOSTag.DET,
    'f0': UDPOSTag.PUNCT,
    'faa': UDPOSTag.PUNCT,
    'fat': UDPOSTag.PUNCT,
    'fc': UDPOSTag.PUNCT,
    'fca': UDPOSTag.PUNCT,
    'fct': UDPOSTag.PUNCT,
    'fd': UDPOSTag.PUNCT,
    'fe': UDPOSTag.PUNCT,
    'fg': UDPOSTag.PUNCT,
    'fh': UDPOSTag.PUNCT,
    'fia': UDPOSTag.PUNCT,
    'fit': UDPOSTag.PUNCT,
    'fp': UDPOSTag.PUNCT,
    'fpa': UDPOSTag.PUNCT,
    'fpt': UDPOSTag.PUNCT,
    'fra': UDPOSTag.PUNCT,
    'frc': UDPOSTag.PUNCT,
    'fs': UDPOSTag.PUNCT,
    'ft': UDPOSTag.PUNCT,
    'fx': UDPOSTag.PUNCT,
    'fz': UDPOSTag.PUNCT,
    'i': UDPOSTag.INTJ,
    'nc00000': UDPOSTag.NOUN,
    'nc0n000': UDPOSTag.NOUN,
    'nc0p000': UDPOSTag.NOUN,
    'nc0s000': UDPOSTag.NOUN,
    'np00000': UDPOSTag.PROPN,
    'p0000000': UDPOSTag.PRON,
    'pd000000': UDPOSTag.PRON,
    'pe000000': UDPOSTag.PRON,
    'pi000000': UDPOSTag.PRON,
    'pn000000': UDPOSTag.PRON,
    'pp000000': UDPOSTag.PRON,
    'pr000000': UDPOSTag.PRON,
    'pt000000': UDPOSTag.PRON,
    'px000000': UDPOSTag.PRON,
    'rg': UDPOSTag.ADV,
    'rn': UDPOSTag.ADV,
    'sp000': UDPOSTag.ADP,
    'va00000': UDPOSTag.VERB,
    'vag0000': UDPOSTag.AUX,
    'vaic000': UDPOSTag.AUX,
    'vaif000': UDPOSTag.AUX,
    'vaii000': UDPOSTag.AUX,
    'vaip000': UDPOSTag.AUX,
    'vais000': UDPOSTag.AUX,
    'vam0000': UDPOSTag.AUX,
    'van0000': UDPOSTag.AUX,
    'vap0000': UDPOSTag.AUX,
    'vasi000': UDPOSTag.AUX,
    'vasp000': UDPOSTag.AUX,
    'vmg0000': UDPOSTag.VERB,
    'vmic000': UDPOSTag.VERB,
    'vmif000': UDPOSTag.VERB,
    'vmii000': UDPOSTag.VERB,
    'vmip000': UDPOSTag.VERB,
    'vmis000': UDPOSTag.VERB,
    'vmm0000': UDPOSTag.VERB,
    'vmn0000': UDPOSTag.VERB,
    'vmp0000': UDPOSTag.VERB,
    'vmsi000': UDPOSTag.VERB,
    'vmsp000': UDPOSTag.VERB,
    'vsg0000': UDPOSTag.AUX,
    'vsic000': UDPOSTag.AUX,
    'vsif000': UDPOSTag.AUX,
    'vsii000	': UDPOSTag.AUX,
    'vsip000': UDPOSTag.AUX,
    'vsis000': UDPOSTag.AUX,
    'vsm0000': UDPOSTag.AUX,
    'vsn0000': UDPOSTag.AUX,
    'vsp0000': UDPOSTag.AUX,
    'vssf000': UDPOSTag.AUX,
    'vssi000': UDPOSTag.AUX,
    'vssp000': UDPOSTag.AUX,
    'w': UDPOSTag.NOUN,
    'z0': UDPOSTag.NUM,
    'zm': UDPOSTag.NOUN,
    'zu': UDPOSTag.NOUN,
    'word': UDPOSTag.X
}


class _EnglishCoreNLPToken(_CoreNLPToken):
    def __init__(self, data, sentence):
        super().__init__(data, sentence)

    @property
    def ud_pos(self) -> UDPOSTag:
        return _upen_pos_tag_to_ud[self._data['pos']]

    @property
    def main_ud_dependency(self) -> UDDependency:
        return UDDependency.from_str(self._data['dep'])


class _GermanCoreNLPToken(_CoreNLPToken):
    def __init__(self, data, sentence):
        super().__init__(data, sentence)

    @property
    def ud_pos(self) -> UDPOSTag:
        return _de_pos_tag_to_ud[self._data['pos']]

    @property
    def main_ud_dependency(self) -> UDDependency:
        return UDDependency.from_str(self._data['dep'])


class _SpanishCoreNLPToken(_CoreNLPToken):
    def __init__(self, data, sentence):
        super().__init__(data, sentence)

    @property
    def ud_pos(self) -> UDPOSTag:
        return _ancora_pos_tag_to_ud[self._data['pos']]

    @property
    def main_ud_dependency(self) -> UDDependency:
        return UDDependency.from_str(self._data['dep'])


class _CoreNLPSentence(Sentence):
    # TODO: we do not support dependency DAGs (only used with improved dependencies)

    def __init__(self, core_nlp_output, language_code):
        self._language_code = language_code
        dependencies_data = sorted(core_nlp_output['basicDependencies'],
                                   key=lambda current_dep: current_dep['dependent'])

        self._tokens = []
        self._token_by_dependency_id = [None] * (len(dependencies_data) + 1)
        self._left_children_ids_by_governor_id = [[] for i in range(len(dependencies_data) + 1)]
        self._right_children_ids_by_governor_id = [[] for i in range(len(dependencies_data) + 1)]

        # Parse tokens and adds to them a dependency id
        current_dep_i = 0
        num_dep_i = len(dependencies_data)
        for token_data in core_nlp_output['tokens']:
            if current_dep_i < num_dep_i and dependencies_data[current_dep_i]['dependentGloss'] == token_data['word']:
                current_dep = dependencies_data[current_dep_i]
                token_data['dep_id'] = current_dep['dependent']
                token_data['dep'] = current_dep['dep']
                token_data['governor'] = current_dep['governor']
                token = self._build_token(token_data)
                self._tokens.append(token)
                self._token_by_dependency_id[current_dep['dependent']] = token
            else:
                self._tokens.append(self._build_token(token_data))
            current_dep_i += 1

        # Fill dependencies map
        for dependency_data in dependencies_data:
            if dependency_data['dep'] == 'ROOT':
                self._root_dependency_id = dependency_data['dependent']
            else:
                if dependency_data['governor'] >= dependency_data['dependent']:
                    self._left_children_ids_by_governor_id[dependency_data['governor']].append(
                        dependency_data['dependent'])
                else:
                    self._right_children_ids_by_governor_id[dependency_data['governor']].append(
                        dependency_data['dependent'])

    def _build_token(self, core_nlp_data) -> Token:
        return _CoreNLPToken(core_nlp_data, self)

    def __getitem__(self, i: int) -> Token:
        return self._tokens[i]

    def __iter__(self):
        return self._tokens.__iter__()

    def __len__(self) -> int:
        return len(self._tokens)

    @property
    def root(self):
        return self._token_by_dependency_id[self._root_dependency_id]

    def token_for_dep_position(self, i: int) -> Token:
        """
        Private function. Unstable.
        """
        return self._token_by_dependency_id[i]

    def left_children_for_dep_position(self, i: int):
        """
        Private function. Unstable.
        """
        return [self._token_by_dependency_id[child] for child in self._left_children_ids_by_governor_id[i]]

    def right_children_for_dep_position(self, i: int):
        """
        Private function. Unstable.
        """
        return [self._token_by_dependency_id[child] for child in self._right_children_ids_by_governor_id[i]]

    @property
    def language_code(self) -> str:
        return self._language_code


class _EnglishCoreNLPSentence(_CoreNLPSentence):
    def _build_token(self, core_nlp_data) -> Token:
        return _EnglishCoreNLPToken(core_nlp_data, self)


class _GermanCoreNLPSentence(_CoreNLPSentence):
    def _build_token(self, core_nlp_data) -> Token:
        return _GermanCoreNLPToken(core_nlp_data, self)


class _SpanishCoreNLPSentence(_CoreNLPSentence):
    def _build_token(self, core_nlp_data) -> Token:
        return _SpanishCoreNLPToken(core_nlp_data, self)


_config_by_language = {
    'de': {
        'annotators': 'lemma,depparse',
        'outputFormat': 'json'
    },
    'en': {
        'annotators': 'lemma,depparse',  # ,ner,coref
        'outputFormat': 'json'
    },
    'es': {
        'annotators': 'lemma,depparse',
        'outputFormat': 'json'
    },
    'fr': {
        'annotators': 'lemma,depparse',
        'outputFormat': 'json',
        'tokenize.language': 'fr',
        'pos.model': 'edu/stanford/nlp/models/pos-tagger/french/french.tagger',
        'parse.model': 'edu/stanford/nlp/models/lexparser/frenchFactored.ser.gz',
        'depparse.model': 'edu/stanford/nlp/models/parser/nndep/UD_French.gz'
    }
}


class CoreNLPParser(NLPParser):
    def __init__(self, server_urls):
        """
        :param server_urls: List[str] URLs of coreNLP servers running version 3.6
        """
        self._servers = server_urls
        self._request_session = requests.session()

    @property
    def supported_languages(self) -> List[str]:
        return ['de', 'en', 'es', 'fr']

    def parse(self, text: str, language_code):
        """
        :param text: the text to parse
        :param language_code: the text language. Only 'en' and 'fr' are currently supported
        :return: List[Sentence]
        """
        core_nlp_result = self._do_parse(text, language_code)
        if language_code == 'en':
            return [_EnglishCoreNLPSentence(core_nlp_sentence, 'en') for core_nlp_sentence in core_nlp_result]
        elif language_code == 'es':
            return [_SpanishCoreNLPSentence(core_nlp_sentence, 'es') for core_nlp_sentence in core_nlp_result]
        elif language_code == 'de':
            return [_GermanCoreNLPSentence(core_nlp_sentence, 'de') for core_nlp_sentence in core_nlp_result]
        else:
            return [_CoreNLPSentence(core_nlp_sentence, language_code) for core_nlp_sentence in core_nlp_result]

    @lru_cache(maxsize=2048)
    def _do_parse(self, sentence: str, language_code: str):
        if language_code not in _config_by_language:
            raise ValueError('{} is not supported by CoreNLP'.format(language_code))

        server = random.choice(self._servers)
        response = self._request_session.post(server,
                                              params={
                                                  'properties': json.dumps(_config_by_language[language_code]),
                                                  'pipelineLanguage': language_code
                                              }, data=sentence.encode('utf8'))
        try:
            return response.json()['sentences']
        except JSONDecodeError:
            raise RuntimeError('CoreNLP invalid response with status code {}: {}'.format(
                response.status_code, response.text)
            )
