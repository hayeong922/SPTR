import time
import sys

#words=['goods','goood','gooder', 'The','Trie','data','structure','keeps','a set of words', 'organized', 'with one node for']

NodeCount = 0
WordCount = 0

from collections import OrderedDict
def load_dict_from_csv(dict_csv_file):
    import csv
    with open(dict_csv_file, 'r', encoding='utf-8') as in_f:
        reader=csv.reader(in_f)
        for rows in reader:
            termDict=OrderedDict({rows[0]: rows[1] for rows in reader})
    return termDict

def levenshtein_similarity(str1,str2):
        '''
        Implements the basic Levenshtein algorithm providing a similarity measure between two strings
        return actual / possible levenstein distance to get 0-1 range normalised by the length of the longest sequence
        
        e.g., http://www.pris.net.cn/wp-content/uploads/2013/12/PRIS2013.notebook.pdf
        '''
        #sim_score=self.load_sim_from_memory(str1, str2)
        #if sim_score is None:
        from distance import nlevenshtein
        dist=nlevenshtein(str1, str2, method=1)
                
        sim_score= 1 - dist
        
        return sim_score

# The Trie data structure keeps a set of words, organized with one node for
# each letter. Each node has a branch for each letter that may follow it in the
# set of words.
class TrieNode:
    def __init__(self):
        self.word = None
        self.children = {}

        global NodeCount
        NodeCount += 1

    def insert( self, word ):
        node = self
        for letter in word:
            if letter not in node.children: 
                node.children[letter] = TrieNode()

            node = node.children[letter]

        node.word = word

# The search function returns a list of all words that are less than the given
# maximum distance from the target word
def search( word, maxCost, trie):

    # build first row
    currentRow = range( len(word) + 1 )

    results = []

    # recursively search each branch of the trie
    for letter in trie.children:
        searchRecursive( trie.children[letter], letter, word, currentRow, 
            results, maxCost )

    return results

# This recursive helper is used by the search function above. It assumes that
# the previousRow has been filled in already.
def searchRecursive( node, letter, word, previousRow, results, maxCost ):

    columns = len( word ) + 1
    currentRow = [ previousRow[0] + 1 ]

    # Build one row for the letter, with a column for each letter in the target
    # word, plus one for the empty string at column 0
    for column in range( 1, columns ):

        insertCost = currentRow[column - 1] + 1
        deleteCost = previousRow[column] + 1

        if word[column - 1] != letter:
            replaceCost = previousRow[ column - 1 ] + 1
        else:                
            replaceCost = previousRow[ column - 1 ]

        currentRow.append( min( insertCost, deleteCost, replaceCost ) )

    # if the last entry in the row indicates the optimal cost is less than the
    # maximum cost, and there is a word in this trie node, then add it.
    if currentRow[-1] <= maxCost and node.word != None:
        results.append( (node.word, currentRow[-1] ) )

    # if any entries in the row are less than the maximum cost, then 
    # recursively search each branch of the trie
    if min( currentRow ) <= maxCost:
        for letter in node.children:
            searchRecursive( node.children[letter], letter, word, currentRow, 
                results, maxCost )
'''
start = time.time()
results = search("TR", 3, trie)
end = time.time()

for result in results: 
    print(result)      

print("Search took %g s" % (end - start))
'''

#print(levenshtein_similarity('O\'Nell', 'O Nell'))