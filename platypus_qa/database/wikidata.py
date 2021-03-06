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
import urllib
from functools import lru_cache
from json import JSONDecodeError
from typing import Dict, List, Union, Optional, Tuple, Iterable

import editdistance
import requests
from pygeoif import Point

from platypus_qa.database.formula import Term, Select, AndFormula, OrFormula, EqualityFormula, TripleFormula, \
    VariableFormula, Formula, ExistsFormula, ValueFormula, NotFormula, AddFormula, SubFormula, MulFormula, DivFormula, \
    GreaterFormula, GreaterOrEqualFormula, LowerOrEqualFormula, LowerFormula, BinaryOrderOperatorFormula, \
    BinaryArithmeticOperatorFormula, Type, ZeroOrMorePathFormula
from platypus_qa.database.model import KnowledgeBase, FormatterError, QAInterpretationResult, EvaluationError
from platypus_qa.database.owl import NamedIndividual, DatatypeProperty, ObjectProperty, owl_Thing, Class, Literal, \
    XSDBooleanLiteral, XSDAnyURILiteral, XSDDateTimeLiteral, xsd_integer, Datatype, Property, XSDDateLiteral, \
    XSDGYearLiteral, XSDGYearMonthLiteral, build_literal, geo_wktLiteral, xsd_string, rdf_langString, \
    xsd_decimal, Entity, xsd_dateTime, rdf_Property, owl_NamedIndividual, xsd_anyURI, xsd_double, xsd_boolean, \
    GeoWKTLiteral, RDFLangStringLiteral

_logger = logging.getLogger('wikidata')

