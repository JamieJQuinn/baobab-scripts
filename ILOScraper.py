import urllib2
import urllib
from bs4 import BeautifulSoup
from pymarc import Record, Field, XMLWriter
import json
import os.path
import sys
import uuid

# Change to ftpdownloads when needed
SAVE_LOCATION='ilo/'

def getParsedHTML(url):
    url = urllib2.urlopen(url)
    html = url.read()
    url.close()
    return BeautifulSoup(html)


# NEEDS CHANGING TO KEEP UP WITH TOTAL PAGE COUNT AT http://www.ilo.org/global/publications/books/lang--en/index.htm
frontPage = getParsedHTML("http://www.ilo.org/global/publications/books/lang--en/index.htm")
pagesToIndex = int(frontPage.find('aside', attrs={'class':'pagination'}).find('strong').string.split(' ')[2])

if not os.path.exists(SAVE_LOCATION+'/.state/'):
	    os.makedirs(SAVE_LOCATION+'/.state/')
cleanListFile = SAVE_LOCATION+'/.state/ILOCleanUrlList.json' # List of URLs already processed
errorListFile = SAVE_LOCATION+'/.state/ILOErrorUrlList.json' # List of URLs that cause problems

downloadLocation =SAVE_LOCATION

# create the clean list file if it doesn't exist
if not os.path.isfile(cleanListFile):
    with open(cleanListFile, 'w') as fp:
        json.dump([], fp)

# create the error list file if it doesn't exist
if not os.path.isfile(errorListFile):
    with open(errorListFile, 'w') as fp:
        json.dump([], fp)

## SCRAPE FOR BOOK URLS ##

incomingUrlList = []

# Scrape url list from ILO puplication list
print "SCRAPING " + str(pagesToIndex) + " PAGES FOR BOOK URLS"
for i in xrange(0, pagesToIndex*10, 10):
    print str((float(i)/pagesToIndex)*10) + "% complete" # Print percentage complete
    parsed_html = getParsedHTML("http://www.ilo.org/global/publications/books/lang--en/nextRow--"+str(i)+"/index.htm")
	# Get specific list of book results
    liList = parsed_html.body.find('div', attrs={'class':'items-list'}).find_all('li')
    for li in liList:
		# Scrape fot urls
        incomingUrlList.append('http://www.ilo.org' + li.a['href'])

# Check scraped list against urls for books that have already been scraped for metadata
with open(cleanListFile) as fp:
    cleanUrlList = json.load(fp)
with open(errorListFile) as fp:
    errorUrlList = json.load(fp)

dirtyUrlList = []
# If book already scraped, delete
for i, url in enumerate(incomingUrlList):
    if url not in cleanUrlList and url not in errorUrlList:
        dirtyUrlList.append(url)

## GET BOOK METADATA ##

bookMetaData = []

print "SCRAPING " + str(len(dirtyUrlList)) + " URLS FOR BOOK METADATA"
for i, url in enumerate(dirtyUrlList):
	print str(float(i)/len(dirtyUrlList)*100) + "% complete"
    # parse book html page
	parsed_html = getParsedHTML(url)
	metaTemp = {}
	try:
		# If the returned URL actually has data
		if parsed_html.find(class_="page-title"):
			metaTemp[u"title"] = parsed_html.find(class_="page-title").h1.string
			metaTemp[u'desc'] =  parsed_html.find(class_="page-title").p.string
		# Get publication metadata
		pubData = parsed_html.find(class_="pub-data").find_all('tr')
		# Sort metadata
		for tr in pubData:
			metaTemp[tr.th.string[:-2].lower()] = tr.td.string
		# Get PDF download link if it exists
		if (parsed_html.find(id='download')):
			metaTemp[u'downloadURL'] = 'http://www.ilo.org' + parsed_html.find(id='download').a['href']
		# Record where all this data came from
		metaTemp[u'originURL'] = url
		metaTemp[u'publisher'] = 'ILO'
	except:
        # If there's an error, put it in error list
		errorUrlList.append(url)
	else:
        # if there's no error, put the url on the clean list & save metadata
		cleanUrlList.append(url)
		bookMetaData.append(metaTemp)

# Save error file
with open(errorListFile, 'wb') as fp:
    json.dump(errorUrlList, fp)

# Save clean file
with open(cleanListFile, 'wb') as fp:
    json.dump(cleanUrlList, fp)

## DOWNLOAD BOOKS ## 

downloadable = []
# Select books that are downloadable
for data in bookMetaData:
    if "downloadURL" in data:
        data[u'UUID'] = str(uuid.uuid1())
        downloadable.append(data)

MARCMapping = {u'UUID':'001', 
               u'title':'245$a', 
               u'authors':'100$a', 
               u'date issued':'260$c',
               u'desc':'520$a',
               u'publisher':'260$b',
               u'reference':'020$a'}

print "DOWNLOADING " + str(len(downloadable)) + " BOOKS"
for i, data in enumerate(downloadable):
    print str(float(i)/len(downloadable)*100) + "% complete"
	# Get PDF
    url = data['downloadURL']
    urllib.urlretrieve(url, downloadLocation + data['UUID'] + '.' + url.rsplit('.')[-1])
	# Print metadata in MARCXML
    record = Record()
    for key in data:
        if key in MARCMapping:
            if(len(MARCMapping[key].split('$')) == 0):
                field = Field(
                    tag = MARCMapping[key].split('$')[0],
                    data = data[key])
            else:
				print key, data[key]
				field = Field(
                    tag = MARCMapping[key].split('$')[0],
                    subfields = [MARCMapping[key].split('$')[1], data[key]],
                    indicators=['0', '0'])  
            record.add_field(field)
    writer = XMLWriter(open(downloadLocation + data[u'UUID'] + '.xml', 'wb'))
    writer.write(record)
    writer.close()  # Important!
