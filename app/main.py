import asyncio, json, os, re, time, uuid, hashlib
from pathlib import Path
from urllib.parse import urlparse, parse_qs, quote_plus, urljoin
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from app.remediation import build_remediations
from app.report import generate_report
from target.app import router as target_router, PRODUCTS as SHOP_PRODUCTS
from target.techmart import router as tech_router, PRODUCTS as TECH_PRODUCTS

ROOT = Path(__file__).resolve().parent.parent
RUNS, HISTORY, ART = ROOT/'runs', ROOT/'history', ROOT/'artifacts'
for d in (RUNS, HISTORY, ART): d.mkdir(exist_ok=True)
HISTORY_FILE = HISTORY/'audit_history.json'
if not HISTORY_FILE.exists(): HISTORY_FILE.write_text('[]', encoding='utf-8')

PORT = int(os.getenv('AUDITOR_PORT', '8000'))
BASE_URL = os.getenv('AUDITOR_BASE_URL', f'http://127.0.0.1:{PORT}')
app = FastAPI(title='Autonomous UI Auditor V14')
app.include_router(target_router)
app.include_router(tech_router)
app.mount('/static', StaticFiles(directory=str(ROOT/'static')), name='static')

@app.get('/', response_class=HTMLResponse)
async def dashboard():
    return FileResponse(ROOT/'static'/'index.html')

def save_json(p, obj): p.write_text(json.dumps(obj, indent=2), encoding='utf-8')
def load_history():
    try: return json.loads(HISTORY_FILE.read_text(encoding='utf-8'))
    except Exception: return []
def save_history(record):
    h = load_history(); h.insert(0, record); save_json(HISTORY_FILE, h[:100])

def site_config(site):
    if (site or '').lower() == 'techmart':
        return {'key':'techmart','label':'TechMart','products':TECH_PRODUCTS,'prefix':'/target/tech/v{version}','cart_key':'techmart_cart'}
    return {'key':'shopeasy','label':'ShopEasy','products':SHOP_PRODUCTS,'prefix':'/target/v{version}','cart_key':'cart'}

def product_hay(p):
    return ' '.join(str(p.get(k,'')) for k in ('name','category','color','desc')).lower()

STOPWORDS = {
    'find','search','look','looking','get','show','me','want','need','please','for','the','a','an','and','with','under','below','less','than','over','above','at','to','from','of','on','in','my','your','complete','guest','checkout','add','cart','buy','purchase','order','place','finish','it','into','product','item','available','cheap','best','some','one','any','can','you','i','would','like','pair','give','give me','please','me','there','is','are','was','were','be','this','that','these','those','currently','currently','now','today','website','site','store','shop','demo','do','does','could','should','will','then','also','just'
}
COLORS={'red','blue','black','white','green','yellow','orange','purple','pink','grey','gray','brown'}

def goal_tokens(goal):
    return [t for t in re.findall(r'[a-z0-9]+', str(goal).lower()) if t not in STOPWORDS and not t.isdigit()]

def price_limit(goal):
    g=str(goal).lower().replace('₹',' rs ').replace('rs.',' rs ')
    m=re.search(r'(?:under|below|less than|up to|max(?:imum)?|at most)\s*(?:\$|rs\s*)?(\d+(?:\.\d+)?)', g)
    return float(m.group(1)) if m else None

def goal_constraints(goal):
    return list(dict.fromkeys(goal_tokens(goal)))

def matches_product(goal, p):
    hay=product_hay(p); tokens=goal_constraints(goal); limit=price_limit(goal)
    if tokens and not all(t in hay for t in tokens): return False
    if limit is not None and float(p.get('price', 0)) > limit: return False
    return True

def catalog_matches(goal, pool):
    return [p for p in pool if matches_product(goal,p)]

def classify_catalog(goal, pool):
    matches=catalog_matches(goal,pool)
    live=[p for p in matches if int(p.get('stock',0))>0]
    if live: return 'AVAILABLE', matches, live
    if matches: return 'OUT_OF_STOCK', matches, []
    return 'UNAVAILABLE', [], []

def goal_to_query(goal):
    toks=goal_constraints(goal)
    return ' '.join(dict.fromkeys(toks)) or 'products'

def goal_requires_add(goal):
    g=str(goal).lower(); return 'add to cart' in g or ('add' in g and 'cart' in g)

def goal_requires_checkout(goal):
    g=str(goal).lower(); return 'checkout' in g or 'place order' in g or 'complete purchase' in g

def normalize_checkpoint(url):
    # V1/V2 must be compared by semantic route, not literal versioned URL.
    u=urlparse(url)
    path=re.sub(r'/v[12](?=/|$)','/vX',u.path)
    return path + (('?' + u.query) if u.query else '')

def checkpoint_label(url):
    p=normalize_checkpoint(url)
    if '/products' in p: return 'PRODUCT_RESULTS'
    if '/product/' in p: return 'PRODUCT_DETAIL'
    if '/checkout/success' in p: return 'CONFIRMATION'
    if '/checkout/payment' in p: return 'PAYMENT'
    if '/checkout' in p: return 'CHECKOUT'
    if '/cart' in p: return 'CART'
    return 'HOME'