_wikibase_property_types = {
    'http://wikiba.se/ontology#WikibaseItem': owl_NamedIndividual,
    'http://wikiba.se/ontology#CommonsMedia': xsd_string,
    'http://wikiba.se/ontology#String': xsd_string,
    'http://wikiba.se/ontology#ExternalId': xsd_string,
    'http://wikiba.se/ontology#GlobeCoordinate': geo_wktLiteral,
    'http://wikiba.se/ontology#Time': xsd_dateTime,
    'http://wikiba.se/ontology#Url': xsd_anyURI,
    'http://wikiba.se/ontology#Quantity': xsd_decimal,
    'http://wikiba.se/ontology#Monolingualtext': rdf_langString,
    'http://wikiba.se/ontology#WikibaseProperty': rdf_Property,
    'http://wikiba.se/ontology#GeoShape': xsd_string,
    'http://wikiba.se/ontology#Math': xsd_string,
    'http://wikiba.se/ontology#TabularData': xsd_string,
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
_wikibase_datatype_registry = {
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


class _WikidataQuerySparqlBuilder:
    def build(self, term: Term, do_ranking=True) -> str:
        if isinstance(term, Select):
            clauses = self._build_internal(term.body).replace('\n', '\n\t')

            suffix = ' LIMIT 100'
            if do_ranking and term.type[0] & Type.from_entity(owl_Thing) != Type.bottom():
                clauses += '\n\tOPTIONAL { ' + str(term.args[0]) + ' wikibase:sitelinks ?sitelinksCount . }'
                suffix = ' ORDER BY DESC(?sitelinksCount) LIMIT 100'

            return 'SELECT DISTINCT {} WHERE {{\n\t{}\n}}{}'.format(
                ' '.join(str(arg) for arg in term.args), clauses, suffix)

        if isinstance(term, Formula):
            if term.type <= Type.from_entity(xsd_boolean):
                return 'ASK {{\n\t{}\n}}'.format(self._build_internal(term))

        raise EvaluationError('Root term not supported by SPARQL builder {}'.format(term))

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
        elif isinstance(term, (BinaryOrderOperatorFormula, BinaryArithmeticOperatorFormula)):
            return 'FILTER{}'.format(self._serialize_expression(term))
        elif isinstance(term, TripleFormula):
            return '{} {} {} .'.format(
                self._serialize_triple_argument(term.subject),
                self._serialize_triple_argument(term.predicate),
                self._serialize_triple_argument(term.object)
            )
        elif isinstance(term, ExistsFormula):
            return self._build_internal(term.body)
        elif isinstance(term, Select):
            return '{SELECT DISTINCT {} WHERE {{\n\t{}\n}}}'.format(
                ' '.join(term.args), self._build_internal(term.body).replace('\n', '\n\t'))
        else:
            raise EvaluationError('Term not supported by SPARQL builder {}'.format(term))

    def _serialize_triple_argument(self, value: Formula) -> str:
        if isinstance(value, ValueFormula):
            return self._serialize_rdf_term(value.term)
        elif isinstance(value, VariableFormula):
            return str(value)
        elif isinstance(value, ZeroOrMorePathFormula):
            return '{}*'.format(self._serialize_triple_argument(value.path))
        else:
            raise EvaluationError('Not able to serialize triple argument {}'.format(value))

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
            raise EvaluationError('Not able to serialize expression {}'.format(expr))

    def _serialize_rdf_term(self, term: Union[Entity, Literal]) -> str:
        if isinstance(term, Entity):
            for prefix, iri in _wikidata_prefix_map.items():
                if term.iri.startswith(iri):
                    return term.iri.replace(iri, prefix + ':')
        return str(term)


_wikidata_to_schema = {
    'http://www.wikidata.org/prop/direct/P10': 'http://schema.org/video',
    'http://www.wikidata.org/prop/direct/P108': 'http://schema.org/worksFor',
    'http://www.wikidata.org/prop/direct/P110': 'http://schema.org/illustrator',
    'http://www.wikidata.org/prop/direct/P1104': 'http://schema.org/numberOfPages',
    'http://www.wikidata.org/prop/direct/P1113': 'http://schema.org/numberOfEpisodes',
    'http://www.wikidata.org/prop/direct/P112': 'http://schema.org/founder',
    'http://www.wikidata.org/prop/direct/P123': 'http://schema.org/publisher',
    'http://www.wikidata.org/prop/direct/P1243': 'http://schema.org/isrcCode',
    'http://www.wikidata.org/prop/direct/P1329': 'http://schema.org/telephone',
    'http://www.wikidata.org/prop/direct/P136': 'http://schema.org/genre',
    'http://www.wikidata.org/prop/direct/P1476': 'http://schema.org/name',
    'http://www.wikidata.org/prop/direct/P154': 'http://schema.org/logo',
    'http://www.wikidata.org/prop/direct/P1545': 'http://schema.org/position',
    'http://www.wikidata.org/prop/direct/P161': 'http://schema.org/actor',
    'http://www.wikidata.org/prop/direct/P162': 'http://schema.org/producer',
    'http://www.wikidata.org/prop/direct/P1657': 'http://schema.org/contentRating',
    'http://www.wikidata.org/prop/direct/P166': 'http://schema.org/award',
    'http://www.wikidata.org/prop/direct/P170': 'http://schema.org/creator',
    'http://www.wikidata.org/prop/direct/P1716': 'http://schema.org/brand',
    'http://www.wikidata.org/prop/direct/P175': 'http://schema.org/byArtist',
    'http://www.wikidata.org/prop/direct/P176': 'http://schema.org/provider',
    'http://www.wikidata.org/prop/direct/P18': 'http://schema.org/image',
    'http://www.wikidata.org/prop/direct/P1811': 'http://schema.org/episodes',
    'http://www.wikidata.org/prop/direct/P19': 'http://schema.org/birthPlace',
    'http://www.wikidata.org/prop/direct/P20': 'http://schema.org/deathPlace',
    'http://www.wikidata.org/prop/direct/P2043': 'http://schema.org/distance',
    'http://www.wikidata.org/prop/direct/P2047': 'http://schema.org/duration',
    'http://www.wikidata.org/prop/direct/P2048': 'http://schema.org/height',
    'http://www.wikidata.org/prop/direct/P2049': 'http://schema.org/width',
    'http://www.wikidata.org/prop/direct/P21': 'http://schema.org/gender',
    'http://www.wikidata.org/prop/direct/P2360': 'http://schema.org/audience',
    'http://www.wikidata.org/prop/direct/P238': 'http://schema.org/iataCode',
    'http://www.wikidata.org/prop/direct/P239': 'http://schema.org/icaoCode',
    'http://www.wikidata.org/prop/direct/P2437': 'http://schema.org/numberOfSeasons',
    'http://www.wikidata.org/prop/direct/P249': 'http://schema.org/tickerSymbol',
    'http://www.wikidata.org/prop/direct/P2561': 'http://schema.org/name',
    'http://www.wikidata.org/prop/direct/P26': 'http://schema.org/spouse',
    'http://www.wikidata.org/prop/direct/P2699': 'http://schema.org/url',
    'http://www.wikidata.org/prop/direct/P27': 'http://schema.org/nationality',
    'http://www.wikidata.org/prop/direct/P275': 'http://schema.org/license',
    'http://www.wikidata.org/prop/direct/P276': 'http://schema.org/location',
    'http://www.wikidata.org/prop/direct/P2860': 'http://schema.org/citation',
    'http://www.wikidata.org/prop/direct/P2888': 'http://schema.org/sameAs',
    'http://www.wikidata.org/prop/direct/P2894': 'http://schema.org/dayOfWeek',
    'http://www.wikidata.org/prop/direct/P3090': 'http://schema.org/flightNumber',
    'http://www.wikidata.org/prop/direct/P361': 'http://schema.org/isPartOf',
    'http://www.wikidata.org/prop/direct/P364': 'http://schema.org/inLanguage',
    'http://www.wikidata.org/prop/direct/P3931': 'http://schema.org/copyrightHolder',
    'http://www.wikidata.org/prop/direct/P3970': 'http://schema.org/broadcastChannelId',
    'http://www.wikidata.org/prop/direct/P40': 'http://schema.org/children',
    'http://www.wikidata.org/prop/direct/P4032': 'http://schema.org/reviewedBy',
    'http://www.wikidata.org/prop/direct/P407': 'http://schema.org/inLanguage',
    'http://www.wikidata.org/prop/direct/P433': 'http://schema.org/issueNumber',
    'http://www.wikidata.org/prop/direct/P444': 'http://schema.org/reviewRating',
    'http://www.wikidata.org/prop/direct/P453': 'http://schema.org/roleName',
    'http://www.wikidata.org/prop/direct/P460': 'http://schema.org/sameAs',
    'http://www.wikidata.org/prop/direct/P463': 'http://schema.org/memberOf',
    'http://www.wikidata.org/prop/direct/P478': 'http://schema.org/volumeNumber',
    'http://www.wikidata.org/prop/direct/P483': 'http://schema.org/recordedAt',
    'http://www.wikidata.org/prop/direct/P495': 'http://schema.org/countryOfOrigin',
    'http://www.wikidata.org/prop/direct/P50': 'http://schema.org/author',
    'http://www.wikidata.org/prop/direct/P51': 'http://schema.org/audio',
    'http://www.wikidata.org/prop/direct/P527': 'http://schema.org/hasPart',
    'http://www.wikidata.org/prop/direct/P551': 'http://schema.org/homeLocation',
    'http://www.wikidata.org/prop/direct/P569': 'http://schema.org/birthDate',
    'http://www.wikidata.org/prop/direct/P57': 'http://schema.org/director',
    'http://www.wikidata.org/prop/direct/P570': 'http://schema.org/deathDate',
    'http://www.wikidata.org/prop/direct/P571': 'http://schema.org/dateCreated',
    'http://www.wikidata.org/prop/direct/P577': 'http://schema.org/datePublished',
    'http://www.wikidata.org/prop/direct/P580': 'http://schema.org/startDate',
    'http://www.wikidata.org/prop/direct/P582': 'http://schema.org/endDate',
    'http://www.wikidata.org/prop/direct/P625': 'http://schema.org/geo',
    'http://www.wikidata.org/prop/direct/P655': 'http://schema.org/translator',
    'http://www.wikidata.org/prop/direct/P674': 'http://schema.org/character',
    'http://www.wikidata.org/prop/direct/P710': 'http://schema.org/participant',
    'http://www.wikidata.org/prop/direct/P734': 'http://schema.org/familyName',
    'http://www.wikidata.org/prop/direct/P735': 'http://schema.org/givenName',
    'http://www.wikidata.org/prop/direct/P767': 'http://schema.org/contributor',
    'http://www.wikidata.org/prop/direct/P840': 'http://schema.org/contentLocation',
    'http://www.wikidata.org/prop/direct/P859': 'http://schema.org/sponsor',
    'http://www.wikidata.org/prop/direct/P86': 'http://schema.org/musicBy',
    'http://www.wikidata.org/prop/direct/P921': 'http://schema.org/about',
    'http://www.wikidata.org/prop/direct/P98': 'http://schema.org/editor'
}

_s = VariableFormula('s')
_o = VariableFormula('o')


def _relation_for_property(property: Property):
    return Select((_s, _o), TripleFormula(_s, ValueFormula(property), _o))

_property_child = ValueFormula(
    ObjectProperty('http://www.wikidata.org/prop/direct/P40', owl_NamedIndividual, owl_NamedIndividual))
_property_sex = ValueFormula(
    ObjectProperty('http://www.wikidata.org/prop/direct/P21', owl_NamedIndividual, owl_NamedIndividual))
_property_author = ValueFormula(
    ObjectProperty('http://www.wikidata.org/prop/direct/P50', owl_NamedIndividual, owl_NamedIndividual))
_property_librettist = ValueFormula(
    ObjectProperty('http://www.wikidata.org/prop/direct/P87', owl_NamedIndividual, owl_NamedIndividual))
_property_cast_member = ValueFormula(
    ObjectProperty('http://www.wikidata.org/prop/direct/P161', owl_NamedIndividual, owl_NamedIndividual))
_property_subclass_of = ValueFormula(
    ObjectProperty('http://www.wikidata.org/prop/direct/P279', owl_NamedIndividual, owl_NamedIndividual))
_item_male = ValueFormula(NamedIndividual('http://www.wikidata.org/entity/Q6581097'))
_item_female = ValueFormula(NamedIndividual('http://www.wikidata.org/entity/Q6581072'))
_hadcoded_relations = {
    'en': {
        'son': Select((_s, _o), TripleFormula(_s, _property_child, _o) & TripleFormula(_o, _property_sex, _item_male)),
        'daughter': Select((_s, _o),
                           TripleFormula(_s, _property_child, _o) & TripleFormula(_o, _property_sex, _item_female)),
        'name': Select((_s, _o), EqualityFormula(_s, _o)),
        'identity': Select((_s, _o), EqualityFormula(_s, _o)),
        'definition': Select((_s, _o), EqualityFormula(_s, _o)),
        'born date': _relation_for_property(
            DatatypeProperty('http://www.wikidata.org/prop/direct/P569', owl_NamedIndividual, xsd_dateTime)),
        'born location': _relation_for_property(
            ObjectProperty('http://www.wikidata.org/prop/direct/P19', owl_NamedIndividual, owl_NamedIndividual)),
        'dead date': _relation_for_property(
            DatatypeProperty('http://www.wikidata.org/prop/direct/P570', owl_NamedIndividual, xsd_dateTime)),
        'dead location': _relation_for_property(
            ObjectProperty('http://www.wikidata.org/prop/direct/P20', owl_NamedIndividual, owl_NamedIndividual)),
        'wrote': Select((_s, _o), TripleFormula(_o, _property_author, _s)),
        'book by': Select((_s, _o),
                          TripleFormula(_s, _property_author, _o) | TripleFormula(_s, _property_librettist, _o)),
        'play in': Select((_s, _o), TripleFormula(_o, _property_cast_member, _s)),
    },
    'es': {
        'fecha de nació': _relation_for_property(
            DatatypeProperty('http://www.wikidata.org/prop/direct/P569', owl_NamedIndividual, xsd_dateTime)),
        'lugar de nació': _relation_for_property(
            ObjectProperty('http://www.wikidata.org/prop/direct/P19', owl_NamedIndividual, owl_NamedIndividual)),
        'fecha de muerto': _relation_for_property(
            DatatypeProperty('http://www.wikidata.org/prop/direct/P570', owl_NamedIndividual, xsd_dateTime)),
        'lugar de muerto': _relation_for_property(
            ObjectProperty('http://www.wikidata.org/prop/direct/P20', owl_NamedIndividual, owl_NamedIndividual)),
    }
}


def _relation_with_subclass_of_closure(property: ObjectProperty):
    _class = VariableFormula('class')
    return Select((_s, _o), TripleFormula(_s, ValueFormula(property), _class) &
                  TripleFormula(_class, ZeroOrMorePathFormula(_property_subclass_of), _o))


_type_relations = [
    _relation_for_property(
        ObjectProperty('http://www.wikidata.org/prop/direct/P21', owl_NamedIndividual, owl_NamedIndividual)),  # sex
    _relation_for_property(
        ObjectProperty('http://www.wikidata.org/prop/direct/P27', owl_NamedIndividual, owl_NamedIndividual)),
    # citizenship
    _relation_with_subclass_of_closure(
        ObjectProperty('http://www.wikidata.org/prop/direct/P31', owl_NamedIndividual, owl_NamedIndividual)),
    # instance of
    _relation_for_property(
        ObjectProperty('http://www.wikidata.org/prop/direct/P105', owl_NamedIndividual, owl_NamedIndividual)),
    # taxon rank
    _relation_with_subclass_of_closure(
        ObjectProperty('http://www.wikidata.org/prop/direct/P106', owl_NamedIndividual, owl_NamedIndividual)),
    # occupation
    _relation_with_subclass_of_closure(
        ObjectProperty('http://www.wikidata.org/prop/direct/P136', owl_NamedIndividual, owl_NamedIndividual))  # genre
]


class WikidataKnowledgeBase(KnowledgeBase):
    _sparql_builder = _WikidataQuerySparqlBuilder()
    _relations_for_label = {}
    _property_for_iri = {}
    _label_for_iri = {}

    def __init__(self, kb_wikidata_uri: str, wikidata_sparql_endpoint_uri: str = 'https://query.wikidata.org/sparql',
                 compacted_individuals=False, preload_languages: Iterable[str] = ()):
        self._kb_wikidata_uri = kb_wikidata_uri
        self._wikidata_sparql_endpoint_ui = wikidata_sparql_endpoint_uri
        self._request_session_sparql = requests.Session()
        self._request_session_kb = requests.Session()
        self._compacted_individuals = compacted_individuals

        for language_code in preload_languages:
            self._fill_relations_for_label(language_code)


    @lru_cache(maxsize=8192)
    def individuals_from_label(self, label: str, language_code: str, type_filter: Class = owl_Thing) -> List[Select]:
        type_filter = type_filter.iri if type_filter != owl_Thing else None
        results = self._execute_entity_search(label, language_code, type_filter)
        var = self._variable_for_name(label)
        if self._compacted_individuals:
            if not results:
                return []
            return [Select(var, OrFormula(
                [EqualityFormula(var, ValueFormula(_WikidataItem(result), label)) for result in results]))]
        else:
            return [Select(var, EqualityFormula(var, ValueFormula(_WikidataItem(result), label))) for result in
                    results]

    @lru_cache(maxsize=8192)
    def relations_from_labels(self, labels: Iterable[str], language_code: str) -> List[Select]:
        if language_code not in self._relations_for_label:
            self._fill_relations_for_label(language_code)

        labels = [label.strip().lower() for label in labels]
        for distance in range(0, 3):
            # we do not want to be fuzzy with too small labels
            labels_to_match = [l for l in labels if len(l) >= 3 * distance + 1]
            relations = self._relations_by_edit_distance(labels_to_match, language_code, distance)
            if relations:
                return list(relations)
        return []

    def _relations_by_edit_distance(self, input_labels: List[str], language_code: str, distance: int):
        results = set()
        for ref_label, properties in self._relations_for_label[language_code].items():
            for input_label in input_labels:
                dist = editdistance.eval(input_label, ref_label)
                if dist == distance:
                    results.update(properties)
        return results

    def _fill_relations_for_label(self, language_code: str):
        _logger.info('Loading Wikidata relations for {}'.format(language_code))
        results = self._execute_sparql_query(
            'SELECT ?directProperty ?propertyType ?label ?propertyLabel { ' +
            '?property wikibase:directClaim ?directProperty ; wikibase:propertyType ?propertyType . ' +
            '{ ?property rdfs:label ?label } UNION { ?property skos:altLabel ?label } ' +
            'FILTER(LANG(?label) = "' + language_code + '" && ?propertyType != wikibase:WikibaseProperty) ' +
            'SERVICE wikibase:label { bd:serviceParam wikibase:language "' + language_code + '". } }'
        )
        mapping = {}
        relations = {}
        labels = {}
        if 'results' in results and 'bindings' in results['results']:
            for result in results['results']['bindings']:
                property_iri = result['directProperty']['value']
                property_type = result['propertyType']['value']
                label = result['label']['value'].lower()
                labels[property_iri] = result['propertyLabel']['value']
                if property_iri not in relations:
                    if property_iri not in self._property_for_iri:
                        if property_type not in _wikibase_property_types:
                            _logger.warning('Unknown property type: {}'.format(property_type))
                            continue
                        else:
                            property_type = _wikibase_property_types[property_type]
                            if isinstance(property_type, Class):
                                self._property_for_iri[property_iri] = \
                                    ObjectProperty(property_iri, owl_NamedIndividual, property_type)
                            elif isinstance(property_type, Datatype):
                                self._property_for_iri[property_iri] = \
                                    DatatypeProperty(property_iri, owl_NamedIndividual, property_type)
                            else:
                                raise EvaluationError('Unexpected range: {}'.format(property_type))
                    relations[property_iri] = _relation_for_property(self._property_for_iri[property_iri])
                lower_label = label.lower()
                if lower_label not in mapping:
                    mapping[lower_label] = []
                mapping[lower_label].append(relations[property_iri])
        for label, relation in _hadcoded_relations.get(language_code, {}).items():
            mapping[label] = [relation]
        self._relations_for_label[language_code] = mapping
        self._label_for_iri[language_code] = labels

    def type_relations(self) -> List[Select]:
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
            return [result['result'] for result in response.json().get('member', ())]
        except JSONDecodeError:
            _logger.warning('Unexpected response from Wikidata service: {}'.format(response))
            return []

    def normalize_for_sparql(self, term: Term) -> Term:
        if isinstance(term, Formula):
            result = VariableFormula('r')
            if not (term.type <= Type.from_entity(xsd_boolean)):
                return Select(result, EqualityFormula(result, term))
        return term

    def build_sparql(self, term: Term) -> str:
        return self._sparql_builder.build(term, False)

    def has_results(self, term: Term) -> bool:
        # We build an ask query
        i = 0
        while isinstance(term, Select):
            term = term(VariableFormula('expected{}'.format(i)))
            i += 1
        result = self._execute_sparql_query(self._sparql_builder.build(term, False))
        if 'boolean' in result:
            return bool(result['boolean'])
        else:
            raise EvaluationError('Unexpected result from Wikidata Query Service {}'.format(result))

    def evaluate_term(self, term: Term) -> List[Tuple[Union[Entity, Literal]]]:
        term = self.normalize_for_sparql(term)
        query = self._sparql_builder.build(term)
        results = self._execute_sparql_query(query)

        if 'results' in results and 'bindings' in results['results']:
            if isinstance(term, Select):
                return [tuple(self._sparql_term_to_resource(result[arg.name]) for arg in term.args)
                        for result in results['results']['bindings']]
            else:
                raise EvaluationError('Invalid term: {} for query: {}'.format(term, query))
        elif 'boolean' in results:
            return [(XSDBooleanLiteral(value=results['boolean']),)]
        else:
            raise EvaluationError('Unexpected result from Wikidata Query Service {}'.format(results))

    @lru_cache(maxsize=8192)
    def _execute_sparql_query(self, query: str):
        response = self._request_session_sparql.post(
            self._wikidata_sparql_endpoint_ui,
            data=query.replace('\t', ''),
            headers={'Accept': 'application/sparql-results+json', 'Content-Type': 'application/sparql-query'})
        response.raise_for_status()
        try:
            return response.json()
        except JSONDecodeError:
            _logger.warning('Unexpected response from Wikidata Query Service: {}'.format(response))
            return {
                'head': {'vars': []},
                'results': {'bindings': []}
            }

    def _sparql_term_to_resource(self, term) -> Union[Entity, Literal]:
        if 'type' not in term:
            raise EvaluationError('Invalid term in SPARQL results serialization {}'.format(term))
        if term['type'] == 'uri':
            if term['value'].startswith('http://www.wikidata.org/entity/Q'):
                return NamedIndividual(term['value'])
            elif term['value'] in self._property_for_iri:
                return self._property_for_iri[term['value']]
            else:
                return XSDAnyURILiteral(term['value'])
        elif term['type'] == 'literal':
            literal = build_literal(term['value'], term.get('datatype', None), term.get('xml:lang', None))
            if isinstance(literal, XSDDateTimeLiteral):
                literal = WikidataKnowledgeBase._clean_wdqs_datetime(literal)
            return literal
        else:
            raise EvaluationError('Unsupported term in SPARQL results serialization {}'.format(term))

    @staticmethod
    def _clean_wdqs_datetime(dateTime: XSDDateTimeLiteral):
        if dateTime.hour != 0 or dateTime.minute != 0 or dateTime.second != 0:
            return dateTime
        elif dateTime.day != 0:
            return XSDDateLiteral(dateTime.year, dateTime.month, dateTime.day, dateTime.timezone_offset)
        elif dateTime.month != 0:
            return XSDGYearMonthLiteral(dateTime.year, dateTime.month, dateTime.timezone_offset)
        elif dateTime.year != 0:
            return XSDGYearLiteral(dateTime.year, dateTime.timezone_offset)
        else:
            raise EvaluationError('Invalid xsd:dateTime:{}'.format(dateTime))

    def format_to_jsonld(self, interpretation_result: QAInterpretationResult, accept_language: str) -> dict:
        value = interpretation_result.result
        # TODO: instead of using datatypes as @type, use Literal?
        if isinstance(value, Entity):
            result = self._format_entity(value.iri, accept_language)
        elif isinstance(value, Literal):
            if isinstance(value, GeoWKTLiteral):
                if isinstance(value.shape, Point):
                    result = {
                        '@id': 'geo:{},{}'.format(value.shape.y, value.shape.x),
                        '@type': 'GeoCoordinates',
                        'latitude': float(value.shape.y),
                        'longitude': float(value.shape.x),
                        '@context': {
                            '@vocab': 'http://schema.org/'
                        }
                    }
                else:
                    raise FormatterError('Unsupported WKT literal: {}'.format(value.lexical_form))
            elif isinstance(value, RDFLangStringLiteral):
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
            raise FormatterError('Unexpected value: {}'.format(value))

        if interpretation_result.context_subject is not None and interpretation_result.context_predicate is not None:
            if interpretation_result.context_predicate.iri in _wikidata_to_schema:
                result['@reverse'] = {
                    _wikidata_to_schema[interpretation_result.context_predicate.iri]:
                        self._format_entity(interpretation_result.context_subject.iri, accept_language)
                }
            else:
                _logger.info('Unmapped property: {}'.format(interpretation_result.context_predicate.iri))
        return result

    @lru_cache(maxsize=8192)
    def _format_entity(self, iri: str, accept_language: str) -> dict:
        response = self._request_session_kb.get(self._kb_wikidata_uri + '/entity/' +
                                                urllib.parse.quote(
                                                    iri.replace('http://www.wikidata.org/entity/', 'wd:'), safe=''),
                                                headers={'Accept-Language': accept_language})
        # TODO: we should not need to reduce URIs
        try:
            return response.json()
        except JSONDecodeError:
            _logger.warning(
                'Unexpected {} response for entity {} from Wikidata service: {}'.format(response.status_code, iri,
                                                                                        response.text))
            return {'@id': iri}

    def get_label(self, entity: Entity, accept_language: str) -> Optional[str]:
        if accept_language in self._label_for_iri and entity.iri in self._label_for_iri[accept_language]:
            return self._label_for_iri[accept_language][entity.iri]
        elif entity.iri.startsWith('http://www.wikidata.org/entity/'):
            entity = self._format_entity(entity.iri, accept_language)
            if 'name' in entity:
                return entity['name']
        else:
            _logger.warning('Unknown entity: {}'.format(entity))
        return None
