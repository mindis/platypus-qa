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
import signal
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError
from typing import Iterable, Dict, List

import langdetect

from platypus_qa.analyzer.grammatical_analyzer import GrammaticalAnalyzer
from platypus_qa.database.formula import Term
from platypus_qa.database.model import KnowledgeBase, QAInterpretation, QAInterpretationResult
from platypus_qa.nlp.model import NLPParser

_logger = logging.getLogger('request_handler')

PROCESSING_TIMEOUT = 15


def safe_limited_response_builder(timeout):
    def raise_timeout_exception(signum, frame):
        raise TimeoutError()

    def wrapper(func):
        def func_wrapper(self, *args):
            try:
                signal.signal(signal.SIGALRM, raise_timeout_exception)  # TODO: POSIX only
                signal.alarm(timeout)
                result = func(self, *args)
                signal.alarm(0)
                return result
            except KeyboardInterrupt:
                raise
            except TimeoutError:
                _logger.warning('Processing timout')
                return []
            except Exception as e:
                _logger.warning(e, exc_info=True)
                return []

        return func_wrapper

    return wrapper


class LazyThreadPoolExecutor(ThreadPoolExecutor):
    def map_first_with_result(self, fn, iterable, condition, default):
        fs = [self.submit(fn, *args) for args in iterable]

        def result_iterator():
            try:
                for future in fs:
                    result = future.result()
                    if condition(result):
                        return result
                return default
            finally:
                for future in fs:
                    future.cancel()

        return result_iterator()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.shutdown(wait=False)
        return False


class QAHandler:
    def __init__(self, parsers: List[NLPParser], knowledge_base: KnowledgeBase, all_interpretations: bool = False):
        self._parsers = parsers
        self._knowledge_base = knowledge_base
        self._all_interpretations = all_interpretations

    def answer(self, question: str, language_code: str = 'und') -> List[QAInterpretation]:
        """
        :param question: The question to reply to
        :param language_code: The language the question is in. "und" if you want to run the language guessing algorithm.
        :return: the possible interpretations for this questions
        """
        language_code = self._clean_language_code(language_code, question)

        for parser in self._parsers:
            results = self._do_with_grammatical_analysis(parser, question, language_code)
            if results:
                return results
        return []

    @staticmethod
    def _clean_language_code(language_code: str, text: str):
        if language_code == 'und':
            return langdetect.detect(text)  # TODO: more clever
        return language_code

    @safe_limited_response_builder(PROCESSING_TIMEOUT)
    def _do_with_grammatical_analysis(self, parser: NLPParser, question: str, language_code: str):
        if language_code not in parser.supported_languages:
            return []
        return self._do_with_terms(
            GrammaticalAnalyzer(parser, self._knowledge_base, language_code).analyze(question)
        )

    def _do_with_terms(self, parsed_terms: Iterable[Term]):
        parsed_terms = list(sorted(parsed_terms, key=lambda term: -term.score))

        with LazyThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(self._knowledge_base.evaluate_term, term) for term in parsed_terms]
            interpretations = []
            max_score = 0
            for i in range(len(parsed_terms)):
                term = parsed_terms[i]
                if term.score < max_score and not self._all_interpretations:
                    return interpretations

                query_results = futures[i].result()
                if query_results:
                    max_score = term.score
                    interpretations.append(QAInterpretation(
                        term, [QAInterpretationResult(result) for result in query_results]))
            return interpretations

    def to_json_ld(self, result: QAInterpretationResult, accept_language: str) -> Dict:
        """
        :param result:
        :param accept_language: language to format the result in
        :return: JSON-LD formatting
        """
        return self._knowledge_base.format_to_jsonld(result, accept_language)
