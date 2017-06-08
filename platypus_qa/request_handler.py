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
import typing
from concurrent.futures import Future
from concurrent.futures import ThreadPoolExecutor

import langdetect
from calchas_polyparser import is_math, parse_natural, is_interesting, relevance, parse_mathematica, parse_latex, IsMath
from calchas_sympy import Translator
from flask import current_app, request, jsonify
from ppp_datamodel import Sentence, List, Resource, MathLatexResource, Request
from ppp_datamodel.communication import TraceItem, Response
from sympy import latex
from typing import Union, Iterable
from werkzeug.exceptions import NotFound

from platypus_qa.analyzer.disambiguation import DisambiguationStep, find_process
from platypus_qa.analyzer.grammatical_analyzer import GrammaticalAnalyzer
from platypus_qa.analyzer.legacy_grammatical_analyzer import LegacyGrammaticalAnalyzer
from platypus_qa.database.formula import Term, ValueFormula
from platypus_qa.database.owl import Entity, Literal
from platypus_qa.database.ppp_datamodel import ToPPPDataModelConverter, FromPPPDataModelConverter, PlatypusResource
from platypus_qa.database.wikidata import WikidataKnowledgeBase
from platypus_qa.logs import DictLogger
from platypus_qa.nlp.core_nlp import CoreNLPParser
from platypus_qa.nlp.model import NLPParser
from platypus_qa.nlp.spacy import SpacyParser
from platypus_qa.nlp.syntaxnet import SyntaxNetParser

