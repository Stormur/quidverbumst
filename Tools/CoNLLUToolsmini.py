#The following code has been developed by Flavio Massimiliano Cecchini between 2018 and 2025. It is part of a package that will hopefully be officially released at some point. Please give credit to the author if you use any part of it. 
#Contact: flaviomassimiliano.cecchini at kuleuven.be

from collections import namedtuple

##Recurrent structures

#Structure of an annotation row in a CoNLL-U file
CoNLLURow = namedtuple('CoNLLURow', 'id form lemma upos xpos feats head deprel deps misc') 
CoNLLURow.__new__.__defaults__ = ('_',)*len(CoNLLURow._fields) 

#Classification of parts of speech according to different dimensions (auto = autosemantic, syn = synsemantic, main = representing of one of the three main phrase units, mod = modifier [adjectives], clit = clitic, meta = metapredicating, pred = predicating [verbs], ref = referent [nouns], alex = not a lexical element)
UDPos = {'ADJ':('auto','main','mod'),\
		 'ADP':('syn','clit'),\
		 'ADV':('syn','auto','main','meta','mod'),\
		 'AUX':('syn','main','pred'),\
		 'CCONJ':('syn','clit'),\
		 'DET':('syn','main','mod'),\
		 'INTJ':('meta',),\
		 'NOUN':('auto','main','ref'),\
		 'NUM':('syn','main','mod'),\
		 'PART':('syn','clit','meta'),\
		 'PRON':('syn','main','ref'),\
		 'PROPN':('auto','main','ref'),\
		 'PUNCT':('alex',),\
		 'SCONJ':('syn','clit'),\
		 'SYM':('alex'),\
		 'VERB':('auto','main','pred'),\
		 'X':(),\
		 'REL':('auto','meta')\
		}


##Methods to read and write CoNLL-U (plus) files

#Generator of trees represented as directed graphs by means of Networkx; features are stored as named tuples under 'features'. The index of a node can be any positive real number, expressed with a given decimal separator (decsep), which has to be different from the dot or the hyphen. Only order is relevant, indices will be recreated when printing the tree (see method).
#Every node is identified by a couple of real numbers: a positive index (zero only for the formal root) and a negative range for multiword tokens, zero otherwise.
#Also an empty tree, i.e. with no syntax, can be read
#Enhanced dependencies are not yet implemented
def readCoNLLU(conllu,comments='#',sents='sent_id',encoding='utf8', decsep=',',syntax=True,plus=False) : 
	
	from collections import namedtuple
	import regex, networkx
	from networkx.algorithms.cycles import simple_cycles
	from networkx.classes.function import is_empty
	
	if decsep in ('-','.') : #not admitted, already used for ranges and extra nodes in enhanced annotation
		raise Exception('Careful! The decimal separator must differ from . or -.')
	
	separators = regex.compile(r'[.-]') 
	interval = regex.compile(r'\p{{N}}+{}?\p{{N}}*-\p{{N}}+{}?\p{{N}}*'.format(decsep,decsep)) 
	
	sentence = {}

	with open(conllu,'r',encoding=encoding) as document :
		
		#Definition of fields and rows
		fields = ('id', 'form', 'lemma', 'upos', 'xpos', 'feats', 'head', 'deprel', 'deps', 'misc')
		plusfields = ()
		if plus :
			plusfields = tuple(map(lambda x : x.replace(':','_'),document.readline()[len('# global.columns = '):].strip(' \n').split(' ')))
		else :
			plusfields = tuple(fields)
		#
		nfields = len(plusfields)
		CoNLLURow = 	namedtuple('CoNLLURow', ' '.join(map(str.lower,plusfields)))
		CoNLLURow.__new__.__defaults__ = tuple(('_' if c in fields else '*') for c in plusfields)  
		#
		
		tree = networkx.DiGraph() 
		
		for row in document :
			
			row = row.strip('\n\r ')
			
			if row.startswith(comments) : 
			
				comm, _, value = row[1:].partition('=')
				sentence[comm.strip()] = value.strip()
				
				if comm.strip() == sents :
					tree = networkx.DiGraph() #syntactic tree: rooted, oriented tree with linear order on the nodes
					tree.add_node((0,0), features = CoNLLURow(id=(0,0))) #artificial node root from which the tree descends
			#	
			elif row.startswith(('1','2','3','4','5','6','7','8','9')) : #token of any kind #this is the most specific condition possible, made explicit

				node = CoNLLURow._make(row.split('\t')[:nfields])
				
				for f in {'feats','misc'}.intersection(plusfields) : #Plus files do not necessarily have feats nor misc
					node = node._replace(**{f : readUDfeatures(getattr(node,f))}) #We need to convert feats-like strings into dictionaries, and viceversa
				#
			
				index = list(map(lambda  x : float(x.replace(decsep,'.')),regex.split(separators,node.id))) #the dot is needed by Python floats
				index += [0]*(2-len(index)) #ordering always works on couples; zero is the default value for regular words
				if regex.fullmatch(interval,node.id) : #treatment of multiword tokens
					index[1] = index[0] - index[1] #the span of the range is given by a negative number
				node = node._replace(id=tuple(index))
				
				try : 
					node = node._replace(head=int(node.head)) #we prefer an integer instead of a string
				except (ValueError) : #when there is no syntax
					pass 
				
				tree.add_node(tuple(map(int,node.id)), features=node._replace(head=(node.head,0) if isinstance(node.head,int) else node.head)) #option for headless nodes, e.g. multiword tokens
				if isinstance(node.head,int) :
					tree.add_edge((node.head,0),node.id) 
			#
			elif not is_empty(tree) or (not syntax and tree.nodes()) : 
				yield sentence, tree
				tree = networkx.DiGraph() #we re-initialise the syntactic tree
				sentence = {}
			#
			
		#to print the final tree	
		if not is_empty(tree) or (not syntax and tree.nodes()) :
			yield sentence, tree
