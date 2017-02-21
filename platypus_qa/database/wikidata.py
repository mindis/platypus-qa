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
import re
import urllib
from functools import lru_cache
from json import JSONDecodeError
from typing import Dict, List, Union, Optional, Tuple

import requests

from platypus_qa.database.formula import Term, Function, AndFormula, OrFormula, EqualityFormula, TripleFormula, \
    VariableFormula, Formula, ExistsFormula, ValueFormula, NotFormula, AddFormula, SubFormula, MulFormula, DivFormula, \
    GreaterFormula, GreaterOrEqualFormula, LowerOrEqualFormula, LowerFormula, BinaryOrderOperatorFormula
from platypus_qa.database.model import KnowledgeBase
from platypus_qa.database.owl import NamedIndividual, DataProperty, ObjectProperty, owl_Thing, Class, Property, Literal, \
    XSDBooleanLiteral, XSDAnyURILiteral, RDFLangStringLiteral, Datatype, XSDStringLiteral, XSDDateTimeLiteral, \
    XSDDateLiteral, XSDGYearLiteral, XSDGYearMonthLiteral, build_literal, geo_wktLiteral, xsd_string, rdf_langString, \
    xsd_decimal, Entity, xsd_dateTime, rdf_Property, owl_NamedIndividual, xsd_anyURI, xsd_double, xsd_boolean, \
    xsd_float, xsd_duration, xsd_integer, xsd_gYearMonth, xsd_gYear, xsd_date

_logger = logging.getLogger('wikidata')

_wikidata_datatype_map = {
    'rdf:langString': rdf_langString,
    'xsd:anyURI': xsd_anyURI,
    'xsd:boolean': xsd_boolean,
    'xsd:date': xsd_date,
    'xsd:dateTime': xsd_dateTime,
    'xsd:decimal': xsd_decimal,
    'xsd:double': xsd_double,
    'xsd:duration': xsd_duration,
    'xsd:float': xsd_float,
    'xsd:gYear': xsd_gYear,
    'xsd:gYearMonth': xsd_gYearMonth,
    'xsd:integer': xsd_integer,
    'xsd:string': xsd_string,
    'geo:wktLiteral': geo_wktLiteral
}
_wikidata_class_map = {
    'NamedIndividual': owl_NamedIndividual,
    'Property': rdf_Property
}
_wikidata_prefix_map = {
    'rdf': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#',
    'xsd': 'http://www.w3.org/2001/XMLSchema#',
    'rdfs': 'http://www.w3.org/2000/01/rdf-schema#',
    'owl': 'http://www.w3.org/2002/07/owl#',
    'skos': 'http://www.w3.org/2004/02/skos/core#',
    'schema': 'http://schema.org/',
    'cc': 'http://creativecommons.org/ns#',
    'geo': 'http://www.opengis.net/ont/geosparql#',
    'prov': 'http://www.w3.org/ns/prov#',
    'wikibase': 'http://wikiba.se/ontology#',
    'wd': 'http://www.wikidata.org/entity/',
    'wdt': 'http://www.wikidata.org/prop/direct/'
}
_wikidata_datatype_registry = {
    'http://www.w3.org/1999/02/22-rdf-syntax-ns#langString': rdf_langString,
    'http://www.w3.org/2001/XMLSchema#boolean': xsd_boolean,
    'http://www.w3.org/2001/XMLSchema#dateTime': xsd_dateTime,
    'http://www.w3.org/2001/XMLSchema#decimal': xsd_decimal,
    'http://www.w3.org/2001/XMLSchema#double': xsd_double,
    'http://www.w3.org/2001/XMLSchema#integer': xsd_integer,
    'http://www.w3.org/2001/XMLSchema#string': xsd_string,
    'http://www.opengis.net/ont/geosparql#wktLiteral': geo_wktLiteral
}


class _WikidataItem(NamedIndividual):
    def __init__(self, json_ld: Dict):
        super().__init__(json_ld['@id'].replace('wd:', 'http://www.wikidata.org/entity/'))  # TODO: range
        self._score = len(json_ld.get('sameAs', ()))

    @property
    def score(self) -> int:
        return self._score


