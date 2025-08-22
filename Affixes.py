#The following code has been developed by Flavio Massimiliano Cecchini as part of the work presented in "Quid verbumst? Applying a definition of word to Latin in Universal Dependencies", SyntaxFest 2025, Ljubljana. Please give credit to the author if you use any part of it. 
#Contact: flaviomassimiliano.cecchini at kuleuven.be

#Important note: as it is now, this script has to be launched once on the whole treebank for the identification of underived words, and once for the extraction of uninflected forms from a treebank annotating inflectional information. This script will be split in further releases.

#Useful imports
import sys, os, configparser, regex#, dill
from pathlib import Path
from operator import itemgetter
from collections import defaultdict, Counter
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
from CoNLLUToolsmini import UDPos, readCoNLLU, syntacticwords, readUDfeatures, writeUDfeatures
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
classificator = confs.get('Parameters','classifier')
inversio = confs.getboolean('Parameters','inversion')
lemmata = confs.getboolean('Parameters','lemmas')
ydioma = confs.get('Parameters','lang')
limes = confs.getint('Parameters','threshold')
#


#Definition of structures and import of word lists
lexemata = dict() 
simplicia = set()
aderivata = set()
frequentiae = Counter()
#
derivata = set()
with open(morphologia / 'derived','r',encoding='utf8') as intro : 
	for riga in intro :
		derivata.add(normalizator(riga.strip()))
#
composita = set()
with open(morphologia / 'compound','r',encoding='utf8') as intro : 
	for riga in intro :
		composita.add(normalizator(riga.strip()))
#
advpos = {}
with open(morphologia / 'ADV.tsv','r',encoding='utf8') as intro : 
	for riga in intro :
		l,p = riga.strip(' \n').split('\t')
		advpos[normalizator(l)] = 'PRON' if p == 'REL' else p #See paper for this decision. The ADV treatment is specific for Latin, but can possibly readapted to other languages
#
corrpos = {'PROPN': lambda x : 'NOUN', 'ADV' : lambda x : advpos.get(x,'ADV') , 'NUM' : lambda x : 'DET'} #Remapping of part-of-speech tags; see paper. This is valid universally (except for ad hoc treatment of ADV)
negfeat = {'Degree' : lambda x : bool(x!='Pos'), 'InflClass' : lambda x : bool(x not in ('Ind','IndEurInd')), 'VerbForm' : lambda x : bool(x!='Fin')} #NB: this list is partly ad hoc, even if it has wider applicability; it might need some additions for other languages
alexpos= {p for p,v in UDPos.items() if 'alex' in v}
#


#Reading and extraction
for s,a in readCoNLLU(conllu,syntax=False) :		
	print(s['sent_id'],end='\r')
	for nodus in syntacticwords(a) :
				
		orthoforma = normalizator(nodus.form)
		ortholemma = normalizator(nodus.lemma) if lemmata else orthoforma
		cupos = corrpos.get(nodus.upos, lambda x : nodus.upos)(ortholemma) 
		
		#Criteria to identify only lexical and analysable forms, so excluding digits, symbols, punctuation marks, abbreviations...
		if cupos not in alexpos \
		and not regex.fullmatch(r'\d+(-\d+)?',orthoforma) \
		and nodus.feats.get('NumForm',None) not in ('Digit','Roman') \
		and not nodus.feats.get('Abbr',None) :
			
			#Checking derivation status
			if ortholemma not in composita : 
				simplicia.add((ortholemma,cupos))
				#NB: The following criteria are partly specific to Latin for the identification of non-derived elements, and could possibly be modified for other languages, if applicable at all
				if ortholemma not in derivata \
				and not nodus.feats.get('Degree',None) \
				and (nodus.feats.get('NumType',None) not in ('Ord','Dist','Mult') or ortholemma in ('semel','bis','ter','quater')) : 
					aderivata.add((ortholemma,cupos))
			#
					
			#Managing productively derived adverbial forms
			if cupos != nodus.upos and 'main' in UDPos[cupos] and nodus.upos == 'ADV' : 
				nodus.feats['Form'] = nodus.feats.get('Form',()) + ('Adverbial',)	
				
			#Finally collecting forms into lexemes	
			lexemata.setdefault((ortholemma,cupos),dict())
			lexemata[(ortholemma,cupos)].setdefault(orthoforma,defaultdict(set))
				
			frequentiae[(ortholemma,cupos,orthoforma)] += 1
			
			proprietates = nodus.feats | nodus.misc
			if inversio and classificator not in proprietates : 
				proprietates[classificator] = 'Yes'
			#
			
			for f,v in proprietates.items() :
				if f not in ('CitationHierarchy','LiLaflcat','LASLAVariant','SpaceAfter') : #NB: this list has been hardcoded with regard to known MISC features in UD Latin treebanks, and might need to be augmented by other features
					fv = tuple(filter(negfeat.get(f,None),v))
					if fv : 
						lexemata[(ortholemma,cupos)][orthoforma][f].update(fv)	
