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
import os
import typing
from concurrent.futures import Future
from concurrent.futures import ThreadPoolExecutor
from typing import Union, Iterable

import langdetect
from flask import current_app, request
from werkzeug.exceptions import NotFound

from platypus_qa.analyzer.grammatical_analyzer import GrammaticalAnalyzer
from platypus_qa.analyzer.legacy_grammatical_analyzer import LegacyGrammaticalAnalyzer
from platypus_qa.database.formula import Term
from platypus_qa.database.owl import Entity
from platypus_qa.database.owl import Literal
from platypus_qa.database.ppp_datamodel import ToPPPDataModelConverter, FromPPPDataModelConverter, PlatypusResource
from platypus_qa.database.wikidata import WikidataKnowledgeBase
from platypus_qa.nlp.core_nlp import CoreNLPParser
from platypus_qa.nlp.model import NLPParser
from platypus_qa.nlp.syntaxnet import SyntaxNetParser

os.environ['PPP_CAS_CONFIG'] = os.path.dirname(os.path.abspath(__file__)) + '/ppp-cas-config.json'
from ppp_cas import evaluator, notation
from ppp_datamodel import Sentence, List, Resource, MathLatexResource, Request
from ppp_datamodel.communication import TraceItem, Response

_logger = logging.getLogger('request_handler')
_core_nlp_parser = CoreNLPParser(['http://163.172.54.30:9000'])
_syntaxnet_parser = SyntaxNetParser(['http://syntaxnet.askplatyp.us/v1/parsey-universal-full'])
_knowledge_base = WikidataKnowledgeBase(compacted_individuals=True)
_default_meas = {'accuracy': 0.5, 'relevance': 0.5}


def _safe_response_builder(func):
    def func_wrapper(self, *args):
        try:
            return func(self, *args)
        except KeyboardInterrupt:
            raise
        except Exception as e:
            _logger.warning(e, exc_info=True)
            return []

    return func_wrapper


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


def _first_future_with_cond(futures: typing.List[Future], condition, default):
    for future in futures:
        result = future.result()
        if condition(result):
            for future2 in futures:
                future2.cancel()
            return result
    return default


