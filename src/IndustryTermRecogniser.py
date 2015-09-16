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

import logging
import configparser

from SolrClient import SolrClient
from TaggingProcessor import TaggingProcessor
from util import TermUtil

import math
from multiprocPool import MultiprocPool

class IndustryTermRecogniser(object):
    '''
    This class perform industry term recognition based on apache solr
    
    '''
    def __init__(self, solr_url):
        
        self._logger=logging.getLogger(__name__)
        config = configparser.ConfigParser()
        configFile=config.read(os.path.join(os.path.dirname(__file__), '..', 'config','config'))
        
        if len(configFile) == 0:
            excMsg="'config' setting file is not found!"
            self._logger.exception(excMsg)
            raise Exception(excMsg)
        
        try:
            self.cut_off_threshold=float(config['DEFAULT']['cut_off_threshold'])
        except KeyError:
            self._logger.exception("Oops! 'cut_off_threshold' is not found in config file. Default to set -100")
            #raise Exception("Please check 'PARALLEL_WORKERS' is properly configured!")
            self.cut_off_threshold = float(-100)
        
        self.solrClient =  SolrClient(solr_url)
    
    def terminology_tagging(self):
        '''
        candidate extraction (AUTOMATIC + DICTIONARY MATCHER) -> candidate ranking -> final term list indexing -> synonym aggregation -> update synonyms via API
        '''
        self._logger.info("executing terminology recognition and tagging...")
        c_value_algorithm = CValueRanker(self.solrClient)
        ranked_term_tuple_list = c_value_algorithm.process(tagging=True)
        
        self._logger.info("filtering ranked term candidate list by cut-off threshold [%s]", self.cut_off_threshold)
        final_term_set = [term_tuple[0] for term_tuple in ranked_term_tuple_list if term_tuple[1] > self.cut_off_threshold]
        self._logger.info("final term size after cut-off [%s]", str(len(final_term_set)))
        #print(final_term_set)
        
        self.final_term_set_indexing(final_term_set)
        self._logger.info("terminology recognition and tagging are completed.")
        
    def final_term_set_indexing(self, final_term_set):
        '''
        indexing filtered term candidates into 'industry_term_ss' field by the final term set
        '''
        self._logger.info("indexing term set into 'industry_term_ss' ...")
        totalDocSize = self.solrClient.total_document_size()
        
        self._logger.info("total document size for final industry term tagging [%s]"%totalDocSize)
        
        rows=10
        self._logger.info("starting candidate term tagging in batch size [%s]" % rows)
        
        for nextCursor in range(0, totalDocSize, rows):        
            result = self.solrClient.load_documents(nextCursor, rows)
            docs = result['docs']
            
            #TODO: parallel annotation
            cur_docs_to_commits=[]
            for doc in docs:
                term_candidates = doc['term_candidates_ss']
                
                filtered_candidates = [candidate for candidate in term_candidates if candidate in final_term_set]
                doc['industry_term_ss'] = filtered_candidates
                #print("filtered_candidates: ", filtered_candidates)
                
                #TODO: remove results in term_candidates_ss
                cur_docs_to_commits.append(doc)
                
            self.solrClient.batch_update_documents(cur_docs_to_commits)
            self._logger.info("batch updated current batch. nextCursor[%s]" %str(nextCursor))
            
        self._logger.info("Industry Term extraction and indexing are completed!")
    
    def synonym_aggregation(self, terms):
        raise NotImplementedError("Should have implemented this method!")
    
    def synonym_update(self, terms):
        raise NotImplementedError("Should have implemented this method!")
        
def term_weight_async_calculation(solrURL, term, optional_params=dict()):    
    rankingMethod=optional_params['rankingMethod']
    if rankingMethod == "cValue":
        all_candidates=optional_params['all_candidates']
        return CValueRanker.calculate(term, all_candidates, solrURL)
    else:
        raise Exception("Ranking Method is not supported!")        
        
