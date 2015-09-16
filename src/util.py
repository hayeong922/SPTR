'''
Created on 15 Sep 2015

@author: jieg
'''
class TermUtil(object):
    @staticmethod
    def normalise(term):
        return term.lower().replace('-',' ')