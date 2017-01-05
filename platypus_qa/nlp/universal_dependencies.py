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

from enum import Enum, unique


@unique
class UDPOSTag(str, Enum):
    ADJ = 'ADJ'  # adjective
    ADP = 'ADP'  # adposition
    ADV = 'ADV'  # adverb
    AUX = 'AUX'  # auxiliary verb
    CONJ = 'CONJ'  # coordinating conjunction
    DET = 'DET'  # determiner
    INTJ = 'INTJ'  # interjection
    NOUN = 'NOUN'  # noun
    NUM = 'NUM'  # numeral
    PART = 'PART'  # particle
    PRON = 'PRON'  # pronoun
    PROPN = 'PROPN'  # proper noun
    PUNCT = 'PUNCT'  # punctuation
    SCONJ = 'SCONJ'  # subordinating conjunction
    SYM = 'SYM'  # symbol
    VERB = 'VERB'  # verb
    X = 'X'  # other

    @staticmethod
    def from_str(string: str):
        return UDPOSTag[string.upper()]

    def __str__(self):
        return self.value


@unique
class UDDependency(Enum):
    """
    Dependencies. We define the order operator in order to allow to easily match on extended dependencies e.g. acl_relcl <= acl.
    """
    acl = ('acl',)  # clausal modifier of noun (adjectival clause)
    advcl = ('advcl',)  # adverbial clause modifier
    advmod = ('advmod',)  # adverbial modifier
    amod = ('amod',)  # adjectival modifier
    appos = ('appos',)  # appositional modifier
    aux = ('aux',)  # auxiliary
    auxpass = ('auxpass',)  # passive auxiliary
    case = ('case',)  # case marking
    cc = ('cc',)  # coordinating conjunction
    ccomp = ('ccomp',)  # clausal complement
    compound = ('compound',)  # compound
    conj = ('conj',)  # conjunct
    cop = ('cop',)  # copula
    csubj = ('csubj',)  # clausal subject
    csubjpass = ('csubjpass',)  # clausal passive subject
    dep = ('dep',)  # unspecified dependency
    det = ('det',)  # determiner
    discourse = ('discourse',)  # discourse element
    dislocated = ('dislocated',)  # dislocated elements
    dobj = ('dobj',)  # direct object
    expl = ('expl',)  # expletive
    foreign = ('foreign',)  # foreign words
    goeswith = ('goeswith',)  # goes with
    iobj = ('iobj',)  # indirect object
    list = ('list',)  # list
    mark = ('mark',)  # marker
    mwe = ('mwe',)  # multi-word expression
    name = ('name',)  # name
    neg = ('neg',)  # negation modifier
    nmod = ('nmod',)  # nominal modifier
    nsubj = ('nsubj',)  # nominal subject
    nsubjpass = ('nsubjpass',)  # passive nominal subject
    nummod = ('nummod',)  # numeric modifier
    parataxis = ('parataxis',)  # parataxis
    punct = ('punct',)  # punctuation
    remnant = ('remnant',)  # remnant in ellipsis
    reparandum = ('reparandum',)  # overridden disfluency
    root = ('root',)  # root
    vocative = ('vocative',)  # vocative
    xcomp = ('xcomp',)  # open clausal complement

    # extensions
    acl_relcl = ('acl', 'relcl')  # en, fr,
    cc_preconj = ('cc', 'preconj')  # en
    compound_prt = ('compound', 'prt')  # en
    det_predet = ('det', 'predet')  # en
    nmod_npmod = ('nmod', 'npmod')  # en
    nmod_poss = ('nmod', 'poss')  # en, fr
    nmod_tmod = ('nmod', 'tmod')  # en

    def __ge__(self, other: 'UDDependency'):
        return len(self.value) <= len(other.value) and self.value == other.value[:len(self.value)]

    def __gt__(self, other: 'UDDependency'):
        return len(self.value) < len(other.value) and self.value == other.value[:len(self.value)]

    def __str__(self):
        return ':'.join(self.value)

    @staticmethod
    def from_str(string: str):
        return UDDependency[string.lower().replace(':', '_')]