class PPPRequestHandler:
    def __init__(self, request: Request):
        self._request = request
        self._language = self._find_language()
        self._to_ppp_datamodel_converter = ToPPPDataModelConverter()

    def _find_language(self):
        if self._request.language == 'und' and isinstance(self._request.tree, Sentence):
            return langdetect.detect(self._request.tree.value)  # TODO: more clever + other than Sentence?
        return self._request.language

    def answer(self):
        all_results = []
        with LazyThreadPoolExecutor(max_workers=4) as executor:
            futures = [
                executor.submit(self._do_simple_execute),
                executor.submit(self._do_cas),
                executor.submit(self._do_with_legacy_en_grammatical_analysis),
                # TODO: move down when grammatical will be improved
                executor.submit(self._do_with_grammatical_corenlp_analysis),
                executor.submit(self._do_with_grammatical_syntaxnet_analysis)
            ]
            results = _first_future_with_cond(futures, self._has_resource, [])
            if self._has_resource(results):
                all_results.extend(results)
        return all_results

    @_safe_response_builder
    def _do_with_grammatical_corenlp_analysis(self):
        return self._do_with_grammatical_analysis(_core_nlp_parser, 'CoreNLP')

    @_safe_response_builder
    def _do_with_grammatical_syntaxnet_analysis(self):
        return self._do_with_grammatical_analysis(_syntaxnet_parser, 'SyntaxNet')

    def _do_with_grammatical_analysis(self, parser: NLPParser, parser_name: str):
        tree = self._request.tree
        if not isinstance(tree, Sentence):
            return []
        return self._do_with_terms(
            GrammaticalAnalyzer(parser, _knowledge_base, self._language).analyze(tree.value),
            parser_name
        )

    @_safe_response_builder
    def _do_with_legacy_en_grammatical_analysis(self):
        tree = self._request.tree
        if not isinstance(tree, Sentence) or self._language != 'en':
            return []
        return self._do_with_terms(
            LegacyGrammaticalAnalyzer(_knowledge_base).analyze(tree.value, self._language),
            'PPP-NLP-Grammatical'
        )

    @_safe_response_builder
    def _do_simple_execute(self):
        tree = self._request.tree
        if isinstance(tree, Sentence):
            return []
        return self._do_with_terms(
            FromPPPDataModelConverter(_knowledge_base, 'en').node_to_terms(tree),
            'Input'
        )

    def _do_with_terms(self, parsed_terms: Iterable[Term], parser_name):
        parsed_terms = sorted(parsed_terms, key=lambda term: -term.score)
        results = []
        for term in parsed_terms:
            try:
                tree = self._to_ppp_datamodel_converter.term_to_node(term)
                if not isinstance(tree, (Resource, List)):
                    results.append(Response(
                        self._language, tree, _default_meas,
                        self._request.trace + [TraceItem('PPP-Platypus-QA+{}'.format(parser_name), tree, _default_meas)]
                    ))
            except ValueError:
                continue  # Ignore trees we are not able to serialize

        with LazyThreadPoolExecutor(max_workers=16) as executor:
            execution_result = executor.map_first_with_result(
                lambda term: (term, _knowledge_base.evaluate_term(term)),
                ((term,) for term in parsed_terms),
                lambda result: bool(result[1]),
                None
            )
            if execution_result is not None:
                values = List(
                    list=[value for value in executor.map(self._format_value, execution_result[1]) if
                          value is not None])
                try:
                    tree = self._to_ppp_datamodel_converter.term_to_node(execution_result[0])
                    results.append(Response(
                        self._language, values, _default_meas,
                        self._request.trace + [TraceItem('PPP-Platypus-QA+{}'.format(parser_name), tree, _default_meas),
                                               TraceItem('PPP-Platypus-QA+{}+Wikidata'.format(parser_name), values,
                                                         _default_meas)]
                    ))
                except ValueError:
                    results.append(Response(
                        self._language, values, _default_meas,
                        self._request.trace + [
                            TraceItem('PPP-Platypus-QA+{}+Wikidata'.format(parser_name), values, _default_meas)]
                    ))

            return results

    @_safe_response_builder
    def _do_cas(self):
        tree = self._request.tree
        if not isinstance(tree, Sentence):
            return []

        math_notation = notation.isMath(tree.value)
        if math_notation == 0:
            return []

        try:
            output_string, output_latex = evaluator.evaluate(tree.value)
        except (ValueError, SyntaxError):
            return []

        if not notation.isInteresting(str(tree.value), output_string) and math_notation == 1:
            return []

        output_tree = MathLatexResource(output_string, latex=output_latex)
        measures = {
            'accuracy': 1,
            'relevance': notation.relevance(tree.value, output_string)
        }
        trace = self._request.trace + [TraceItem('CAS', output_tree, measures)]
        return [Response(self._request.response_language, output_tree, measures, trace)]

    @staticmethod
    def _has_resource(results) -> bool:
        for result in results:
            if isinstance(result.tree, (Resource, List)):
                return True
        return False

    def _format_value(self, value: Union[Entity, Literal]) -> Resource:
        return self._json_ld_to_resource(_knowledge_base.format_value(value, self._request.response_language))

    @staticmethod
    def _json_ld_to_resource(json_ld):
        if json_ld is None:
            return None
        if 'name' in json_ld:
            return PlatypusResource(value=str(json_ld['name']), graph=json_ld)
        elif 'http://www.w3.org/1999/02/22-rdf-syntax-ns#value' in json_ld and \
                        '@value' in json_ld['http://www.w3.org/1999/02/22-rdf-syntax-ns#value']:
            return PlatypusResource(value=json_ld['http://www.w3.org/1999/02/22-rdf-syntax-ns#value']['@value'],
                                    graph=json_ld)
        elif '@id' in json_ld:
            return PlatypusResource(value=json_ld['@id'], graph=json_ld)
        else:
            return PlatypusResource(value='', graph=json_ld)


class WikidataSparqlHandler:
    _knowledge_base = WikidataKnowledgeBase(compacted_individuals=False)

    def build_sparql(self):
        self._question = request.args['q']
        self._question_language_code = self._clean_language_code(request.args.get('lang', 'und'), self._question)

        with LazyThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(self._do_with_legacy_en_grammatical_analysis),
                # TODO: move down when grammatical will be improved
                executor.submit(self._do_with_grammatical_analysis, _core_nlp_parser),
                executor.submit(self._do_with_grammatical_analysis, _syntaxnet_parser)
            ]
            sparql = _first_future_with_cond(futures, bool, None)
            if sparql is None:
                raise NotFound('Not able to build a good SPARQL question for the {} question "{}"'.format(
                    self._question_language_code, self._question
                ))
            return current_app.response_class(sparql, mimetype='application/sparql-query')

    @staticmethod
    def _clean_language_code(language_code: str, text: str):
        if language_code == 'und':
            return langdetect.detect(text)  # TODO: more clever
        return language_code

    def _do_with_grammatical_analysis(self, parser: NLPParser):
        return self._do_with_terms(
            GrammaticalAnalyzer(parser, self._knowledge_base, self._question_language_code).analyze(self._question)
        )

    @_safe_response_builder
    def _do_with_legacy_en_grammatical_analysis(self):
        if self._question_language_code != 'en':
            return None
        return self._do_with_terms(
            LegacyGrammaticalAnalyzer(self._knowledge_base).analyze(self._question, self._question_language_code)
        )

    def _do_with_terms(self, parsed_terms: Iterable[Term]):
        parsed_terms = sorted(parsed_terms, key=lambda term: -term.score)

        with LazyThreadPoolExecutor(max_workers=16) as executor:
            execution_result = executor.map_first_with_result(
                lambda term: (term, self._knowledge_base.build_sparql(term)),
                ((term,) for term in parsed_terms),
                lambda result: bool(result[1]),
                None
            )
            return execution_result[1] if execution_result is not None else None
