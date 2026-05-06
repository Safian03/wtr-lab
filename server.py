from flask import Flask,jsonify,request,send_from_directory,Response
from flask_cors import CORS
import time,urllib.parse,re,threading,uuid,requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

app=Flask(__name__,static_folder='.')
CORS(app)
H={'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'}
WTR='https://wtr-lab.com/en/novel-finder?text={}'
jobs={}

def nm(t):return re.sub(r'[^a-z0-9 ]','',t.lower()).strip()
def pc(x):
 nums=re.findall(r'\d+',str(x).replace(',',''))
 if not nums: return 0
 n=int(nums[0])
 if n>100000: return n//3000
 return n

_c={}
def ow(title):
 n=nm(title)
 if n in _c:return _c[n]
 try:
  import json as _json
  r=requests.get(WTR.format(urllib.parse.quote(title)),headers=H,timeout=12)
  if r.status_code==403:_c[n]=None;return None
  # Try CN character matching via __NEXT_DATA__
  m=re.search(r'__NEXT_DATA__[^>]*>(.*?)</script',r.text)
  if m:
   data=_json.loads(m.group(1))
   series=data.get('props',{}).get('pageProps',{}).get('series',[])
   tc=set(re.findall(r'[\u4e00-\u9fff\u3400-\u4dbf\u4e00-\u9fa5]',title))
   if tc:
    for item in series:
     st=item.get('search_text','')
     sc=set(re.findall(r'[\u4e00-\u9fff\u3400-\u4dbf\u4e00-\u9fa5]',st))
     if not sc:continue
     overlap=len(tc&sc)/len(tc)
     if overlap>=0.65:_c[n]=True;return True
  # Fallback word overlap
  for el in BeautifulSoup(r.text,'html.parser').select('[class*=title],h2,h3,h4,a'):
   et=nm(el.get_text());wa=set(n.split());wb=set(et.split())
   if wa and wb and len(wa)>1 and len(wa&wb)/max(len(wa),len(wb))>=0.75:_c[n]=True;return True
  _c[n]=False;return False
 except:_c[n]=None;return None

def ow_detail(title):
 """Returns (status, confidence_pct, matched_en_title, wtr_url)"""
 try:
  import json as _json
  r=requests.get(WTR.format(urllib.parse.quote(title)),headers=H,timeout=12)
  if r.status_code==403:return ('unverified',0,None,None)
  m=re.search(r'__NEXT_DATA__[^>]*>(.*?)</script',r.text)
  if m:
   data=_json.loads(m.group(1))
   series=data.get('props',{}).get('pageProps',{}).get('series',[])
   tc=set(re.findall(r'[\u4e00-\u9fff\u3400-\u4dbf]',title))
   best=0;best_item=None
   for item in series:
    st=item.get('search_text','')
    sc=set(re.findall(r'[\u4e00-\u9fff\u3400-\u4dbf]',st))
    if not sc:continue
    overlap=len(tc&sc)/max(len(tc),1)
    if overlap>best:best=overlap;best_item=item
   if best_item and best>=0.65:
    slug=best_item.get('slug','')
    en_title=best_item.get('data',{}).get('title','')
    return ('duplicate',int(best*100),en_title,f'https://wtr-lab.com/en/serie-list/{slug}')
   elif best_item and best>=0.35:
    slug=best_item.get('slug','')
    en_title=best_item.get('data',{}).get('title','')
    return ('probable',int(best*100),en_title,f'https://wtr-lab.com/en/serie-list/{slug}')
  return ('new',0,None,None)
 except:return ('unverified',0,None,None)

