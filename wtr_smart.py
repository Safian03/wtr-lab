import requests, json, re, time
from difflib import SequenceMatcher
from functools import lru_cache

_HDR = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
_CACHE = {}

def extract_keywords(cn_title):
    """Extract 2-3 key search terms from Chinese title"""
    # Remove common noise patterns
    clean = re.sub(r'[：:，,！!？?。．\[\]【】()（）]', ' ', cn_title)
    # Split and get segments
    parts = [p.strip() for p in clean.split() if len(p.strip()) >= 2]
    # Take first meaningful segment (usually the series name)
    if parts:
        first = parts[0]
        # If long enough, take first 4-6 chars as core keyword
        return first[:6] if len(first) >= 4 else first
    return cn_title[:4]

def wtr_search(keyword):
    """Search WTR Lab and return list of series with search_text"""
    import urllib.parse
    url = f'https://wtr-lab.com/en/novel-list?name={urllib.parse.quote(keyword)}'
    try:
        r = requests.get(url, headers=_HDR, timeout=12)
        m = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', r.text)
        if not m:
            return []
        data = json.loads(m.group(1))
        series = data.get('props',{}).get('pageProps',{}).get('series',[])
        return series
    except Exception as e:
        return []

def cn_overlap(title, search_text):
    """Calculate how many chars of title appear in search_text"""
    if not search_text:
        return 0.0
    title_chars = set(re.findall(r'[\u4e00-\u9fff]', title))
    if not title_chars:
        return 0.0
    search_chars = set(re.findall(r'[\u4e00-\u9fff]', search_text))
    overlap = len(title_chars & search_chars)
    return overlap / len(title_chars)

def check_wtr_smart(cn_title, author=''):
    """
    Smart WTR check with fuzzy matching.
    Returns: (status, confidence, matched_title, wtr_url)
    status: 'confirmed' | 'probable' | 'new'
    """
    cache_key = cn_title[:20]
    if cache_key in _CACHE:
        return _CACHE[cache_key]

    keyword = extract_keywords(cn_title)
    results = wtr_search(keyword)
    
    best_score = 0.0
    best_match = None
    
    for item in results:
        search_text = item.get('search_text', '')
        item_data = item.get('data', {})
        wtr_title = item_data.get('title', '')
        wtr_author = item_data.get('author', '')
        slug = item.get('slug', '')
        
        # Score 1: Chinese character overlap
        cn_score = cn_overlap(cn_title, search_text)
        
        # Score 2: Full sequence match on search text
        seq_score = SequenceMatcher(None, cn_title, search_text).ratio()
        
        # Score 3: Author match bonus
        author_bonus = 0.1 if author and author in search_text else 0.0
        
        # Combined score
        score = max(cn_score, seq_score) + author_bonus
        
        if score > best_score:
            best_score = score
            best_match = {
                'title': wtr_title,
                'author': wtr_author,
                'url': f'https://wtr-lab.com/en/serie-list/{slug}',
                'score': score
            }
    
    # Classify
    if best_score >= 0.65:
        status = 'confirmed'
    elif best_score >= 0.35:
        status = 'probable'
    else:
        status = 'new'
    
    result = (status, round(best_score * 100), best_match)
    _CACHE[cache_key] = result
    return result

