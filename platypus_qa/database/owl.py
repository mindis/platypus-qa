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

import json
import re
from datetime import datetime, timezone, timedelta, date, time
from decimal import Decimal
from typing import Sequence, Union, Optional

from pygeoif import geometry

"""
Implementation of basic OWL for use in formulas
"""


class Entity:
    def __init__(self, iri, types: Sequence['Class']):
        self.iri = iri
        self.types = types

    def to_jsonld(self) -> dict:
        return {
            '@id': self.iri,
            '@type': [type.iri for type in self.types]
        }

    def is_instance_of(self, other: 'Class'):
        return any(type.is_subclass_of(other) for type in self.types)

    @property
    def score(self) -> int:
        return 0

    def __str__(self) -> str:
        return '<{}>'.format(self.iri)

    def __eq__(self, other):
        return isinstance(other, Entity) and self.iri == other.iri

    def __hash__(self):
        return hash(self.iri)


rdfs_Class = None  # Forward declaration


class Class(Entity):
    def __init__(self, iri: str, subclass_of: Sequence['Class']):
        if iri == 'http://www.w3.org/2000/01/rdf-schema#Class':
            super().__init__(iri, (self,))
        else:
            super().__init__(iri, (rdfs_Class,))
        self._subclass_of = subclass_of

    def is_subclass_of(self, other: 'Class') -> bool:
        if self == owl_Nothing:
            return True

        return self == other or any(super_dt.is_subclass_of(other) for super_dt in self._subclass_of)


rdfs_Class = Class('http://www.w3.org/2000/01/rdf-schema#Class', ())  # Should be the first Class instance created!
owl_Thing = Class('http://www.w3.org/2002/07/owl#Thing', ())
owl_Nothing = Class('http://www.w3.org/2002/07/owl#Nothing', ())
rdfs_Datatype = Class('http://www.w3.org/2000/01/rdf-schema#Datatype', ())
rdf_Property = Class('http://www.w3.org/1999/02/22-rdf-syntax-ns#Property', (owl_Thing,))
owl_ObjectProperty = Class('http://www.w3.org/2002/07/owl#ObjectProperty', (rdf_Property,))
owl_DatatypeProperty = Class('http://www.w3.org/2002/07/owl#DatatypeProperty', (rdf_Property,))
owl_NamedIndividual = Class('http://www.w3.org/2002/07/owl#NamedIndividual', (owl_Thing,))
schema_Person = Class('http://schema.org/Person', (owl_NamedIndividual,))
schema_Place = Class('http://schema.org/Place', (owl_NamedIndividual,))


class NamedIndividual(Entity):
    def __init__(self, iri: str, types: Sequence['Class'] = (owl_Thing, owl_NamedIndividual)):
        super().__init__(iri, types)


class Datatype(Entity):
    def __init__(self, iri: str, restriction_of: Sequence['Datatype']):
        super().__init__(iri, (rdfs_Datatype,))
        self._restriction_of = restriction_of

    def is_restriction_of(self, other: 'Datatype') -> bool:
        return self == other or any(super_dt.is_restriction_of(other) for super_dt in self._restriction_of)