_logger = logging.getLogger('request_handler')


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
    def __init__(self, core_nlp_url: str, syntaxnet_url: str, wikidata_kb_url: str, request_logger: DictLogger):
        self._spacy_parser = SpacyParser()
        self._core_nlp_parser = CoreNLPParser([core_nlp_url])
        self._syntaxnet_parser = SyntaxNetParser([syntaxnet_url])
        self._wikidata_kb = WikidataKnowledgeBase(wikidata_kb_url, compacted_individuals=True)
        self._request_logger = request_logger
        self._to_ppp_datamodel_converter = ToPPPDataModelConverter()

    def _find_language(self):
        if self._request.language == 'und' and isinstance(self._request.tree, Sentence):
            return langdetect.detect(self._request.tree.value)  # TODO: more clever + other than Sentence?
        return self._request.language

    def answer(self, request: Request):
        timestamp = time.time()
        self._request = request
        self._language = self._find_language()

        all_results = []
        with LazyThreadPoolExecutor(max_workers=4) as executor:
            futures = [
                executor.submit(self._do_simple_execute),
                executor.submit(self._do_cas),
                executor.submit(self._do_with_legacy_en_grammatical_analysis),
                # TODO: move down when grammatical will be improved
                executor.submit(self._do_with_grammatical_spacy_analysis),
                executor.submit(self._do_with_grammatical_corenlp_analysis),
                executor.submit(self._do_with_grammatical_syntaxnet_analysis)
            ]
            results = _first_future_with_cond(futures, self._has_resource, [])
            if self._has_resource(results):
                all_results.extend(results)

        if isinstance(self._request.tree, Sentence):
            self._request_logger.log({
                'question': self._request.tree.value,
                'language': self._language,
                'with_results': bool(all_results),
                'timestamp': timestamp,
                'answer_time': time.time() - timestamp
            })

        return all_results

    @_safe_response_builder
    def _do_with_grammatical_spacy_analysis(self):
        if self._language != 'fr':
            return []  # TODO: enable Spacy for languages other than fr
        return self._do_with_grammatical_analysis(self._spacy_parser, 'Spacy')

    @_safe_response_builder
    def _do_with_grammatical_corenlp_analysis(self):
        return self._do_with_grammatical_analysis(self._core_nlp_parser, 'CoreNLP')

    @_safe_response_builder
    def _do_with_grammatical_syntaxnet_analysis(self):
        return self._do_with_grammatical_analysis(self._syntaxnet_parser, 'SyntaxNet')

    def _do_with_grammatical_analysis(self, parser: NLPParser, parser_name: str):
        tree = self._request.tree
        if not isinstance(tree, Sentence):
            return []
        return self._do_with_terms(
            GrammaticalAnalyzer(parser, self._wikidata_kb, self._language).analyze(tree.value),
            parser_name
        )

    @_safe_response_builder
    def _do_with_legacy_en_grammatical_analysis(self):
        tree = self._request.tree
        if not isinstance(tree, Sentence) or self._language != 'en':
            return []
        return self._do_with_terms(
            LegacyGrammaticalAnalyzer(self._wikidata_kb).analyze(tree.value, self._language),
            'PPP-NLP-Grammatical'
        )

    @_safe_response_builder
    def _do_simple_execute(self):
        tree = self._request.tree
        if isinstance(tree, Sentence):
            return []
        return self._do_with_terms(
            FromPPPDataModelConverter(self._wikidata_kb, 'en').node_to_terms(tree),
            'Input'
        )

    def _do_with_terms(self, parsed_terms: Iterable[Term], parser_name):
        parsed_terms = list(sorted(parsed_terms, key=lambda term: -term.score))
        results = []
        for term in parsed_terms:
            try:
                tree = self._to_ppp_datamodel_converter.term_to_node(term)
                if not isinstance(tree, (Resource, List)):
                    measures = {'accuracy': 0.5, 'relevance': term.score / 100}  # TODO: is good constant?
                    results.append(Response(
                        self._language, tree, measures,
                        self._request.trace + [TraceItem('PPP-Platypus-QA+{}'.format(parser_name), tree, measures)]
                    ))
            except ValueError:
                continue  # Ignore trees we are not able to serialize

        with LazyThreadPoolExecutor(max_workers=16) as executor:
            futures = [executor.submit(self._wikidata_kb.evaluate_term, term) for term in parsed_terms]
            results = []
            max_score = 0
            for i in range(len(parsed_terms)):
                term = parsed_terms[i]
                if term.score < max_score:
                    return results

                result = futures[i].result()
                if result:
                    max_score = term.score
                    values = List(
                        list=[value for value in executor.map(self._format_value, result) if
                              value is not None])
                    measures = {'accuracy': 0.5, 'relevance': term.score / 100}  # TODO: is good constant?
                    try:
                        tree = self._to_ppp_datamodel_converter.term_to_node(term)
                        results.append(Response(
                            self._language, values, measures,
                            self._request.trace + [TraceItem('PPP-Platypus-QA+{}'.format(parser_name), tree, measures),
                                                   TraceItem('PPP-Platypus-QA+{}+Wikidata'.format(parser_name), values,
                                                             measures)]
                        ))
                    except ValueError:
                        results.append(Response(
                            self._language, values, measures,
                            self._request.trace + [
                                TraceItem('PPP-Platypus-QA+{}+Wikidata'.format(parser_name), values, measures)]
                        ))
            return results

    @_safe_response_builder
    def _do_cas(self):
        tree = self._request.tree
        if not isinstance(tree, Sentence):
            return []

        math_notation = is_math(tree.value)
        if math_notation == IsMath.No:
            return []

        calchas_tree = parse_mathematica(tree.value)
        if calchas_tree is None:
            calchas_tree = parse_natural(tree.value)
        if calchas_tree is None:
            calchas_tree = parse_latex(tree.value)
        if calchas_tree is None:
            return []

        sympy_tree = Translator().to_sympy_tree(calchas_tree)
        output_string = str(sympy_tree)

        if not is_interesting(str(tree.value), output_string) and math_notation == IsMath.Maybe:
            return []

        output_tree = MathLatexResource(output_string, latex=latex(sympy_tree))
        measures = {
            'accuracy': 1,
            'relevance': relevance(tree.value, output_string)
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
        return self._json_ld_to_resource(self._wikidata_kb.format_value(value, self._request.response_language))

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


class _BaseWikidataSparqlHandler:
    def __init__(self, core_nlp_url: str, syntaxnet_url: str, wikidata_kb_url: str):
        self._core_nlp_parser = CoreNLPParser([core_nlp_url])
        self._syntaxnet_parser = SyntaxNetParser([syntaxnet_url])
        self._knowledge_base = WikidataKnowledgeBase(wikidata_kb_url, compacted_individuals=False)

    def build_sparql(self):
        self._question = request.args['q']
        self._question_language_code = self._clean_language_code(request.args.get('lang', 'und'), self._question)

        with LazyThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(self._do_with_legacy_en_grammatical_analysis),
                # TODO: move down when grammatical will be improved
                executor.submit(self._do_with_grammatical_analysis, self._core_nlp_parser),
                executor.submit(self._do_with_grammatical_analysis, self._syntaxnet_parser)
            ]
            return self._output_result(_first_future_with_cond(futures, bool, None))

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
        raise NotImplementedError()

    def _output_result(self, result):
        raise NotImplementedError()


