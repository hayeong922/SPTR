'''
Created on 11 Sep 2015

@author: jieg
'''
import os
import sys
import re
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

import logging
import nltk
from FileUtil import read_by_line
from nltk.tokenize import sent_tokenize
from LinguisticPreprocessor import LinguisticPreprocessor
from util import TermUtil

class TaggingProcessor(object):
    pos_sequences_file=""
    linguistic_processor=None
    stopword_list=set()
    _logger=None
    
    def __init__(self, config=None, solrClient=None):
        self._logger=logging.getLogger(__name__)
        
        if self.linguistic_processor is None:            
            self.linguistic_processor = LinguisticPreprocessor()
            
        if config:
            try:
                self.pos_sequences_file=config['DEFAULT']['pos_sequence_filter']
            except KeyError:
                self._logger.exception("Oops! 'pos_sequence_filter' is not found in config file.")
                raise Exception("Please check 'pos_sequence_filter' is properly configured!")
            
            try:
                self.solr_core_url=config['DEFAULT']['solr_core_url']
            except KeyError:
                errMsg="Target index url 'solr_core_url' is not configured in config file. Use default index directory instead."
                self._logger.exception(errMsg)
                raise Exception(errMsg)
            
            try:
                self._max_tokens=int(config['DEFAULT']['max_tokens'])
            except KeyError:
                errMsg="'max_tokens' is not configured in config file. Default as 6 instead."
                self._logger.warn(errMsg)
                self._max_tokens=6
            
            try:
                self._min_tokens=int(config['DEFAULT']['min_tokens'])
            except KeyError:
                errMsg="'min_tokens' is not configured in config file. Default as 1 instead."
                self._logger.warn(errMsg)
                self._min_tokens=6
            
            try:
                self._min_char_length=int(config['DEFAULT']['min_char_length'])
            except KeyError:
                errMsg="'min_char_length' is not configured in config file. Default as 2 instead."
                self._logger.warn(errMsg)
                self._min_char_length=2
                
            try:
                self._min_term_freq=int(config['DEFAULT']['min_term_freq'])
            except KeyError:
                errMsg="'min_term_freq' is not configured in config file. Default is 1 instead."
                self._logger.warning(errMsg)
                self._min_term_freq=1
            
            if len(self.stopword_list) == 0 :
                from nltk.corpus import stopwords
                self.stopword_list=set()
                #The union operator is much faster than add
                self.stopword_list |= set(stopwords.words('english'))
                try:
                    customised_stopword_file=config['DEFAULT']['stopwords']
                except KeyError:
                    errMsg="Oops! customisable stopword file is not found in config file. Use default english stopword list instead!"
                    self._logger.error(errMsg)
                
                smart_stopword_list=os.path.join(os.path.dirname(__file__), '..','config','smart-stop-list.txt')
                if (customised_stopword_file is not None):
                    
                    self.stopword_list |= set(read_by_line(customised_stopword_file))
                    self.stopword_list |= set(read_by_line(smart_stopword_list))
                
                self._logger.debug("final stopword size: [%s]", len(self.stopword_list))
        
        if solrClient is None:
            from SolrClient import SolrClient
            self.solrClient=SolrClient(self.solr_core_url)
        else:
            self.solrClient=solrClient          
        
    def load_grammars(self):
        grammars=[]
        
        pos_sequences = read_by_line(self.pos_sequences_file)
        for sequence_str in pos_sequences:
            grammars.append(sequence_str.replace('\n','').strip())
        
        return grammars
    
    def parsing_candidates_regexp(self, text_pos_tokens,candidate_grammar):
        cp = nltk.RegexpParser(candidate_grammar)
        
        candidate_chunk=cp.parse(text_pos_tokens)    
        term_candidates=set()
        for node_a in candidate_chunk:
            if type(node_a) is nltk.Tree:
                if node_a.label() == 'TermCandidate':
                    term_tokens=[]
                    for node_b in node_a:
                        if node_b[0] == '"':
                            #TODO: find a more elegant way to deal with spurious POS tagging for quotes
                            continue
                        if node_b[1] == 'POS':
                            term_tokens.append(node_b[0])
                        elif node_b[1] == 'DT':
                            #only append if DT is in the middle,e.g., ratio of the tensile
                            term_tokens.append('' if len(term_tokens) == 0 else node_b[0])
                            #continue
                        else:
                            term_tokens.append('' if len(term_tokens) == 0 else ' ')
                            term_tokens.append(node_b[0])
                    
                    term_candidates.add(''.join(term_tokens))
        return term_candidates
    
    def sentence_split(self, content):
        '''
        heuristic/pattern (e.g., by '\r\n' or '\t') based sentence splitting + NLTK's recommended sentence tokenizer         
        return list, sentence list
        '''
        pattern_split = re.compile(r"[\r\n|\t]")
        sent_list = pattern_split.split(content.strip())
        
        
        sent_list = [sent_tokenize(sent.strip()) for sent in sent_list if sent.strip()]
        #flatten sentence list
        sent_list = [item for sublist in sent_list for item in sublist]
        return sent_list
        
    def term_candidate_extraction(self,content):
        '''
        Sentence based term candidates extraction. The content need to be tokenised and sentence splitted before parsing.
        params:
            content: content string to be analysed
        return set, term candidates extracted from content
        '''
        self._logger.debug("term candidate extraction for single document...")
        term_candidates=set()
        grammars=['TermCandidate: {'+item+'}' for item in self.load_grammars() if not item.startswith('#')]
        
        sent_tokenize_list = self.sentence_split(content)
                
        for sent_content in sent_tokenize_list:
            pos_sent_content=self.linguistic_processor.customised_preprocessing(sent_content)
            #print(pos_sent_content)
            for candidate_grammar in grammars:
                pos_filter_candidates=self.parsing_candidates_regexp(pos_sent_content,candidate_grammar)
                term_candidates.update(pos_filter_candidates)
            
        self._logger.debug("term_candidates size after PoS filtering: [%s]", len(term_candidates))
        term_candidates = self.linguistic_filter(term_candidates)
        term_candidates = self.frequency_filtering(term_candidates)
        
        self._logger.debug("Term candidate extraction for current doc is completed.")
        return term_candidates
    
    def frequency_filtering(self, term_candidates):
        '''
        Corpus (whole index) based frequency filtering
        
        params:
            term_candidates: set()
        
        return set, filtered term candidates
        '''
        self._logger.info("term frequency filtering for candidates [%s] by min frequency [%s]  ...",str(len(term_candidates)), str(self._min_term_freq))
        
        if self._min_term_freq > 1:
            ttf_term_candidates = self.solrClient.totaltermfreq('content', term_candidates)
            
            for term_debug in term_candidates:
                if self.get_term_ttf(term_debug, ttf_term_candidates) == 0:
                    self._logger.warning("Error!! term [%s] has no ttf value. Please check tokenisation method for irregular text or the shingling range for the min and max value.", term_debug)
                    #open-teemed Bloom Identities Cast No.
            
            term_candidates=set([term for term in term_candidates if self.get_term_ttf(term, ttf_term_candidates) > self._min_term_freq])
        self._logger.info("current term candidate size after frequency filtering [%s]", str(len(term_candidates)))
        return term_candidates
    
    def get_term_ttf(self, term, ttf_dict):
        '''
        get term ttf value from a given ttf dictionary returned from SolrClient.totaltermfreq
        return ttf numerical value
        '''
        return ttf_dict[TermUtil.normalise(term)]
    
    def check_min_char_limit(self, multiword_term):
        '''
        return True if none of term unit length less than minimum char length
        '''
        is_exist_min_char=0
        
        for token in multiword_term.split(' '):
            if len(token) < self._min_char_length:
                is_exist_min_char+=1
                
        if is_exist_min_char > 0:
            return False
        
        return True
    
    def linguistic_filter(self, candidate_set=set()):
        """
        linguistic based term candidates filtering
        
        1) stopword based filtering: any word in candidates matched with the stopwords will be removed!
        2) ngram range filtering
        3) minimum character filtering: none of term unit length less than minimum char length
        
        """        
        #TODO: check how many gold standards can be filtered
        self._logger.info("linguistic filtering ...")
        self._logger.info("stopword size: [%s], minimum tokens allowed: [%s], maximum tokens allowed [%s], min character allowed: [%s]", str(len(self.stopword_list)), str(self._min_tokens), str(self._max_tokens), str(self._min_char_length))
        #filter by matching with a stopwords
        #use the word_lower_func to lowercase the words to do stopword match except symbolic character is uppercase (for e.g., Longitudinal S prints, US)
        word_lower_func=lambda w: re.escape(w.lower()) if len(w) > 2 else w
        resultSet= set([x for x in candidate_set if any(word_lower_func(word) in self.stopword_list for word in x.split()) is False])
        
        #add back filtered results by removing first stopword
        stopword_filtered_resultSet= candidate_set - resultSet
        #print("stopword_filtered_resultSet:", stopword_filtered_resultSet)        
        first_word_striped_resultset=[' '.join(term.split()[1:]) for term in stopword_filtered_resultSet if len(term.split()) > 1 and word_lower_func(term.split()[0]) in self.stopword_list]
        #print("add back striped results:", first_word_striped_resultset)
        resultSet.update(first_word_striped_resultset)        
        #print("results after stopwords filtering:", resultSet)
        
        resultSet= set([x for x in resultSet if len(x.split()) >= self._min_tokens and len(x.split()) <= self._max_tokens])
        
        #to filter candidates e.g., "A.", "B."
        #resultSet= set([x for x in resultSet if len(x.replace('.','')) >= self._min_char_length])
        
        if self._min_char_length >1:
            resultSet= set([x for x in resultSet if self.check_min_char_limit(x)])
        
        resultSet=set(filter(None,resultSet))
        self._logger.debug("linguistic filtering is completed. current candidate size [%s]", len(resultSet))
        
        #TODO: filter common noun (a noun that can be found in WordNet) 
        # refer to C. Arora, M. Sabetzadeh, F. Zimmer, and P. Werner, "Improving Requirements Glossary Construction via Clustering : Approach and Industrial Case Studies," 2014.
        # Single-word common nouns typically either constitute general knowledge or do not convey any special meaning outside their context. 
        # We retain as a candidate term any single-word noun that is not found in the dictionary as well as any single-word common noun that is capitalized ,these nouns are likely to denote abbreviations and proper nouns
        return resultSet

