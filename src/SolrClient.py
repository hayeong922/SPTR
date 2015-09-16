'''
Copyright &copy;2015 Sheffield University (OAK Group)
All Rights Reserved.

Developer(s):
   Jie Gao (j.gao@sheffield.ac.uk)

@author: jieg
'''
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from urllib.parse import urlencode
from urllib.parse import urljoin, urlsplit
import json
import re

from util import TermUtil
import requests
from httplib2 import Http

DATETIME_REGEX = re.compile('^(?P<year>\d{4})-(?P<month>\d{2})-(?P<day>\d{2})T(?P<hour>\d{2}):(?P<minute>\d{2}):(?P<second>\d{2})(\.\d+)?Z$')
ER_RE = re.compile ('<pre>(.|\n)*?</pre>')

class Results(object):
    def __init__(self, response=None,decoder=None):
        self.decoder = decoder or json.JSONDecoder()
        if not response:
            self.result = {}
        else:
            self.result =  self.decoder.decode(response)
        
        self.highlighting = {}
        self.facets = {}
        self.spellcheck = {}
        self.matches = {}
        self.interesting_terms = {}
        self.response = response
            
        if self.result.get('highlighting'): # highlighting
            self.highlighting = self.result['highlighting']
        
        if self.result.get('facet_counts'):
            self.facets = self.result['facet_counts']
        
        if self.result.get('spellcheck'):
            self.spellcheck = self.result['spellcheck']
    
        if self.result.get('interestingTerms'):
            self.interesting_terms = self.result["interestingTerms"]
        
        if self.result.get('match',{}).get('docs'):
            self.matches = self.result['match']['docs']

        response = self.result.get('response')
        if response:
            self.docs = response['docs']
            self.hits = response['numFound']
        else:
            self.docs, self.hits = ([],0)
    
    def __len__(self):
        return len(self.docs)

    def __iter__(self):
        return iter(self.docs)

class GroupedResults(object):
    def __init__(self, response=None,decoder=None):
        self.decoder = decoder or json.JSONDecoder()
        self.result = self.decoder.decode(response)

        grouped_response = self.result.get('grouped')
        docs = {}
        for name,res in grouped_response.iteritems():
            r = Results()
            r.docs = res.get('doclist',{}).get('docs')
            r.hits = res.get('doclist',{}).get('numFound')
            docs[name] = r
                                       
        self.docs = docs
                    
    def __iter__(self):
        return iter(self.docs)


class TermVectorResult(object):
    '''
    return TermVectorResult
    
    TermVectorResult.tv(uniqueKeyFieldName, warnings, **docIds(uniqueKey, **field(**term(tf-idf,df,positions(position),tf,offsets(start,end)))) )
    TermVectorResult.docs(id,resourcename,content_type[],content[])
    
    '''
    def __init__(self,field,response=None,decoder=None):
        self.decoder = decoder or json.JSONDecoder()
        
        #result = self.decoder.decode(response.decode("utf-8"))
        result = response
        
        #print("result", result)        
        # term vectors from /tvrh
        if 'termVectors' in result:
            tv = result['termVectors']
            
            self.tv = nested_list2dict(tv)
                        
        self.docs = result['response']['docs']
    
    def __len__(self):
        return len(self.docs)

    def __iter__(self):
        return iter(self.docs)
    
