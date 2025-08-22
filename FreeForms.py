#The following code has been developed by Flavio Massimiliano Cecchini as part of the work presented in "Quid verbumst? Applying a definition of word to Latin in Universal Dependencies", SyntaxFest 2025, Ljubljana. Please give credit to the author if you use any part of it. 
#Contact: flaviomassimiliano.cecchini at kuleuven.be

#Useful imports
import sys, os, configparser, regex, dill, json, random
from pathlib import Path
from operator import itemgetter
from collections import defaultdict, Counter, namedtuple
from matplotlib import pyplot as plt
#

#Inputs, specifications and data
try :
	configurationes = sys.argv[1]
except (IndexError) :
	print('Please specify the path to a file storing the configurations for this data extraction.')
	quit()
#
confs = configparser.ConfigParser(delimiters='\t',comment_prefixes='#',inline_comment_prefixes='#')
confs.read(Path(configurationes))
#
tools = Path(confs.get('Tools','reader')).resolve()
sys.path.append(os.path.abspath(tools))
from CoNLLUToolsmini import UDPos, readCoNLLU, syntacticwords, conllunode, readUDfeatures, writeUDfeatures, extractnucleus, featsfusion
normo = Path(confs.get('Tools','normaliser')).resolve()
sys.path.append(os.path.abspath(normo))
try : 
	from Normaliser import orthonormalizatio #the name can change according to your script
	normalizator = orthonormalizatio
except ImportError :
	normalizator = lambda x : x.lower()
#
conllu = Path(confs.get('Data','conllu')).resolve()
print('Extracting data from: {}\n'.format(conllu))
morphologia = Path(confs.get('Data','derivation')).resolve()
#
ydioma = confs.get('Parameters','lang')
#


#Definition of structures and import of word lists
syntagmata = defaultdict(lambda : defaultdict(list))
singula = defaultdict(lambda : defaultdict(lambda : defaultdict(lambda : defaultdict(list))))
freeheadpos = dict()
randoff = {}
radnum = 0
sentnum = 0
#
advpos = {}
with open(morphologia / 'ADV.tsv','r',encoding='utf8') as intro : 
	for riga in intro :
		l,p = riga.strip(' \n').split('\t')
		advpos[normalizator(l)] = 'PRON' if p == 'REL' else p #See paper for this decision. The ADV treatment is specific for Latin, but can possibly readapted to other languages
#
allbdeprel = set()
with open(morphologia / 'udeprels.json','r',encoding='utf8') as intus : 
	allbdeprel = set(json.load(intus)['udeprels'])
#	
corrpos = {'PROPN': lambda x : 'NOUN', 'ADV' : lambda x : advpos.get(x,'ADV') , 'NUM' : lambda x : 'DET'} #Remapping of part-of-speech tags; see paper. This is valid universally (except for ad hoc treatment of ADV)
funcpos = {p for p,v in UDPos.items() if 'syn' in v}
alexpos = {p for p,v in UDPos.items() if 'alex' in v}
lexpos = UDPos.keys() - alexpos
phrasalia = ('csubj','ccomp','xcomp','advcl','acl','parataxis')
argumenta = ('nsubj','obj','iobj','csubj','ccomp','xcomp','obl','vocative','expl','dislocated','advcl','advmod','discourse')
aphrasalia = allbdeprel.difference(phrasalia)
singularia = allbdeprel.difference({'parataxis'}) 
sincipita = ('fixed','flat')
#


# Identification and extraction of free forms

