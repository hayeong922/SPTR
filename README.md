# SPEEAK-PC Terminology Recognition (SPTR)

This project implements an Automatic Terminology Recognition (ATR) and automatic indexing tool providing the integration with Apache Solr using Nature Language Processing technology. The tool performs batch processing over the entire corpus in Solr/Lucene indexes and enrich the indexes/documents with the specified metadata (i.e., industry terms). The automatic indexing process transforms textual data from unstructured data to semi-structured data, which enables more advanced knowledge mining, e.g., semantic search, text summarisation,  cause analysis for business intelligence, etc.

The core of ATR is based on C-Value algorithm and contrastive corpus analysis. Following figure presents a general architecture which consists of 5 main phrases: 1) content extraction and normalisation; 2) solr indexing and pre-processing; 3) term extraction, scoring, ranking and filtering; 4) automatic term indexing; 5) search and export.

![alt tag](https://github.com/jerrygaoLondon/SPTR/blob/master/general_architecture.JPG)

## Configuration

The tool supports various configurations including Part-Of-Tagging sequence patterns for term candidate submission forms, pre-filtering and cut-off threshold based post filtering. The tool also suppors dictionary tagging with exact matching and fuzzy matching configurable. To be processed by the ATR tool, the corpus must be processed by Solr with TR aware anlayser chain as pre-requisite for subsequent term extraction. TR aware anlayser chain can be configured in various ways so as to allow domain-specific customisation.

To pre-process and index content for candidate extraction, a solr schema.xml needs 2 things:
 * A unique key field
 * A content field (from where terms are extracted) indexed with Term Recognition (TR) aware Analyser Chain
 
	For term ranking, the content field's index analyzer needs to end in shingling (solr.ShingleFilterFactory). Term vectors must be enabled so that term statistics can be queried and used for ranking algorithms.Term Offsets can also be enabled to allow term highlighting.
	
 Here is a sample TR aware content field type config :
	```
		<fieldType name="text_tr_general" class="solr.TextField" positionIncrementGap="100">
			<analyzer type="index">
				<!-- more friendly with technical terms, and good at parsing documents with terms like Oracle 8i/9i/10g/11g and DB2/UDB. -->
				<charFilter class="solr.PatternReplaceCharFilterFactory" pattern="(\.\s)" replacement=" " />
				<charFilter class="solr.PatternReplaceCharFilterFactory" pattern="(\.$)" replacement=" " />
				<charFilter class="solr.PatternReplaceCharFilterFactory" pattern="(\|)" replacement=" " />
				<charFilter class="solr.PatternReplaceCharFilterFactory" pattern="(\/)" replacement=" " />
				<charFilter class="solr.PatternReplaceCharFilterFactory" pattern="(\\t)" replacement=" \\n " />
				
				<tokenizer class="solr.StandardTokenizerFactory" />
				
				<filter class="solr.LowerCaseFilterFactory" />
				<filter class="solr.ASCIIFoldingFilterFactory"/>
				<filter class="solr.EnglishMinimalStemFilterFactory"/>
				<filter class="solr.ShingleFilterFactory" minShingleSize="2" maxShingleSize="6"
						outputUnigrams="true" outputUnigramsIfNoShingles="false" tokenSeparator=" "/>
			</analyzer>
			<analyzer type="query">				
				<tokenizer class="solr.StandardTokenizerFactory" />
				<!-- <filter class="solr.StopFilterFactory" ignoreCase="false" words="stopwords.txt" enablePositionIncrements="true" /> -->
				<filter class="solr.LowerCaseFilterFactory" />
				<filter class="solr.SynonymFilterFactory" synonyms="synonyms.txt" ignoreCase="true" expand="true" />				
				<filter class="solr.ASCIIFoldingFilterFactory"/>
				<filter class="solr.EnglishMinimalStemFilterFactory"/>
			</analyzer>
		</fieldType>
	```
 And, a sample of content filed configured with the analyser:
 
	```
	<!--Main body of document extracted by SolrCell.-->
	<field name="content" type="text_tr_general" indexed="true" stored="true" multiValued="false" termVectors="true" termPositions="true" termOffsets="true"/>
	```

In term extraction phrase, a solr schema.xml needs 2 things:
 * A multiValued string field for storing term candidates 
 * A solr analyser chain to normalise term candidates for ranking accuracy
		This needs to be consistent with content index analyser so that indexed n-grams will be matched with term candidates.
 * A field for storing final terms
		
 A sample config of term candidate field :
 
	```
	<!-- A dynamicField field can be configured for terms needs be indexed and stored with term vectors and offsets.-->
	<dynamicField name="*_tvss" type="string" indexed="true"  stored="true" multiValued="true" termVectors="true" termPositions="true" termOffsets="true"/>
	```
	
 A sample config of term solr normaliser:
 
	```
	<fieldType name="industry_term_normaliser" class="solr.TextField" positionIncrementGap="100">
		<analyzer>
			<tokenizer class="solr.StandardTokenizerFactory" />
			<!--<charFilter class="solr.PatternReplaceCharFilterFactory" pattern="(\-)" replacement=" " />-->
			
			<!-- setting of WordDelimiterFilterFactory is useful for compound words. Can be enabled to make sure tokens like "bloom485" or "TermRecognition" are split in order to improve accuracy. This can also be used to improve subsequent POS tagging and allow stop words like "year" to be matched
			-->
			<!-- see details via https://lucene.apache.org/core/4_6_0/analyzers-common/org/apache/lucene/analysis/miscellaneous/WordDelimiterFilter.html -->
			<!-- <filter class="solr.WordDelimiterFilterFactory" protected="protectedword.txt" generateWordParts="1" generateNumberParts="1" catenateWords="1" catenateNumbers="1" catenateAll="0" splitOnCaseChange="1"/> -->
			<filter class="solr.LowerCaseFilterFactory"/>
			<filter class="solr.ASCIIFoldingFilterFactory"/>
			<filter class="solr.EnglishMinimalStemFilterFactory"/>
		 </analyzer>
	</fieldType>
	```
 A sample config of final(filtered) terms:
 
	```
	<field name="industryTerm" type="industry_term_type" indexed="true" stored="true" multiValued="true" omitNorms="true" termVectors="true"/>
	<!-- Experimental field used for normalised term via term variations analysis -->
	<fieldType name="industry_term_type" class="solr.TextField" positionIncrementGap="100">
		<analyzer>
			<tokenizer class="solr.KeywordTokenizerFactory"/>		
			<charFilter class="solr.PatternReplaceCharFilterFactory" pattern="(\-)" replacement=" " />		
			<filter class="solr.LowerCaseFilterFactory"/>
			<filter class="solr.ASCIIFoldingFilterFactory"/>
			<filter class="solr.EnglishMinimalStemFilterFactory"/>
		 </analyzer>
	</fieldType>
	```
A Solr solrconfig.xml must be configured with Field Analysis Request Handler and can be configured with Solr Cell Update Request Handler (recommeded) and Language identification as an option.

## Usage
 The Term Recognition tool is run as a batch processing job and can be triggered by a simple shell script in Linux.
	
	./industry_term_enrichment.sh
	
### The run-time parameters are
 * pos_sequence_filter: a text file providing part-of-speech(pos) sequence pattern for filtering term candidate lexical units
 * stopwords: stop words list for filtering term candidates in a minimal manner
 * max_tokens: Maximum number of words allowed in a multi-word term; must also be compatible with ngram size range for solr.ShingleFilterFactory in solr schema.xml;
 * min_tokens: Minimum number of words allowed in a multi-word term; must also be compatible with ngram size range for solr.ShingleFilterFactory in solr schema.xml;
 * max_char_length: Minimum number of characters allowed in any term candidates units
 * min_char_length: Minimum number of characters allowed in any term candidates units;increase for better precision
 * min_term_freq: Minimum frequency allowed for term candidates; increase for better precision
 * PARALLEL_WORKERS: Maximum number of processes (for annotation and dictionary tagging) that can run at the same time
 * cut_off_threshold: cut-off threshold (exclusive) for term recognition
	
 * solr_core_url: Solr index core
 * solr_field_content: solr content field from where terminology and frequency information will be queried and analysed. Terminology Recognition aware NLP pipeline must be configured for this field.
 * solr_field_doc_id: solr document unique identifier field, default to 'id'
 * solr_term_normaliser: The solr terminology normalisation analyser
 * solr_field_term_candidates: solr field where term candidates will be stored and indexed
 * solr_field_industry_term: solr field where final filtered terms will be stored and indexed
	
	
 * tagging: a boolean config allows turn on and off term candidate extraction. Disabling this setting will only executing ranking for candidates and indexing filtered candidates
 * export_term_candidates: a boolean config allows to turn on and off term candidate export. Exporting (all) term candidates can help to evaluate and choose a suitable cut-off threshold.
 * export_term_variants: a boolean config allows to turn on and off term variants export.
 * term_variants_export_file_name: A file for exporting term (filtered terms) variants (CSV format by default) 
	
 * dict_tagging: a boolean config allows to turn on and off dictionary tagging
 * dictionary_file: One term dictionary file is configured here to tag the indexed documents. The dictionary file must be in csv format with two columns (term surface form and descriptions) and must not include heading in first row.
 * dict_tagger_fuzzy_matching: A boolean config to turn on and off fuzzy matching based on normalised Levenshtein distance.
 * dict_tagger_sim_threshold: similarity threshold (range: [0-1]) for fuzzy matching
 * solr_field_dictionary_term: The Solr field to where the dictionary matched terms will be indexed and stored.
 * index_dict_term_with_industry_term: A boolean field to determine whether dictionary term can indexed either separately (different solr field) or with solr_field_industry_term	