rdfs_Literal = Datatype('http://www.w3.org/2000/01/rdf-schema#Literal', ())
rdf_langString = Datatype('http://www.w3.org/1999/02/22-rdf-syntax-ns#langString', (rdfs_Literal,))
platypus_calendar = Datatype('http://askplatyp.us/vocab#calendar', (rdfs_Literal,))  # TODO: right URI?
platypus_numeric = Datatype('http://askplatyp.us/vocab#numeric', (rdfs_Literal,))  # TODO: right URI?
xsd_anyURI = Datatype('http://www.w3.org/2001/XMLSchema#anyURI', (rdfs_Literal,))
xsd_boolean = Datatype('http://www.w3.org/2001/XMLSchema#boolean', (rdfs_Literal,))
xsd_dateTime = Datatype('http://www.w3.org/2001/XMLSchema#dateTime', (rdfs_Literal, platypus_calendar))
xsd_date = Datatype('http://www.w3.org/2001/XMLSchema#date', (rdfs_Literal, platypus_calendar))
xsd_decimal = Datatype('http://www.w3.org/2001/XMLSchema#decimal', (rdfs_Literal, platypus_numeric))
xsd_double = Datatype('http://www.w3.org/2001/XMLSchema#double', (rdfs_Literal, platypus_numeric))
xsd_duration = Datatype('http://www.w3.org/2001/XMLSchema#duration', (rdfs_Literal,))
xsd_float = Datatype('http://www.w3.org/2001/XMLSchema#float', (rdfs_Literal, platypus_numeric))
xsd_gYearMonth = Datatype('http://www.w3.org/2001/XMLSchema#gYearMonth', (rdfs_Literal, platypus_calendar))
xsd_gYear = Datatype('http://www.w3.org/2001/XMLSchema#gYear', (rdfs_Literal, platypus_calendar))
xsd_integer = Datatype('http://www.w3.org/2001/XMLSchema#integer', (rdfs_Literal, platypus_numeric, xsd_decimal))
xsd_string = Datatype('http://www.w3.org/2001/XMLSchema#string', (rdfs_Literal,))
xsd_time = Datatype('http://www.w3.org/2001/XMLSchema#time', (rdfs_Literal, platypus_calendar))
geo_wktLiteral = Datatype('http://www.opengis.net/ont/geosparql#wktLiteral', (rdfs_Literal,))

_datatype_registry = {
    'http://www.w3.org/1999/02/22-rdf-syntax-ns#langString': rdf_langString,
    'http://www.w3.org/2001/XMLSchema#anyURI': xsd_anyURI,
    'http://www.w3.org/2001/XMLSchema#boolean': xsd_boolean,
    'http://www.w3.org/2001/XMLSchema#dateTime': xsd_dateTime,
    'http://www.w3.org/2001/XMLSchema#date': xsd_date,
    'http://www.w3.org/2001/XMLSchema#decimal': xsd_decimal,
    'http://www.w3.org/2001/XMLSchema#double': xsd_double,
    'http://www.w3.org/2001/XMLSchema#duration': xsd_duration,
    'http://www.w3.org/2001/XMLSchema#float': xsd_float,
    'http://www.w3.org/2001/XMLSchema#gYearMonth': xsd_gYearMonth,
    'http://www.w3.org/2001/XMLSchema#gYear': xsd_gYear,
    'http://www.w3.org/2001/XMLSchema#integer': xsd_integer,
    'http://www.w3.org/2001/XMLSchema#string': xsd_string,
    'http://www.w3.org/2001/XMLSchema#time': xsd_time,
    'http://www.opengis.net/ont/geosparql#wktLiteral': geo_wktLiteral
}


class Literal:
    @property
    def lexical_form(self) -> str:
        raise NotImplementedError('Literal.lexical_form is not implemented')

    @property
    def datatype(self) -> Datatype:
        raise NotImplementedError('Literal.datatype is not implemented')

    def to_jsonld(self) -> dict:
        return {
            '@type': self.datatype.iri,
            '@value': self.lexical_form
        }

    def __str__(self) -> str:
        return '{}^^{}'.format(json.dumps(self.lexical_form), self.datatype)

    def __eq__(self, other):
        return isinstance(other, Literal) and \
               self.lexical_form == other.lexical_form and self.datatype == other.datatype

    def __hash__(self):
        return hash(self.lexical_form)


_xsd_datetime_re = re.compile(r'([+-]?\d{2,})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2}(\\.\d+)?)(.{0,6})')
_xsd_date_re = re.compile(r'([+-]?\d{2,})-(\d{2})-(\d{2})(\\.{0,6})')
_xsd_time_re = re.compile(r'(\d{2}):(\d{2}):(\d{2}(.\d+)?)(\\.{0,6})')
_xsd_gYearMonth_re = re.compile(r'([+-]?\d{2,})-(\d{2})(\\.{0,6})')
_xsd_gYear_re = re.compile(r'([+-]?\d{2,})(\\.{0,6})')
_xsd_timezone_re = re.compile(r'([+-])(\d{2}):(\d{2})')