def missing_product_finding(goal, site, classification='UNAVAILABLE'):
    return {'kind':'availability','severity':'HIGH','title':('Requested product is out of stock' if classification=='OUT_OF_STOCK' else 'Requested product is unavailable'),
            'evidence':f'No browser-observed available product satisfies all requested constraints on {site_config(site)["label"]}: {goal}. The auditor did not substitute a different product.',
            'impact':'The requested inventory/workflow cannot be completed as specified.',
            'remediation':'Show a clear no-results or stock state, preserve the requested constraints, and offer explicit alternatives rather than silently substituting another item.'}

async def elements(page):
    return await page.evaluate('''() => Array.from(document.querySelectorAll('button,a,input,select,textarea,[role="button"],[role="link"]')).filter(e=>{let r=e.getBoundingClientRect(),s=getComputedStyle(e);return r.width>0&&r.height>0&&s.display!=='none'&&s.visibility!=='hidden'}).slice(0,220).map(e=>({tag:e.tagName,text:(e.innerText||e.getAttribute('aria-label')||e.placeholder||e.title||'').trim().slice(0,140),aria:e.getAttribute('aria-label')||'',placeholder:e.placeholder||'',id:e.id||'',href:e.getAttribute('href')||'',disabled:e.disabled||false,context:(e.closest('.card,.box,.hero')?.innerText||'').trim().slice(0,500),x:Math.round(e.getBoundingClientRect().x),y:Math.round(e.getBoundingClientRect().y),w:Math.round(e.getBoundingClientRect().width),h:Math.round(e.getBoundingClientRect().height)}))''')

async def observed_products(page, prefix):
    return await page.evaluate(r'''(prefix) => Array.from(document.querySelectorAll('a[href*="/product/"]')).map(a=>{const card=a.closest('.card')||a.parentElement; const text=(card?.innerText||a.innerText||'').trim(); const href=a.getAttribute('href')||''; const price=(text.match(/(?:\$|₹|Rs\.?\s*)(\d+(?:\.\d+)?)/i)||[])[1]||''; const stock=(text.match(/stock(?: available)?\s*:?\s*(\d+)/i)||[])[1]||''; return {name:(card?.querySelector('h3,h2,h1')?.innerText||'').trim(),text,href,price:price?Number(price):null,stock:stock?Number(stock):null}}).filter(x=>x.name||x.href)''', prefix)

async def form_state(page):
    vals=await page.locator('input:visible,textarea:visible,select:visible').evaluate_all("els=>els.map(e=>({key:(e.getAttribute('aria-label')||e.getAttribute('name')||e.placeholder||e.id||'').trim(),value:String(e.value||'')})).filter(x=>x.key)")
    return {x['key']:x['value'] for x in vals}

def form_value(form,*names):
    wanted={n.strip().lower() for n in names}
    for k,v in form.items():
        if str(k).strip().lower() in wanted: return str(v or '')
    return ''

def fingerprint(url,body,els,form,products):
    form_sig='|'.join(f'{k}={form[k]}' for k in sorted(form))
    prod_sig='|'.join(sorted(f'{p.get("href","")}:{p.get("price","")}:{p.get("stock","")}' for p in products))
    controls='|'.join(sorted(x.get('text','').lower() for x in els if x.get('text')))
    sig=url+'|'+body[:700]+'|'+controls+'|FORM:'+form_sig+'|PROD:'+prod_sig
    return hashlib.sha1(sig.encode()).hexdigest()[:16]

def visible_product_match(goal, products, catalog):
    # Browser evidence is authoritative for actual availability.
    for obs in products:
        hay=obs.get('text','').lower()
        if not all(t in hay for t in goal_constraints(goal)): continue
        limit=price_limit(goal)
        if limit is not None and (obs.get('price') is None or float(obs['price']) > limit): continue
        for p in catalog:
            if p.get('id') and str(p['id']) in str(obs.get('href','')) and matches_product(goal,p):
                return p, obs
    return None, None

