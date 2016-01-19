__author__ = 'jieg'

import logging
import requests
import json

import os
from SolrClient import SolrClient
from FileUtil import is_url_accessible
from FileUtil import is_image
from SolrClient import SolrClient
from IndustryTermRecogniser import IndustryTermRecogniser

remote_solr_server="http://speeak-pc.k-now.co.uk:8983/solr/default/"
local_solr_server="http://localhost:8983/solr/tatasteel"
# local_solr_server="http://oakanalysis.shef.ac.uk:8983/solr/tatasteel"
# attachment retrieval api to access document store
attachment_retrieval_api = "http://speeak-pc.k-now.co.uk/mobile/api/v2/attachments"
# authorisation token to access documents
attachment_retrieval_api_auth_token="Token token=0c3737ded50f387416cb0492022d0b18"


class Integrator(object):
    """
    Provide integration with KNow Knowledge Portal as scheduled batch job
    """
    def __init__(self):
        self._logger=logging.getLogger(__name__)
        self.remote_solr_client = SolrClient(remote_solr_server)
        self.local_solr_client=SolrClient(local_solr_server)

    def batch_processing_product_issue_attachments(self):
        """
        query remote Solr server to retrieve all the attachment ids
        :return:
        """
        self._logger.info("starting to retrieving attachement urls and batch indexing textual attachments ...")
        # solrClient=SolrClient(remote_solr_server)

        batch_num=10

        response = self.remote_solr_client.load_documents_by_custom_query('attachment_ids_txt:*',start=0,rows=batch_num)
        total_num = response['numFound']
        self._logger.info("total number of document with attachments: [%s]", total_num)

        if total_num > batch_num :
            for start_index in range(0,total_num,batch_num):
                response = self.remote_solr_client.load_documents_by_custom_query('attachment_ids_txt:*',
                                                                                  start=start_index,
                                                                                  rows=batch_num)
                docs = response['docs']
                self.batch_indexing_documents(docs)
                self._logger.info("batch indexing documents. progress [%s]",start_index)

        self._logger.info("complete batch processing of documents. Documents has been indexed completely.")

    def batch_indexing_documents(self,docs):
        """
        batch process a number of attachments associated with product issue

        :param docs: dictionary, Solr document objects
        :return:
        """
        self._logger.info("batch processing and indexing [%s] product issues ..." % len(docs))

        docs_to_index=[]

        for doc in docs:
            prod_issue_doc_id=doc['id']
            attachment_ids=doc['attachment_ids_txt'] if 'attachment_ids_txt' in doc else ''

            # domain specific metadata
            prod_issue=doc['product_issue_details#productIssue_s'] if 'product_issue_details#productIssue_s' in doc else ''
            product=doc['product_issue_details#product_s'] if 'product_issue_details#product_s' in doc else ''
            prod_issue_location=doc['product_issue_details#location_s'] if 'product_issue_details#location_s' in doc else ''
            prod_issue_owner=doc['product_issue_details#owner_s'] if 'product_issue_details#owner_s' in doc else ''

            location_type=doc['location#type_s'] if 'location#type_s' in doc else ''
            location_local_name=doc['location#localName_s'] if 'location#localName_s' in doc else ''

            metadata_dict={"literal.product_issue_details#productIssue_s":prod_issue,
                           "literal.product_issue_details#product_s":product,
                           "literal.product_issue_details#location_s":prod_issue_location,
                           "literal.location#type_s":location_type,
                           "literal.product_issue_details#owner_s":prod_issue_owner,
                           "literal.location#localName_s":location_local_name,
                           "literal.prod_issue_doc_id_s":prod_issue_doc_id}

            for attachment_id in attachment_ids:
                attachment_url = self.request_attachment_url_by_id(attachment_id)
                if not is_url_accessible(attachment_url):
                    self._logger.warn("The attachment [%s] is not accessible.", attachment_url)
                    continue

                if is_image(attachment_url):
                    self._logger.warn("The attachment [%s] is image. Skip for indexing", attachment_url)
                    continue

                existing_doc = self.local_solr_client.load_document_by_id(attachment_url)
                if existing_doc is None:
                    self.local_solr_client.update_document_by_url(attachment_url,metadata=metadata_dict)
                else:
                    # if current doc is existed
                    #   update existing doc with possible new metadata
                    existing_doc.update(metadata_dict)
                    self.local_solr_client.update_document_by_url(attachment_url,metadata=existing_doc)

            # config Solr for improved indexing speed
            # self.solr_client.commit_all()


    @staticmethod
    def request_attachment_url_by_id(attachment_id):
        """
        request attachment url by attachement id
        :param attachment_id:
        :return: string, attachment url
        """
        _headers={"Authorization":attachment_retrieval_api_auth_token}
        attachment_retrieval_get_api=attachment_retrieval_api

        r = requests.get(attachment_retrieval_get_api+"/"+str(attachment_id),headers=_headers)
        if r.status_code == 200:
            response=json.loads(r.text,encoding="utf-8")
            attachment_url = response["url"]
        else:
            raise Exception(r.reason)

        return attachment_url

###########################################
######### test & evaluate #################
###########################################

def test_request_attachment_url_by_id():
    try:
        attachment_url = Integrator.request_attachment_url_by_id("15")
        print(attachment_url)
    except Exception as error:
        print("Exception: ", error)


def test_retrieve_attachment_ids():
    integrator = Integrator()
    integrator.retrieve_attachment_ids()


def test_batch_processing_product_issue_attachments():
    integrator = Integrator()
    integrator.batch_processing_product_issue_attachments()

if __name__ == '__main__':
    import logging.config
    logging.config.fileConfig(os.path.join(os.path.dirname(__file__), '..', 'config', 'logging.conf'))

    integrator = Integrator()
    integrator.batch_processing_product_issue_attachments()

    trTagger = IndustryTermRecogniser(local_solr_server)
    trTagger.terminology_tagging()