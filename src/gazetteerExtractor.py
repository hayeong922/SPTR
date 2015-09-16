"""Toolsets to mine structured data and export data as gazetteer file serialised into JSON
"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

import csv
def remove_linebreak(inFilePath,outFileName):
    with open(inFilePath, mode='r', encoding='utf-8') as infile:
        reader = csv.reader(infile)
        steelDict={rows[0].replace('\n',''):rows[1].replace('\n','') for rows in reader}        
        write_to_csv_dict(outFileName, steelDict)
    return steelDict

def write_to_csv_dict(outFileName, steelDict):
    steelDict=OrderedDict(sorted(steelDict.items(), key=lambda t: t[0].upper()))
    with open(outFileName, mode='w', encoding='utf-8') as outfile:
        csvwriter = csv.writer(outfile,delimiter=',',quotechar='"',quoting=csv.QUOTE_ALL,lineterminator="\n")
        for key in steelDict:
            csvwriter.writerow([key,steelDict[key]])

def export_dict_to_csv(dictData,outFilePath):
    with open(outFilePath, mode='w', encoding='utf-8') as outfile:
        csvwriter = csv.writer(outfile,delimiter=',',quotechar='"',quoting=csv.QUOTE_ALL,lineterminator="\n")
        for key in dictData:
            csvwriter.writerow([key,','.join(dictData[key])])
"""    with open(outFilePath, 'w') as f:  # Just use 'w' mode in 3.x
        w = csv.DictWriter(f, my_dict.keys())
        #w.writeheader()
        w.writerow(my_dict)"""

import json
from collections import OrderedDict
def export_to_json(termDict,outputFile,is_sorted=True,cls=None):
    if is_sorted:
        termDict=OrderedDict(sorted(termDict.items(), key=lambda t: t[0].upper()))
    
    with open(outputFile, mode='w', encoding='utf-8') as f:
            json.dump(termDict, f, indent=2,cls=cls)

def load_termDict_from_json(json_file):
    with open(json_file,'r',encoding='utf-8') as f:
        #termDict=json.load(f)
        termDict=json.load(f,object_pairs_hook=OrderedDict)
    return termDict

def load_dict_from_csv(dict_csv_file):
    import csv
    with open(dict_csv_file, 'r', encoding='utf-8') as in_f:
        reader=csv.reader(in_f)
        termDict=OrderedDict({rows[0]: rows[1] for rows in reader})
    return termDict

def load_binary_tuple_from_file(tuple_file):
    import csv
    with open(tuple_file, 'r', encoding='utf-8') as infile:
        csvReader=csv.reader(infile, delimiter='\t',lineterminator="\n")
        binary_tuple_list=list((rows[0],rows[1]) for rows in csvReader)
    return binary_tuple_list

import urllib.request
import re
def htmlExtractor_nass_glassory():
    url="http://www.nass.org.uk/glossary/"
    response = urllib.request.urlopen(url)
    html = response.read()
    html = html.decode('utf-8')
    with open("rawNasshtml.txt", mode='w',encoding='utf-8') as outfile:
         outfile.write(html)      
    """regex_pattern = r"(<h3 class=\"glos\">(\n)?(\n<li>)?)(.+)((<\/li>\n)?<\/h3>)?(\n\n)<p>(.+[\n]?.*)<\/li>"
        pattern=re.compile(r"(<h3 class=\"glos\">(\n)?(\n<li>)?)(.+)((</li>\n)?\n\n?</h3>)?") -> 322
        pattern=re.compile(r"<p>(.+[\n]?.*)</li>") ->322
    """
    
    pattern_termName=re.compile(r"<h3 class=\"glos\">\r?\n?[<li>]{0,5}(.+)[</li>]{0,5}\r?\n?</h3>")
    pattern_termDesc=re.compile(r"<p>(.+[\n]?.*)</li>")
    
    matches_termName = re.findall(pattern_termName,html)
    matches_termName=[term.replace('</li>\r','') for term in matches_termName]
    matches_termDesc = re.findall(pattern_termDesc,html)
    
    print('Num of matches for Nass glossary term name? %s' % (len(matches_termName)))
    print('Num of matches for Nass glossary term desc? %s' % (len(matches_termDesc)))
    
    termDictionary = dict(zip(matches_termName,matches_termDesc))
    
    return termDictionary

from bs4 import BeautifulSoup
def htmlTableExtractor_steelonthenet_terms(url):
    response = urllib.request.urlopen(url)
    html = response.read()
    html = html.decode('utf-8')
    soup = BeautifulSoup(html)
    table = soup.find("table", attrs={"class":"w96"})
    headings = [th.get_text() for th in table.find("tr").find_all("td",attrs={"class":"center"})]
    
    termsTags=table.find_all(lambda tag: tag.name=='td' and not tag.attrs)
    termDictionary = {}
    column_termName=0
    column_termDesc=1
    while (len(termsTags)>1  and column_termDesc <= (len(termsTags) - 1)):
        abbrTag = termsTags[column_termName].find("abbr")
        termFullName = abbrTag['title'] if abbrTag!=None else ""
        termAbbr = termsTags[column_termName].get_text()
        termName = termFullName+'('+termAbbr+')'
        termDesc = termsTags[column_termDesc].get_text()
        column_termName+=2
        column_termDesc+=2
        termDictionary[termName if abbrTag!=None else termAbbr] = termDesc
    return termDictionary

def steelonthenet_terms_extraction():
    links={'A - C':"http://www.steelonthenet.com/glossary.html",
           'D - H':"http://www.steelonthenet.com/files/glossary-1.html",
           'I - O':"http://www.steelonthenet.com/files/glossary-2.html",
           'P - S':"http://www.steelonthenet.com/files/glossary-3.html",
           'T - Z':"http://www.steelonthenet.com/files/glossary-4.html"}
    links=OrderedDict(sorted(links.items(), key=lambda t: t[0]))
    termDictionary={}
    for page in links:
        print("Extract table data gazetteer from '%s' page"%page)
        pageTermDict = htmlTableExtractor_steelonthenet_terms(links[page])
        termDictionary.update(pageTermDict)
    
    print("Final gazetteer size from steelonthenet.com is [%s]" % len(termDictionary))
    
    
    return termDictionary

from whoosh.lang.morph_en import variations
def get_variations(term):
    return variations(term)

def main():
    print("load 'Steel-Terminology_Tata-Steel-raw.csv' file...")
    print("processing raw data file exported from original pdf...")
    steelDict = remove_linebreak('../data/glossary/raw/Steel-Terminology-Tata-Steel-raw.csv','../data/glossary/Steel-Terminology-Tata-Steel-processed.csv')
    print('Total [%s] terms extracted into TATA Steel gazetteer!'% len(steelDict))
    print('processed dictionary data has been exported into [%s]' % '../data/glossary/Tata_Steel_Term_Gazetteer.csv')
    print('serialising data into json...')
    export_to_json(steelDict,'../data/glossary/Tata_Steel_Term_Gazetteer.json')
    print('TATA Steel Terminology dictionary has been loaded and serialised into json ../data/glossary/Tata_Steel_Term_Gazetteer.json')
    print('=============')
    
    print('Continue on processing NASS Terminology dictionary extracted from http://www.nass.org.uk/glossary/')
    nassTermDict = htmlExtractor_nass_glassory()
    write_to_csv_dict("../data/glossary/Nass_Steel_Term_Gazetteer.csv", nassTermDict)
    print('NASS Terminology gazetteer is exported to ../data/glossary/Nass_Steel_Term_Gazetteer.csv')
    export_to_json(nassTermDict,'../data/glossary/Nass_Steel_Term_Gazetteer.json')
    print('NASS Steel Terminology dictionary has been loaded and serialised into json ../data/glossary/Nass_Steel_Term_Gazetteer.json')

    print('=============')
    
    print('Continue on processing steelonthenet.com Steel Industry Glossary of Terms...')
    steelonthenetTermDict = steelonthenet_terms_extraction()
    write_to_csv_dict("../data/glossary/Steelonthenet_Term_Gazetteer.csv", steelonthenetTermDict)
    print('Steelonthenet.com gazetteer is Exported to ../data/glossary/Steelonthenet_Term_Gazetteer.csv')
    export_to_json(steelonthenetTermDict,'../data/glossary/Steelonthenet_Term_Gazetteer.json')
    print('Steelonthenet.com Terminology dictionary has been loaded and serialised into json ../data/glossary/Steelonthenet_Term_Gazetteer.json')
    print('Complete processing gazettteers!')
if __name__ == '__main__':
    main()