class TermRanker(object):
    def __init__(self, solr_client):
        self._logger=logging.getLogger(__name__)        
        
        config = configparser.ConfigParser()
        configFile=config.read(os.path.join(os.path.dirname(__file__), '..', 'config','config'))
        
        if len(configFile) == 0:
            excMsg="'config' setting file is not found!"
            self._logger.exception(excMsg)
            raise Exception(excMsg)
        
        self.taggingProcessor = TaggingProcessor(config=config)
        
        self.solrClient=solr_client
        
        try:
            self.parallel_workers=config['DEFAULT']['PARALLEL_WORKERS']
        except KeyError:
            self._logger.exception("Oops! 'PARALLEL_WORKERS' is not found in config file. Running with 1 worker instead.")
            #raise Exception("Please check 'PARALLEL_WORKERS' is properly configured!")
            self.parallel_workers = 1
    
    def batch_candidate_tagging(self):
        #*_ss
        totalDocSize = self.solrClient.total_document_size()
        
        self._logger.info("total document size for candidate term tagging [%s]"%totalDocSize)
        
        rows=10
        self._logger.info("starting candidate term tagging in batch size [%s]" % rows)
        
        for nextCursor in range(0, totalDocSize, rows):        
            result = self.solrClient.load_documents(nextCursor, rows)
            docs = result['docs']
            
            #TODO: parallel annotation
            cur_docs_to_commits=[]
            for doc in docs:
                content = doc['content']
                #lang= doc['language_s']
                #skip non-english ?
                '''
                if lang != 'en':
                    continue
                '''
                term_candidates = self.taggingProcessor.term_candidate_extraction(content)
                
                doc['term_candidates_ss']=list(term_candidates)
                cur_docs_to_commits.append(doc)
                
            self.solrClient.batch_update_documents(cur_docs_to_commits)
            self._logger.info("batch updated current batch. nextCursor[%s]" %str(nextCursor))
            
        self._logger.info("Term candidate extraction and loading for whole index is completed!")
        
    def get_all_candidates(self):
        all_candidates = self.solrClient.field_terms('term_candidates_ss')
        return all_candidates
    
    def get_all_candidates_N(self):
        '''
        N is the total number of candidates appeared in the corpus
        '''        
        self._logger.debug("get_all_candidates Num...")
        candidates = self.get_all_candidates()
        self._logger.debug("all candidates(surface form) number: [%s]", len(candidates))
        return TermRanker.sum_ttf_candidates(self.solrClient, list(candidates.keys()))        
    
    @staticmethod
    def sum_ttf_candidates(solrClient, candidates_list):
        candidates=set([term.lower() for term in candidates_list])
        #self._logger.debug("lower case normalised candidates size: [%s]", len(candidates))
        candidates_ttf=solrClient.totaltermfreq('content', candidates)
        return sum(candidates_ttf.values())        
    
    def process(self, tagging=True):
        raise NotImplementedError("Should have implemented this method!")
    
    def ranking(self):
        raise NotImplementedError("Should have implemented this method!")
    