class SolrClient(object):
    '''
    Example from https://github.com/Parsely/python-solr/blob/master/pythonsolr/pysolr.py
    '''
    solrURL="http://localhost:8983/solr/tatasteel"
    
    def __init__(self, server_url, decoder=None, timeout=60,result_class=Results,use_cache=None,cache=None):
        self.decoder = decoder or json.JSONDecoder()        
        self.solrURL = server_url
        self.scheme, netloc, path, query, fragment = urlsplit(server_url)
        netloc = netloc.split(':')
        self.host = netloc[0]
        if len(netloc) == 1:
            self.host, self.port = netloc[0], None
        else:
            self.host, self.port = netloc            
        
        self.path = path.rstrip('/')
        self.timeout=timeout
        self.result_class = result_class
        
        if use_cache:
            self.http = Http(cache=cache or ".cache",timeout=self.timeout)
        else:
            self.http = Http(timeout=self.timeout)
    
    def load_documents(self, start=0, rows=10):
        '''
        load/fetch indexed documents (& stored metadata) in a range (start, rows)
        start: $page_number
        rows: $rows_per_page
        
        return documents {'docs'[],'numFound','start' }
        '''
        params = {'q': '*:*', 'start':start, 'rows':rows}
        params['wt'] = 'json' # specify json encoding of results
        path = '%s/select?%s' % (self.path, urlencode(params, True))
        
        response = self._send_request('GET', path)
        
        return response['response']
    
    def batch_update_documents(self, docs, commit=True):
        '''
        batch update documents
        
        docs: documment object set in dict json format
        '''
        
        docs = json.dumps(docs, ensure_ascii=False).encode(encoding='utf_8')        
        
        params={'commit':'true' if commit else 'false'}
        val_headers= {"Content-type": "application/json"}
        path = '%s/update/json?%s' % (self.path, urlencode(params, True))
        
        response = self._send_request('POST', path, data=docs, headers=val_headers)
        
        '''
        import pysolr
        solr = pysolr.Solr(self.solrURL, timeout=10)
        response = solr.add(docs, commit=commit)
        '''
        #{'responseHeader': {'status': 0, 'QTime': 115}}
        return response
    
    def total_document_size(self):
        result = self.load_documents(rows=0)
        return result['numFound']
    
    def term_vectors(self,q,field=None,**kwargs):
        params = {'q': q or '','tv.all':'true' }
        if field:
            params['tv.fl'] = field
            
        params.update(**kwargs)
        
        response = self._tvrh(params)
        return TermVectorResult(field,response)
    
    def terms_query_longer_terms(self, field, subterm):
        '''
        This function uses Solr Terms Component to query longer terms indexed in the [field] matched with a [sub-term] expression.
        
        return terms (dictionary) list with df values
        
        http://localhost:8983/solr/tatasteel/terms?terms.fl=content&terms.regex=^(.*?(\bsurface%20defects\b)[^$]*)$&terms.regex.flag=case_insensitive&terms.sort=count&terms.limit=10000
        '''
        longerTerms={}
        
        return longerTerms
    
    def totaltermfreq(self,field, terms={}):
        '''
        This function uses Solr ttf functionQuery to total term (ngram) frequency in whole index
        
        Can support multiple terms per request
        if mutiple terms is requested, the result may return less result than requested as only normalised term will be returned.
        param:
            field, indexed term (lower case + hyphen normalised) to query
            terms, a set of terms to query total frequency from the 'field'
        return dict, term ttf dictionary with normalised term as key and ttf as value
        '''
        max_terms_per_request=10
        terms=list(terms)
        
        resultSet={}
        for next_cursor in range(0, len(terms), max_terms_per_request):
            current_terms = terms[next_cursor:next_cursor+max_terms_per_request]
            
            params={'q':'*:*','fl':','.join(['ttf(%s,\'%s\')'%(field,TermUtil.normalise(term)) for term in current_terms])}
                    
            params['q'] = self._encode_q(params['q'])
            params['rows']=1
            params['wt'] = 'json' # specify json encoding of results
            path = '%s/select?%s' % (self.path, urlencode(params, True))
            #print(path)
            response = self._send_request('GET', path)
            
            #self.decoder = json.JSONDecoder()        
            #result = self.decoder.decode(response.decode("utf-8"))
            #result=result['response']['docs']
            result=response['response']['docs']
            resultSet.update(result[0])
            
            #return list(result[0].values())[0]
        return dict([(k.replace('ttf(%s,\''%field,'').replace('\')',''),v) for k, v in resultSet.items()])
    
    def field_terms(self, fieldname):
        """Yields all term values (converted from on-disk bytes) in the given
        field.
        return dictionary, term dictionary with term name as key and document frequency as value
        """
        #'terms.sort':'count', 
        params={'terms.fl':fieldname,'terms.limit':-1}
        params['wt'] = 'json'
        path = '%s/terms?%s' % (self.path, urlencode(params, True))
        
        response=self._send_request('GET', path)
        
        all_terms=response['terms'][fieldname]
        return list2dict(all_terms)
        
    def _send_request(self, method, path, data=None, headers=None):
        '''
        return response: requests.models.Response.json()
        '''
        url = self.solrURL.replace(self.path, '')
        response = requests.request(method=method, url=urljoin(url, path),headers=headers,data=data)
        
        if response.status_code not in (200, 304):
            raise SolrError(self._extract_error(headers, response.reason))
        
        return response.json()
    
    def _extract_error(self, headers, response):
        """
        Extract the actual error message from a solr response. Unfortunately,
        this means scraping the html.
        """
        #print("response:", response)
        reason = ER_RE.search(response)
        if reason:
            reason = reason.group()
            reason = reason.replace('<pre>','')
            reason = reason.replace('</pre>','')
            return "Error: %s" % str(reason)
        return "Error: %s" % response
        
    def _tvrh(self, params):
        # encode the query as utf-8 so urlencode can handle it
        params['q'] = self._encode_q(params['q'])
        params['wt'] = 'json' # specify json encoding of results
        path = '%s/tvrh?%s' % (self.path, urlencode(params, True))
        #print(path)
        return self._send_request('GET', path)
    
    def _encode_q(self,qarg):
        if type(qarg) == list:
            return [q.encode('utf-8') for q in qarg]
        else:
            return qarg.encode('utf-8')