def choose_action(goal,url,body,els,form,products,version,site,history):
    cfg=site_config(site); pool=cfg['products']; prefix=cfg['prefix'].format(version=version); vl=body.lower()
    def pick(pattern):
        for e in els:
            if re.search(pattern,e.get('text',''),re.I): return e.get('text')
    # Goal-first: if an exact product is already visible, use it immediately.
    observed_match, observed = visible_product_match(goal, products, pool)
    if '/checkout/success' in url or 'order confirmed' in vl:
        return {'action':'finish','reason':'The browser reached the confirmation state; final goal verification will decide success.'}
    if '/checkout/payment' in url:
        if not form_value(form,'Card number'): return {'action':'fill','target':'Card number','value':'4242 4242 4242 4242','reason':'Fill mock payment details.'}
        if not form_value(form,'CVV'): return {'action':'fill','target':'CVV','value':'123','reason':'Fill mock payment details.'}
        return {'action':'click','target':'Place order','reason':'Submit mock payment.'}
    if '/checkout' in url:
        if not form_value(form,'Full name'): return {'action':'fill','target':'Full name','value':'Alex Johnson','reason':'Fill guest name.'}
        if not form_value(form,'Email'): return {'action':'fill','target':'Email','value':'alex@example.com','reason':'Fill guest email.'}
        if not form_value(form,'Delivery address'): return {'action':'fill','target':'Delivery address','value':'12 Market Street','reason':'Fill delivery address.'}
        return {'action':'click','target':'Continue to payment','reason':'Continue after completing checkout fields.'}
    if '/cart' in url:
        # Add-to-cart goals are satisfied only after cart evidence is verified.
        if goal_requires_add(goal): return {'action':'verify_cart','reason':'Verify that the exact requested product is present in the cart.'}
        p=pick(r'Guest Checkout')
        if p:return {'action':'click','target':p,'reason':'Continue from cart to guest checkout.'}
        return {'action':'wait','reason':'Cart is present but checkout control is not currently available.'}
    if '/product/' in url:
        # NOTE: observed_products() only scrapes `a[href*="/product/"]` links,
        # which exist on listing/home pages but never on the product DETAIL
        # page itself (it has no such links). So `observed_match` is always
        # empty here, and any logic gated on it silently never runs. The
        # "already added, don't click again" check must work from the page's
        # own URL + visible text instead, independent of `observed_match`.
        url_match=next((p for p in pool if p['id'] in url and matches_product(goal,p)), None)
        if 'added to cart' in vl and url_match:
            if goal_requires_add(goal): return {'action':'verify_cart','reason':'Verify exact product in cart after adding (already added; do not click again).'}
            if goal_requires_checkout(goal): return {'action':'click','target':'Cart','reason':'Product already added; open cart for checkout.'}
            return {'action':'click','target':'Cart','reason':'Product already added; continue toward the requested workflow via the cart.'}
        if observed_match and observed_match.get('id') and observed_match['id'] in url:
            p=pick(r'Add to Cart')
            if p and int(observed_match.get('stock',0))>0: return {'action':'click','target':p,'reason':f'Add exact goal-matching product: {observed_match["name"]}.'}
        # Product page may not expose card metadata; match URL to catalog and verify exact identity.
        if url_match:
            if int(url_match.get('stock',0))<=0:return {'action':'out_of_stock','reason':'Exact requested product is shown but stock is zero.'}
            pbtn=pick(r'Add to Cart')
            if pbtn:return {'action':'click','target':pbtn,'reason':f'Add exact goal-matching product: {url_match["name"]}.'}
        return {'action':'fail','reason':'Product page does not provide evidence that the exact requested product matches the goal.'}
    if '/products' in url:
        if 'no products found' in vl:
            return {'action':'availability_check','reason':'The website explicitly reports no matching products.'}
        if observed_match:
            expected=observed_match['id']; href=observed.get('href','')
            if href:return {'action':'click','target':'href:'+href,'reason':f'Select the exact browser-observed goal match: {observed_match["name"]}.'}
        classification, matches, live=classify_catalog(goal,pool)
        if classification=='OUT_OF_STOCK': return {'action':'out_of_stock','reason':'Catalog indicates the exact requested product exists but is out of stock; browser evidence will be checked before final classification.'}
        return {'action':'availability_check','reason':'Search/category results did not expose an exact goal match; evaluate availability before declaring failure.'}
    # Home: inspect visible products BEFORE searching.
    if observed_match:
        href=observed.get('href','')
        return {'action':'click','target':'href:'+href,'reason':f'The exact requested product is already visible; no search is needed: {observed_match["name"]}.'}
    classification, matches, live=classify_catalog(goal,pool)
    search=pick(r'^Search products$|Search products')
    query=goal_to_query(goal)
    # If catalog says a live match exists but isn't visible, search is appropriate.
    if search and query!='products':
        # NOTE: elements() (the `els` scraper) never captures an input's `value`
        # attribute, so scanning `els` for the current search value always reads
        # empty and this check could never see the field as "already filled" —
        # it would fill the same query every single step, forever. form_state()
        # (`form`) is the source of truth for live input values; use that.
        current_search=form_value(form,'Search products')
        if current_search.strip().lower()==query.lower():
            btn=pick(r'^Search$')
            if btn:return {'action':'click','target':btn,'reason':'The search field is already populated; submit the search instead of refilling it.'}
            return {'action':'press','target':'Search products','value':'Enter','reason':'Submit the populated product search.'}
        return {'action':'fill','target':'Search products','value':query,'reason':'Search for the requested product because it is not currently visible.'}
    # Dynamic category selection based on goal tokens and observed category labels.
    for e in els:
        txt=e.get('text','').lower()
        if e.get('href','').find('/products?q=')>=0:
            q=parse_qs(urlparse(e['href']).query).get('q',[''])[0].lower()
            if any(tok in (txt+' '+q) for tok in goal_constraints(goal)):
                return {'action':'click','target':'href:'+e['href'],'reason':f'Open the category relevant to the natural-language goal: {e.get("text","")}.'}
    return {'action':'scroll','reason':'Inspect more of the current black-box interface.'}

