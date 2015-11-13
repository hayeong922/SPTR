'''
Copyright &copy;2015 Sheffield University (OAK Group)
All Rights Reserved.

Developer(s):
   Jie Gao (j.gao@sheffield.ac.uk)

@author: jieg
'''
import chardet
import sys
import os
import logging
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

import urllib.request

encodings = ['utf-8', 'ISO-8859-2', 'windows-1250', 'windows-1252', 'latin1', 'ascii','ISO-8859-1']
def determine_file_encoding(rawBytes):
    result = chardet.detect(rawBytes)
    string_encoding = result['encoding']
    
    return string_encoding

def load_doc_bytes(docPath):
    with open(docPath,'rb') as doc:
        content=doc.read()
    return content

def load_corpus(corpus_dir):
    _logger=logging.getLogger(__name__)
    
    _logger.debug('loading corpus...')
    corpus={}
    for file in os.listdir(corpus_dir):
        #if file.endswith(".*"):
        corpus[file.replace('.*','')]=corpus_dir+'/'+file
    
    _logger.debug("[%s] documents found.", len(corpus))
    
    return corpus


def export_to_pickle(obj, filename=""):
    import pickle
    pickle.dump(obj, open(filename, "wb"))


def load_from_pickle(filename=""):    
    _logger=logging.getLogger(__name__)
    import pickle
    try:
        return pickle.load(open(filename, 'rb'))
    except FileNotFoundError:
        _logger.debug("[%s] not found.", filename)
        
    return None


def export_to_txt_file(file_dir, file_name, content):
    if not os.path.exists(os.path.join(file_dir)):
        os.makedirs(os.path.join(file_dir))
    
    with open(os.path.join(file_dir, file_name+".txt"), mode='w', encoding='utf-8') as outfile:
        outfile.write(content)


def export_list_of_list_to_csv(file_dir, file_name, list_values):
    '''
    export a list of list to csv
    '''   
    with open(os.path.join(file_dir, file_name+".csv"), mode='w', encoding='utf-8') as outfile:
        csvWriter=csv.writer(outfile, delimiter=",",lineterminator='\n',quoting=csv.QUOTE_MINIMAL)
        for row in list_values:
                csvWriter.writerow(row)

def continuous_export_to_file(file_dir, file_name, content):
    if not os.path.exists(os.path.join(file_dir)):
        os.makedirs(os.path.join(file_dir))
    
    with open(os.path.join(file_dir, file_name), mode='a', encoding='utf-8') as outfile:
        outfile.write(content)

import csv
from collections import OrderedDict
def load_ann_sent_dict_from_acl_rd_tec_file(file):
    with open(file, 'r', encoding='utf-8') as infile:
        csvReader=csv.reader(infile, delimiter='\t',lineterminator="\n")
        sent_dict_list=OrderedDict({int(rows[0]): rows[1] for rows in csvReader if rows[0] !='#SENTENCE_ID'})
    return sent_dict_list

def load_sent_term_dict_from_acl_rd_tec_file(filepath):
    _logger=logging.getLogger(__name__)
    
    _logger.info('extracting and loading all tagged terms from [%s]', filepath)
    with open(filepath, 'r', encoding='utf-8') as infile:
        sent_term_dict=OrderedDict()
        for rows in csv.reader(infile, delimiter='\t',lineterminator="\n"):
            if rows[0] =='#SENTENCE_ID':
                continue
            if sent_term_dict.get(rows[0]) is None:                
                sent_terms=set()
                term_str=extract_tagged_term_from_sent(rows[1])
                if term_str is not None:
                    sent_terms.add(term_str)
                sent_term_dict[rows[0]]=sent_terms
            else:
                sent_term=extract_tagged_term_from_sent(rows[1])
                if sent_term is not None:
                    sent_term_dict.get(rows[0]).add(sent_term)
        #sent_term_dict=set(filter(None, sent_term_dict))
        import gc
        gc.collect()
        _logger.info("complete extraction and load for all tagged term.")
        return sent_term_dict

