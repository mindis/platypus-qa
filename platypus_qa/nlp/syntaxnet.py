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

import random
from functools import lru_cache

import requests
from requests.packages.urllib3.exceptions import HTTPError

from platypus_qa.nlp.conllu import CoNLLUParser
from platypus_qa.nlp.model import NLPParser


class SyntaxNetParser(NLPParser):
    _corenllu_parser = CoNLLUParser()

    def __init__(self, server_urls):
        """
        :param server_urls: List[str] URLs of servers running SyntaNet
        """
        self._servers = server_urls
        self._request_session = requests.session()

    def parse(self, text: str, language_code: str):
        """
        :param text: the text to parse
        :param language_code: the text language
        :return: List[Sentence]
        """
        return self._corenllu_parser.parse(self._do_parse(text, language_code), language_code)

    @lru_cache(maxsize=2048)
    def _do_parse(self, text: str, language_code: str) -> str:
        server = random.choice(self._servers)
        response = self._request_session.post(server, data=text.encode('utf8'),
                                              headers={'Content-Language': language_code})
        if response.status_code != 200:
            raise HTTPError('SyntaxNet server error {}:\n{}'.format(response.status_code, response.text))
        return response.text