def _parse_timezone(text: str, datatype: str) -> Optional[int]:
    if text == '':
        return None
    if text == 'Z':
        return 0
    match = _xsd_timezone_re.match(text)
    if not match:
        raise ValueError('Invalid {} lexical form: {}'.format(datatype, text))
    return (-1 if match.group(1) == '-' else 1) * (int(match.group(2)) * 60 + int(match.group(3)))


def build_literal(lexical_form: str, datatype: Optional[Union[Datatype, str]] = None,
                  language_code: Optional[str] = None) -> Literal:
    # default datatype
    if datatype is None:
        datatype = xsd_string if language_code is None else rdf_langString

    # parse datatype
    if isinstance(datatype, str):
        if datatype in _datatype_registry:
            datatype = _datatype_registry[datatype]
        else:
            datatype = Datatype(datatype, (rdfs_Literal,))

    # language_code validation
    if language_code is not None and datatype != rdf_langString:
        raise ValueError('Literals with language code must have the rdf:langString datatype')

    # we build objects
    if datatype == rdf_langString:
        if language_code is None:
            raise ValueError('rdf:langString literals should have a language code')
        else:
            return RDFLangStringLiteral(lexical_form, language_code)
    if datatype == xsd_anyURI:
        return XSDAnyURILiteral(lexical_form)
    elif datatype == xsd_boolean:
        if lexical_form == 'true' or lexical_form == '1':
            return XSDBooleanLiteral(True)
        elif lexical_form == 'false' or lexical_form == '0':
            return XSDBooleanLiteral(False)
        else:
            raise ValueError('Invalid xsd:boolean lexical form: {}'.format(lexical_form))
    elif datatype == xsd_dateTime:
        match = _xsd_datetime_re.match(lexical_form)
        if match is None:
            raise ValueError('Invalid xsd:dateTime lexical form: {}'.format(lexical_form))
        return XSDDateTimeLiteral(int(match.group(1)), int(match.group(2)), int(match.group(3)),
                                  int(match.group(4)), int(match.group(5)), int(match.group(6)),
                                  _parse_timezone(match.group(8), 'xsd:dateTime'))
    elif datatype == xsd_date:
        match = _xsd_date_re.match(lexical_form)
        if match is None:
            raise ValueError('Invalid xsd:date lexical form: {}'.format(lexical_form))
        return XSDDateLiteral(int(match.group(1)), int(match.group(2)), int(match.group(3)),
                              _parse_timezone(match.group(4), 'xsd:date'))
    elif datatype == xsd_decimal:
        return XSDDecimalLiteral(Decimal(lexical_form))
    elif datatype == xsd_double:
        return XSDDoubleLiteral(float(lexical_form))  # TODO: parses everything?
    elif datatype == xsd_float:
        return XSDFloatLiteral(float(lexical_form))  # TODO: parses everything?
    elif datatype == xsd_gYearMonth:
        match = _xsd_date_re.match(lexical_form)
        if match is None:
            raise ValueError('Invalid xsd:gYear lexical form: {}'.format(lexical_form))
        return XSDGYearMonthLiteral(int(match.group(1)), int(match.group(2)),
                                    _parse_timezone(match.group(3), 'xsd:gYearMonth'))
    elif datatype == xsd_gYear:
        match = _xsd_date_re.match(lexical_form)
        if match is None:
            raise ValueError('Invalid xsd:gYear lexical form: {}'.format(lexical_form))
        return XSDGYearLiteral(int(match.group(1)), _parse_timezone(match.group(2), 'xsd:gYear'))
    elif datatype == xsd_integer:
        return XSDIntegerLiteral(int(lexical_form))
    elif datatype == xsd_time:
        match = _xsd_time_re.match(lexical_form)
        if match is None:
            raise ValueError('Invalid xsd:time lexical form: {}'.format(lexical_form))
        return XSDTimeLiteral(int(match.group(1)), int(match.group(2)), int(match.group(3)),
                              _parse_timezone(match.group(5), 'xsd:time'))
    elif datatype == xsd_string:
        return XSDStringLiteral(lexical_form)
    elif datatype == geo_wktLiteral:
        return GeoWKTLiteral(lexical_form)
    else:
        return UnknownLiteral(lexical_form, datatype)