def load_tuple_list_from_file(filepath, pdelimiter='\t'):
    _logger=logging.getLogger(__name__)
    _logger.info('loading tuple list from [%s]', filepath)
    tuple_list=list()
    
    text_content_list=read_by_line(filepath)
    
    for content in text_content_list:
        word_freq=content.split(pdelimiter)
        tuple_list.append((word_freq[0], word_freq[1]))
        
    return tuple_list        

import pandas as pd
def load_terms_from_csv(dict_csv_file):
    '''
    load terms from term dictionary csv file
    return set, term set from first column
    '''
    data = pd.read_csv(dict_csv_file,header=None)
    return set(data[0])
      
from bs4 import BeautifulSoup
def extract_tagged_term_from_sent(_tagged_sentence):
    _logger=logging.getLogger(__name__)
    
    term_tag_content_pattern='(<term id[\s\S]*<\/term>)'
    
    import re
    m=re.search(term_tag_content_pattern,_tagged_sentence)
    if m:
        found=m.group(1)
    #print("found text snippet:", found)
    found_tag_snippet=found    
    
    try:
        soup = BeautifulSoup(found_tag_snippet)
        ann_type=soup.term['ann']
        
        term_str=soup.term.string
        if ann_type != '0':
            return term_str
        else:
            return None
    except TypeError:
        #print("No tagged term in the sentence [%s]" %_tagged_sentence.encode('utf-8'))
        _logger.error("No tagged term in the sentence [%s]" %found_tag_snippet)
    except KeyError:
        _logger.error("No attribute in term tag in the sentence [%s]" %found_tag_snippet)
    finally:
        soup.decompose()
    
    return None    

def read_by_line(filePath):
    """
    load file content
    return file content in list of lines
    """
    DELIMITER = "\n"
    with open(filePath, encoding="utf-8") as f:
        content = [line.rstrip(DELIMITER) for line in f.readlines()]
    return content

def path_leaf(path):
    import ntpath
    head, tail = ntpath.split(path)
    return tail or ntpath.basename(head)    
    
import json
def export_set_to_json(term_set,outputFile):    
    with open(outputFile, mode='w', encoding='utf-8') as f:
            json.dump(list(term_set), f, indent=2)

def load_list_from_json(jsonfile):
    with open(jsonfile, mode='r', encoding='utf-8') as f:
        term_list=json.loads(f.read())
    return term_list

class HeadRequest(urllib.request.Request):
    def get_method(self):
        return 'HEAD'

def is_image(doc_url):
    """
    detect the file content for the file type whether is image
    """
    response= urllib.request.urlopen(HeadRequest(doc_url))
    maintype= response.headers['Content-Type'].split(';')[0].lower()
    if maintype is not None and maintype.startswith('image'):
        return True

    return False


def is_url_accessible(doc_url):
    """
    detect the accessibility via the file URL
    :param doc_url:
    :return: True or False
    """
    import urllib.error
    try:
        if urllib.request.urlopen(doc_url).getcode() == 200:
            return True
    except urllib.error.HTTPError as error:
        print("URL [%s] is not accessible: %s"%(doc_url, error))

    return False

#####################################
##########Testing####################
#####################################

def test_tuple_list_loading():
    tuple_list=load_tuple_list_from_file("../config/bnc_unifrqs.normal")
    print("bnc freq list:", len(tuple_list))
    print(tuple_list[0])

def test_is_url_accessible():
    # http://speak-pc.k-now.co.uk/uploads/attachment/attachment/15/ORB_Decarb_Anneal.jpg
    print(is_url_accessible("http://www.cs.toronto.edu/~bonner/courses/2014s/csc321/lectures/lec51.pdf"))

if __name__ == '__main__':
    # test_tuple_list_loading()
    test_is_url_accessible()