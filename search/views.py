from django.shortcuts import render
import requests
from bs4 import BeautifulSoup
from django.http import HttpResponse
import threading
import woosh
from autocorrect import Speller
from pymongo import MongoClient
from elasticsearch import Elasticsearch
import random



def index(request):
    es = Elasticsearch(['http://localhost:9200'])
    es_publications = es.search(index="publication")['hits']['hits']
    context = {}

    if es_publications:
        context['publications'] = publicationMakeContextElastic(es, es_publications)
        #publicationShowElastic(es, es_publications)
    else:
        print("İçerik Bulunamadı!")
          
    return render(request, 'search/index.html', context)

def publicationMakeContextElastic(es, publications):
    pdf_titles = []
    IDs = []
    urls = []

    for publication in publications:
        try:
            result = es.get(index="publication", id=publication['_id'])
            source = result['_source']
            IDs.append(result['_id'])
            pdf_titles.append(source['title'])
            urls.append(source['url'])
        except Exception as e:
            print(f"Hata: {e}")

    context_list = []

    for title, id, url in zip(pdf_titles, IDs, urls):
        context_list.append({
            'title': title,
            'id': id,
            'url': url,
        })

    return context_list

def deleteAllPublicationsElastic(es):
    indexs = es.indices.get_alias().keys()
    print(indexs)
    for index in indexs:
        es.indices.delete(index=index)

def savePublicationsElastic(es, publications):
    for publication in publications:
        publication_id = publication.pop('_id')
        es.index(
            index="publication",
            id= publication_id,
            body=publication
        )

def downloadPDF(url, file_name):
    try:
        response = requests.get(url)
        if response.status_code == 200:
            with open(file_name, 'wb') as f:
                f.write(response.content)
                print(f"{file_name} başarıyla indirildi.")
        else:
            print("İstek başarısız oldu. Durum kodu:", response.status_code)
    except Exception as e:
        print("Hata:", e)

def takeArticlesName(soup):
    card_titles = soup.find_all('h5', class_='card-title')
    headings = []
    counter = 0
    for card_title in card_titles:
        if counter < 10:
            heading = card_title.find('a').text.strip()
            headings.append(heading)
            counter += 1
        else:
            break
    return headings

def takePDFLink(url):
    response = requests.get(url)
    soup = BeautifulSoup(response.content, "html.parser")
    link = soup.find('div', id='article-toolbar').find('a')['href']
    pdf_link = "https://dergipark.org.tr" + link
    return pdf_link

def takeWebsiteLink(soup):
    card_titles = soup.find_all('h5', class_='card-title')
    links = []
    counter = 0
    for card_title in card_titles:
        if counter < 10:
            link = card_title.find('a')['href']
            links.append(link)
            counter += 1
        else:
            break
    return links

def takeAllPdfLinks(links):
    pdfLinks = []
    for link in links:
        pdfLinks.append(takePDFLink(link))
    return pdfLinks

def takeArticlesDates(soup):
    small_tags = soup.find_all('small', class_='article-meta')
    years = []
    for small_tag in small_tags:
        text = small_tag.get_text(strip=True)
        if '(' in text and ')' in text:
            year = text[text.find('(') + 1: text.find(')')]
            years.append(year)
    return years

def download_pdf_background(pdf_links):
    for pdf_link in pdf_links:
        file_name = pdf_link.split('/')[-1] + ".pdf"
        downloadPDF(pdf_link, file_name)

def correct_spelling(query):
    spell = Speller(lang='en')
    corrected_query = spell(query)
    return corrected_query

def takeAllCiteCount(websites):
    citeCounter = []

    for website in websites:
        response = requests.get(website)
        html_content = response.text
        soup = BeautifulSoup(html_content, 'html.parser')
        citeCounter.append(len(takeDetailArticlesCites(soup)))
    return citeCounter

def show_result(request):
    es = Elasticsearch(['http://localhost:9200'])
    
    client = MongoClient('mongodb://localhost:27017/')
    db = client['yazlab']
    collection = db['publications']
    publications = collection.find()

    if publications:
        deleteAllPublicationsElastic(es)
        collection.drop()   

    query = request.GET.get('q')
    corrected_query = correct_spelling(query)
    url = f"https://dergipark.org.tr/en/search?q={corrected_query}&section=articles"
    response = requests.get(url)

    if response.status_code == 200:
        html_content = response.text
        soup = BeautifulSoup(html_content, 'html.parser')
        pdf_titles = takeArticlesName(soup)
        websitelinks = takeWebsiteLink(soup)
        pdf_links = takeAllPdfLinks(websitelinks)
        years = takeArticlesDates(soup)
        cites = takeAllCiteCount(websitelinks)

        for year in years:
            print(year)
        
        #threading.Thread(target=download_pdf_background, args=(pdf_links,)).start() # Pdfleri indirme işlemi
    pdf_zip = zip(pdf_titles, pdf_links, websitelinks, years, cites)
    print(url) 
 
    print("Kontrol Noktası 1")
    counterTitle = 0
    for website in websitelinks:
       print("Kontrol Noktası 2")
       id = random.randint(1, 10000000)
       saveAllDetail(website, query, id, pdf_titles[counterTitle])
       counterTitle += 1
    print("Kontrol Noktası 3")
    
    print("Kontrol Noktası 4")
    collectionNew = db['publications']
    print("Kontrol Noktası 5")
    publicationsNew = collectionNew.find()
    print("Kontrol Noktası 6")
    savePublicationsElastic(es, publicationsNew)
    print("Kontrol Noktası 7")
    

    context = {
        'query': query,
        'corrected_query': corrected_query,
        'url': url,
        'pdf_zip': pdf_zip,
    }

    return render(request, 'search/showResults.html', context)