def find_range(json_ld: Dict):
    if 'range' in json_ld:
        return json_ld['range']
    else:
        raise ValueError('No range provided')


class _WikidataDataProperty(DataProperty):
    def __init__(self, json_ld: Dict):
        super().__init__(
            iri=json_ld['@id'].replace('wdt:', 'http://www.wikidata.org/prop/direct/'),
            range=self._parse_range(find_range(json_ld))
        )

    @staticmethod
    def _parse_range(range: str) -> Datatype:
        if range not in _wikidata_datatype_map:
            raise ValueError('Unexpected range {}'.format(range))
        return _wikidata_datatype_map[range]


class _WikidataObjectProperty(ObjectProperty):
    def __init__(self, json_ld: Dict):
        super().__init__(
            iri=json_ld['@id'].replace('wdt:', 'http://www.wikidata.org/prop/direct/'),
            range=self._parse_range(find_range(json_ld))
        )

    @staticmethod
    def _parse_range(range: str) -> Class:
        if range not in _wikidata_class_map:
            raise ValueError('Unexpected range {}'.format(range))
        return _wikidata_class_map[range]


class _WikidataQuerySparqlBuilder:
    def build(self, term: Term, retrieve_context=False, do_ranking=True) -> str:
        term = self._prepare_term(term, retrieve_context)

        if isinstance(term, Function):
            arguments = [term.argument]
            while isinstance(term.body, Function):
                term = term.body
                arguments.append(term.argument)
            clauses = self._build_internal(term.body).replace('\n', '\n\t')

            suffix = ' LIMIT 100'
            if do_ranking:
                if VariableFormula('s') in arguments:
                    clauses += '\n\tOPTIONAL { ?s wikibase:sitelinks ?sitelinksCount . }'
                else:
                    clauses += '\n\tOPTIONAL { ?r wikibase:sitelinks ?sitelinksCount . }'
                suffix = ' ORDER BY DESC(?sitelinksCount) LIMIT 100'

            return 'SELECT DISTINCT {} WHERE {{\n\t{}\n}}{}'.format(
                ' '.join(str(argument) for argument in arguments), clauses, suffix)
        elif isinstance(term, Formula):
            return 'ASK {{\n\t{}\n}}'.format(self._build_internal(term))
        else:
            raise ValueError('Root term not supported by SPARQL builder {}'.format(term))

    def _prepare_term(self, term: Term, retrieve_context=False) -> Term:
        if isinstance(term, Function):
            result = VariableFormula('r')
            term = Function(result, term(result))
        if retrieve_context:
            term = self._add_context_variable(term)
        return term

    def _add_context_variable(self, term: Term) -> Term:
        if not isinstance(term, Function):
            return term

        result = term.argument
        subject_var = VariableFormula('s')
        predicate_var = VariableFormula('p')

        def explore(term: Term) -> Tuple[Term, bool]:
            if isinstance(term, TripleFormula):
                if term.object == result:
                    return TripleFormula(subject_var, predicate_var, result) & EqualityFormula(subject_var,
                                                                                               term.subject) & EqualityFormula(
                        predicate_var, term.predicate), True
                return term, False
            elif isinstance(term, AndFormula):
                found = False
                modified = []
                for arg in term.args:
                    if found:
                        modified.append(arg)  # The value is already set, we do not modify anything
                    else:
                        arg, found_ = explore(arg)
                        modified.append(arg)
                        found = found or found_
                return AndFormula(modified), found
            elif isinstance(term, OrFormula):
                modified = []
                found = False
                for arg in term.args:
                    arg, found_ = explore(arg)
                    modified.append(arg)
                    found = found or found_
                return OrFormula(modified), found
            elif isinstance(term, ExistsFormula):
                out, found = explore(term.body)
                return ExistsFormula(term.argument, out), found
            else:
                return term, False

        body, found = explore(term.body)

        if found:
            return Function(result, Function(subject_var, Function(predicate_var, body)))
        else:
            return term

    def _build_internal(self, term: Term) -> str:
        if isinstance(term, OrFormula):
            return '{{\n\t{}\n}}'.format('\n} UNION {\n\t'.join(
                sorted(self._build_internal(child).replace('\n', '\n\t') for child in term.args))
            )
        elif isinstance(term, AndFormula):
            return '\n'.join(sorted(self._build_internal(child) for child in term.args))
        elif isinstance(term, EqualityFormula):
            if isinstance(term.left, VariableFormula) and isinstance(term.right, ValueFormula):
                return 'BIND({} AS {})'.format(self._serialize_expression(term.right), str(term.left))
            elif isinstance(term.right, VariableFormula) and isinstance(term.left, ValueFormula):
                return 'BIND({} AS {})'.format(self._serialize_expression(term.left), str(term.right))
            else:
                return 'FILTER{}'.format(self._serialize_expression(term))
        elif isinstance(term, BinaryOrderOperatorFormula):
            return 'FILTER{}'.format(self._serialize_expression(term))
        elif isinstance(term, TripleFormula):
            return '{} {} {} .'.format(
                self._serialize_triple_argument(term.subject),
                self._serialize_triple_argument(term.predicate),
                self._serialize_triple_argument(term.object)
            )
        elif isinstance(term, ExistsFormula):
            return self._build_internal(term.body)
        elif isinstance(term, Function):
            arguments = [term.argument]
            while isinstance(term.body, Function):
                term = term.body
                arguments.append(term.argument)
            return '{SELECT DISTINCT {} WHERE {{\n\t{}\n}}}'.format(' '.join(arguments),
                                                                    self._build_internal(term.body).replace('\n',
                                                                                                            '\n\t'))
        else:
            raise ValueError('Term not supported by SPARQL builder {}'.format(term))

    def _serialize_triple_argument(self, value: Formula) -> str:
        if isinstance(value, ValueFormula):
            return self._serialize_rdf_term(value.term)
        elif isinstance(value, VariableFormula):
            return str(value)
        else:
            raise ValueError('Not able to serialize triple argument {}'.format(value))

    def _serialize_expression(self, expr: Formula) -> str:
        if isinstance(expr, ValueFormula):
            return self._serialize_rdf_term(expr.term)
        elif isinstance(expr, VariableFormula):
            return str(expr)
        elif isinstance(expr, OrFormula):
            return '({})'.format(' || '.join(self._serialize_expression(arg) for arg in expr.args))
        elif isinstance(expr, AndFormula):
            return '({})'.format(' && '.join(self._serialize_expression(arg) for arg in expr.args))
        elif isinstance(expr, NotFormula):
            return '! {}'.format(self._serialize_expression(expr.arg))
        elif isinstance(expr, AddFormula):
            return '({} + {})'.format(self._serialize_expression(expr.left), self._serialize_expression(expr.right))
        elif isinstance(expr, SubFormula):
            return '({} - {})'.format(self._serialize_expression(expr.left), self._serialize_expression(expr.right))
        elif isinstance(expr, MulFormula):
            return '({} * {})'.format(self._serialize_expression(expr.left), self._serialize_expression(expr.right))
        elif isinstance(expr, DivFormula):
            return '({} / {})'.format(self._serialize_expression(expr.left), self._serialize_expression(expr.right))
        elif isinstance(expr, EqualityFormula):
            return '({} = {})'.format(self._serialize_expression(expr.left), str(expr.right))
        elif isinstance(expr, GreaterFormula):
            return '({} > {})'.format(self._serialize_expression(expr.left), self._serialize_expression(expr.right))
        elif isinstance(expr, GreaterOrEqualFormula):
            return '({} >= {})'.format(self._serialize_expression(expr.left), self._serialize_expression(expr.right))
        elif isinstance(expr, LowerFormula):
            return '({} < {})'.format(self._serialize_expression(expr.left), self._serialize_expression(expr.right))
        elif isinstance(expr, LowerOrEqualFormula):
            return '({} <= {})'.format(self._serialize_expression(expr.left), self._serialize_expression(expr.right))
        else:
            raise ValueError('Not able to serialize expression {}'.format(expr))

    def _serialize_rdf_term(self, term: Union[Entity, Literal]) -> str:
        if isinstance(term, Entity):
            for prefix, iri in _wikidata_prefix_map.items():
                if term.iri.startswith(iri):
                    return term.iri.replace(iri, prefix + ':')
        return str(term)