class RDFLangStringLiteral(Literal):
    def __init__(self, string: str, language_tag: str):
        self._string = string
        self.language_tag = language_tag

    @property
    def lexical_form(self) -> str:
        return self._string

    @property
    def datatype(self) -> Datatype:
        return rdf_langString

    def to_jsonld(self) -> dict:
        return {
            '@language': self.language_tag,
            '@value': self.lexical_form
        }

    def __str__(self) -> str:
        return '{}@{}'.format(json.dumps(self.lexical_form), self.language_tag)

    def __eq__(self, other):
        return super.__eq__(self, other) and self.language_tag == other.language_tag

    def __hash__(self):
        return hash(self.lexical_form) ^ hash(self.language_tag)


class XSDAnyURILiteral(Literal):
    def __init__(self, uri: str):
        self._uri = uri

    @property
    def lexical_form(self) -> str:
        return self._uri

    @property
    def datatype(self) -> Datatype:
        return xsd_anyURI


class XSDBooleanLiteral(Literal):
    def __init__(self, value: bool):
        self.value = value

    @property
    def lexical_form(self) -> str:
        return 'true' if self.value else 'false'

    @property
    def datatype(self) -> Datatype:
        return xsd_boolean

    def __str__(self) -> str:
        return self.lexical_form


def _format_timezone(offset: Optional[int]) -> str:
    if offset is None:
        return ''
    elif offset == 0:
        return 'Z'
    else:
        '{:+02d}:{:02d}'.format(offset / 60, abs(offset) % 60)


def _timezone_to_python(offset: Optional[int]) -> Optional[timezone]:
    if offset is None:
        return None
    return timezone(timedelta(minutes=offset))


class XSDDateTimeLiteral(Literal):
    def __init__(self, year: int, month: int, day: int, hour: int, minute: int, second: int,
                 timezone_offset: Optional[int] = None):
        """
        :param timezone_offset: The timezone offset in minutes
        """
        self.year = year
        self.month = month
        self.day = day
        self.hour = hour
        self.minute = minute
        self.second = second
        self.timezone_offset = timezone_offset

    @property
    def lexical_form(self) -> str:
        return '{:04d}-{:02d}-{:02d}T{:02d}:{:02d}:{:02d}{}'.format(
            self.year, self.month, self.day, self.hour, self.minute, self.second,
            _format_timezone(self.timezone_offset))

    @property
    def datatype(self) -> Datatype:
        return xsd_dateTime

    @property
    def datetime(self) -> datetime:
        """
        :raise ValueError if not in datetime range
        """
        return datetime(self.year, self.month, self.day, self.hour, self.minute, self.second, 0,
                        _timezone_to_python(self.timezone_offset))


class XSDDateLiteral(Literal):
    def __init__(self, year: int, month: int, day: int, timezone_offset: Optional[int] = None):
        """
        :param timezone_offset: The timezone offset in minutes
        """
        self.year = year
        self.month = month
        self.day = day
        self.timezone_offset = timezone_offset

    @property
    def lexical_form(self) -> str:
        return '{:04d}-{:02d}-{:02d}{}'.format(self.year, self.month, self.day, _format_timezone(self.timezone_offset))

    @property
    def datatype(self) -> Datatype:
        return xsd_date

    @property
    def date(self) -> date:
        """
        :raise ValueError if not in date range
        """
        return date(self.year, self.month, self.day)


class XSDDecimalLiteral(Literal):
    def __init__(self, value: Decimal):
        self.value = value.normalize()

    @property
    def lexical_form(self) -> str:
        form = str(self.value)
        return form if '.' in form else form + '.'

    @property
    def datatype(self) -> Datatype:
        return xsd_decimal

    def __str__(self) -> str:
        return self.lexical_form


class XSDDoubleLiteral(Literal):
    def __init__(self, value: float):
        self.value = value

    @property
    def lexical_form(self) -> str:
        return str(self.value)

    @property
    def datatype(self) -> Datatype:
        return xsd_double


class XSDFloatLiteral(Literal):
    def __init__(self, value: float):
        self.value = value

    @property
    def lexical_form(self) -> str:
        return str(self.value)

    @property
    def datatype(self) -> Datatype:
        return xsd_float