def show_filtered(request):
    sort_option = request.GET.get('sort')
    url = request.GET.get('url')
    query = request.GET.get('query')
    corrected_query = request.GET.get('corrected_query')
    response = requests.get(url)
    
    if response.status_code == 200:
        html_content = response.text
        soup = BeautifulSoup(html_content, 'html.parser')
        pdf_titles = takeArticlesName(soup)
        websitelinks = takeWebsiteLink(soup)
        pdf_links = takeAllPdfLinks(websitelinks)
        years = takeArticlesDates(soup)
        cites = takeAllCiteCount(websitelinks)
    pdf_zip = zip(pdf_titles, pdf_links, websitelinks, years, cites)
    if sort_option == 'oldest':
        pdf_zip = sorted(pdf_zip, key=lambda x: x[3])
    elif sort_option == 'newest':
        pdf_zip = sorted(pdf_zip, key=lambda x: x[3], reverse=True)
    elif sort_option == 'much':
        pdf_zip = sorted(pdf_zip, key=lambda x: x[4], reverse=True)
    elif sort_option == 'less':
        pdf_zip = sorted(pdf_zip, key=lambda x: x[4])

    context = {
        'query': query,
        'corrected_query': corrected_query,
        'url': url,
        'pdf_zip': pdf_zip,
    }

    return render(request, 'search/showResults.html', context)

def detail(request):
    title = request.GET.get('title', '')
    websitelink = request.GET.get('websitelink', '')
    response = requests.get(websitelink)
    if response.status_code == 200:
        html_content = response.text
        soup = BeautifulSoup(html_content, 'html.parser')
        publishDate = takeDetailArticleDate(soup)
        authors = takeDetailArticlesAuthors(soup)
        abstract = takeDetailArticlesAbstract(soup)
        keywords = takeDetailArticlesKeywords(soup)
        references = takeDetailArticlesRefrences(soup)
        citations = takeDetailArticlesCites(soup)
        doi = takeDetailArticlesDOINumber(soup)
        publisher = takeDetailPublisherTitle(soup)
        researchType = takeDetailArticlesType(soup)

    return render(request, 'search/detail.html', {'title': title,
                                                   'websitelink': websitelink,
                                                     'publishDate': publishDate,
                                                       'authors': authors,
                                                       'abstract': abstract,
                                                       'keywords': keywords,
                                                       'references': references,
                                                       'citations': citations,
                                                       'doi': doi,
                                                       'publisher': publisher,
                                                       'researchType': researchType,
                                                       })

def takeDetailArticleDate(soup):
  span_tag = soup.find('span', class_='article-subtitle')
  subtitle_content = span_tag.text.strip()
  date = subtitle_content.split(',')[-1].strip()
  return date

def takeDetailArticlesAuthors(soup):
  p_tag = soup.find('p', class_='article-authors')
  author_content = p_tag.text.strip()
  return author_content

def takeDetailArticlesAbstract(soup):
  div_tag = soup.find('div', class_='article-abstract')
  abstract_content = div_tag.find('p').text.strip()
  return abstract_content

def takeDetailArticlesKeywords(soup):
  div_tag = soup.find('div', class_='article-keywords')
  p_tag = div_tag.find('p')
  keywords = [a.text.strip() for a in p_tag.find_all('a')]
  return keywords

def takeDetailArticlesRefrences(soup):
  div_tag = soup.find('div', class_='article-citations')
  if div_tag:
    list_items = div_tag.find_all('li')
    references = [item.text.strip() for item in list_items]
    return references
  else:
    return None

def takeDetailArticlesCites(soup):
  cite_items = soup.find_all('td', class_='cite-table-item')

  citations = {}
  for item in cite_items:
      cite_name = item.text.strip() 
      cite_content = item.find_next('td').text.strip() 
      citations[cite_name] = cite_content

  return citations

def takeDetailArticlesDOINumber(soup):
  doi_link_tag = soup.find('a', class_='doi-link')
  if doi_link_tag:
    doi_link = doi_link_tag['href']
    return doi_link
  else:
    return "DOI Numarası İçermemektedir!"

def takeDetailPublisherTitle(soup):
  journal_title = soup.find('h1', id='journal-title').text.strip()
  return journal_title

def takeDetailArticlesType(soup):
    research_article_tag = soup.find('span', class_='kt-font-bold')
    if research_article_tag is not None:
        research_article = research_article_tag.text.strip()
        return research_article
    else:
        return ""

def saveAllDetail(url, query, ID, pdf_title):
    response = requests.get(url)
    if response.status_code == 200:
        html_content = response.text
        soup = BeautifulSoup(html_content, 'html.parser')
        publishDate = takeDetailArticleDate(soup)
        authors = takeDetailArticlesAuthors(soup)
        abstract = takeDetailArticlesAbstract(soup)
        keywords = takeDetailArticlesKeywords(soup)
        references = takeDetailArticlesRefrences(soup)
        citations = takeDetailArticlesCites(soup)
        doi = takeDetailArticlesDOINumber(soup)
        publisher = takeDetailPublisherTitle(soup)
        researchType = takeDetailArticlesType(soup)

        client = MongoClient('mongodb://localhost:27017/')
        db = client['yazlab']
        collection = db['publications']

        publication_data = {
            '_id': ID,
            'title': pdf_title,
            'publication_date': publishDate,
            'authors': authors,
            'publication_type': researchType,
            'publisher': publisher,
            'keywords_search': query,
            'keywords_article': keywords,
            'summary': abstract,
            'references': references,
            'citation_count': len(citations),
            'doi': doi,
            'url': url,
        }


        collection.insert_one(publication_data)