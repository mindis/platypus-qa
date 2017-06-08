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
from decimal import Decimal

from typing import Sequence, Union, Optional

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
        raise ValueError('Entity.score is not implemented')

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


class NamedIndividual(Entity):
    def __init__(self, iri, types: Sequence['Class'] = (owl_Thing,)):
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
xsd_decimal = Datatype('http://www.w3.org/2001/XMLSchema#decimal', (rdfs_Literal, platypus_numeric))
xsd_double = Datatype('http://www.w3.org/2001/XMLSchema#double', (rdfs_Literal, platypus_numeric))
xsd_duration = Datatype('http://www.w3.org/2001/XMLSchema#duration', (rdfs_Literal,))
xsd_float = Datatype('http://www.w3.org/2001/XMLSchema#float', (rdfs_Literal, platypus_numeric))
xsd_integer = Datatype('http://www.w3.org/2001/XMLSchema#integer', (rdfs_Literal, platypus_numeric, xsd_decimal))
xsd_string = Datatype('http://www.w3.org/2001/XMLSchema#string', (rdfs_Literal,))
xsd_dateTime = Datatype('http://www.w3.org/2001/XMLSchema#dateTime', (rdfs_Literal, platypus_calendar))
xsd_date = Datatype('http://www.w3.org/2001/XMLSchema#date', (rdfs_Literal, platypus_calendar))
xsd_gYearMonth = Datatype('http://www.w3.org/2001/XMLSchema#gYearMonth', (rdfs_Literal, platypus_calendar))
xsd_gYear = Datatype('http://www.w3.org/2001/XMLSchema#gYear', (rdfs_Literal, platypus_calendar))
geo_wktLiteral = Datatype('http://www.opengis.net/ont/geosparql#wktLiteral', (rdfs_Literal,))


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


def build_literal(lexical_form: str, datatype: Optional[Datatype] = None, language_code: Optional[str] = None):
    if language_code is not None:
        if datatype is not None and datatype != rdf_langString:
            raise ValueError('Literals with language code must have the rdf:langString datatype')
        return RDFLangStringLiteral(lexical_form, language_code)
    elif datatype is None or datatype == xsd_string:
        return XSDStringLiteral(lexical_form)
    else:
        return UnknownLiteral(lexical_form, datatype)  # TODO: improve


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
        self._value = value

    @property
    def lexical_form(self) -> str:
        return 'true' if self._value else 'false'

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


class XSDDecimalLiteral(Literal):
    def __init__(self, value: Decimal):
        self._value = value.normalize()

    @property
    def lexical_form(self) -> str:
        form = str(self._value)
        return form if '.' in form else form + '.'

    @property
    def datatype(self) -> Datatype:
        return xsd_decimal

    def __str__(self) -> str:
        return self.lexical_form


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
        self._value = value

    @property
    def lexical_form(self) -> str:
        return str(self._value)

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
