__author__ = 'jieg'

from flask import Flask
from flask import request
from flask import Response
from datetime import timedelta
from flask import make_response, current_app
from functools import update_wrapper
import logging
import json

from integration import Integrator
from integration import local_solr_server
from integration import remote_solr_server
from integration import IntegrationException
from IndustryTermRecogniser import IndustryTermRecogniser

import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__)))

basestring = (str, bytes)

app = Flask(__name__)

integration = Integrator()

_logger = logging.getLogger("IntegrationService")


def crossdomain(origin=None, methods=None, headers=None,
                max_age=21600, attach_to_all=True,
                automatic_options=True):
    if methods is not None:
        methods = ', '.join(sorted(x.upper() for x in methods))
    if headers is not None and not isinstance(headers, basestring):
        headers = ', '.join(x.upper() for x in headers)
    if not isinstance(origin, basestring):
        origin = ', '.join(origin)
    if isinstance(max_age, timedelta):
        max_age = max_age.total_seconds()

    def get_methods():
        if methods is not None:
            return methods

        options_resp = current_app.make_default_options_response()
        return options_resp.headers['allow']

    def decorator(f):
        def wrapped_function(*args, **kwargs):
            if automatic_options and request.method == 'OPTIONS':
                resp = current_app.make_default_options_response()
            else:
                resp = make_response(f(*args, **kwargs))
            if not attach_to_all and request.method != 'OPTIONS':
                return resp

            h = resp.headers

            h['Access-Control-Allow-Origin'] = origin
            h['Access-Control-Allow-Methods'] = get_methods()
            h['Access-Control-Max-Age'] = str(max_age)
            if headers is not None:
                h['Access-Control-Allow-Headers'] = headers
            return resp

        f.provide_automatic_options = False
        return update_wrapper(wrapped_function, f)

    return decorator


@app.route('/batchProcessing', methods=['POST'])
@crossdomain(origin='*')
def batch_processing_documents():
    _logger.info("start batch processing integration service for indexing and tagging documents...")

    isError = False
    error_message = ""
    results = {'success': True}

    try:
        integration.batch_processing_product_issue_attachments()
    except IntegrationException as integrationErr:
        isError = True
        error_message = "Error while indexing documents: " + str(integrationErr)
        _logger.error("error in integrationService:"+error_message)
    except Exception as error:
        isError = True
        error_message = "Error while indexing documents: " + str(error)
        _logger.error("error in integrationService:"+error_message)

    _logger.info("complete indexing documents from remote server:"+remote_solr_server)

    if not isError:
        _logger.info("start tagging documents in local server:"+local_solr_server)
        try:
            trTagger = IndustryTermRecogniser(local_solr_server)
            trTagger.terminology_tagging()

        except Exception as error:
            isError = True
            error_message = "Error while tagging documents: " + str(error)
            _logger.error(error_message)


        _logger.info("complete tagging documents indexed in local server:"+local_solr_server)

    if isError:
        results['success'] = False
        results['reason'] = error_message
        resp = Response(json.dumps(results), status=202, mimetype='application/json')
    else:
        resp = Response(json.dumps(results), status=200, mimetype='application/json')

    return resp


def shutdown_server():
    func = request.environ.get('werkzeug.server.shutdown')
    if func is None:
        _logger.error('Not running with the Werkzeug Server')
        raise RuntimeError('Not running with the Werkzeug Server')
    func()


@app.route('/shutdown', methods=['GET', 'POST'])
def shutdown():
    shutdown_server()
    _logger.info('Server shutting down...')
    return 'Server shutting down...'


if __name__ == '__main__':
    import logging.config

    logging.config.fileConfig(os.path.join(os.path.dirname(__file__), '..', 'config', 'logging.conf'))

    app.run(host="localhost", port=8083, debug=True, threaded=True)
    # app.run(host="oakanalysis.shef.ac.uk", port=8083, debug=False, processes=3)