_wikidata_to_schema = {
    'http://www.wikidata.org/prop/direct/P921': 'http://schema.org/about',  # main subject
    'http://www.wikidata.org/prop/direct/P161': 'http://schema.org/actor',  # cast member
    'http://www.wikidata.org/prop/direct/P2360': 'http://schema.org/audience',  # intended public
    'http://www.wikidata.org/prop/direct/P51': 'http://schema.org/audio',  # audio
    'http://www.wikidata.org/prop/direct/P50': 'http://schema.org/author',  # author
    'http://www.wikidata.org/prop/direct/P166': 'http://schema.org/award',  # award received
    'http://www.wikidata.org/prop/direct/P569': 'http://schema.org/birthDate',  # date of birth
    'http://www.wikidata.org/prop/direct/P19': 'http://schema.org/birthPlace',  # place of birth
    'http://www.wikidata.org/prop/direct/P1716': 'http://schema.org/brand',  # brand
    'http://www.wikidata.org/prop/direct/P175': 'http://schema.org/byArtist',  # performer
    'http://www.wikidata.org/prop/direct/P674': 'http://schema.org/character',  # characters
    'http://www.wikidata.org/prop/direct/P40': 'http://schema.org/children',  # child
    'http://www.wikidata.org/prop/direct/P2860': 'http://schema.org/citation',  # cites
    'http://www.wikidata.org/prop/direct/P86': 'http://schema.org/composer',  # composer
    'http://www.wikidata.org/prop/direct/P840': 'http://schema.org/contentLocation',  # narrative location
    'http://www.wikidata.org/prop/direct/P1657': 'http://schema.org/contentRating',  # MPAA film rating
    'http://www.wikidata.org/prop/direct/P767': 'http://schema.org/contributor',  # contributor
    'http://www.wikidata.org/prop/direct/P495': 'http://schema.org/countryOfOrigin',  # country of origin
    'http://www.wikidata.org/prop/direct/P170': 'http://schema.org/creator',  # creator
    'http://www.wikidata.org/prop/direct/P571': 'http://schema.org/dateCreated',  # inception
    'http://www.wikidata.org/prop/direct/P577': 'http://schema.org/datePublished',  # publication date
    'http://www.wikidata.org/prop/direct/P2894': 'http://schema.org/dayOfWeek',  # day of week
    'http://www.wikidata.org/prop/direct/P570': 'http://schema.org/deathDate',  # date of death
    'http://www.wikidata.org/prop/direct/P20': 'http://schema.org/deathPlace',  # place of death
    'http://www.wikidata.org/prop/direct/P57': 'http://schema.org/director',  # director
    'http://www.wikidata.org/prop/direct/P2043': 'http://schema.org/distance',  # length
    'http://www.wikidata.org/prop/direct/P2047': 'http://schema.org/duration',  # duration
    'http://www.wikidata.org/prop/direct/P98': 'http://schema.org/editor',  # editor
    'http://www.wikidata.org/prop/direct/P582': 'http://schema.org/endDate',  # end time
    'http://www.wikidata.org/prop/direct/P1811': 'http://schema.org/episodes',  # list of episodes
    'http://www.wikidata.org/prop/direct/P734': 'http://schema.org/familyName',  # family name
    'http://www.wikidata.org/prop/direct/P3090': 'http://schema.org/flightNumber',  # flight number
    'http://www.wikidata.org/prop/direct/P112': 'http://schema.org/founder',  # founder
    'http://www.wikidata.org/prop/direct/P21': 'http://schema.org/gender',  # sex or gender
    'http://www.wikidata.org/prop/direct/P136': 'http://schema.org/genre',  # genre
    'http://www.wikidata.org/prop/direct/P625': 'http://schema.org/geo',  # coordinate location
    'http://www.wikidata.org/prop/direct/P735': 'http://schema.org/givenName',  # given name
    'http://www.wikidata.org/prop/direct/P527': 'http://schema.org/hasPart',  # has part
    'http://www.wikidata.org/prop/direct/P2048': 'http://schema.org/height',  # height
    'http://www.wikidata.org/prop/direct/P238': 'http://schema.org/iataCode',  # IATA airport code
    'http://www.wikidata.org/prop/direct/P239': 'http://schema.org/icaoCode',  # ICAO airport code
    'http://www.wikidata.org/prop/direct/P110': 'http://schema.org/illustrator',  # illustrator
    'http://www.wikidata.org/prop/direct/P18': 'http://schema.org/image',  # image
    'http://www.wikidata.org/prop/direct/P407': 'http://schema.org/inLanguage',  # language of work or name
    'http://www.wikidata.org/prop/direct/P364': 'http://schema.org/inLanguage',  # original language of work
    'http://www.wikidata.org/prop/direct/P361': 'http://schema.org/isPartOf',  # part of
    'http://www.wikidata.org/prop/direct/P1243': 'http://schema.org/isrcCode',  # International Standard Recording Code
    'http://www.wikidata.org/prop/direct/P433': 'http://schema.org/issueNumber',  # issue
    'http://www.wikidata.org/prop/direct/P275': 'http://schema.org/license',  # license
    'http://www.wikidata.org/prop/direct/P276': 'http://schema.org/location',  # location
    'http://www.wikidata.org/prop/direct/P154': 'http://schema.org/logo',  # logo image
    'http://www.wikidata.org/prop/direct/P463': 'http://schema.org/memberOf',  # member of
    'http://www.wikidata.org/prop/direct/P2561': 'http://schema.org/name',  # name
    'http://www.wikidata.org/prop/direct/P1476': 'http://schema.org/name',  # title
    'http://www.wikidata.org/prop/direct/P27': 'http://schema.org/nationality',  # country of citizenship
    'http://www.wikidata.org/prop/direct/P1113': 'http://schema.org/numberOfEpisodes',  # number of episodes
    'http://www.wikidata.org/prop/direct/P1104': 'http://schema.org/numberOfPages',  # number of pages
    'http://www.wikidata.org/prop/direct/P710': 'http://schema.org/participant',  # participant
    'http://www.wikidata.org/prop/direct/P1545': 'http://schema.org/position',  # series ordinal
    'http://www.wikidata.org/prop/direct/P162': 'http://schema.org/producer',  # producer
    'http://www.wikidata.org/prop/direct/P176': 'http://schema.org/provider',  # manufacturer
    'http://www.wikidata.org/prop/direct/P123': 'http://schema.org/publisher',  # publisher
    'http://www.wikidata.org/prop/direct/P483': 'http://schema.org/recordedAt',  # recorded at
    'http://www.wikidata.org/prop/direct/P444': 'http://schema.org/reviewRating',  # review score
    'http://www.wikidata.org/prop/direct/P453': 'http://schema.org/roleName',  # character role
    'http://www.wikidata.org/prop/direct/P460': 'http://schema.org/sameAs',  # said to be the same as
    'http://www.wikidata.org/prop/direct/P26': 'http://schema.org/spouse',  # spouse
    'http://www.wikidata.org/prop/direct/P580': 'http://schema.org/startDate',  # start time
    'http://www.wikidata.org/prop/direct/P249': 'http://schema.org/tickerSymbol',  # ticker symbol
    'http://www.wikidata.org/prop/direct/P655': 'http://schema.org/translator',  # translator
    'http://www.wikidata.org/prop/direct/P2699': 'http://schema.org/url',  # URL
    'http://www.wikidata.org/prop/direct/P10': 'http://schema.org/video',  # video
    'http://www.wikidata.org/prop/direct/P478': 'http://schema.org/volumeNumber',  # volume
    'http://www.wikidata.org/prop/direct/P2049': 'http://schema.org/width',  # width
    'http://www.wikidata.org/prop/direct/P108': 'http://schema.org/worksFor',  # employer
}

