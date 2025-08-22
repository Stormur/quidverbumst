#The following code has been developed by Flavio Massimiliano Cecchini as part of the work presented in "Quid verbumst? Applying a definition of word to Latin in Universal Dependencies", SyntaxFest 2025, Ljubljana. Please give credit to the author if you use any part of it. 
#Contact: flaviomassimiliano.cecchini at kuleuven.be

#Light, Latin-oriented normalisation function #removes any diacritics; lowercases; replaces v with u, j with i, & with et; removes any kind of punctuation mark (so much for in-quantum or vol'); removes spaces #Note: this annihilates punctuation marks
def orthonormalizatio(s,diacritics=False) :
	import regex,unicodedata
	#
	if not diacritics :
		s = regex.sub(r'(\p{M})','',unicodedata.normalize('NFKD',s))
	return regex.sub(r'( |\p{P})','',s.lower()).replace('j','i').replace('v','u').replace('&','et')
#
