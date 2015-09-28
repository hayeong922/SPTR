#!/bin/sh
curl http://localhost:8983/solr/tatasteel/update -F stream.body=' <optimize />'