##The following search for radical forms among the lexicon is ad hoc for Latin and uses a specific resource (LatInfLexi). It might need adjustments according to the evolution of that resources (e.g. inclusion of further parts of speech).
if ydioma == 'la' : 

	flexionarium = defaultdict(lambda : defaultdict(set))
	flpos = {'n':'NOUN','v':'VERB'}	
	
	with open(morphologia / 'LatInfLexi-forms.csv','r',encoding='utf8') as intro : 
		next(intro)
		for riga in intro :
			f,l,m,of,pf,*_ = map(lambda x : x.strip('"'),riga.strip().split(','))
			ll,lp = l.split('_')
			flexionarium[(ll,flpos[lp])][pf.replace(' ','').replace('ˈ','')].add(m) 
	#

	radicalia = defaultdict(lambda : defaultdict(set))
	
	for l,ff in flexionarium.items() : 
		communis = os.path.commonprefix(list(ff.keys()))
		if communis in ff : 
			radicalia[l[1]][tuple(sorted(ff[communis]))].add((l[0],communis))
	#		
	
	with open('_'.join(('radicalforms',ydioma)) + '.tsv','w',encoding='utf8') as exo : 
		for p,casi in radicalia.items() :
			for m,ll in casi.items() : 
				for l,f in sorted(ll,key = lambda x : regex.sub(r'\d','',x[0])[::-1]) : 
					exo.write('{}\t{}\t{}\t{}\n'.format(p,','.join(m),l,f))
	#
##

#Extraction of single-word sentences: syntax is not required
for s,a in readCoNLLU(conllu,syntax=False) :	
	
	print(s['sent_id'],end='\r')

	ln = [n for n in syntacticwords(a) if n.upos not in alexpos]
	
	if len(ln) == 1 :
		
		l = ln[0]
		
		ortholemma,orthoforma = map(normalizator,(l.lemma,l.form))
		
		cupos = corrpos.get(l.upos, lambda x : l.upos)(ortholemma)
		
		singula[cupos][ortholemma][orthoforma]['sent'].append(s['sent_id'])
		singula[cupos][ortholemma][orthoforma]['morph'].append(l.feats)
#

with open('_'.join(('singleforms',ydioma)) + '.tsv','w',encoding='utf8') as exo :
	for p,lfd in singula.items() :															 
		for l,fd in lfd.items() :
			for f,d in fd.items() :				
				omnimorpho = featsfusion(d['morph'])
				exo.write('{}\t{}\t{}\t{}\t{}\n'.format(p,\
								   						l,\
														f,\
								   						writeUDfeatures(omnimorpho),\
								   						','.join(d['sent'])\
												   		))		
##

##Two-step extraction of clausal free forms: syntax is needed #NB: if the syntax parameter of readCoNLLU is true, sentences without syntactic annotation are simply not yielded (= they are ignored)
for s,a in readCoNLLU(conllu,syntax=True) :	
	
	sentnum += 1
	
	print(s['sent_id'],end='\r')
	
	for l in syntacticwords(a) : 
		
		brel = l.deprel.split(':')[0] 
			
		#We start the extraction from roots, but exclude those that are found in a co'ordination
		if brel == 'root' and not any([conllunode(a,nd).deprel.split(':')[0] == 'conj' for nd in a[l.id]]) : 
					
			radnum += 1
			
			nucleus = extractnucleus(a,l.id,funcrel=aphrasalia,funcpos=funcpos,multi=sincipita) #we ignore possible conjuncts of dependents (e.g. "can [and must] work"; "this [and that] thing") 
			bnrels = {dr.split(':')[0] for dr in nucleus.deprels}
			subarbor = extractnucleus(a,l.id,funcrel=singularia,funcpos=lexpos,multi=sincipita)

			#We check that we really just have a sentence coinciding with a nucleus, in other words, a simple clause with no extensions or nested clauses (ignoring co-ordination). We further exclude marked elliptical structures (orphan); require the clause to be "finite" (this criterion might need adjustments for different languages in the current state of UD annotation); and given the unclear status of ADV (straddling the grammaticality cline), we exclude clauses which have an ADV in the arguments, since we require only the head be autosemantic, if ever 
			if not set(subarbor.ids).difference(nucleus.ids) \
			and 'orphan' not in bnrels \
			and ('Fin' in nucleus.feats.get('VerbForm',()) or bnrels.intersection(argumenta)) \
			and not any([corrpos['ADV'](nucleus.lemmas[i]) == 'ADV' for i,d in enumerate(nucleus.ids) if d != l.id and nucleus.upos[i] == 'ADV']) : 
				ortholemma = normalizator(l.lemma)
				syntagmata[corrpos.get(l.upos, lambda x : l.upos)(ortholemma)][ortholemma].append((s['sent_id'],nucleus._replace(forms=tuple(map(normalizator,nucleus.forms)))))