class SimpleWikidataSparqlHandler(_BaseWikidataSparqlHandler):
    def _do_with_terms(self, parsed_terms: Iterable[Term]):
        parsed_terms = sorted(parsed_terms, key=lambda term: -term.score)
        with LazyThreadPoolExecutor(max_workers=16) as executor:
            execution_result = executor.map_first_with_result(
                lambda term: self._knowledge_base.build_sparql(term) if self._knowledge_base.has_results(
                    term) else None,
                ((term,) for term in parsed_terms),
                bool,
                None
            )
            return execution_result

    def _output_result(self, sparql):
        if sparql is None:
            raise NotFound('Not able to build a good SPARQL question for the {} question "{}"'.format(
                self._question_language_code, self._question
            ))
        return current_app.response_class(sparql, mimetype='application/sparql-query')


class DisambiguatedWikidataSparqlHandler(_BaseWikidataSparqlHandler):
    def _do_with_terms(self, parsed_terms: Iterable[Term]):
        # TODO: sorting
        disambiguation_tree = find_process(sorted(parsed_terms, key=lambda term: -term.score))
        with LazyThreadPoolExecutor(max_workers=16) as executor:
            return self._serialize_disambiguation_tree(disambiguation_tree, executor)

    def _serialize_disambiguation_tree(self, disambiguation_tree: Union[DisambiguationStep, Iterable[Term]], executor):
        if isinstance(disambiguation_tree, DisambiguationStep):
            choices = []
            for k, v in disambiguation_tree.possibilities.items():
                child_serialization = self._serialize_disambiguation_tree(v, executor)
                if child_serialization:
                    choices.append({
                        '@type': 'DisambiguatedValue',
                        'value': self._term_to_json(k),  # TODO
                        'result': child_serialization
                    })
            others = self._serialize_disambiguation_tree(disambiguation_tree.others, executor)
            if not choices:
                return others
            elif len(choices) == 1:
                return choices[0]['result']
            else:
                return {
                    '@type': 'DisambiguationStep',
                    'name': disambiguation_tree.str_to_disambiguate,
                    'choices': choices,
                    'others': others
                }
        elif isinstance(disambiguation_tree, Iterable):
            # TODO: tous les retourner ?
            execution_result = executor.map_first_with_result(
                lambda term: self._knowledge_base.build_sparql(term) if self._knowledge_base.has_results(
                    term) else None,
                ((term,) for term in sorted(disambiguation_tree, key=lambda term: -term.score)),
                bool,
                None
            )
            if execution_result is None:
                return None
            return {
                '@type': 'SPARQLFormula',
                'sparql': execution_result
            }
        else:
            raise ValueError('Unexpected element in a disambiguation tree: {}'.format(type(disambiguation_tree)))

    @staticmethod
    def _term_to_json(term: Term):
        if not isinstance(term, ValueFormula):
            raise ValueError('Only ValueFormula are expected as disambiguation value')
        return term.term.to_jsonld()

    def _output_result(self, disambiguation_tree):
        return jsonify(disambiguation_tree)