class SolrError(Exception):
    pass
    

def list2dict(data):
    # convert : [u'tf', 1, u'df', 2, u'tf-idf', 0.5]
    # to a dict
    stop = len(data)
    keys = [data[i] for i in range(stop) if i%2==0]
    values = [data[i] for i in range(stop) if i%2==1]
    if keys[0] == 'start' or keys[0] == 'position':
        #for positions, offsets
        listOfDict=[]
        kv_tuples=list(zip(keys,values))
        for i in range(0,len(kv_tuples),2):
            listOfDict.append(dict(kv_tuples[i:i+2]))
        return listOfDict              
    else:
        return dict(list(zip(keys,values)))

def nested_list2dict(data):
    d = list2dict(data)
    #print("d:",d)
    if isinstance(d, dict):
        for k, v in d.items():
            if isinstance(v, list):
                v = nested_list2dict(v)
                
            d[k] = v
    return d
        
def test_term_vectors():
    tatasteelClient = SolrClient("http://localhost:8983/solr/tatasteel")
    params = dict()
    params['fl']="id,content"
    params['start']=0
    params['rows']=1
    
    result= tatasteelClient.term_vectors("\"max P levels\"", field="content", start=0,rows=1)
    print("TermVectors: ", result.tv)
    print(result.docs[0]['id'])
    print(result.docs[0]['content'])
    print(result.tv[result.docs[0]['id']])

