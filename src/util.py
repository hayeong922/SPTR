'''
A mix of utilities
'''

class TermUtil(object):
    @staticmethod
    def normalise(term):
        return term.lower().replace('-',' ')
