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
from typing import List

from dateparser import DateDataParser

from platypus_qa.database.formula import Type
from platypus_qa.database.owl import Literal, rdf_langString, RDFLangStringLiteral, xsd_string, XSDStringLiteral, \
    XSDDateTimeLiteral, XSDDateLiteral, XSDGYearMonthLiteral, XSDGYearLiteral, xsd_dateTime, xsd_gYear, xsd_gYearMonth, \
    xsd_date

_logger = logging.getLogger('literal_parser')


def parse_literal(text: str, language_code: str, expected_type: Type) -> List[Literal]:
    results = []
    if expected_type >= rdf_langString:
        results.append(RDFLangStringLiteral(text, language_code))
    if expected_type >= xsd_string:
        results.append(XSDStringLiteral(text))

    # calendar
    date_data = DateDataParser(languages=[language_code], allow_redetect_language=True).get_date_data(text)
    period = date_data['period']
    date = date_data['date_obj']
    if date is not None:
        timezone_offset = None
        if date.tzinfo is not None:
            timezone_offset = date.tzinfo.utcoffset
        if period == 'second':
            if expected_type >= xsd_dateTime:
                results.append(XSDDateTimeLiteral(date.year, date.month, date.day, date.hour, date.minute, date.second,
                                                  timezone_offset))
        elif period == 'day':
            if expected_type >= xsd_date:
                results.append(XSDDateLiteral(date.year, date.month, date.day, timezone_offset))
            if expected_type >= xsd_dateTime:
                results.append(XSDDateTimeLiteral(date.year, date.month, date.day, 0, 0, 0, timezone_offset))
        elif period == 'month':
            if expected_type >= xsd_gYearMonth:
                results.append(XSDGYearMonthLiteral(date.year, date.month, timezone_offset))
            if expected_type >= xsd_date:
                results.append(XSDDateLiteral(date.year, date.month, 0, timezone_offset))
            if expected_type >= xsd_dateTime:
                results.append(XSDDateTimeLiteral(date.year, date.month, 0, 0, 0, 0, timezone_offset))
        elif period == 'year':
            if expected_type >= xsd_gYear:
                results.append(XSDGYearLiteral(date.year, timezone_offset))
            if expected_type >= xsd_gYearMonth:
                results.append(XSDGYearMonthLiteral(date.year, 0, timezone_offset))
            if expected_type >= xsd_date:
                results.append(XSDDateLiteral(date.year, 0, 0, timezone_offset))
            if expected_type >= xsd_dateTime:
                results.append(XSDDateTimeLiteral(date.year, 0, 0, 0, 0, 0, timezone_offset))
        else:
            _logger.info('LiteralParser does not support dateparser precision {}'.format(period))

    return results