def test_totaltermfreq():
    tatasteelClient = SolrClient("http://localhost:8983/solr/tatasteel")
    #term_candidates={'U.S.A.', 'V', 'Longitudinal S prints', 'S prints', 'transverse', 'area', 'strand', 'extends', 'Sollac', 'cast', 'Lucchini', 'MSM', 'drops', 'total thickness', 'side', 'country', 'Routine', 'Unimetal blooms', 'B219 steel code', 'B214', 'image', 'Saarstahl', 'light ic', '3rd HP rail Sequence', 'Grade', 'bloom format', 'format', 'cl Grade', 'martyn', 'Andrew Clark', 'scanner', 'final US rate'}
    #term_candidates={'SCP', 'Chase water', 'Submerged opening trials', 'Monitor', 'UT defects', 'Send', 'DG', 'Decarb samples', 'Invite Mark Taylor', 'scheduling SK casts', 'AC', 'MSM Supply', 'performance List', 'Investigate possibility', 'Water modelling', 'KW', 'Re-brief shift Techs', 'action Potential', 'Rota', 'Agree UT spreadsheet conclusions', 'SK systems', 'Progress', 'CC5', 'Ladle', 'Porous plug', 'HP UT performance', 'Update', 'HP', 'crane rail Feedback', 'UT analysis', 'Graph', 'ST info', 'Action', 'Ladle lids Stop period', 'CC4', 'N', 'Continue', 'Send Sulphur print failure info', 'EN', 'SK', 'Accelerometer', 'Trial bloom', 'HP Rail casting Fog', 'meet Amepa insufficient ladles', 'Rail Cleanness Group meetings', 'Circulate', 'HP UT', 'Future trials', 'September Now', 'ST', 'Caster', 'Status','CRF Strand effect', 'JB Strand effect', 'CH defect', 'Liason Group', 'Data', 'ongoing Rail Actions', 'CWJs office', 'JB', 'JB UT', 'CH defects', 'DB', 'MO Bloom length', 'S', 'Exercise', 'CH rails', 'CRF Relationship', 'Mike Orr', 'Teesside', 'CRF', 'JB Side crack', 'SCP', 'Chase water', 'Submerged opening trials', 'Monitor', 'UT defects', 'Send', 'DG', 'Decarb samples', 'Invite Mark Taylor', 'scheduling SK casts', 'AC', 'MSM Supply', 'performance List', 'Investigate possibility', 'Water modelling', 'KW', 'Re-brief shift Techs', 'action Potential', 'Rota', 'Agree UT spreadsheet conclusions', 'SK systems', 'Progress', 'CC5', 'Ladle', 'Porous plug', 'HP UT performance', 'Update', 'HP', 'crane rail Feedback', 'UT analysis', 'Graph', 'ST info', 'Action', 'Ladle lids Stop period', 'CC4', 'N', 'Continue', 'Send Sulphur print failure info', 'EN', 'SK', 'Accelerometer', 'Trial bloom', 'HP Rail casting Fog', 'meet Amepa insufficient ladles', 'Rail Cleanness Group meetings', 'Circulate', 'HP UT', 'Future trials', 'September Now', 'ST', 'Caster', 'Status', 'SCP', 'BAD CUT', 'Bloom Identities Cast No', 'Andrew Alert Code P', 'SURFACE', 'blooms Alert Code P', 'Hinge crack grade', 'Hydris', 'Rail Steel Campaign', 'Pin', 'Cast No', 'Campaign', 'BLOOMS SCRAPPED AT SCUNTHORPE Bloom', 'Seq Posn', 'SENs', 'Hinge Crack Grade', 'Cast', 'Hayange Supply', 'Y', 'final H2', 'Alert Code T P', 'Calculated H2', 'Te H2', 'Quality', 'worse Bloom Identities Cast No', 'Hinge', 'Strand', 'Hood Cooled', 'Bloom', 'N', 'Alert Code P', 'C', 'Max', 'Hayange casts', 'Denis', 'L'}
    #term_candidates={'leader-primary steelmaking', 'off-bos', 'post-hood cooling', 'manganese-alumino-silicates', 'manganese-silicates', 'break-out location', 'pre-heat process', 'non-metallic inclusions', 'break-out', 'harsco shift co-ordinator', 'shift co-ordinator', 'jean-michel', 're-oxidation product', 'non-conforming material', 'slabyard shift co-ordinator', 'non-conforming items', 'as-cast bloom', 'non-conformity', 'jean-luc perrin', 'tundish-after c', 'back-end blooms', 'team leader-primary steelmaking', 'non-rail', 're-brief shift techs', 'non-ends', 'break-out report', 'put-up temperatures', 'macro-inclusions', 'm-ems', 'two-sample t', 'jean-michel leduc', 'co-ordinator', 'x-ray', 'analytical non-conformity', 'k-factor', 's-prints', 'non-branded side gauge corner', 'slag carry-over', 'occasional manganese-alumino-silicates', 'centre-line segregation', 'v-ratio', 'tundish set-up'}
    term_candidates={'leader-primary steelmaking'}
    print("size of requested term candidates:", len(term_candidates))
    response = tatasteelClient.totaltermfreq("content", term_candidates)
    print(response)
    print("response size:", len(response))

def test_load_documents():
    tatasteelClient = SolrClient("http://localhost:8983/solr/tatasteel")
    
    totalDocSize = tatasteelClient.total_document_size()
    print("totalDocSize:", totalDocSize)
    
    '''
    #pagination algorithm to load all the documents
    rows=10
    test_doc_size=0
    for nextCursor in range(0, totalDocSize, rows):        
        result = tatasteelClient.load_documents(nextCursor, rows)
        docs = result['docs']
        test_doc_size+=len(docs)
    print("test doc size:", test_doc_size)
    '''
    
    result = tatasteelClient.load_documents(0, 1)
    docs = result['docs']
    print(docs[0])

def test_doc(doc):
    doc['test_s']='test_termXXX'
    return doc
    
def test_batch_update_json_docs():
    tatasteelClient = SolrClient("http://localhost:8983/solr/tatasteel")
    result = tatasteelClient.load_documents(0, 2)
    docs = result['docs']
    
    docs = [test_doc(doc) for doc in docs]
    
    print(docs)
    response = tatasteelClient.batch_update_documents(docs)
    print(response)
    
def test_field_terms():
    tatasteelClient = SolrClient("http://localhost:8983/solr/tatasteel")
    
    all_terms = tatasteelClient.field_terms('term_candidates_ss')
    print(all_terms)
    print(len(all_terms))
    
    
if __name__ == '__main__':
    
    #test_term_vectors()
    #test_load_documents()
    #test_batch_update_json_docs()
    test_totaltermfreq()
    #test_field_terms()