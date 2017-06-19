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
import time
import unittest

from ppp_datamodel import Sentence, Resource, List, Request

from platypus_qa.database.wikidata import WikidataKnowledgeBase
from platypus_qa.logs import DummyDictLogger
from platypus_qa.nlp.core_nlp import CoreNLPParser
from platypus_qa.nlp.syntaxnet import SyntaxNetParser
from platypus_qa.request_handler import PPPRequestHandler
from platypus_qa.samples import SAMPLE_QUESTIONS

logging.basicConfig(level=logging.WARNING)

_logger = logging.getLogger('test_ppp_module')


class RequestHandlerTest(unittest.TestCase):
    """
    Warning: very slow tests to don't overload servers
    """

    def testQuestions(self):
        request_handler = PPPRequestHandler(
            [CoreNLPParser(['https://corenlp.askplatyp.us/1.7/']),
             SyntaxNetParser(['https://syntaxnet.askplatyp.us/v1/parsey-universal-full'])],
            WikidataKnowledgeBase('https://kb.askplatyp.us/api/v1', compacted_individuals=False),
            DummyDictLogger()
        )
        bad_count = 0
        for (language_code, questions) in SAMPLE_QUESTIONS.items():
            for question in questions:
                results = request_handler.answer(Request(
                    'foo', language_code, Sentence(question), {}, [], language_code
                ))
                resource_results = [result for result in results
                                    if isinstance(result.tree, Resource) or
                                    (isinstance(result.tree, List) and result.tree.list)]
                if resource_results:
                    _logger.warning('[ppp_module_test] Resources found for the {} question {}.'
                                    .format(language_code, question))
                else:
                    _logger.warning('[ppp_module_test] No resources found for the {} question {}.\nReturned results: {}'
                                    .format(language_code, question, results))
                    bad_count += 1
                time.sleep(5)  # to don't overload servers
        if bad_count > 0:
            raise AssertionError(
                '{} on {} tests failed'.format(bad_count,
                                               sum(len(questions) for questions in SAMPLE_QUESTIONS.values())))
