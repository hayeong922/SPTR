"""
Copyright &copy;2015 Sheffield University (OAK Group)
All Rights Reserved.

Developer(s):
   Jie Gao (j.gao@sheffield.ac.uk)

@author: jieg
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

import logging
import configparser

import csv

import sqlite3

from SolrClient import SolrClient
from TaggingProcessor import TaggingProcessor
from util import TermUtil
from FileUtil import path_leaf

import math
from multiprocPool import MultiprocPool

#content field from where industry terms will be extracted
FIELD_CONTENT="content"
FIELD_DOC_ID="id"
FIELD_TERM_CANDIDATES="term_candidates_tvss"
FIELD_INDUSTRY_TERM="industryTerm"
FIELD_DICTIONARY_TERM="dictTerm_ss"

class IndustryTermRecogniser(object):
    """
    This class perform industry term recognition based on Apache Solr    
    """
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
            self.cut_off_threshold = float(-100)
        
        try:
            self.sim_threshold = float(config['DEFAULT']['sim_threshold'])
        except KeyError:
            self._logger.exception("Oops! 'sim_threshold' is not found in config file. Default to set 0.99")
            self.sim_threshold = float(0.99)    
            
        try:
            self.tagging = config['DEFAULT']['tagging']
            if "true" == self.tagging.lower():
                self.tagging = True
            elif "false" == self.tagging.lower():
                self.tagging = False
            else:
                raise Exception("current setting [%s] for 'tagging' is not supported!"%self.tagging)
        except KeyError:
            self._logger.exception("Oops! 'tagging' is set incorrectly in config file. Default to set true")
            self.tagging = True
            
        global FIELD_TERM_CANDIDATES
        try:            
            FIELD_TERM_CANDIDATES = config['DEFAULT']['solr_field_term_candidates']
        except KeyError:
            self._logger.exception("Oops! 'solr_field_term_candidates' is not found in config file. Default to [%s]", FIELD_TERM_CANDIDATES)
        
        global FIELD_CONTENT
        try:            
            FIELD_CONTENT = config['DEFAULT']['solr_field_content']
        except KeyError:
            self._logger.exception("Oops! 'solr_field_content' is not found in config file. Default to [%s]", FIELD_CONTENT)
        
        try:
            self.index_dict_term_with_industry_term=config['DICTIONARY_TAGGER']['index_dict_term_with_industry_term']
            if "true" == self.index_dict_term_with_industry_term.lower():
                self.index_dict_term_with_industry_term = True
            elif "false" == self.index_dict_term_with_industry_term.lower():
                self.index_dict_term_with_industry_term = False
            else:
                raise Exception("current setting [%s] for 'tagging' is not supported!"%self.tagging)
        except KeyError:
            self._logger.exception("Oops! 'index_dict_term_with_industry_term' is set incorrectly in config file. Default to set true")
            self.index_dict_term_with_industry_term = True
            
        global FIELD_INDUSTRY_TERM
        try:            
            FIELD_INDUSTRY_TERM = config['DEFAULT']['solr_field_industry_term']
        except KeyError:
            self._logger.exception("Oops! 'solr_field_industry_term' is not found in config file. Default to [%s]", FIELD_TERM_CANDIDATES)
                
        try:
            self.export_term_candidates = config['DEFAULT']['export_term_candidates']
            if "true" == self.export_term_candidates.lower():
                self.export_term_candidates=True
            elif "false" == self.export_term_candidates.lower():
                self.export_term_candidates=False
            else:
                raise Exception("current setting [%s] for 'export_term_candidates' is not supported!"%self.export_term_variants)
        except KeyError:
            self._logger.exception("Oops! 'export_term_candidates' is set incorrectly in config file. Default to set false")
            self.export_term_candidates = False
        
        try:
            self.export_term_variants = config['DEFAULT']['export_term_variants']
            if "true" == self.export_term_variants.lower():
                self.export_term_variants=True
            elif "false" == self.export_term_variants.lower():
                self.export_term_variants=False
            else:
                raise Exception("current setting [%s] for 'export_term_variants' is not supported!"%self.export_term_variants)
        except KeyError:
            self._logger.exception("Oops! 'export_term_variants' is set incorrectly in config file. Default to set false")
            self.export_term_variants = False
        
        try:
            self.term_variants_export_file_name=config['DEFAULT']['term_variants_export_file_name']
        except KeyError:
            self._logger.exception("Oops! 'term_variants_export_file_name' is set incorrectly in config file. Default to set 'term_variants'")
            self.term_variants_export_file_name = "term_variants"
        
        global FIELD_DICTIONARY_TERM
        try:
            FIELD_DICTIONARY_TERM=config['DICTIONARY_TAGGER']['solr_field_dictionary_term']
        except KeyError:
            self._logger.exception("Oops! 'solr_field_dictionary_term' is set incorrectly in config file. Default to index into the 'dictTerm_ss' field")
            FIELD_DICTIONARY_TERM='dictTerm_ss'
            
        self.solrClient =  SolrClient(solr_url)
    
    def terminology_tagging(self):
        """
        candidate extraction (AUTOMATIC + DICTIONARY MATCHER) -> candidate ranking -> final term list indexing -> synonym aggregation -> update synonyms via API
        """
        self._logger.info("executing terminology recognition and tagging...")
        c_value_algorithm = CValueRanker(self.solrClient)
        ranked_term_tuple_list = c_value_algorithm.process(tagging=self.tagging)
        
        self._logger.info("filtering ranked term candidate list by cut-off threshold [%s]", self.cut_off_threshold)
        final_term_set = [term_tuple[0] for term_tuple in ranked_term_tuple_list if term_tuple[1] > self.cut_off_threshold]
        
        self._logger.info("final term size after cut-off [%s]", str(len(final_term_set)))
        
        self.final_term_set_indexing(final_term_set)
        term_db_path = self.save_ranked_candidates_to_db(self.solrClient.solr_core, ranked_term_tuple_list)
        if self.export_term_candidates:
            self.export_ranked_terms_to_csv(term_db_path)
        else:
            self._logger.info("skip exporting term candidates from Solr.")
        
        self.synonym_aggregation(final_term_set)
        self._logger.info("terminology recognition and tagging are completed.")
        
    def final_term_set_indexing(self, final_term_set):
        """
        indexing filtered term candidates into 'industry_term_ss' field by the final term set
        """
        self._logger.info("indexing term set into '%s' ...", FIELD_INDUSTRY_TERM)
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
                if FIELD_TERM_CANDIDATES in doc:
                    term_candidates = doc[FIELD_TERM_CANDIDATES]
                    filtered_candidates = [candidate for candidate in term_candidates if candidate in final_term_set]
                    
                    if self.index_dict_term_with_industry_term and FIELD_DICTIONARY_TERM in doc:
                        dict_terms = doc[FIELD_DICTIONARY_TERM]
                        if dict_terms:
                            filtered_candidates.extend(dict_terms)
                    
                    #print("final industry_terms:", industry_terms)
                    doc[FIELD_INDUSTRY_TERM] = list(set(filtered_candidates))
                    
                    cur_docs_to_commits.append(doc)
                else:
                    doc[FIELD_INDUSTRY_TERM]=[]
                
            self.solrClient.batch_update_documents(cur_docs_to_commits)
            self._logger.info("batch updated current batch. nextCursor[%s]" %str(nextCursor))
            
        self._logger.info("Industry Term extraction and indexing are completed!")
    
    def save_ranked_candidates_to_db(self, core_name, ranked_term_tuple_list):
        """
        save all ranked term candidates to sqllite db and export afterward for the sake of evaluation and cut-off threshold selection
        params:
            core_name,                solr core name
            ranked_term_tuple_list,   ranked term tuple list (term, weight) 
        return string, database path
        """
        
        db_path=os.path.join(os.path.dirname(__file__), '..', str(core_name)+"_term_candidates.db")
        self._logger.info("loading into terminology database [%s]", db_path)
        db_conn = sqlite3.connect(db_path)
        try:            
            c = db_conn
            #create table
            c.execute('''create table IF NOT EXISTS term_candidates(term_name TEXT PRIMARY KEY, 
                    weight float)''')
            #clear table
            c.execute('''delete from term_candidates;''')
            c.commit()
            
            for term, score in ranked_term_tuple_list:
                try:
                    c.execute('INSERT INTO term_candidates(term_name, weight) VALUES(?,?)', [term,score])        
                    
                except sqlite3.IntegrityError:
                    print("duplicated term! term is [%s]"%term);
                except:
                    print("SQL Insert Error",sys.exc_info()[0])
            c.commit()
        except:
            print("SQL Insert Error",sys.exc_info()[0])
        finally:
            db_conn.close()
        self._logger.info("complete data loading into db.")
        return db_path
        
    def export_ranked_terms_to_csv(self, term_db_path):        
        self._logger.info("exporting [%s] into csv ...", term_db_path)
        
        dbname=path_leaf(term_db_path)
        
        output_csv=os.path.join(os.path.dirname(__file__), '..',dbname+".csv")
        
        query_term_set='''select * from term_candidates;'''
        conn_term_db=sqlite3.connect(term_db_path)
        term_resultset = conn_term_db.execute(query_term_set)
        with open(output_csv, 'w', encoding="utf-8") as outfile:
            csvWriter=csv.writer(outfile, delimiter=",",lineterminator='\n',quoting=csv.QUOTE_MINIMAL)
            csvWriter.writerow(['term','weight'])
            for row in term_resultset:
                csvWriter.writerow([row[0],row[1]])
        
        self._logger.info("terms has been exported into [%s]", output_csv)

    def synonym_aggregation(self, terms=set()):
        '''
        Term variants identification: interlinking terms with normalisation, similarity computation and aggregate  
        1) case insensitivity matching;
        2) ASCII-equivalent matching () ;
        3) Diacritic-elimination matching ()
        4) Punctuation-elimination matching (Marc Anthony <==> Marc-Anthony or Beer Sheva <==> Be'er Sheva)
        5) stemming
        6) string distance matching (normalised levenshtein metrics) -> TODO: later
        '''
        
        if not self.export_term_variants:
            self._logger.info("Skip exporting term variants!")
            return
        
        self._logger.info("Term variation detection and aggregation...")
        
        v = {}
        norm_term_dict = dict((term, self.solrClient.get_industry_term_field_analysis(term)) for term in terms)
        for key, value in sorted(norm_term_dict.items()):
            v.setdefault(value, []).append(key)
        
        aggregated_terms = v.values()
        
        #TODO: normed Levenshtein similarity matching
        
        from FileUtil import export_list_of_list_to_csv
        export_list_of_list_to_csv(os.path.join(os.path.dirname(__file__), '..'), self.term_variants_export_file_name, list(aggregated_terms))
        
    def term_variations_detection(self, term1, term2, terms=set()):
        '''
        perform terminology variation detection via Solr
        param:
            term1,
            term2,
            terms, optional, providing all the terms can improve efficiency significantly
        return True, if term2 is the variation of term1
        '''
        if len(terms) > 0:            
            global norm_term_dict
            if norm_term_dict:
                self._logger.debug("loading normalised terms ...")
                norm_term_dict = dict((term, self.solrClient.get_industry_term_field_analysis(term)) for term in terms)
                self._logger.debug("term dict loaded.")
        
        if norm_term_dict:
            term1_phonetic_norm = norm_term_dict(term1)
            term2_phonetic_norm = norm_term_dict(term2)
        else:
            term1_phonetic_norm = self.solrClient.get_industry_term_field_analysis(term1)
            term2_phonetic_norm = self.solrClient.get_industry_term_field_analysis(term2)
        
        return term1_phonetic_norm == term2_phonetic_norm 
    
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
    #TODO: may add additional algorithm, see http://www.nltk.org/howto/collocations.html
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
            self.parallel_workers = 1
        
        try:
            self.field_doc_id=config['DEFAULT']['solr_field_doc_id']
        except KeyError:
            self._logger.exception("Oops! 'solr_field_doc_id' is not found in config file. Default to 'id' field instead.")
            self.field_doc_id = 'id'
    
    def batch_candidate_tagging(self):
        '''
        batch term candidate tagging + dictionary tagging (optional)
        '''
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
                content = doc[FIELD_CONTENT]
                doc_id = doc[self.field_doc_id]
                #lang= doc['language_s']
                #skip non-english ?
                '''
                if lang != 'en':
                    continue
                '''
                term_candidates = self.taggingProcessor.term_candidate_extraction(content)
                doc[FIELD_TERM_CANDIDATES]=list(term_candidates)
                
                if self.taggingProcessor.dict_tagging:
                    dictionary_terms = self.taggingProcessor.term_dictionary_tagging(doc_id)
                    doc[FIELD_DICTIONARY_TERM]=list(dictionary_terms)
                
                cur_docs_to_commits.append(doc)
                
            self.solrClient.batch_update_documents(cur_docs_to_commits)
            self._logger.info("batch updated current batch. nextCursor[%s]" %str(nextCursor))
            
        self._logger.info("Term candidate extraction and loading for whole index is completed!")
        
    def get_all_candidates(self):
        '''
        query all indexed terms from FIELD_TERM_CANDIDATES
        '''
        all_candidates = self.solrClient.field_terms(FIELD_TERM_CANDIDATES)
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
        candidates_ttf_dict, normed_candidates_dict =solrClient.totaltermfreq(FIELD_CONTENT, set(candidates_list))
        return sum(candidates_ttf_dict.values())        
    
    def process(self, tagging=True):
        raise NotImplementedError("Should have implemented this method!")
    
    def ranking(self):
        raise NotImplementedError("Should have implemented this method!")

class CValueRanker(TermRanker):
    '''
    C-Value ranking method (candidate extraction can be independent from the ranking algorithm)
    
    Frantzi, K., Ananiadou, S., & Mima, H. (2000). Automatic recognition of multi-word terms:. the C-value/NC-value method. International Journal on Digital Libraries, 3(2), 115-130.
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
        
        Simply term normalisation is applied. Could be extended with "solr_term_normaliser"
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
        C-Value parallel term ranking
        
        return tuple list: (term, c-value)
        '''
        self._logger.info("term candidate c-value ranking...")
        
        self._logger.info("loading all candidates ...")
        all_candidates = super().get_all_candidates()
        self._logger.info("all candidates is loaded. Total [%s] candidates to rank...", len(all_candidates))
        self._logger.info(" compute c-values for all candidates with [%s] parallel workers ...", self.parallel_workers)
        
        with MultiprocPool(processes=int(self.parallel_workers)) as pool:
            optional_parameter={'rankingMethod':'cValue', 'all_candidates':all_candidates}
            ranked_all_candidates=pool.starmap(term_weight_async_calculation, [(self.solrClient.solrURL, candidate, optional_parameter) for candidate in all_candidates])
               
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
        term_freq_dict,normed_term_dict = solrClient.totaltermfreq(FIELD_CONTENT, {term})
        
        term_freq = list(term_freq_dict.values())[0]
        
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
    
    term_cvalue = cvalueAlg.calculate("BAD CUT", all_candidates, solrClient.solrURL)
    print("cvalue 'BAD CUT' :", term_cvalue)
    
    
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
    
    #test_get_longer_term()
    #test_cvalue_calcuation()
    #test_cvalue_ranking()
    test_tr_tagging()
    
    
                

    
    
                
                
        