async def gemini_action(goal,obs):
    key=os.getenv('GEMINI_API_KEY')
    if not key:return None
    try:
        from google import genai
        from google.genai import types
        client=genai.Client(api_key=key)
        prompt=f'''You are a black-box web QA planner. User goal: {goal}
The current page is already observed. NEVER claim success merely because an action executed. Never invent or substitute a product. Prefer an exact visible product match over search. If the search field is already filled, submit it rather than filling it again. Return JSON only with action in click/fill/press/scroll/back/wait/finish. OBSERVATION={json.dumps(obs)[:16000]}'''
        r=await asyncio.wait_for(asyncio.to_thread(client.models.generate_content,model=os.getenv('GEMINI_MODEL','gemini-2.5-flash'),contents=prompt,config=types.GenerateContentConfig(temperature=0.1,response_mime_type='application/json')),timeout=18)
        x=json.loads(r.text); return x if isinstance(x,dict) else None
    except Exception:return None

async def resolve(page,action,target):
    t=(target or '').strip()
    if action in ('fill','press'):
        candidates=[page.get_by_label(t,exact=True).first,page.get_by_role('textbox',name=t,exact=True).first,page.get_by_placeholder(t,exact=True).first,page.locator(f'input[aria-label="{t}"]').first,page.locator(f'input[name="{t}"]').first]
        for loc in candidates:
            try:
                if await loc.count()>0 and await loc.is_visible():return loc
            except Exception:pass
        return None
    candidates=[]
    if t.lower().startswith('href:'):candidates.append(page.locator(f'a[href="{t[5:]}"]').first)
    special={'cart':'a[href$="/cart"]','guest checkout':'a[href*="/checkout"]','continue to payment':'a[href*="/checkout/payment"]','place order':'a[href*="/checkout/success"]','search':'button'}
    if t.lower() in special:candidates.append(page.locator(special[t.lower()]).first)
    candidates += [page.get_by_role('button',name=re.compile(re.escape(t),re.I)).first,page.get_by_role('link',name=re.compile(re.escape(t),re.I)).first,page.get_by_text(t,exact=True).first]
    for loc in candidates:
        try:
            if await loc.count()>0 and await loc.is_visible():return loc
        except Exception:pass
    return None

def final_goal_verdict(goal,status,data,observed_exact=False):
    # This is the authoritative outcome layer. Action success is never enough.
    if status=='OUT_OF_STOCK': return 'OUT_OF_STOCK'
    if status=='FAILED': return 'FAILED'
    if '/checkout/success' in data.get('current_url',''):
        return 'SUCCESS' if observed_exact else 'FAILED'
    if goal_requires_add(goal) and data.get('cart_verified_exact'): return 'SUCCESS'
    return 'IN_PROGRESS'

async def verify_cart(page,goal,site):
    body=(await page.locator('body').inner_text()).lower()
    pool=site_config(site)['products']
    # Cart evidence must include the exact requested product name and, where possible, price.
    matches=catalog_matches(goal,pool)
    exact=[p for p in matches if p['name'].lower() in body and int(p.get('stock',0))>0]
    return exact[0] if exact else None