#

##Writing and creation of objects for plotting
with open('_'.join(('freeforms',ydioma)) + '.tsv','w',encoding='utf8') as exo :
	for p,lnnn in syntagmata.items() :
		
		numtypi = 0
		numsingtypi = 0
		numlemmasing = 0
		
		for l,nnn in lnnn.items() :
			ntypi = defaultdict(lambda : defaultdict(set))
			for s,n in nnn :
				ntypi[' '.join(n.forms)]['sent'].add(s)
				ntypi[' '.join(n.forms)]['rel'].update(map(lambda x : x.split(':')[0],n.deprels))
			#	
			
			numtypi += len(ntypi)
			sing = len([n for n in ntypi if len(n.split()) == 1])
			numlemmasing += 1 if sing else 0
			numsingtypi += sing
			
			randoff[p] = random.choice(list(ntypi.keys()))
			
			for n,sr in ntypi.items() : 				
				exo.write('{}\t{}\t{}\t{}\t{}\t{}\n'.format(p,\
								   					l,\
													n,\
								   					len(n.split()),\
								   					len(ntypi[n]),\
													','.join(sr['sent'])\
												   ))
		#		
		freeheadpos[p] = (numtypi,numsingtypi,len(lnnn),numlemmasing)			
#

##Handy statistics
print('The syntactically annotated part of the treebank contains {} sentences, of which {} do not have a root co-ordination.\n'.format(sentnum,radnum))
print('The {} extracted clausal free forms ({} consisting of a single form) are headed by {} distinct lexemes ({} for single-form clausal free forms). NB: these figures are computed only on the syntactically annotate part of the treebank).\n'.format(sum(map(itemgetter(0),freeheadpos.values())),sum(map(itemgetter(1),freeheadpos.values())),sum(map(itemgetter(2),freeheadpos.values())),sum(map(itemgetter(3),freeheadpos.values()))))
print('Here is a random example for each part of speech appearing as head (beware that data might be noisy or incorrect, always check it!):\n')
for p,ex in randoff.items() :
	print('- {}:\t{}'.format(p,ex))
#


# Plotting

posord = sorted(UDPos.keys() - alexpos - {'PROPN','NUM','X'}, key = lambda x : freeheadpos.get(x,(0,0,0,0))[2],reverse=True) #Attention: this is rather ad hoc with respect to the function corrpos, might need adaptation if you want to keep/visualise specific POS
colores = {p : {'omnia': 'r' if 'auto' in UDPos[p] else 'm', 'sing': 'b' if 'auto' in UDPos[p] else 'c'} for p in posord}
#
data = [freeheadpos.get(p,(0,0,0,0))[2] for p in posord]
datasing = [freeheadpos.get(p,(0,0,0,0))[3] for p in posord]
datafreesing = [len(singula[p]) for p in posord]
datafreemorph = [0]*len(posord)

plt.figure(1)
plt.bar(posord,datasing,color=[colores[p]['sing'] for p in posord])
plt.bar(posord,[ data[i] - datasing[i] for i,p in enumerate(posord)],bottom=datasing,color=[colores[p]['omnia'] for p in posord])
plt.xticks(range(len(posord)), posord)
plt.xticks(rotation=60)
#
plt.savefig('_'.join(('freeformdistr',ydioma)) + '.png',bbox_inches='tight')
plt.show()
#

plt.figure(2)
plt.bar(posord,datafreemorph,color=[colores[p]['sing'] for p in posord])
plt.bar(posord,[ datafreesing[i] - datafreemorph[i] for i,p in enumerate(posord)],bottom=datafreemorph,color=[colores[p]['omnia'] for p in posord])
plt.xticks(range(len(posord)), posord)
plt.xticks(rotation=60)
#
plt.savefig('_'.join(('freesingformdistr',ydioma)) + '.png',bbox_inches='tight')
plt.show()



