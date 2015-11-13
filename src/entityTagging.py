'''
Copyright &copy;2015 Sheffield University (OAK Group)
All Rights Reserved.

Developer(s):
   Jie Gao (j.gao@sheffield.ac.uk)

@author: jieg
'''
import requests

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

class Calais():
    """
    Experimental Calais entity tagger
    
    refer to http://developer.permid.org/open-calais-api/open-calais-tagging-reference/
    http://new.opencalais.com/wp-content/uploads/2015/06/Thomson-Reuters-Open-Calais-API-User-Guide-v3.pdf
    """

    _CALAIS_URL="https://api.thomsonreuters.com/permid/calais"
    #_CALAIS_URL="http://api.opencalais.com/enlighten/rest/"
    _uniqueAccessKey="FYiVFJUjyVSGhG7LtofR1iNAOHNWGJZQ"
    #_uniqueAccessKey="f7w6w5n8e3ygzkyft7xct6tn"
    _headers={"X-AG-Access-Token":_uniqueAccessKey,"Content-Type":"text/raw", "outputformat":"application/json"}
    
    
    ENTITY_TYPE_PERSON="Person"
    ENTITY_TYPE_ORG="Organisation"
    ENTITY_TYPE_LOC="Location"
    ENTITY_TYPE_URL="URL"
    ENTITY_TYPE_EMAIL="EmailAddress"
    ENTITY_TYPE_FAC="Facility"
    ENTITY_TYPE_PHONE="PhoneNumber"
    ENTITY_TYPE_POSITION="Position"
    ENTITY_TYPE_PROD="Product"
    ENTITY_TYPE_TECH="Technology"
    ENTITY_TYPE_INDUSTRY_TERM="IndustryTerm"
    
    #this field is referred by indexer for batching indexing new fields
    SUPPORTED_ENTITIES=set([ENTITY_TYPE_PERSON,ENTITY_TYPE_ORG,ENTITY_TYPE_LOC,ENTITY_TYPE_URL,
                            ENTITY_TYPE_EMAIL,ENTITY_TYPE_FAC,ENTITY_TYPE_PHONE,
                            ENTITY_TYPE_POSITION,ENTITY_TYPE_PROD,ENTITY_TYPE_TECH,ENTITY_TYPE_INDUSTRY_TERM])
    
    
    def __init__(self, api_key=None):
        if api_key:
            self._uniqueAccessKey=api_key
        import logging
        #import logging.config
        #logging.config.fileConfig(os.path.join(os.path.dirname(__file__), '..', 'config', 'logging.config'))
        self._logger=logging.getLogger(__name__)
    
    def rest_POST(self, content, content_type="TEXT/RAW"):
        """
        send post request
        return json result
        """
        #_data={"Text":content}
        _data={"content":content}

        _headers={"X-AG-Access-Token":self._uniqueAccessKey,"Content-Type":content_type, "outputformat":"application/json"}
        
        #urllib.request.urlopen(...).read()
        result=requests.post(self._CALAIS_URL,data=_data,headers=_headers, verify=False)
        print(result.text)
        print(result.content)
        try:
            data = result.json()
            #print("data:", data)
        except ValueError:
            self._logger.error("Error while decoding json results from [%s]", result)
            data={}    
        #data=json.loads(result.text)
        return data
    
    
    @staticmethod
    def extract_entities(json_result):
        '''
        
        '''
        #refer to OpenCalais metadata types Thomson-Reuters-Open-Calais-API-User-Guide-v3.pdf
        location={"City","Country", "ProvinceOrState", "Region", "Continent","NaturalFeature"}
        organisation={"Company", "Organization"}
        person={"Person", "Journalist"}
        url={"URL"}
        emailAddr={"EmailAddress"}
        facility={"Facility"}
        phoneNum={"PhoneNumber", "FaxNumber"}
        position={"Position"}
        product={"Product"}
        technology={"Technology"}
        industryTerm={"IndustryTerm"}
        
        entity_dist={Calais.ENTITY_TYPE_LOC:set(), Calais.ENTITY_TYPE_ORG:set(), Calais.ENTITY_TYPE_PERSON:set(), 
                     Calais.ENTITY_TYPE_URL:set(), Calais.ENTITY_TYPE_EMAIL:set(), Calais.ENTITY_TYPE_FAC:set(), Calais.ENTITY_TYPE_PHONE:set(),
                     Calais.ENTITY_TYPE_POSITION:set(), Calais.ENTITY_TYPE_PROD:set(), Calais.ENTITY_TYPE_TECH:set(), 
                     Calais.ENTITY_TYPE_INDUSTRY_TERM:set()}
        
        if json_result:
            for key, items in json_result.items():
                if "_typeGroup" in items and items['_typeGroup'] == 'entities':
                    if items["_type"] in location and items["name"]:
                            entity_dist[Calais.ENTITY_TYPE_LOC].add(items["name"])
                    if items["_type"] in organisation and items["name"]:
                        entity_dist[Calais.ENTITY_TYPE_ORG].add(items["name"])
                    if items["_type"] in person and items["name"]:
                        entity_dist[Calais.ENTITY_TYPE_PERSON].add(items["name"])
                    if items["_type"] in url and items["name"]:
                        entity_dist[Calais.ENTITY_TYPE_URL].add(items["name"])
                    if items["_type"] in emailAddr and items["name"]:
                        entity_dist[Calais.ENTITY_TYPE_EMAIL].add(items["name"])
                    if items["_type"] in facility and items["name"]:
                        entity_dist[Calais.ENTITY_TYPE_FAC].add(items["name"])
                    if items["_type"] in phoneNum and items["name"]:
                        entity_dist[Calais.ENTITY_TYPE_PHONE].add(items["name"])
                    if items["_type"] in position and items["name"]:
                        entity_dist[Calais.ENTITY_TYPE_POSITION].add(items["name"])
                    if items["_type"] in product and items["name"]:
                        entity_dist[Calais.ENTITY_TYPE_PROD].add(items["name"])
                    if items["_type"] in technology and items["name"]:
                        entity_dist[Calais.ENTITY_TYPE_TECH].add(items["name"])
                    if items["_type"] in industryTerm and items["name"]:
                        entity_dist[Calais.ENTITY_TYPE_INDUSTRY_TERM].add(items["name"])
            
        #print(entity_dist)
        return entity_dist
    
    def extract_entities_from_raw_text(self, content):
        #print("content before calais tagging:", content)
        json_result = self.rest_POST(content)
        #print("=======================result=====================")
        #print(json_result)
        return Calais.extract_entities(json_result)
    
    def test_http_request(self):
        '''
        from http import client
        conn=client.HTTPSConnection(self._CALAIS_URL)
        
        conn.request("POST", url, body, headers)
        '''
        
        "ECDH+AESGCM:DH+AESGCM:ECDH+AES256:DH+AES256:ECDH+AES128:DH+AES:ECDH+HIGH:DH+HIGH:ECDH+3DES:DH+3DES:RSA+AESGCM:RSA+AES:RSA+HIGH:RSA+3DES:!aNULL:!eNULL:!MD5"
        #print(requests.packages.urllib3.util.ssl_.DEFAULT_CIPHERS)
    