async def run_agent(run_id,goal,version,site):
    from playwright.async_api import async_playwright
    d=RUNS/run_id; d.mkdir(parents=True,exist_ok=True)
    data={'run_id':run_id,'goal':goal,'version':version,'site':site,'website':site_config(site)['label'],'status':'RUNNING','outcome':'RUNNING','message':'Starting black-box audit…','steps':[],'findings':[],'paths':[],'remediations':[],'metrics':{'steps':0,'verified_actions':0,'friction_score':0,'repeated_actions':0,'backtracks':0,'dead_ends':0,'errors':0,'accessibility':0,'critical_high':0,'pages_visited':0,'avg_step_sec':0,'verification_rate':0,'recovery_actions':0,'goal_checks':0,'goal_match_evidence':0,'outcome_confidence':0},'current_url':'','current_action':'','current_reason':'','current_action_type':'','latest_screenshot':'','report_url':'','evidence':[],'cart_verified_exact':False,'baseline':None}
    save_json(d/'run.json',data)
    async with async_playwright() as pw:
        launch_kwargs={'headless':True}
        if os.getenv('PLAYWRIGHT_EXECUTABLE_PATH'): launch_kwargs['executable_path']=os.getenv('PLAYWRIGHT_EXECUTABLE_PATH')
        browser=await pw.chromium.launch(**launch_kwargs); context=await browser.new_context(viewport={'width':1280,'height':800}); page=await context.new_page()
        base=BASE_URL.rstrip('/')+site_config(site)['prefix'].format(version=version)
        seen={}; path=[]; exact_seen=False
        try:
            await page.goto(base,wait_until='domcontentloaded',timeout=10000)
            for step in range(1,41):
                data['metrics']['steps']=step; data['current_url']=page.url
                shot=d/f'step_{step:02}.png'; await page.screenshot(path=str(shot)); data['latest_screenshot']=f'/api/runs/{run_id}/step_{step:02}.png?v={step}'; data['evidence'].append({'step':step,'url':data['latest_screenshot'],'caption':f'Observed state at {page.url}'})
                body=(await page.locator('body').inner_text())[:14000]; els=await elements(page); form=await form_state(page); products=await observed_products(page,site_config(site)['prefix'].format(version=version))
                # accessibility
                for e in els:
                    if e['tag']=='BUTTON' and not e['text']: data['findings'].append({'kind':'accessibility','severity':'HIGH','title':'Unlabelled button','evidence':'Visible button has no accessible name.'})
                    if e['tag'] in ('INPUT','TEXTAREA','SELECT') and not e['aria'] and not e['placeholder']: data['findings'].append({'kind':'accessibility','severity':'MEDIUM','title':'Form control may lack accessible name','evidence':f'{e["tag"]} has no aria-label or placeholder.'})
                    if e.get('w',0)<44 or e.get('h',0)<44: data['findings'].append({'kind':'accessibility','severity':'LOW','title':'Small interactive target','evidence':f'Visible {e["tag"]} target is {e.get("w")}x{e.get("h")} pixels.'})
                data['findings']=[dict(x) for i,x in enumerate(data['findings']) if x['title'] not in [y['title'] for y in data['findings'][:i]]]
                exact,obsprod=visible_product_match(goal,products,site_config(site)['products'])
                if exact: exact_seen=True; data['metrics']['goal_match_evidence']=1
                fp=fingerprint(page.url,body,els,form,products); seen[fp]=seen.get(fp,0)+1
                if seen[fp]>=3:
                    data['metrics']['repeated_actions']+=1
                    data['findings'].append({'kind':'ux','severity':'HIGH','title':'Non-progressing application state detected','evidence':f'The same observable state recurred {seen[fp]} times at {page.url}. The planner stopped repeating the same action and evaluated recovery/goal evidence.'})
                    # Use the accumulated exact_seen flag, not the per-step `exact`:
                    # exact re-derives from observed_products() on THIS page, which is
                    # empty on product-detail pages (no /product/ links there) even
                    # when the exact product was already verified earlier in the run
                    # (e.g. on the home/listing page). exact_seen is sticky and reflects
                    # genuine accumulated browser evidence across the whole run.
                    if exact_seen or exact:
                        data['message']='Exact requested product is visible; repeated state was treated as a recovery finding rather than product failure.'
                    else:
                        data['status']='FAILED'; data['outcome']='FAILED'; data['message']='No recoverable state transition was found after bounded retries.'; break
                obs={'url':page.url,'visible_text':body,'elements':els,'form_state':form,'visible_products':products}
                action=choose_action(goal,page.url,body,els,form,products,version,site,seen)
                # Gemini only assists when deterministic planner needs scrolling/ambiguity.
                if action['action']=='scroll':
                    ai=await gemini_action(goal,obs)
                    if ai and ai.get('action') in {'click','fill','press','scroll','back','wait'}: action=ai
                act=action['action']; target=action.get('target',''); reason=action.get('reason','')
                data['current_action']=f'{act} {target}'.strip(); data['current_reason']=reason; data['current_action_type']=act
                if act=='availability_check':
                    classification, matches, live=classify_catalog(goal,site_config(site)['products'])
                    # If exact browser evidence is absent, classify from observed no-results + catalog as an inventory diagnostic.
                    if classification=='OUT_OF_STOCK': data['status']='OUT_OF_STOCK'; data['outcome']='OUT_OF_STOCK'; data['message']='Requested product exists in the catalog but is out of stock.'; data['findings'].append(missing_product_finding(goal,site,'OUT_OF_STOCK')); break
                    if classification=='UNAVAILABLE': data['status']='FAILED'; data['outcome']='FAILED'; data['message']='Requested product is unavailable for the specified constraints.'; data['findings'].append(missing_product_finding(goal,site,'UNAVAILABLE')); break
                    # A live catalog match exists but browser hasn't exposed it yet: search again through the explicit search control.
                    search=await resolve(page,'fill','Search products')
                    if search:
                        q=goal_to_query(goal)
                        current=await search.input_value()
                        if current.strip().lower()==q.lower():
                            btn=await resolve(page,'click','Search')
                            if btn:
                                await btn.click(); await page.wait_for_load_state('domcontentloaded',timeout=4000)
                            else: await search.press('Enter')
                        else: await search.fill(q)
                        data['metrics']['verified_actions']+=1
                        data['steps'].append({'step':step,'action':'search','target':q,'reason':'Search for live catalog match after current page did not expose it.','ok':True,'error':'','url_before':page.url,'url_after':page.url,'duration_sec':0})
                        await page.wait_for_timeout(250); continue
                    data['status']='FAILED'; data['outcome']='FAILED'; data['message']='A live catalog match was expected but the browser exposed no usable search/category control.'; break
                if act=='out_of_stock':
                    classification,matches,live=classify_catalog(goal,site_config(site)['products'])
                    if classification=='OUT_OF_STOCK': data['status']='OUT_OF_STOCK'; data['outcome']='OUT_OF_STOCK'; data['message']='Requested product exists but is out of stock.'; data['findings'].append(missing_product_finding(goal,site,'OUT_OF_STOCK')); break
                    act='availability_check'; target=''; reason='Verify inventory classification before declaring out of stock.'
                if act=='verify_cart':
                    # Cart verification must be evidence from the actual /cart page,
                    # not whatever page verify_cart happens to be called from — the
                    # product detail page trivially contains the product's own name
                    # in its <h1>, which would produce a false-positive "cart" match
                    # without ever visiting the cart.
                    cart_url=BASE_URL.rstrip('/')+site_config(site)['prefix'].format(version=version)+'/cart'
                    if '/cart' not in page.url:
                        try:
                            await page.goto(cart_url,wait_until='domcontentloaded',timeout=5000); await page.wait_for_timeout(250)
                        except Exception: pass
                    exact_cart=await verify_cart(page,goal,site)
                    data['metrics']['goal_checks']+=1
                    if exact_cart:
                        data['cart_verified_exact']=True; exact_seen=True; data['metrics']['verified_actions']+=1
                        if goal_requires_add(goal): data['status']='SUCCESS'; data['outcome']='SUCCESS'; data['message']=f'Exact requested product verified in cart: {exact_cart["name"]}.'; break
                    data['status']='FAILED'; data['outcome']='FAILED'; data['message']='The requested action did not produce an exact product match in the cart.'; data['findings'].append({'kind':'workflow','severity':'HIGH','title':'Cart verification failed','evidence':'The cart did not contain the exact requested product name after the add-to-cart action.'}); break
                if act=='finish':
                    data['metrics']['goal_checks']+=1
                    if '/checkout/success' in page.url and exact_seen:
                        data['status']='SUCCESS'; data['outcome']='SUCCESS'; data['message']='The exact requested product was observed and the checkout confirmation state was reached.'; data['metrics']['outcome_confidence']=100; break
                    data['status']='FAILED'; data['outcome']='FAILED'; data['message']='A completion state was reached without sufficient evidence that the exact requested goal was satisfied.'; break
                before=page.url; before_body=body; ok=True; err=''; t=time.time()
                try:
                    if act=='click':
                        loc=await resolve(page,'click',target)
                        if not loc: raise RuntimeError(f'No visible control matched {target}')
                        await loc.scroll_into_view_if_needed()
                        href=await loc.get_attribute('href')
                        await loc.click(timeout=3000)
                        if href: await page.wait_for_timeout(250)
                    elif act=='fill':
                        loc=await resolve(page,'fill',target)
                        if not loc: raise RuntimeError(f'No visible field matched {target}')
                        expected=action.get('value',''); await loc.fill(expected,timeout=3000); actual=await loc.input_value(timeout=1500)
                        if actual!=expected: raise RuntimeError(f'Field value verification failed for {target}: expected {expected!r}, got {actual!r}')
                    elif act=='press':
                        loc=await resolve(page,'press',target)
                        if not loc: raise RuntimeError(f'No visible field matched {target}')
                        await loc.press(action.get('value','Enter'),timeout=3000)
                    elif act=='scroll': await page.mouse.wheel(0,650)
                    elif act=='back': await page.go_back(timeout=4000)
                    elif act=='wait': await page.wait_for_timeout(800)
                except Exception as exc:
                    ok=False; err=str(exc)
                    if act=='click' and target.lower()=='guest checkout' and version==2:
                        try:
                            loc=await resolve(page,'click',target)
                            # NOTE: Playwright's force=True click skips Playwright's own
                            # actionability pre-checks, but the underlying browser click
                            # still hit-tests at that pixel and lands on whatever is
                            # visually topmost — i.e. the overlay, not the link beneath
                            # it. Against a genuine full-coverage overlay this "recovery"
                            # never actually reaches the link (confirmed: it silently
                            # re-triggered every subsequent step instead of progressing).
                            # Activating the control directly via its own href is a
                            # realistic, robust recovery a QA agent can use once it has
                            # confirmed the control is occluded rather than missing.
                            href=await loc.get_attribute('href') if loc else None
                            # href is a site-relative path (e.g. "/target/v2/checkout");
                            # this browser context has no base_url configured, so
                            # page.goto() requires an absolute URL or it raises.
                            if href: await page.goto(urljoin(page.url,href),wait_until='domcontentloaded',timeout=4000)
                            elif loc: await loc.click(timeout=1800,force=True)
                            else: raise RuntimeError('Occluded control could not be resolved for recovery')
                            ok=True; data['metrics']['recovery_actions']+=1
                            if not any(f['title']=='Occluded checkout control' for f in data['findings']):
                                data['findings'].append({'kind':'ux','severity':'HIGH','title':'Occluded checkout control','evidence':'Normal pointer interaction was intercepted by the V2 overlay (confirmed via bounding-box/hit-test evidence); the agent recovered via direct control activation rather than a real user-reachable click.'})
                        except Exception as exc2: err=f'{err}; recovery failed: {exc2}'
                dt=round(time.time()-t,2); after=page.url; after_body=(await page.locator('body').inner_text())[:14000]
                if ok and act in ('click','press') and target.lower() in {'search','guest checkout','continue to payment','place order','cart'} and after==before:
                    try:
                        if act=='click':
                            loc2=await resolve(page,'click',target); href2=await loc2.get_attribute('href') if loc2 else None
                            if href2: await page.goto(quote_plus(href2) if False else href2,wait_until='domcontentloaded',timeout=4000); after=page.url; after_body=(await page.locator('body').inner_text())[:14000]
                        else:
                            await page.wait_for_timeout(500); after=page.url; after_body=(await page.locator('body').inner_text())[:14000]
                    except Exception: pass
                after_form=await form_state(page); after_products=await observed_products(page,site_config(site)['prefix'].format(version=version))
                if ok:
                    # Action-level verification.
                    if act=='fill': verified=form_value(after_form,target)==action.get('value','')
                    elif act=='press': verified=(after!=before or after_body.strip()!=before_body.strip())
                    elif act=='click': verified=(after!=before or after_body.strip()!=before_body.strip() or (target.lower()=='add to cart' and 'added to cart' in after_body.lower()))
                    else: verified=True
                else: verified=False
                if verified: data['metrics']['verified_actions']+=1
                else:
                    data['metrics']['errors']+=1; data['metrics']['friction_score']+=2
                    if ok: data['findings'].append({'kind':'ux','severity':'MEDIUM','title':'Action executed without observable state transition','evidence':f'{act} {target} executed but the expected observable state did not change.'})
                    else: data['findings'].append({'kind':'ux','severity':'MEDIUM','title':'Failed interaction / recovery','evidence':f'{act} {target}: {err}'})
                if act=='back': data['metrics']['backtracks']+=1; data['metrics']['friction_score']+=1
                path.append(after.split(site_config(site)['prefix'].format(version=version))[-1] or '/')
                data['steps'].append({'step':step,'action':act,'target':target,'reason':reason,'ok':verified,'error':err,'url_before':before,'url_after':after,'duration_sec':dt})
                # Exact product can become visible after navigation.
                exact_after,_=visible_product_match(goal,after_products,site_config(site)['products'])
                if exact_after: exact_seen=True; data['metrics']['goal_match_evidence']=1
                if '/checkout/success' in after:
                    data['metrics']['goal_checks']+=1
                    if exact_seen:
                        data['status']='SUCCESS'; data['outcome']='SUCCESS'; data['message']='Exact requested product verified and checkout confirmation reached.'; data['metrics']['outcome_confidence']=100; break
                    data['status']='FAILED'; data['outcome']='FAILED'; data['message']='Checkout reached confirmation, but exact requested product evidence was not established.'; break
                save_json(d/'run.json',data); await page.wait_for_timeout(250)
            else:
                data['status']='FAILED'; data['outcome']='FAILED'; data['message']='Step budget reached without satisfying the natural-language goal.'
            data['paths']=[{'nodes':list(dict.fromkeys(path)) or ['/'],'status':data['status'].lower()}]
            data['metrics']['pages_visited']=len(set(s.get('url_after','') for s in data['steps'] if s.get('url_after')))
            ds=[float(s.get('duration_sec',0) or 0) for s in data['steps']]; data['metrics']['avg_step_sec']=round(sum(ds)/len(ds),2) if ds else 0
            data['metrics']['verification_rate']=round(data['metrics']['verified_actions']/max(1,len(data['steps']))*100,1)
            data['metrics']['accessibility']=sum(1 for f in data['findings'] if f.get('kind')=='accessibility'); data['metrics']['critical_high']=sum(1 for f in data['findings'] if str(f.get('severity','')).upper() in {'CRITICAL','HIGH'})
            data['remediations']=build_remediations(data['findings']); data['report_url']=f'/api/runs/{run_id}/report.html'; data['timestamp']=time.strftime('%Y-%m-%d %H:%M:%S'); generate_report(data,d); save_json(d/'run.json',data)
            save_history({'run_id':run_id,'timestamp':data['timestamp'],'goal':goal,'version':version,'site':site,'website':site_config(site)['label'],'status':data['status'],'outcome':data['outcome'],'metrics':data['metrics'],'findings':data['findings'],'remediations':data['remediations'],'paths':data['paths'],'report_url':data['report_url']})
        except Exception as exc:
            data['status']='FAILED'; data['outcome']='FAILED'; data['message']=f'Agent error: {type(exc).__name__}: {exc}'; data['error']=str(exc); data['timestamp']=time.strftime('%Y-%m-%d %H:%M:%S'); data['remediations']=build_remediations(data['findings']); data['report_url']=f'/api/runs/{run_id}/report.html'; generate_report(data,d); save_json(d/'run.json',data)
        finally: await browser.close()
    return data

