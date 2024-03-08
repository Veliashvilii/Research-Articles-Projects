from django.shortcuts import render
import requests
from bs4 import BeautifulSoup
from django.http import HttpResponse
import threading
import woosh
from autocorrect import Speller
from pymongo import MongoClient

def index(request):
    return render(request, 'search/index.html')

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

def show_result(request):
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

        for year in years:
            print(year)
        
        #threading.Thread(target=download_pdf_background, args=(pdf_links,)).start() # Pdfleri indirme işlemi
    pdf_zip = zip(pdf_titles, pdf_links, websitelinks, years)
    print(url)

    for website in websitelinks:
       saveAllDetail(website)

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
    pdf_zip = zip(pdf_titles, pdf_links, websitelinks, years)
    if sort_option == 'oldest':
        pdf_zip = sorted(pdf_zip, key=lambda x: x[3])
    elif sort_option == 'newest':
        pdf_zip = sorted(pdf_zip, key=lambda x: x[3], reverse=True)

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
  research_article = soup.find('span', class_='kt-font-bold').text.strip()
  return research_article

def takeDetailTitle(soup):
  title_element = soup.find('h3', class_='article-title')
  title = title_element.text.strip()
  return title

def saveAllDetail(url):
    response = requests.get(url)
    if response.status_code == 200:
        html_content = response.text
        soup = BeautifulSoup(html_content, 'html.parser')
        title = takeDetailTitle(soup)
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
            'title': title,
            'publication_date': publishDate,
            'authors': authors,
            'publication_type': researchType,
            'publisher': publisher,
            'keywords_search': keywords,
            'keywords_article': keywords,
            'summary': abstract,
            'references': references,
            'citation_count': len(citations),
            'doi': doi,
            'url': url,
        }

        collection.insert_one(publication_data)