#


#Printing and writing

## Handy statistics
print('\nSome statistics:')
print('The treebank contains {} (normalised) word lexemes, of which {} have been identified as non-compounds (simple), and {} as underived from any base.'.format(len(lexemata),len(simplicia),len(aderivata)))

print('\nTheir distributions according to parts of speech is as follows:')
posdistrlex = [Counter([k[1] for k in lexemata]), Counter([k[1] for k in simplicia]), Counter([k[1] for k in aderivata])]
print('\nPOS\tLexemes\tSimple\tUnderived')
for p in UDPos :
	lsa = [pdl[p] for pdl in posdistrlex]
	if any(lsa) : 
		print('{}\t{}'.format(p,'\t'.join(map(str,lsa))))
#

##Full list and random selection of 100 lexemes identified as non-derived according to the supplied morphological information

with open('underived_lexemes' + f'_{ydioma}'+'.tsv','w',encoding='utf8') as exo :
	for ad in aderivata :
		exo.write('{}\t{}\n'.format(ad[0],ad[1]))
#
import random
rn = 100
with open('underived_lexemes_random' + str(rn) + f'_{ydioma}'+'.tsv','w',encoding='utf8') as exo :
	for rf in random.sample(tuple(aderivata),rn) :
		exo.write('{}\t{}\n'.format(rf[0],rf[1]))
#


# Identification of uninflectable lexemes/forms

aclitica = defaultdict(dict)
#
contapos = defaultdict(set)
apos = defaultdict(set)
contafeat = defaultdict(Counter)
afeat = defaultdict(Counter)

for l,f in lexemata.items() :
	
	for ff,ft in f.items() :								 
		proprietates = writeUDfeatures(ft)
		contafeat[l[1]].update(proprietates.split('|'))
		contapos[l[1]].add((l[0],ff))
		#
		if classificator not in ft :
			afeat[l[1]].update(proprietates.split('|'))
			aclitica[(l[0],l[1])][ff] = proprietates
			apos[l[1]].add((l[0],ff))
		
		
aclifeats = sorted(set().union(*[set(d.keys()) for d in afeat.values() ]))	
		
tabula = '_'.join(('aclitica',ydioma)) + '.tsv'	
with open(tabula,'w',encoding='utf8') as exo : 
	for l,fp in aclitica.items() :
		aformae = set()
		afs = defaultdict(set)
		for f,p in fp.items() : 
			if frequentiae[(l[0],l[1],f)] > limes :
				aformae.add(f)
				for k,v in readUDfeatures(p).items() :
					afs[k].update(v)				
		#
		infl = set(lexemata[l]) - aformae
		morfinfl = defaultdict(set)
		for fl in infl : 
			for k,v in lexemata[l][fl].items() :
				morfinfl[k].update(v)			
		solinfl = set(morfinfl) - set(afs)		
		#		
		if aformae : 
			exo.write('{}\t{}\t{}\t{}\t{}\t{}\t{}\n'.format(l[0],\
												l[1],\
												','.join(sorted(aformae)),\
												sum([frequentiae[(l[0],l[1],af)] for af in aformae]),\
												writeUDfeatures(afs),\
												','.join(infl),\
												','.join(solinfl),\
													   ))

tabulapos = '_'.join(('aclitica_pos',ydioma)) + '.tsv'
with open(tabulapos,'w',encoding='utf8') as exo : 
	for pos,c in contapos.items() :
		exo.write('{}\t{}\t{}\t{}\n'.format(pos,\
											str(len(apos[pos])/len(contapos[pos])),\
											str(sum([frequentiae[(lx[0],pos,lx[1])] for lx in apos[pos]])/sum([frequentiae[(lx[0],pos,lx[1])] for lx in contapos[pos]])),\
										'\t'.join([':'.join(map(str,fc)) for fc in sorted([(af,afeat[pos][af]/contafeat[pos][af]) for af in aclifeats if af in afeat[pos]],key = itemgetter(1),reverse=True)])\
									   ))
		
		