def pw_scrape(url,selector_fn,log,wait=2):
 results=[]
 try:
  with sync_playwright() as p:
   browser=p.chromium.launch(headless=True)
   ctx=browser.new_context(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36')
   page=ctx.new_page()
   page.goto(url,wait_until='domcontentloaded',timeout=30000)
   time.sleep(wait)
   html=page.content()
   browser.close()
   results=selector_fn(html)
 except Exception as e:
  log(f'Browser error: {e}','warn')
 return results

def parse_fanqi(html,mc):
 soup=BeautifulSoup(html,'html.parser')
 res=[]
 for item in soup.select('div.stack-book-item,div.book-item-text'):
  a=item.select_one('a.book-item-title,a[href*="/page/"]')
  if not a:continue
  title=a.get_text(strip=True)
  href=a.get('href','')
  url=href if href.startswith('http') else 'https://fanqienovel.com'+href
  author_el=item.select_one('[class*=author],.book-item-author')
  author=author_el.get_text(strip=True).replace('Author:','').strip() if author_el else 'Unknown'
  chap_el=item.select_one('[class*=count],[class*=chap],[class*=serial]')
  chaps=pc(chap_el.get_text()) if chap_el else 999
  if title and chaps>=mc:
   res.append({'title':title,'author':author,'chapters':chaps,'url':url,'source':'fanqienovel.com'})
 return res

def parse_69shu(html,mc):
 soup=BeautifulSoup(html,'html.parser')
 res=[]
 for li in soup.select('ul li'):
  a=li.select_one('a[href*="/book/"]')
  if not a:continue
  href=a.get('href','')
  url=href if href.startswith('http') else 'https://www.69shuba.com'+href
  title_el=li.select_one('h3.ellipsis_1,h3')
  title=title_el.get_text(strip=True) if title_el else a.get_text(strip=True)
  author_el=li.select_one('h4')
  author=author_el.get_text(strip=True) if author_el else 'Unknown'
  chap_el=li.select_one('[class*=chap],[class*=count],.zs')
  chaps=pc(chap_el.get_text()) if chap_el else 999
  if title and chaps>=mc:
   res.append({'title':title,'author':author,'chapters':chaps,'url':url,'source':'69shuba.com'})
 return res

def parse_twkan(html,mc):
 soup=BeautifulSoup(html,'html.parser')
 res=[]
 for li in soup.select('ul li'):
  a=li.select_one('a[href*="/book/"]')
  if not a:continue
  href=a.get('href','')
  url=href if href.startswith('http') else 'https://twkan.com'+href
  title_el=li.select_one('h3.ellipsis_1,h3')
  title=title_el.get_text(strip=True) if title_el else a.get_text(strip=True)
  author_el=li.select_one('h4')
  author=author_el.get_text(strip=True) if author_el else 'Unknown'
  chap_el=li.select_one('[class*=chap],[class*=count],.zs')
  chaps=pc(chap_el.get_text()) if chap_el else 999
  if title and chaps>=mc:
   res.append({'title':title,'author':author,'chapters':chaps,'url':url,'source':'twkan.com'})
 return res

def parse_uuread(html,mc):
 from bs4 import BeautifulSoup
 soup=BeautifulSoup(html,'html.parser')
 res=[]
 seen=set()
 for a in soup.find_all('a',href=True):
  href=a.get('href','')
  if 'uuread.tw/' in href and href.split('/')[-1].isdigit() and a.get_text(strip=True):
   if href in seen:continue
   seen.add(href)
   title=a.get('title','') or a.get_text(strip=True)
   parent=a.find_parent('div',class_='media-body')
   author='Unknown'
   if parent:
    sp=parent.find('span',class_='index-body-nr-left-span')
    if sp:
     au=sp.find('a')
     if au:author=au.get_text(strip=True)
   res.append({'title':title,'author':author,'chapters':9999,'url':href,'source':'uuread.tw'})
 return res
def scrape_auto(src,genre,mc,log):
 res=[]
 log(f'Searching {src} with browser (bypassing Cloudflare)...')
 try:
  if src=='fanqi':
   gid=GENRE_URLS['fanqi'].get(genre,'0')
   for p in range(1,4):
    url=f'https://fanqienovel.com/library?page_count={p}&genre={gid}&order=0'
    html_res=[]
    def fn(html,mc=mc):return parse_fanqi(html,mc)
    novels=pw_scrape(url,fn,log)
    res+=novels
    if not novels:break
    time.sleep(1)
  elif src=='69shu':
   gid=GENRE_URLS['69shu'].get(genre,'1')
   for p in range(1,4):
    url=f'https://www.69shuba.com/sort.htm?c={gid}&page={p}'
    novels=pw_scrape(url,lambda html,mc=mc:parse_69shu(html,mc),log)
    res+=novels
    if not novels:break
    time.sleep(1)
  elif src=='twkan':
   gid=GENRE_URLS['twkan'].get(genre,'1')
   for p in range(1,4):
    url=f'https://twkan.com/sort.htm?c={gid}&page={p}'
    novels=pw_scrape(url,lambda html,mc=mc:parse_twkan(html,mc),log)
    res+=novels
    if not novels:break
    time.sleep(1)
  elif src=='uuread':
   import requests as _req
   _hdrs={'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
   # Scrape both ongoing (/sort/) and completed (/full/) novels
   _urls=[]
   for _p in range(1,9):
    _urls.append(f'https://www.uuread.tw/sort/all/{_p}.html')
    _urls.append(f'https://www.uuread.tw/full/all/{_p}.html')
   for _url in _urls:
    try:
     _r=_req.get(_url,headers=_hdrs,timeout=15)
     _novels=parse_uuread(_r.text,mc)
     res+=_novels
     _tag='completed' if '/full/' in _url else 'ongoing'
     log(f'uuread {_tag} p{_url.split("/")[-1].split(".")[0]}: {len(_novels)} novels')
    except Exception as _e:
     log(f'uuread error {_url}: {_e}','err')
    time.sleep(0.5)
 except Exception as e:
  log(f'Error scraping {src}: {e}','err')
 log(f'Found {len(res)} on {src}')
 return res

def check_manual_urls(urls,log):
 res=[]
 log(f'Processing {len(urls)} manual URLs...')
 for url in urls:
  url=url.strip()
  if not url:continue
  src='unknown'
  if 'fanqi' in url:src='fanqienovel.com'
  elif '69shu' in url:src='69shuba.com'
  elif 'twkan' in url:src='twkan.com'
  elif 'uuread' in url:src='uuread.tw'
  elif 'tadu' in url:src='tadu.com'
  elif 'qimao' in url:src='qimao.com'
  res.append({'title':url,'author':'Unknown','chapters':0,'url':url,'source':src})
 return res

def run_job(jid,genre,mc,sources,manual_urls=None):
 job=jobs[jid]
 def log(m,lv='info'):job['logs'].append({'msg':m,'level':lv})
 try:
  all_r=[]
  if manual_urls:
   all_r=check_manual_urls(manual_urls,log)
  else:
   for i,src in enumerate(sources):
    all_r+=scrape_auto(src,genre,mc,log)
    job['progress']=int(10+((i+1)/len(sources))*40)
  seen=set();uniq=[]
  for n in all_r:
   if n['url'] not in seen:seen.add(n['url']);uniq.append(n)
  log(f'Dedup: {len(all_r)}->{len(uniq)} unique')
  job['progress']=52
  log(f'Checking {len(uniq)} against WTR Lab...')
  nc=dc=uc=0
  for i,nv in enumerate(uniq):
   title_to_check=nv['title'] if not manual_urls else nv['url']
   wstatus,wconf,wen_title,wurl=ow_detail(title_to_check)
   nv['wtr_status']=wstatus
   nv['wtr_confidence']=wconf
   nv['wtr_en_title']=wen_title or ''
   nv['wtr_url']=wurl or ''
   nv['wtr_search_url']='https://wtr-lab.com/en/novel-finder?text='+urllib.parse.quote(nv['title'])
   if wstatus=='duplicate':dc+=1
   elif wstatus=='new':nc+=1
   else:uc+=1
   job['results'].append(nv)
   job['progress']=int(52+((i+1)/len(uniq))*46)
   if (i+1)%5==0 or i==len(uniq)-1:log(f'[{i+1}/{len(uniq)}] {nc} new {dc} dupes {uc} unverified','dim')
   time.sleep(1.5)
  log(f'Done! {nc} new {dc} dupes {uc} unverified','ok')
  job['status']='done'
 except Exception as e:
  log(f'Error: {e}','err')
  job['status']='error'

@app.route('/')
def index():return send_from_directory('.','index.html')

@app.route('/api/search',methods=['POST'])
def api_search():
 d=request.json;jid=str(uuid.uuid4())
 jobs[jid]={'status':'running','progress':0,'logs':[],'results':[]}
 manual=d.get('manual_urls',None)
 threading.Thread(target=run_job,args=(jid,d.get('genre','fantasy'),int(d.get('min_chapters',100)),d.get('sources',['fanqi','69shu','twkan','uuread']),manual),daemon=True).start()
 return jsonify({'job_id':jid})

@app.route('/api/job/<jid>')
def api_job(jid):
 j=jobs.get(jid)
 return jsonify({'status':j['status'],'progress':j['progress'],'logs':j['logs'],'results':j['results']}) if j else (jsonify({'error':'Not found'}),404)

@app.route('/api/export/<jid>')
def api_export(jid):
 j=jobs.get(jid)
 if not j:return jsonify({'error':'Not found'}),404
 rows=['title,author,chapters,url,source,wtr_status']+[','.join(f'"{str(n.get(f,"")).replace(chr(34),chr(39))}"'for f in['title','author','chapters','url','source','wtr_status'])for n in j['results']if n.get('wtr_status')!='duplicate']
 return Response('\n'.join(rows),mimetype='text/csv',headers={'Content-Disposition':'attachment; filename=wtrlab_results.csv'})

if __name__=='__main__':
 print('Server running at: http://localhost:5000')
 app.run(debug=False,port=5000)