class CValueRanker(TermRanker):
    '''
    C-Value ranking method (candidate extraction can be independent from the ranking algorithm)
    '''
    def __init__(self, solrClient):
        super().__init__(solrClient)
        self._logger=logging.getLogger(__name__)
        self._logger.info(self.__class__.__name__)
    
    def process(self, tagging=True):
        '''
        load term candidates-> c-value based ranking
        return tuple list, ranked term tuple list (term, c-value)
        '''
        if tagging:
            super().batch_candidate_tagging()
        
        ranked_term_tuple_list = self.ranking()
        return ranked_term_tuple_list             
    
    @staticmethod
    def get_longer_terms(term, all_candidates):
        '''
        the number of candidate terms that contain current term
        params:
            term, current term surface form
            all candidates: all candidates surface form from index
        return longer term list
        '''
        _logger=logging.getLogger(__name__)
        try:
            return [longer_term for longer_term in all_candidates 
                        if term != longer_term and TermUtil.normalise(term) != TermUtil.normalise(longer_term) and
                        set(TermUtil.normalise(term).split(' ')).issubset(set(TermUtil.normalise(longer_term).split(' ')))]
        except AttributeError:
            import traceback
            _logger.error(traceback.format_exc())
            _logger.error("AttributeError when processing candidate term [%s]", term)
        return []
    
    def ranking(self):
        '''
        C-Value ranking
        return tuple list, (term, c-value)
        '''
        self._logger.info("term candidate c-value ranking...")
        
        self._logger.info("loading all candidates ...")
        all_candidates = super().get_all_candidates()
        self._logger.info("all candidates is loaded. Total [%s] candidates to rank...", len(all_candidates))
        self._logger.info(" compute c-values for all candidates with [%s] parallel workers ...", self.parallel_workers)
        #ranked_all_candidates=[self.calculate(candidate, all_candidates)for candidate in all_candidates]
        with MultiprocPool(processes=int(self.parallel_workers)) as pool:
            option_parameter={'rankingMethod':'cValue', 'all_candidates':all_candidates}
            ranked_all_candidates=pool.starmap(term_weight_async_calculation, [(self.solrClient.solrURL, candidate, option_parameter) for candidate in all_candidates])
               
        self._logger.info(" all candidates c-value computation is completed.")
        
        self._logger.info(" all candidates c-value ranking...")
        ranked_all_candidates={term_cvalue_tuple[0]:term_cvalue_tuple[1] for term_cvalue_tuple in ranked_all_candidates}
        
        import operator
        ranked_all_candidates=sorted(ranked_all_candidates.items(), key=operator.itemgetter(1),reverse=True)
        
        self._logger.info("final term size [%s] after c-value ranking. ", str(len(ranked_all_candidates)))
        return ranked_all_candidates
    
    @staticmethod
    def calculate(term, all_candidates, solr_core_url):
        solrClient = SolrClient(solr_core_url)
        
        longer_terms = CValueRanker.get_longer_terms(term, all_candidates)
        term_freq = solrClient.totaltermfreq('content', {term})
        #print(term_freq)
        term_freq = list(term_freq.values())[0]
        
        #print("term freq of '",term,"': ", term_freq)
        
        num_of_term_words=len(TermUtil.normalise(term).split(' '))
        #print("num of term words:", num_of_term_words)
        
        log2a=math.log(num_of_term_words,2)
        #print("log2a:", log2a)
        
        if longer_terms:
            p_ta=len(longer_terms)
            #print("p_ta:", p_ta)
            sum_fb = TermRanker.sum_ttf_candidates(solrClient, longer_terms)
            #print("sum_fb:", sum_fb)
            term_cValue=log2a*(term_freq - (1/p_ta)*sum_fb)
        else:
            term_cValue=log2a*term_freq
            
        return (term,term_cValue)            
        
def test_get_longer_term():
    solrClient =  SolrClient("http://localhost:8983/solr/tatasteel")
    termRanker = TermRanker(solrClient)
    
    cvalue = CValueRanker(solrClient)
    
    longer_terms = cvalue.get_longer_terms("surface defects", set(termRanker.get_all_candidates().keys()))
    print("longer_terms of 'surface defects':", longer_terms)
    
    longer_terms = cvalue.get_longer_terms("temperatures", set(termRanker.get_all_candidates().keys()))
    print("longer_terms of 'temperatures':", longer_terms)
    
    longer_terms = cvalue.get_longer_terms("temperature", set(termRanker.get_all_candidates().keys()))
    print("longer_terms of 'temperature':", longer_terms)
    
    longer_terms = cvalue.get_longer_terms("silicates", set(termRanker.get_all_candidates().keys()))
    print("longer_terms of 'silicates':", longer_terms)

