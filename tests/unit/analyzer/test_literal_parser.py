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

import unittest

from platypus_qa.analyzer.literal_parser import parse_literal
from platypus_qa.database.formula import Type
from platypus_qa.database.owl import rdf_langString, RDFLangStringLiteral, xsd_string, XSDStringLiteral, XSDDateLiteral, \
    XSDGYearMonthLiteral, platypus_calendar, XSDGYearLiteral, xsd_date, xsd_dateTime, XSDDateTimeLiteral, xsd_gYearMonth


class LiteralParserTest(unittest.TestCase):
    def test_parse_literal(self):
        self.assertListEqual(
            parse_literal('foo', 'en', Type.from_entity(rdf_langString)),
            [RDFLangStringLiteral('foo', 'en')]
        )
        self.assertListEqual(
            parse_literal('foo', 'en', Type.from_entity(xsd_string)),
            [XSDStringLiteral('foo')]
        )
        self.assertListEqual(
            parse_literal('1931', 'en', Type.from_entity(platypus_calendar)),
            [XSDGYearLiteral(1931), XSDGYearMonthLiteral(1931, 0), XSDDateLiteral(1931, 0, 0),
             XSDDateTimeLiteral(1931, 0, 0, 0, 0, 0)]
        )
        self.assertListEqual(
            parse_literal('June 1931', 'en', Type.from_entity(xsd_gYearMonth)),
            [XSDGYearMonthLiteral(1931, 6)]
        )
        self.assertListEqual(
            parse_literal('June 1931, 1st', 'en', Type.from_entity(xsd_date)),
            [XSDDateLiteral(1931, 6, 1)]
        ),
        self.assertListEqual(
            parse_literal('June 1931, 1st', 'en', Type.from_entity(xsd_dateTime)),
            [XSDDateTimeLiteral(1931, 6, 1, 0, 0, 0)]
        ),
        self.assertListEqual(
            parse_literal('June 1931, 1st', 'en', Type.from_entity(xsd_date) | Type.from_entity(xsd_string)),
            [XSDStringLiteral('June 1931, 1st'), XSDDateLiteral(1931, 6, 1)]
        )