_s = VariableFormula('s')
_o = VariableFormula('o')

_property_child = ValueFormula(
    _WikidataObjectProperty({'@id': 'wdt:P40', '@type': ['ObjectProperty'], 'range': 'NamedIndividual'}))
_property_sex = ValueFormula(
    _WikidataObjectProperty({'@id': 'wdt:P21', '@type': ['ObjectProperty'], 'range': 'NamedIndividual'}))
_item_male = ValueFormula(_WikidataItem({'@id': 'wd:Q6581097', '@type': ['NamedIndividual']}))
_item_female = ValueFormula(_WikidataItem({'@id': 'wd:Q6581072', '@type': ['NamedIndividual']}))
_hadcoded_relations = {
    'en': {
        'son': Function(_s, Function(_o,
                                     TripleFormula(_s, _property_child, _o) &
                                     TripleFormula(_o, _property_sex, _item_male))),
        'daughter': Function(_s, Function(_o,
                                          TripleFormula(_s, _property_child, _o) &
                                          TripleFormula(_o, _property_sex, _item_female))),
        'name': Function(_s, Function(_o, EqualityFormula(_s, _o))),
        'identity': Function(_s, Function(_o, EqualityFormula(_s, _o))),
        'definition': Function(_s, Function(_o, EqualityFormula(_s, _o)))
    }
}

