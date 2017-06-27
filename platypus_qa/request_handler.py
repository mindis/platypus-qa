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
from concurrent.futures import Future, TimeoutError
from typing import Union, Iterable, List, Optional

from calchas_polyparser import is_math, parse_natural, is_interesting, relevance, parse_mathematica, parse_latex, IsMath
from calchas_sympy import Translator
from flask import current_app, request, jsonify
from pyld import jsonld
from sympy import latex
from werkzeug.exceptions import NotFound

from platypus_qa import FormatterError, WikidataKnowledgeBase, QAHandler
from platypus_qa.analyzer.disambiguation import DisambiguationStep, find_process
from platypus_qa.database.formula import Term, ValueFormula
from platypus_qa.logs import DictLogger
from platypus_qa.qa import safe_limited_response_builder, LazyThreadPoolExecutor

_logger = logging.getLogger('request_handler')

PROCESSING_TIMEOUT = 15
_platypus_context = {
    '@vocab': 'http://schema.org/',
    'goog': 'http://schema.googleapis.com/',
    'hydra': 'http://www.w3.org/ns/hydra/core#',
    'owl': 'http://www.w3.org/2002/07/owl#',
    'platypus': 'http://askplatyp.us/vocab#',
    'rdf': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#',
    'rdfs': 'http://www.w3.org/2000/01/rdf-schema#',
    'wd': 'http://www.wikidata.org/entity/',
    'xsd': 'http://www.w3.org/2001/XMLSchema#',
    'resultScore': 'goog:resultScore',
    'totalItems': 'hydra:totalItems',
    'member': 'hydra:member',
    'platypus:term': {
        '@type': 'xsd:string'
    }
}


def _first_future_with_cond(futures: List[Future], condition, default, timeout=None):
    for future in futures:
        try:
            result = future.result(timeout)
            if condition(result):
                for future2 in futures:
                    future2.cancel()
                return result
        except TimeoutError as e:
            _logger.warning('Future processing timout')
            future.cancel()
    return default


class RequestHandler:
    def __init__(self, qa_handler: QAHandler, request_logger: DictLogger):
        self._qa_handler = qa_handler
        self._request_logger = request_logger

    def ask(self, question: str, language_code: str, accept_language: Optional[str]):
        timestamp = time.time()

        results = self._do_cas(question)
        if not results:
            interpretations = self._qa_handler.answer(question, language_code)
            results = []
            existing_results = set()
            for interpretation in interpretations:
                for result in interpretation.results:
                    if result.result in existing_results:
                        continue
                    existing_results.add(result.result)
                    try:
                        results.append({
                            'result': self._qa_handler.knowledge_base.format_to_jsonld(result, accept_language),
                            'resultScore': interpretation.interpretation.score / 100,
                            'platypus:term': str(interpretation.interpretation)
                        })
                    except FormatterError as e:
                        _logger.warning(e)

        self._request_logger.log({
            'question': question,
            'language': language_code,
            'with_results': bool(results),
            'timestamp': timestamp,
            'answer_time': time.time() - timestamp
        })

        return jsonld.compact({
            '@context': _platypus_context,
            '@type': 'hydra:Collection',
            'totalItems': len(results),
            'member': results
        }, _platypus_context)

    @safe_limited_response_builder(5)
    def _do_cas(self, question: str):
        math_notation = is_math(question)
        if math_notation == IsMath.No:
            return []

        calchas_tree = parse_mathematica(question)
        if calchas_tree is None:
            calchas_tree = parse_natural(question)
        if calchas_tree is None:
            calchas_tree = parse_latex(question)
        if calchas_tree is None:
            return []

        sympy_tree = Translator().to_sympy_tree(calchas_tree)
        output_string = str(sympy_tree)
        output_latex = latex(sympy_tree)

        if not is_interesting(str(question), output_string) and math_notation == IsMath.Maybe:
            return []
        if len(output_latex) > 1 and output_latex.isalpha():
            return []

        return [{
            'result': {
                '@type': 'platypus:LaTeX',
                'name': output_string,
                'rdf:value': {
                    '@type': 'platypus:LaTeX',
                    '@value': output_latex
                }
            },
            'resultScore': relevance(question, output_string)
        }]


class SimpleWikidataSparqlHandler:
    def __init__(self, qa_handler: QAHandler, knowledge_base: WikidataKnowledgeBase):
        self._qa_handler = qa_handler
        self._knowledge_base = knowledge_base

    def build_sparql(self):
        question = request.args['q']
        language_code = request.args.get('lang', 'und')
        interpretations = self._qa_handler.answer(question, language_code)
        if not interpretations:
            raise NotFound('Not able to build a good SPARQL question for the {} question "{}"'.format(
                language_code, question))
        return current_app.response_class(
            self._knowledge_base.build_sparql(
                self._knowledge_base.normalize_for_sparql(interpretations[0].interpretation)),
            mimetype='application/sparql-query')


class DisambiguatedWikidataSparqlHandler:
    def __init__(self, qa_handler: QAHandler, knowledge_base: WikidataKnowledgeBase):
        self._qa_handler = qa_handler
        self._knowledge_base = knowledge_base

    def build_sparql(self):
        question = request.args['q']
        language_code = request.args.get('lang', 'und')
        parsed_terms = [interpretation.interpretation for interpretation in
                        self._qa_handler.answer(question, language_code)]

        # TODO: sorting
        disambiguation_tree = find_process(sorted(parsed_terms, key=lambda term: -term.score))
        with LazyThreadPoolExecutor(max_workers=8) as executor:
            return jsonify(self._serialize_disambiguation_tree(disambiguation_tree, executor))

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
                lambda term: self._knowledge_base.build_sparql(self._knowledge_base.normalize_for_sparql(term))
                if self._knowledge_base.has_results(term) else None,
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