def main():
    #calaisAPI = Calais()
    import entityTagging
    oldCalaisAPI= entityTagging.Calais("f7w6w5n8e3ygzkyft7xct6tn")
    
    content="If sample is complete and slag-free, send to BOS Laboratory. London is a great city. Shanghai is a good city. Tom Golden is a very nice person. Jerry is also very nice. Current date is 22/06/2015. Microsoft is a good company. The steel is made from the Porter Brook river."
    content1=" Casts for CN\n  Hayange liaison\n Andrew Clark\n For the head hardened quality (9647/48) we increased the settings from 200  to 490 to get better stirring in the mould.  We were suffering from cracks  on the side of the head thought to be due to poor powder performance. Jon Jim Worsley/UK/Corus  \t \tTo \tRichard Longbottom/UK/Corus@Corus01, Andrew Anderson/UK/Corus@Corus01,  Martyn Eames/UK/Corus@Corus01 \tcc \tAndrew Clark/UK/Corus@Corus01, Jon Pickford/UK/Corus@Corus01 \tSubject \t \t \t \t \t All  See below request from Hayange -  refers to work done on EMS around   2003.   - Andy / Richard, assume you were involved.  Pascale has asked the question,  what work has been done following this to  reduce seg streaking in rail head. ?  As far as I can see we have only 2 grades set with reduced EMS @ 200 A  (family 48) - 9678Q & 9658Q  -  These were last made in 2006 and 2003.  All other rail grades are cast using 490 A and have been since. ? Please  give me a call to discuss  / let me have any comments for Hayange  Thanks.  Pascal SECORDEL/FR/Corus@SOGERAIL  \t \tTo \tJim Worsley/UK/Corus@Corus01 \tcc \tJon Pickford/UK/Corus@Corus01, Peter Smith/UK/Corus@Corus01, Kim  Southward/UK/Corus@Corus01, Pascale BONNET/FR/Corus@Sogerail, Daniel  BRARD/FR/Corus@Sogerail, Colin MCGIBBON/FR/Corus@Sogerail, Denis  LITZENBURGER/FR/Corus@Sogerail \tSubject \tCasts for CN \t \t \t \t \t Hi Jim, We are expecting an order in the next monthes from Canadian National  (136RE, grade MHH code B225).  - H2 level that cannot be over 2,5 ppm in the liquid steel (but  derogations at 3,0 ppm were agreed by CN in the past)  - streakings are not allowed in the upper part of the head and in the  lower part of the foot.   You will find attached the reports of trials done some years ago aiming at  reducing the streaking, acting on the EMS current level, you have probably  got them. Could you have a look on these issues and tell us is some improvements  have been done in the last 3 years on the CC to reduce the streaking  effects ? In any case, we will take the opportunity of a rolling planned in 2 weeks  for Canadian Pacific (CP) refering to AREMA, to evaluate if the  macrosegregations we will get are in conformance or not with the CN  standard. We will forward you obviously the results. Best regards,   Pascal Secordel Corus Rail France"
    content2="Software issues at SK in handling part casts. RL to check  progress with PM team."
    #json_result = calaisAPI.rest_POST(content)
    #calaisAPI.extract_entities(json_result)
    #result=calaisAPI.extract_entities_from_raw_text(content2.encode(encoding='utf_8'))
    result = oldCalaisAPI.analyze(content2)
    entityResult=result.extract_supported_entities()
    #extractedEntities=Calais.extract_entities(result.entities)
    print(entityResult)

if __name__ == '__main__':
    main()   