class XSDGYearMonthLiteral(Literal):
    def __init__(self, year: int, month: int, timezone_offset: Optional[int] = None):
        """
        :param timezone_offset: The timezone offset in minutes
        """
        self.year = year
        self.month = month
        self.timezone_offset = timezone_offset

    @property
    def lexical_form(self) -> str:
        return '{:04d}-{:02d}{}'.format(self.year, self.month, _format_timezone(self.timezone_offset))

    @property
    def datatype(self) -> Datatype:
        return xsd_gYearMonth


class XSDGYearLiteral(Literal):
    def __init__(self, year: int, timezone_offset: Optional[int] = None):
        """
        :param timezone_offset: The timezone offset in minutes
        """
        self.year = year
        self.timezone_offset = timezone_offset

    @property
    def lexical_form(self) -> str:
        return '{:04d}{}'.format(self.year, _format_timezone(self.timezone_offset))

    @property
    def datatype(self) -> Datatype:
        return xsd_gYear


class XSDIntegerLiteral(Literal):
    def __init__(self, value: int):
        self.value = value

    @property
    def lexical_form(self) -> str:
        return str(self.value)

    @property
    def datatype(self) -> Datatype:
        return xsd_integer

    def __str__(self) -> str:
        return self.lexical_form


class XSDStringLiteral(Literal):
    def __init__(self, string: str):
        self._string = string

    @property
    def lexical_form(self) -> str:
        return self._string

    @property
    def datatype(self) -> Datatype:
        return xsd_string

    def __str__(self) -> str:
        return json.dumps(self._string)


class XSDTimeLiteral(Literal):
    def __init__(self, hour: int, minute: int, second: int, timezone_offset: Optional[int] = None):
        """
        :param timezone_offset: The timezone offset in minutes
        """
        self.hour = hour
        self.minute = minute
        self.second = second
        self.timezone_offset = timezone_offset

    @property
    def lexical_form(self) -> str:
        return '{:02d}:{:02d}:{:02d}{}'.format(self.hour, self.minute, self.second,
                                               _format_timezone(self.timezone_offset))

    @property
    def datatype(self) -> Datatype:
        return xsd_time

    @property
    def time(self) -> time:
        """
        :raise ValueError if not in time range
        """
        return time(self.hour, self.minute, self.second, 0, _timezone_to_python(self.timezone_offset))


class GeoWKTLiteral(Literal):
    def __init__(self, shape: Union[str, object, dict]):
        try:
            if isinstance(shape, str):
                self.shape = geometry.from_wkt(shape.upper())
            elif hasattr(shape, '__geo_interface__') or isinstance(shape, dict):
                self.shape = geometry.as_shape(shape)
            else:
                raise ValueError('GeoWKTLiteral could not parse {}'.format(shape))
        except NotImplementedError:
            raise ValueError('GeoWKTLiteral could not parse {}'.format(shape))

    @property
    def lexical_form(self) -> str:
        return self.shape.wkt

    @property
    def datatype(self) -> Datatype:
        return geo_wktLiteral


class UnknownLiteral(Literal):
    def __init__(self, lexical_form: str, datatype: Datatype):
        if datatype == rdf_langString:
            raise ValueError('rdf:langString should have a language tag')

        self._lexical_form = lexical_form
        self._datatype = datatype

    @property
    def lexical_form(self) -> str:
        return self._lexical_form

    @property
    def datatype(self) -> Datatype:
        return self._datatype


class Property(Entity):
    """
    Abstract parent for properties
    """

    def __init__(self, iri: str, types: Sequence[Class], domain: Class, range: Union[Class, Datatype]):
        super().__init__(iri, types)
        self.domain = domain
        self.range = range


class ObjectProperty(Property):
    def __init__(self, iri: str, domain: Class = owl_Thing, range: Class = owl_Thing):
        super().__init__(iri, (rdf_Property, owl_ObjectProperty), domain, range)


class DatatypeProperty(Property):
    def __init__(self, iri: str, domain: Class = owl_Thing, range: Datatype = rdfs_Literal):
        super().__init__(iri, (rdf_Property, owl_DatatypeProperty), domain, range)