def test_cvalue_calcuation():
    solrClient =  SolrClient("http://localhost:8983/solr/tatasteel")
    
    cvalueAlg = CValueRanker(solrClient)
    all_candidates = cvalueAlg.get_all_candidates()
    
    term_cvalue = cvalueAlg.calculate("surface defects", all_candidates, solrClient.solrURL)
    print("cvalue 'surface defects' :", term_cvalue)
    
    term_cvalue = cvalueAlg.calculate("HP UT performance", all_candidates, solrClient.solrURL)
    print("HP UT performance' :", term_cvalue)    
    
    term_cvalue = cvalueAlg.calculate("m-ems", all_candidates, solrClient.solrURL)
    print("cvalue 'm-ems' :", term_cvalue)
    
    term_cvalue = cvalueAlg.calculate("leader-primary steelmaking", all_candidates, solrClient.solrURL)
    print("cvalue 'leader-primary steelmaking' :", term_cvalue)
    
    term_cvalue = cvalueAlg.calculate("k-factor", all_candidates, solrClient.solrURL)
    print("cvalue 'k-factor' :", term_cvalue)
    
    term_cvalue = cvalueAlg.calculate("s-prints", all_candidates, solrClient.solrURL)
    print("cvalue 's-prints' :", term_cvalue)
    
    term_cvalue = cvalueAlg.calculate("S Prints", all_candidates, solrClient.solrURL)
    print("cvalue 'S Prints' :", term_cvalue)
    
    term_cvalue = cvalueAlg.calculate("Longitudinal S prints", all_candidates, solrClient.solrURL)
    print("cvalue 'Longitudinal S prints' :", term_cvalue)
    
    term_cvalue = cvalueAlg.calculate("pre-heat process", all_candidates, solrClient.solrURL)
    print("cvalue 'pre-heat process' :", term_cvalue)
    
    term_cvalue = cvalueAlg.calculate("v-ratio", all_candidates, solrClient.solrURL)
    print("cvalue 'v-ratio' :", term_cvalue)
    
    term_cvalue = cvalueAlg.calculate("action", all_candidates, solrClient.solrURL)
    print("cvalue 'action' :", term_cvalue)
    
    term_cvalue = cvalueAlg.calculate("Action", all_candidates, solrClient.solrURL)
    print("cvalue 'Action' :", term_cvalue)
    
    term_cvalue = cvalueAlg.calculate("Action No", all_candidates, solrClient.solrURL)
    print("cvalue 'Action No' :", term_cvalue)
    
    term_cvalue = cvalueAlg.calculate("add", all_candidates, solrClient.solrURL)
    print("cvalue 'add' :", term_cvalue)
    
    term_cvalue = cvalueAlg.calculate("afternoon", all_candidates, solrClient.solrURL)
    print("cvalue 'afternoon' :", term_cvalue)
    
    term_cvalue = cvalueAlg.calculate("aid", all_candidates, solrClient.solrURL)
    print("cvalue 'aid' :", term_cvalue)
    
    term_cvalue = cvalueAlg.calculate("All", all_candidates, solrClient.solrURL)
    print("cvalue 'All' :", term_cvalue)
    
    term_cvalue = cvalueAlg.calculate("Any longer", all_candidates, solrClient.solrURL)
    print("cvalue 'Any longer' :", term_cvalue)
    
    term_cvalue = cvalueAlg.calculate("At", all_candidates, solrClient.solrURL)
    print("cvalue 'At' :", term_cvalue)
    
    term_cvalue = cvalueAlg.calculate("Attached", all_candidates, solrClient.solrURL)
    print("cvalue 'Attached' :", term_cvalue)
    
    term_cvalue = cvalueAlg.calculate("Bad", all_candidates, solrClient.solrURL)
    print("cvalue 'Bad' :", term_cvalue)
    
    term_cvalue = cvalueAlg.calculate("click", all_candidates, solrClient.solrURL)
    print("cvalue 'click' :", term_cvalue)
    
    term_cvalue = cvalueAlg.calculate("compare", all_candidates, solrClient.solrURL)
    print("cvalue 'compare' :", term_cvalue)
    
    term_cvalue = cvalueAlg.calculate("confirm", all_candidates, solrClient.solrURL)
    print("cvalue 'confirm' :", term_cvalue)
    
    term_cvalue = cvalueAlg.calculate("Confirm", all_candidates, solrClient.solrURL)
    print("cvalue 'Confirm' :", term_cvalue)
    
    term_cvalue = cvalueAlg.calculate("confirmed", all_candidates, solrClient.solrURL)
    print("cvalue 'confirmed' :", term_cvalue)
    
    term_cvalue = cvalueAlg.calculate("confirmation", all_candidates, solrClient.solrURL)
    print("cvalue 'confirmation' :", term_cvalue)
    
    
def test_cvalue_ranking():
    solrClient =  SolrClient("http://localhost:8983/solr/tatasteel")    
    cvalueAlg = CValueRanker(solrClient)
    ranked_terms = cvalueAlg.ranking()
    
    print(ranked_terms)

def test_tr_tagging():
    trTagger = IndustryTermRecogniser("http://localhost:8983/solr/tatasteel")
    trTagger.terminology_tagging()
    
if __name__ == '__main__':
    import logging.config
    logging.config.fileConfig(os.path.join(os.path.dirname(__file__), '..', 'config', 'logging.conf'))
    
    '''
    from SolrClient import SolrClient
    solrClient =  SolrClient("http://localhost:8983/solr/tatasteel")
    termRanker = TermRanker(solrClient)
    #termRanker.batch_candidate_tagging()
    '''
    #test_get_longer_term()
    #test_cvalue_calcuation()
    #test_cvalue_ranking()
    test_tr_tagging()
    
    
                

    
    
                
                
        