#

#Produces a dictionary out of a feats-like string, taking into account possible multiple values for a feature with tuples
def readUDfeatures(ftstring,null=('_',),sepfeat='|',sepval='=',sepint=',') : 
	
	if ftstring in null :
		return {}
	else :
		return { f:tuple(v.split(sepint)) for f,v in [ft.split(sepval,maxsplit=1) for ft in ftstring.split(sepfeat) if ft not in null and sepval in ft]} #tries to make up for faulty strings (e.g. empty values)
#

#The inverse of the previous method, either from a dictionary or a named tuple
def writeUDfeatures(tfeats,sepfeat='|',sepval='=',sepint=',') : 
	
	if not any(tfeats.values()) : #even if we have feature names, if they are empty it means they have not to be annotated
		return '_'
	else : 
		return sepfeat.join([sepval.join([f,sepint.join(sorted(( (v,) if isinstance(v,str) else v )))])\
						 for f,v in sorted(tfeats.items(), key = lambda x : x[0].lower()) if v]) #we need to be able to treat at the same time values expressed as bare strings or as tuples
#	


##Secondary extractive methods

#Returns a node of the syntactic tree as a set of features
def conllunode(a,i) :
	return a.nodes[i]['features']
#	

#Returns only syntactic words
def syntacticwords(tree) : 
	for n in sorted(tree) : 
		if n[0] > 0 and n[1] == 0 :
			yield conllunode(tree,n) #tree.nodes[n]['features']
#

#Given a node in a syntactic trees, it extracts a subtree satisfying all conditions for dependency relations and/or parts of speech (set as functional by default, returning it in form of a named tuple combining and counting forms/lemmas/POS/relations/features
#The node is represented just by the index
def extractnucleus(tree,node,funcrel=('expl','advmod','discourse','aux','cop','mark','nummod','det','clf','case','cc','punct'),funcpos=('ADV','ADP','AUX','CCONJ','DET','INTJ','NUM','PART','PRON','SCONJ','PUNCT'),multi=('flat','fixed','goeswith')) : 
	
	import networkx as nx
	from itertools import chain
	from collections import Counter, namedtuple
	
	Nucleus = namedtuple('Nucleus', 'ids forms lemmas upos feats deprels') 

	criteria = lambda x : ((tree.nodes[x]['features'].deprel.split(':')[0] in funcrel if funcrel else True) and (tree.nodes[x]['features'].upos in funcpos if funcpos else True)) or (tree.nodes[x]['features'].deprel.split(':')[0] in multi if multi else False)
		
	nucleus = [node]
	corona = list(filter(criteria, nx.descendants_at_distance(tree,node,1)))
	nucleus.extend(corona)
	
	while corona :
		corona = list(chain.from_iterable([filter(criteria, nx.descendants_at_distance(tree,c,1)) for c in corona]))
		nucleus.extend(corona)
	#
	
	nucleus = sorted(nucleus) #it might be useful to keep the linear order of the nucleus, especially for printing the form sequence
	
	combonucleus = Nucleus(ids = nucleus,\
						   forms = tuple([tree.nodes[i]['features'].form for i in nucleus]),\
						   lemmas = tuple([tree.nodes[i]['features'].lemma for i in nucleus]),\
						   upos = tuple([tree.nodes[i]['features'].upos for i in nucleus]),\
						   feats = featsfusion([tree.nodes[i]['features'].feats for i in nucleus]),\
						   deprels = tuple([tree.nodes[i]['features'].deprel for i in set(nucleus) - {node}]) ) #we usually do not want the relation of our subtree's root, as it is "external" #!Asymmetry with the other lists
	
	return combonucleus
#	

#Other manipulations of data

#It takes a list of feats-like dictionaries and fuses it in one, taking into count the multiplicity of feature values (e.g. Polarity=Neg appearing twice as opposed to once, which can make a difference in some languages)
def featsfusion(flist) : 

	from collections import defaultdict,Counter
	import collections.abc
	
	fusion = defaultdict(Counter)
	
	for d in flist :
		for k,v in d.items() :
			
			multi = isinstance(v,collections.abc.Iterable) and not isinstance(v,str) #we accept both bare values, or tuples of values
			
			fusion[k].update(v if multi else tuple(v,))
	#
	
	return dict(**fusion) #better than a defaultdict as absent values will return a KeyError
#

