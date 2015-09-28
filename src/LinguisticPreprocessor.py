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

class LinguisticPreprocessor(object):
    pos_tagging=None
    default_tagger=None
    text_tokeniser=None
    np_extractor=None
    _logger=None
    
    def __init__(self):
        import logging
        '''
        if self.default_tagger is None:
            self.default_tagger = self.get_perceptron_tagger()
        '''
        self._logger=logging.getLogger(__name__)
        
    def preprocessing(self, content):
        """
        tokenisation -> part-of-speech tagging
        return tuple list
        e.g., [('A', 'DT'), ('forge', 'NN'), ('is', 'VBZ'), ('a', 'DT'), ('type', 'NN'), ('of', 'IN'), ('hearth', 'NN')]
        """
        if self.default_tagger is None:
            self.default_tagger = self.get_perceptron_tagger()
        return self.default_tagger(content).tags
        
    def customised_preprocessing(self, sent_content):
        '''
        customised tokeniser for irregular text
        NLTK pos tagging
        return normalised pos tagging in tuple list 
        '''
        if self.text_tokeniser is None:
            self.text_tokeniser = self.get_special_text_tokeniser()
        if self.pos_tagging is None:
            self.pos_tagging = self.nltk_pos_tag()
            
        pos_tags= self.pos_tagging(self.text_tokeniser.tokenize(sent_content))
        return tuple(map(lambda x: (x[0], x[0]) if x[0]=='(' or x[0]==')' or x[0] == '@' or x[0] == '\\' or x[0] == '/' else (x[0], x[1]), pos_tags))
        
    def get_perceptron_tagger(self):
        """
        Perform preprocessing (shallow parsing) by state-of-the-art PerceptronTagger (98.8% accuracy)
        However, it stripped punctuations to avoid ambiguity
        http://stevenloria.com/tutorial-state-of-the-art-part-of-speech-tagging-in-textblob/
        """
        from textblob import Blobber
        from textblob_aptagger import PerceptronTagger
        tb = Blobber(pos_tagger=PerceptronTagger())
        return tb

    def get_special_text_tokeniser(self):
        '''
        for special cases: e.g., 3rd, 2nd,1-23-4562, 425-12-3456, wal-mart
        TODO: try to use solr StandardTokenizer 
        '''
        from nltk.tokenize.regexp import RegexpTokenizer
        special_text_token_pattern=r''' (?x) # set flag to allow verbose regexps
                    ([A-Z]\.)+     # abbreviations, e.g. U.S.A.
                    |(\$)?\d+(\.\d+)?%?[a-zA-Z0-9]* # currency and percentages, $12.40, 50%, and mix of number and characters, 3rd, 2nd
                    |\w+(-\w+)*     # words with internal hyphens
                    #|[a-zA-Z0-9]+  # 
                    |'s # POS                
                    |\.\.\.         # ellipsis
                    |[][.,;"'?():*\-_/\\@&']    # separate special character tokens                    
        '''
        return RegexpTokenizer(special_text_token_pattern)
    
    def customised_pos_tag(self):
        pos_model={')':')', '(':'(', '$':'$'}
        import nltk
        default_tagger = nltk.data.load(nltk.tag._POS_TAGGER)
        from nltk.tag import UnigramTagger
        pos_tagger=UnigramTagger(model=pos_model, backoff=default_tagger)
        return pos_tagger
    
    def nltk_pos_tag(self):
        """
            pos_tag(self.get_special_text_tokeniser().tokenize(sent_content))
        """
        from nltk import pos_tag
        return pos_tag    
    
    @staticmethod
    def whoosh_stemmer_func(lang="en"):
        '''
        get stemmer function
        e.g., whoosh_stemmer_fun(term)
        '''
        from whoosh.lang import stemmer_for_language
        stemfn = stemmer_for_language(lang)
        return stemfn
    #from text.taggers import PatternTagger, NLTKTagger
    
    def pos_accuracy(self, test_set, tagger):
        """
        It's a challenge to have a unified benchmarking solution, as it depends on tokenisation and specific objective (e.g., exclude (or not) the punctuation)
        """
        n_correct = 0
        total = 0
        from textblob import Blobber
        
        from textblob_aptagger import PerceptronTagger
        tb=None
        if type(tagger) is PerceptronTagger:
            tb = Blobber(pos_tagger=tagger)            
            
        for tagged_sentence in test_set:
            # Get the untagged sentence string
            # e.g. "Pierre Vinken , 61 years old , will join the board ..."
            raw_sentence = ' '.join([word for word, tag in tagged_sentence])
            
            tags=[]
            if type(tagger) is PerceptronTagger:
                blob = tb(raw_sentence)  # Create a blob that uses the specified tagger
                tags=blob.tags
            elif tagger.__name__ == 'pos_tag':
                tb = Blobber()
                blob = tb(raw_sentence)                
                tokens_sentence=list(blob.tokens)
                tags=tagger(tokens_sentence)
            # tagger excludes punctuation by default
            tags = [tag for word, tag in tags]
            # exclude punctuation in test data
            import string
            #exclude-> if tag not in string.punctuation
            target_tags = [tag for word, tag in tagged_sentence]
            if type(tagger) is PerceptronTagger:
                target_tags = [tag for word, tag in tagged_sentence if tag not in string.punctuation]
            
            total += len(tags)
            
            # Add the number of correct tags
            n_correct += sum(1 for i in range(len(tags)) if tags[i] == target_tags[i])
        return float(n_correct) / total  # The accuracy
    
    def noun_phrase_extract(self, content):
        """
        Returns a list of noun phrases for the textual data
        """
        if self.np_extractor is None:            
            self.np_extractor = self.get_NP_extractor()
        
        return self.np_extractor(content).noun_phrases
    
    def get_NP_extractor(self):
        '''
        return text blob NP extractor
        '''
        #from textblob import TextBlob
        from textblob.np_extractors import ConllExtractor
        
        from textblob import Blobber
        #extractor = ConllExtractor()
        extractor =ConllExtractor()
        tb = Blobber(np_extractor=extractor)
        return tb
    
    def extract_entities(self, text):
        import nltk
        entities=set()
        for sent in nltk.sent_tokenize(text):
            entities=self.extract_entities_from_pos_tagged_text(nltk.pos_tag(nltk.word_tokenize(sent)))
        
        return entities
    
    def extract_entities_from_pos_tagged_text(self, pos_tagged_text):
        from nltk import ne_chunk
        from nltk.tree import Tree
        entities=set()
        for chunk in ne_chunk(pos_tagged_text,binary=True):            
            if type(chunk) is Tree:
                entities.add(' '.join(node[0] for node in chunk.leaves()))
        
        #print("entities:", entities)
        return entities
        
    def benchmaking(self):
        test = [[(u'Pierre', u'NNP'), (u'Vinken', u'NNP'), (u',', u','), (u'61', u'CD'),
            (u'years', u'NNS'), (u'old', u'JJ'), (u',', u','), (u'will', u'MD'),
            (u'join', u'VB'), (u'the', u'DT'), (u'board', u'NN'), (u'as', u'IN'),
            (u'a', u'DT'), (u'nonexecutive', u'JJ'), (u'director', u'NN'),
            (u'Nov.', u'NNP'), (u'29', u'CD'), (u'.', u'.')],
        [(u'Mr.', u'NNP'), (u'Vinken', u'NNP'), (u'is', u'VBZ'), (u'chairman', u'NN'),
            (u'of', u'IN'), (u'Elsevier', u'NNP'), (u'N.V.', u'NNP'), (u',', u','),
            (u'the', u'DT'), (u'Dutch', u'NNP'), (u'publishing', u'VBG'),
            (u'group', u'NN'), (u'.', u'.'), (u'Rudolph', u'NNP'), (u'Agnew', u'NNP'),
            (u',', u','), (u'55', u'CD'), (u'years', u'NNS'), (u'old', u'JJ'),
            (u'and', u'CC'), (u'former', u'JJ'), (u'chairman', u'NN'), (u'of', u'IN'),
            (u'Consolidated', u'NNP'), (u'Gold', u'NNP'), (u'Fields', u'NNP'),
            (u'PLC', u'NNP'), (u',', u','), (u'was', u'VBD'), (u'named', u'VBN'),
            (u'a', u'DT'), (u'nonexecutive', u'JJ'), (u'director', u'NN'), (u'of', u'IN'),
            (u'this', u'DT'), (u'British', u'JJ'), (u'industrial', u'JJ'),
            (u'conglomerate', u'NN'), (u'.', u'.')],
        [(u'A', u'DT'), (u'form', u'NN'),
            (u'of', u'IN'), (u'asbestos', u'NN'), (u'once', u'RB'), (u'used', u'VBN'),
            (u'to', u'TO'), (u'make', u'VB'), (u'Kent', u'NNP'), (u'cigarette', u'NN'),
            (u'filters', u'NNS'), (u'has', u'VBZ'), (u'caused', u'VBN'), (u'a', u'DT'),
            (u'high', u'JJ'), (u'percentage', u'NN'), (u'of', u'IN'),
            (u'cancer', u'NN'), (u'deaths', u'NNS'),
            (u'among', u'IN'), (u'a', u'DT'), (u'group', u'NN'), (u'of', u'IN'),
            (u'workers', u'NNS'), (u'exposed', u'VBN'), (u'to', u'TO'), (u'it', u'PRP'),
            (u'more', u'RBR'), (u'than', u'IN'), (u'30', u'CD'), (u'years', u'NNS'),
            (u'ago', u'IN'), (u',', u','), (u'researchers', u'NNS'),
            (u'reported', u'VBD'), (u'.', u'.')]]
        """
            [(u'A', u'DT'), (u'forge', u'NN'),
            (u'is', u'VBZ'), (u'a', u'DT'), (u'type', u'NN'), (u'of', u'IN'),
            (u'hearth', u'JJ'), (u'used', u'VBN'), (u'for', u'IN'), (u'heating', u'NN'),
            (u'metals', u'NNS'), (u'.', u'.'), (u'or', u'CC'), (u'the', u'DT'),
            (u'workplace', u'NN'), (u'(', u'('), (u'smithy', u'JJ'),
            (u')', u')'), (u'where', u'WRB'),
            (u'such', u'JJ'), (u'a', u'DT'), (u'hearth', u'JJ'), (u'is', u'VBZ'),
            (u'located', u'VBN'), (u'.', u'.')]"""
        from textblob_aptagger import PerceptronTagger
        import nltk
        
        print("perceptron tagger accuracy based on conll2000: ",self.pos_accuracy([nltk.corpus.conll2000.tagged_words()[:30], 
                                                                  nltk.corpus.conll2000.tagged_words()[30:60],
                                                                  nltk.corpus.conll2000.tagged_words()[60:90],
                                                                  nltk.corpus.conll2000.tagged_words()[90:120],
                                                                  nltk.corpus.conll2000.tagged_words()[120:150],
                                                                  nltk.corpus.conll2000.tagged_words()[300:330]], PerceptronTagger()))
        print("NLTK pos tagger accuracy based on conll2000: ", self.pos_accuracy([nltk.corpus.conll2000.tagged_words()[:30], 
                                                                  nltk.corpus.conll2000.tagged_words()[30:60],
                                                                  nltk.corpus.conll2000.tagged_words()[60:90],
                                                                  nltk.corpus.conll2000.tagged_words()[90:120],
                                                                  nltk.corpus.conll2000.tagged_words()[120:150],
                                                                  nltk.corpus.conll2000.tagged_words()[300:330]], self.nltk_pos_tag()))
                       
        '''print("NLTK pos tagger accuracy based on brown corpus: ", self.pos_accuracy([nltk.corpus.brown.tagged_words()[:30], 
                                                                  nltk.corpus.brown.tagged_words()[30:60],
                                                                  nltk.corpus.brown.tagged_words()[60:90],
                                                                  nltk.corpus.brown.tagged_words()[90:120],
                                                                  nltk.corpus.brown.tagged_words()[120:150],
                                                                  nltk.corpus.brown.tagged_words()[300:330]], self.nltk_pos_tag()))'''
        
        print("perceptron tagger accuracy based on test data: ",self.pos_accuracy(test, PerceptronTagger()))
        print("NLTK pos tagger accuracy based on test data: ", self.pos_accuracy(test, self.nltk_pos_tag()))
        '''print("NLTK pos tagger accuracy based on brown corpus: ", self.pos_accuracy([nltk.corpus.brown.tagged_words()[:30], 
                                                                  nltk.corpus.brown.tagged_words()[30:60],
                                                                  nltk.corpus.brown.tagged_words()[60:90],
                                                                  nltk.corpus.brown.tagged_words()[90:120],
                                                                  nltk.corpus.brown.tagged_words()[120:150],
                                                                  nltk.corpus.brown.tagged_words()[300:330]], self.nltk_pos_tag()))'''

    def test_extract_entities(self):
        entities=self.extract_entities("English Gigaword, now being released in its fourth edition, is a comprehensive archive of newswire text data that has been acquired over several years by the LDC at the University of Pennsylvania.")
        print(entities)
        
    def test_customised_preprocessing(self):
        #sent_content="Mather/UK/Corus@Corus01, Tracey Brown/UK/Corus@Corus01, Frank __"
        #sent_content="MAIN RISKS / AREAS FOR CONCERN "
        #sent_content="Minutes of CC&I/CR Technical Liason meeting"
        sent_content=" Web Void Defects - Position in Rail"
        pos_tagged_content=self.customised_preprocessing(sent_content)
        print(pos_tagged_content)
        
    def test_special_text_tokeniser(self):
        #content="\n \n  \n  \n  \n  \n  \n  \n  \n  \n \n   1515: Longitudinal S prints from 3rd HP rail Sequence\r\n  MSM\r\n Andrew Clark\r\n Longitudinal S prints attached below. Note, scanned area is limited to 220  mm (of 305 mm total thickness) by scanner bed. V segregate extends to approx 45 mm either side of centre-line. There is some light ic on strand one, which is not resolved on the scanned  image. Routine (transverse, 87 cast)  S prints were Grade 1 cl & Grade 0  ic. martyn \t \n U.S.A. is a country. US currency drops 30% by $12.40. We rolled 7000t of Lucchini in B214 of 245*340mm format with a final US  rate of 0.8%.  We rolled also from Saarstahl (320*240)   2000t of Unimetal blooms in 360*320 format and B219 steel code with a  final US rate of 1.9%.  For Sollac we were around 1.5% at the end  for a bloom format of 320*260."
        #content="M.Grant has a project to submit costs with all quality codes which  will prove very  useful."
        content="Minutes of CC&I/CR Technical Liason meeting "
        tokens_content = self.get_special_text_tokeniser().tokenize(content)
        print(tokens_content)
        #context to ignore for term recognition, but may cause problems (e.g., candidate extraction of "E daniel"):
        # E daniel.pyke@corusgroup.com www.muchmorethanrail.com Keith Bennett/UK/Corus
        # M.Grant has a project to submit costs with all quality codes which  will prove very  useful.
        # solr standard tokeniser will tokenise "M.Grant", "daniel.pyke" as a whole
        # for some irregular text, there is no space between two sentences. It becomes difficult to split.
if __name__ == '__main__':
    print("===========Extract entities============")
    linguisticProcessor=LinguisticPreprocessor()
    linguisticProcessor.test_customised_preprocessing()
    #linguisticProcessor.test_special_text_tokeniser()