_type_relations = [Function(_s, Function(_o, TripleFormula(_s, ValueFormula(p), _o))) for p in [
    _WikidataObjectProperty({'@id': 'wdt:P21', '@type': ['ObjectProperty'], 'range': 'NamedIndividual'}),  # sex
    _WikidataObjectProperty({'@id': 'wdt:P27', '@type': ['ObjectProperty'], 'range': 'NamedIndividual'}),  # citizenship
    _WikidataObjectProperty({'@id': 'wdt:P31', '@type': ['ObjectProperty'], 'range': 'NamedIndividual'}),  # instance of
    _WikidataObjectProperty({'@id': 'wdt:P105', '@type': ['ObjectProperty'], 'range': 'NamedIndividual'}),  # taxon rank
    _WikidataObjectProperty({'@id': 'wdt:P106', '@type': ['ObjectProperty'], 'range': 'NamedIndividual'}),  # occupation
    _WikidataObjectProperty({'@id': 'wdt:P136', '@type': ['ObjectProperty'], 'range': 'NamedIndividual'})  # genre
]]


class WikidataKnowledgeBase(KnowledgeBase):
    _sparql_builder = _WikidataQuerySparqlBuilder()

    def __init__(self, kb_wikidata_uri: str = 'http://kb.askplatyp.us/api/v1',
                 wikidata_sparql_endpoint_uri: str = 'https://query.wikidata.org/sparql',
                 compacted_individuals=False):
        self._kb_wikidata_uri = kb_wikidata_uri
        self._wikidata_sparql_endpoint_ui = wikidata_sparql_endpoint_uri
        self._request_session_sparql = requests.Session()
        self._request_session_kb = requests.Session()
        self._compacted_individuals = compacted_individuals

    @lru_cache(maxsize=8192)
    def individuals_from_label(self, label: str, language_code: str, type_filter: Class = owl_Thing) \
            -> List[Function[Formula]]:
        type_filter = type_filter.iri if type_filter != owl_Thing else None
        results = self._execute_entity_search(label, language_code, type_filter)
        var = self._variable_for_name(label)
        if self._compacted_individuals:
            if not results:
                return []
            return [Function(var, OrFormula(
                [EqualityFormula(var, ValueFormula(_WikidataItem(result))) for result in results]))]
        else:
            return [Function(var, EqualityFormula(var, ValueFormula(_WikidataItem(result)))) for result in results]

    @lru_cache(maxsize=8192)
    def relations_from_label(self, label: str, language_code: str) -> List[Function[Function[Formula]]]:
        if language_code in _hadcoded_relations and label in _hadcoded_relations[language_code]:
            return [_hadcoded_relations[language_code][label]]
        results = self._execute_entity_search(label, language_code, 'Property')
        return [Function(_s, Function(_o, TripleFormula(_s, ValueFormula(self._build_property(result)), _o)))
                for result in results]

    @staticmethod
    def _build_property(json_ld: Dict) -> Property:
        if 'ObjectProperty' in json_ld['@type']:
            return _WikidataObjectProperty(json_ld)
        elif 'DatatypeProperty' in json_ld['@type']:
            return _WikidataDataProperty(json_ld)
        else:
            raise ValueError('Unknown type for property {}'.format(json_ld))

    def type_relations(self) -> List[Function[Function[Formula]]]:
        return _type_relations

    @staticmethod
    def _variable_for_name(name: str):
        return VariableFormula(''.join([c for c in name if c.isalnum()]))

    def _execute_entity_search(self, label: str, language_code: str, type_filter: Optional[str]):
        params = {'q': label, 'lang': language_code, 'limit': 1000}  # TODO: configure limit?
        if type_filter is not None:
            params['type'] = type_filter
        response = self._request_session_kb.get(self._kb_wikidata_uri + '/search/simple', params=params)
        try:
            return [result['result'] for result in response.json()['member']]
        except JSONDecodeError:
            _logger.warning('Unexpected response from Wikidata service: {}'.format(response))
            return []

    def build_sparql(self, term: Term) -> str:
        return self._sparql_builder.build(term, False, False)

    def evaluate_term(self, term: Term) -> List[Union[Entity, Literal]]:
        query = self._sparql_builder.build(term, retrieve_context=True)
        results = self._execute_sparql_query(query)
        if 'results' in results and 'bindings' in results['results']:
            try:
                return [result for result in (
                    self._sparql_result_to_resource_with_context(result) for result in results['results']['bindings']
                    if 'r' in result) if result is not None]
            except ValueError:
                _logger.warning('Invalid result for query: {}'.format(query))
                return []
        elif 'boolean' in results:
            return [XSDBooleanLiteral(value=results['boolean'])]
        else:
            raise ValueError('Unexpected result from Wikidata Query Service {}'.format(results))

    @lru_cache(maxsize=8192)
    def _execute_sparql_query(self, query: str):
        response = self._request_session_sparql.get(self._wikidata_sparql_endpoint_ui,
                                                    params={'query': query.replace('\t', '')},
                                                    headers={'Accept': 'application/sparql-results+json'})
        try:
            return response.json()
        except JSONDecodeError:
            _logger.warning('Unexpected response from Wikidata Query Service: {}'.format(response))
            return {
                'head': {'vars': []},
                'results': {'bindings': []}
            }

    def _sparql_result_to_resource_with_context(self, result) -> Optional[Union[NamedIndividual, Literal]]:
        resource = self._sparql_result_to_resource(result)
        if resource is None:
            return resource
        if 's' in result and 'p' in result:
            resource.context_subject = result['s']['value']
            resource.context_predicate = result['p']['value']
        return resource

    @staticmethod
    def _sparql_result_to_resource(result) -> Optional[Union[NamedIndividual, Literal]]:
        term = result['r']
        if 'type' not in term:
            raise ValueError('Invalid term in SPARQL results serialization {}'.format(term))
        if term['type'] == 'uri':
            if term['value'].startswith('http://www.wikidata.org/entity/Q'):
                return _WikidataItem({'@id': term['value']})
            else:
                return XSDAnyURILiteral(term['value'])
        elif term['type'] == 'literal':
            if 'xml:lang' in term:
                return RDFLangStringLiteral(term['value'], term['xml:lang'])
            elif 'datatype' in term:
                if term['datatype'] == 'http://www.w3.org/2001/XMLSchema#dateTime':
                    return WikidataKnowledgeBase._format_wdqs_time(term['value'])
                else:
                    return build_literal(term['value'],
                                         _wikidata_datatype_registry[term['datatype']])  # TODO: find datatype
            else:
                return XSDStringLiteral(term['value'])
        elif term['type'] == 'bnode':
            return None
        else:
            raise ValueError('Unsupported term in SPARQL results serialization {}'.format(term))

    @staticmethod
    def _format_wdqs_time(time):
        # TODO: very hacky
        date_time = re.match(r'([+-]?\d{2,})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})Z', time)
        if not date_time or date_time.group(4) != '00' or date_time.group(5) != 0 or date_time.group(6) != 0:
            return XSDDateTimeLiteral(
                int(date_time.group(1)), int(date_time.group(2)), int(date_time.group(3)),
                int(date_time.group(4)), int(date_time.group(5)), int(date_time.group(6)), 0)
        elif date_time.group(3) != '00':
            return XSDDateLiteral(int(date_time.group(1)), int(date_time.group(2)), int(date_time.group(3)), 0)
        elif date_time.group(2) != '00':
            return XSDGYearMonthLiteral(int(date_time.group(1)), int(date_time.group(2)), 0)
        else:
            return XSDGYearLiteral(int(date_time.group(1)), 0)

    def format_value(self, value: Union[Entity, Literal], language_code: str) -> dict:
        # TODO: instead of using datatypes as @type, use Literal?
        if isinstance(value, Entity):
            result = self._format_entity(value.iri, language_code)
        elif isinstance(value, Literal):
            if value.datatype == geo_wktLiteral:
                match = re.match('^Point\((-?\d+(?:\.\d+)?) (-?\d+(?:\.\d+)?)\)$', value.lexical_form)
                if match:
                    result = {
                        '@id': 'geo:{},{}'.format(match.group(2), match.group(1)),
                        '@type': 'GeoCoordinates',
                        'latitude': float(match.group(2)),
                        'longitude': float(match.group(1)),
                        '@context': {
                            '@vocab': 'http://schema.org/'
                        }
                    }
                else:
                    raise ValueError('Unsupported WKT literal: {}'.format(value.lexical_form))
            elif value.datatype == rdf_langString:
                result = {
                    '@type': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#langString',
                    'name': value.to_jsonld(),
                    'http://www.w3.org/1999/02/22-rdf-syntax-ns#value': value.to_jsonld()
                }
            else:
                result = {
                    '@type': value.datatype.iri,
                    'name': value.lexical_form,  # TODO: string formatting
                    'http://www.w3.org/1999/02/22-rdf-syntax-ns#value': value.to_jsonld()
                }
        else:
            raise ValueError('Unexpected value: {}'.format(value))

        if 'context_subject' in value.__dict__ and 'context_predicate' in value.__dict__ and \
                value.__dict__['context_subject'] and value.__dict__['context_predicate'] in _wikidata_to_schema:
            result['@reverse'] = {
                _wikidata_to_schema[value.__dict__['context_predicate']]:
                    self._format_entity(value.__dict__['context_subject'], language_code)
            }
        return result

    @lru_cache(maxsize=8192)
    def _format_entity(self, iri: str, language_code: str) -> dict:
        response = self._request_session_kb.get(self._kb_wikidata_uri + '/entity/' +
                                                urllib.parse.quote(
                                                    iri.replace('http://www.wikidata.org/entity/', 'wd:'), safe=''),
                                                headers={'Accept-Language': language_code})
        # TODO: we should not need to reduce URIs
        try:
            return response.json()
        except JSONDecodeError:
            _logger.warning(
                'Unexpected {} response for entity {} from Wikidata service: {}'.format(response.status_code, iri,
                                                                                        response.text))
            return {'@id': iri}
