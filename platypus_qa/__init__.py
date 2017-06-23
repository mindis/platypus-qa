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

from platypus_qa.database.wikidata import WikidataKnowledgeBase
from platypus_qa.nlp.core_nlp import CoreNLPParser
from platypus_qa.nlp.spacy import SpacyParser
from platypus_qa.nlp.syntaxnet import SyntaxNetParser
from platypus_qa.qa import QAHandler
from platypus_qa.samples import SAMPLE_QUESTIONS

CoreNLPParser = CoreNLPParser
SpacyParser = SpacyParser
SyntaxNetParser = SyntaxNetParser
WikidataKnowledgeBase = WikidataKnowledgeBase
SAMPLE_QUESTIONS = SAMPLE_QUESTIONS
QAHandler = QAHandler
