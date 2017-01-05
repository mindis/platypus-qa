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

from flask import Flask, request
from flask import redirect
from flask.json import jsonify
from flask_cors import CORS
from flask_swaggerui import build_static_blueprint, render_swaggerui
from ppp_datamodel import Request
from ppp_datamodel.exceptions import AttributeNotProvided
from werkzeug.exceptions import BadRequest

from platypus_qa.request_handler import PPPRequestHandler, WikidataSparqlHandler

logging.basicConfig(level=logging.INFO)

# Flask setup
_flask_app = Flask(__name__)
_flask_app.config['JSONIFY_PRETTYPRINT_REGULAR'] = False
CORS(_flask_app)
_wikidata_sparql_handler = WikidataSparqlHandler()


@_flask_app.route('/', methods=['GET', 'POST'])
def root():
    if request.method == 'GET':
        return redirect('/v0')

    try:
        ppp_request = Request.from_dict(request.get_json(force=True))
    except ValueError:
        raise BadRequest('Data is not valid JSON.')
    except KeyError:
        raise BadRequest('Missing mandatory field in request object.')
    except AttributeNotProvided as exc:
        raise BadRequest('Attribute not provided: %s.' % exc.args[0])

    return jsonify([x.as_dict() for x in PPPRequestHandler(ppp_request).answer()])


@_flask_app.route('/v0/wikidata-sparql', methods=['GET'])
def wikidata_sparql():
    return _wikidata_sparql_handler.build_sparql()


@_flask_app.route('/v0')
def v0root():
    return render_swaggerui(swagger_spec_path='/v0/swagger.json')


@_flask_app.route('/v0/swagger.json')
def spec():
    return jsonify({
        'swagger': '2.0',
        'info': {
            'version': 'dev',
            'title': 'Platypus question answering API',
        },
        'host': 'qa.dev.askplatyp.us',
        'basePath': '/v0',
        'paths': {
            '/wikidata-sparql': {
                'get': {
                    'summary': 'Builds a SPARQL query from a natural language question',
                    'parameters': [
                        {
                            'name': 'q',
                            'in': 'query',
                            'description': 'The question.',
                            'required': True,
                            'type': 'string',
                            'x-example': 'Who are Wikidata\'s developpers?'
                        },
                        {
                            'name': 'lang',
                            'in': 'query',
                            'description': 'The language code of the question like "en" or "fr". If "und", the language is guessed.',
                            'required': False,
                            'type': 'string',
                            'default': 'und'
                        }
                    ],
                    'produces': [
                        'application/sparql-query'
                    ],
                    'responses': {
                        '200': {
                            'description': 'The SPARQL creation succeded.'
                        },
                        '400': {
                            'description': 'The "q" parameter have not been set.'
                        },
                        '404': {
                            'description': 'Platypus is not able to build SPARQL for this query'
                        }
                    }
                }
            }
        }
    })


_flask_app.register_blueprint(build_static_blueprint('swaggerui', __name__))

_flask_app.run(port=8000)