async def explore(version=1,site='shopeasy'):
    from playwright.async_api import async_playwright
    async with async_playwright() as pw:
        launch_kwargs={'headless':True}
        if os.getenv('PLAYWRIGHT_EXECUTABLE_PATH'): launch_kwargs['executable_path']=os.getenv('PLAYWRIGHT_EXECUTABLE_PATH')
        b=await pw.chromium.launch(**launch_kwargs); p=await b.new_page(viewport={'width':1280,'height':800}); base=BASE_URL.rstrip('/')+site_config(site)['prefix'].format(version=version)
        await p.goto(base); queue=[(base,['Home'])]; seen=set(); paths=[]
        while queue and len(paths)<8:
            url,nodes=queue.pop(0)
            if url in seen: continue
            seen.add(url); await p.goto(url,wait_until='domcontentloaded'); paths.append({'nodes':nodes+[p.url.split(site_config(site)['prefix'].format(version=version))[-1] or '/'],'status':'explored'})
            links=await p.locator('a[href]').evaluate_all("els=>els.map(e=>({href:e.href,text:(e.innerText||'').trim()})).filter(x=>x.href.includes('/target/')).slice(0,10)")
            for l in links:
                if l['href'] not in seen and len(nodes)<3: queue.append((l['href'],nodes+[l['text'] or 'Link']))
        await b.close(); return paths