def test_sentence_split():
    import configparser
    config = configparser.ConfigParser()
    
    taggingProcessor = TaggingProcessor(config)
    sentlist = taggingProcessor.sentence_split("\n \n  \n  \n  \n  \n  \n  \n  \n  \n \n   1515: Longitudinal S prints from 3rd HP rail Sequence\r\n  MSM\r\n Andrew Clark\r\n Longitudinal S prints attached below. Note, scanned area is limited to 220  mm (of 305 mm total thickness) by scanner bed. V segregate extends to approx 45 mm either side of centre-line. There is some light ic on strand one, which is not resolved on the scanned  image. Routine (transverse, 87 cast)  S prints were Grade 1 cl & Grade 0  ic. martyn \t \n  test haha \t test haha11111")
    print(sentlist)

def test_term_candidate_extraction():
    import configparser
    config = configparser.ConfigParser()
    config.read(os.path.join(os.path.dirname(__file__), '..', 'config','config'))
    taggingProcessor = TaggingProcessor(config)
    #content="\n \n  \n  \n  \n  \n  \n  \n  \n  \n \n   1515: Longitudinal S prints from 3rd HP rail Sequence\r\n  MSM\r\n Andrew Clark\r\n Longitudinal S prints attached below. Note, scanned area is limited to 220  mm (of 305 mm total thickness) by scanner bed. V segregate extends to approx 45 mm either side of centre-line. There is some light ic on strand one, which is not resolved on the scanned  image. Routine (transverse, 87 cast)  S prints were Grade 1 cl & Grade 0  ic. martyn \t \n U.S.A. is a country. US currency drops 30% by $12.40. We rolled 7000t of Lucchini in B214 of 245*340mm format with a final US  rate of 0.8%.  We rolled also from Saarstahl (320*240)   2000t of Unimetal blooms in 360*320 format and B219 steel code with a  final US rate of 1.9%.  For Sollac we were around 1.5% at the end  for a bloom format of 320*260. \n "
    #content="Absolute maximum length cold is 9.350m  Absolute minimum cold length is  5.700m Except for rail steels which are ordered to a dead length. TBM 4500 to 4750mm  5550 to 7000mm 7800 to 9600mm Hot Usable Lengths  4545 to 4795mm 5605 to 7070mm 7875 to 9695 mm       Any longer must be cropped back Any shorter than 4500 will  be scrap Any between the length ranges above are in the furnace dead lengths and  should be cropped back to take length into the acceptable range."
    #content="If the strand is capped off or lost during the sequence  revert to the next available strand."
    content=" \n \n  \n  \n  \n  \n  \n  \n  \n  \n \n   Web Void Defects - Position in Rail\r\n  "
    term_candidates = taggingProcessor.term_candidate_extraction(content)
    print("term_candidates: ", term_candidates)
                
if __name__ == '__main__':
    import logging.config
    logging.config.fileConfig(os.path.join(os.path.dirname(__file__), '..', 'config', 'logging.conf'))
    
    test_term_candidate_extraction()
    
    