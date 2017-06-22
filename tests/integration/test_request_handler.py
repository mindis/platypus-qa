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
import unittest

from platypus_qa.database.wikidata import WikidataKnowledgeBase
from platypus_qa.logs import DummyDictLogger
from platypus_qa.nlp.core_nlp import CoreNLPParser
from platypus_qa.nlp.syntaxnet import SyntaxNetParser
from platypus_qa.samples import SAMPLE_QUESTIONS
from request_handler import RequestHandler

logging.basicConfig(level=logging.WARNING)

_logger = logging.getLogger('test_request_handler')


class RequestHandlerTest(unittest.TestCase):
    """
    Warning: very slow tests to don't overload servers
    """

    def testQuestions(self):
        request_handler = RequestHandler(
            [CoreNLPParser(['https://corenlp.askplatyp.us/1.7/']),
             SyntaxNetParser(['https://syntaxnet.askplatyp.us/v1/parsey-universal-full'])],
            WikidataKnowledgeBase('https://kb.askplatyp.us/api/v1', compacted_individuals=False),
            DummyDictLogger()
        )
        bad_count = 0
        for (language_code, questions) in SAMPLE_QUESTIONS.items():
            for question in questions:
                results = request_handler.ask(question, language_code, language_code)
                if results:
                    _logger.warning('Resources found for the {} question {}.'
                                    .format(language_code, question))
                else:
                    _logger.warning('No resources found for the {} question {}.\nReturned results: {}'
                                    .format(language_code, question, results))
                    bad_count += 1
        if bad_count > 0:
            raise AssertionError(
                '{} on {} tests failed'.format(bad_count,
                                               sum(len(questions) for questions in SAMPLE_QUESTIONS.values())))