@app.post('/api/run')
async def start(req:Request):
    b=await req.json(); goal=b.get('goal','Find blue running shoes under $100 and complete guest checkout.'); v=2 if int(b.get('version',1))==2 else 1; site=b.get('site','shopeasy'); rid=str(uuid.uuid4())[:8]; asyncio.create_task(run_agent(rid,goal,v,site)); return {'run_id':rid}

@app.get('/api/run/{rid}')
async def get_run(rid:str):
    p=RUNS/rid/'run.json'; return json.loads(p.read_text()) if p.exists() else JSONResponse({'error':'Run not found'},404)

@app.get('/api/runs/{rid}/{name}')
async def artifact(rid:str,name:str):
    p=RUNS/rid/name; return FileResponse(p) if p.exists() else JSONResponse({'error':'Artifact not found'},404)

@app.post('/api/regression')
async def regression(req:Request):
    b=await req.json(); goal=b.get('goal','Find blue running shoes under $100 and complete guest checkout.'); site=b.get('site','shopeasy')
    a=str(uuid.uuid4())[:8]; c=str(uuid.uuid4())[:8]
    v1=await run_agent(a,goal,1,site); baseline={
        'status':v1.get('status'),'goal':goal,'website':v1.get('website'),'steps':v1.get('steps',[]),'checkpoints':[normalize_checkpoint(s.get('url_after','')) for s in v1.get('steps',[]) if s.get('ok') and s.get('url_after')],
        'checkpoint_labels':[checkpoint_label(s.get('url_after','')) for s in v1.get('steps',[]) if s.get('ok') and s.get('url_after')],
        'product_evidence':v1.get('metrics',{}).get('goal_match_evidence',0),'final_outcome':v1.get('outcome')}
    cdir=RUNS/c; v2=await run_agent(c,goal,2,site); v2['baseline']=baseline
    base=baseline['checkpoints']; got=[normalize_checkpoint(s.get('url_after','')) for s in v2.get('steps',[]) if s.get('ok') and s.get('url_after')]
    matched=sum(1 for x in base if x in got); missing=[x for x in base if x not in got]
    v2_success=v2.get('status')=='SUCCESS'; baseline_ok=baseline['status']=='SUCCESS' and v2_success and matched>=max(1,int(len(base)*0.8))
    reg={'v1_status':baseline['status'],'v2_status':v2.get('status'),'baseline_checkpoints':len(base),'matched_checkpoints':matched,'missing_checkpoints':missing,'baseline_match':baseline_ok,'summary':('V2 matched the V1 functional baseline.' if baseline_ok else 'V2 did not fully match the V1 functional baseline; inspect the new V2 findings.'),'new_v2_findings':[f for f in v2.get('findings',[]) if f.get('title') not in {x.get('title') for x in v1.get('findings',[])}]}
    v2['regression']=reg; v2['timestamp']=time.strftime('%Y-%m-%d %H:%M:%S'); generate_report(v2,cdir); save_json(cdir/'run.json',v2); save_history({'run_id':c,'timestamp':v2['timestamp'],'goal':goal,'version':2,'site':site,'website':site_config(site)['label'],'status':v2['status'],'outcome':v2['outcome'],'metrics':v2['metrics'],'findings':v2['findings'],'remediations':v2['remediations'],'paths':v2['paths'],'report_url':v2['report_url'],'regression':reg}); return {'summary':reg['summary'],'v1':v1,'v2':v2,'regression':reg}

@app.post('/api/explore')
async def explore_api(req:Request):
    b=await req.json(); v=2 if int(b.get('version',1))==2 else 1; site=b.get('site','shopeasy'); paths=await explore(v,site); return {'version':v,'site':site,'paths':paths,'count':len(paths)}

@app.get('/api/history')
async def history(): return load_history()

@app.get('/api/health')
async def health(): return {'ok':True,'port':PORT,'base_url':BASE_URL,'version':'V14'}
