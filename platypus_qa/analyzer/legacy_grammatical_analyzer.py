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
from functools import lru_cache
from itertools import chain
from json import JSONDecodeError
from typing import List

import requests
from ppp_datamodel import Request, Sentence, Response
from ppp_datamodel.exceptions import UnknownNodeType

from platypus_qa.database.formula import Formula
from platypus_qa.database.model import KnowledgeBase
from platypus_qa.database.ppp_datamodel import FromPPPDataModelConverter

_logger = logging.getLogger('legacy_grammatical_analyzer')


class LegacyGrammaticalAnalyzer:
    def __init__(self, knowledge_base: KnowledgeBase,
                 grammatical_url: str = 'https://grammatical.backend.askplatyp.us/'):
        self._grammatical_url = grammatical_url
        self._request_session = requests.Session()
        self._ppp_datamodel_converter = FromPPPDataModelConverter(knowledge_base, 'en')

    @lru_cache(maxsize=1024)
    def analyze(self, text: str, language_code: str = 'en') -> List[Formula]:
        if language_code != 'en':
            raise ValueError('Only English is supported by the legacy grammatical analyzer')

        response = self._request_session.post(self._grammatical_url,
                                              data=Request('new-qa-backend-request', 'en', Sentence(text), {},
                                                           []).as_json())
        try:
            out = response.json()
            if not out:
                return []
            return [result for result in chain.from_iterable(
                self._ppp_datamodel_converter.node_to_terms(Response.from_dict(response).tree) for response in out
            ) if result]
        except JSONDecodeError:
            _logger.warning('Unexpected response from grammatical service: {}'.format(response.text))
            return []
        except UnknownNodeType:
            _logger.warning('Unsupported node from grammatical service: {}'.format(response.json()))
            return []
