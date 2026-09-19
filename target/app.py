from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from urllib.parse import quote

router = APIRouter()

PRODUCTS = [
    {'id':'blue-sprint','name':'Blue Sprint Running Shoes','color':'blue','category':'running shoes','price':89,'stock':7,'desc':'Lightweight road running shoes.'},
    {'id':'blue-trail','name':'Blue Trail Running Shoes','color':'blue','category':'running shoes','price':99,'stock':4,'desc':'Trail-ready running shoes.'},
    {'id':'black-run','name':'Black Running Shoes','color':'black','category':'running shoes','price':119,'stock':5,'desc':'Everyday black running shoes.'},
    {'id':'red-sneaker','name':'Red Sneakers','color':'red','category':'sneakers','price':75,'stock':8,'desc':'Casual red sneakers.'},
    {'id':'headphones','name':'Wireless Headphones','color':'black','category':'electronics','price':69,'stock':10,'desc':'Wireless over-ear headphones.'},
    {'id':'yellow-jacket','name':'Yellow Jacket','color':'yellow','category':'jackets','price':79,'stock':6,'desc':'Lightweight yellow outdoor jacket.'},
    {'id':'black-jacket','name':'Black Jacket','color':'black','category':'jackets','price':69,'stock':0,'desc':'Black insulated jacket, currently out of stock.'},
    {'id':'green-hoodie','name':'Green Hoodie','color':'green','category':'hoodies','price':59,'stock':9,'desc':'Soft green everyday hoodie.'},
    {'id':'white-sneakers','name':'White Sneakers','color':'white','category':'sneakers','price':95,'stock':11,'desc':'Clean white everyday sneakers.'},
    {'id':'orange-jacket','name':'Orange Jacket','color':'orange','category':'jackets','price':89,'stock':5,'desc':'Lightweight orange trail jacket.'},
    {'id':'blue-hoodie','name':'Blue Hoodie','color':'blue','category':'hoodies','price':64,'stock':7,'desc':'Soft blue everyday hoodie.'},
]

def base_css(v):
    # NOTE: previously right/bottom-positioned within a full-width block wrapper,
    # so it landed far away from the (left-aligned, content-width) checkout
    # button and never actually overlapped it — the "occluded control" defect
    # was not reproducible. Anchored to the button's own top-left corner instead,
    # so it reliably covers the clickable control regardless of container width.
    overlay = '' if v == 1 else '.checkout-wrap{position:relative;display:inline-block}.occluder{position:absolute;left:0;top:0;width:180px;height:48px;background:rgba(10,16,30,.82);z-index:20;border-radius:12px;pointer-events:auto}'
    return f'''<style>
*{{box-sizing:border-box}}body{{margin:0;font-family:Inter,Arial,sans-serif;background:#f5f7fb;color:#182033}}header{{background:#111827;color:white;padding:18px 7%;display:flex;justify-content:space-between;align-items:center}}header a{{color:#cbd5e1;text-decoration:none;margin-left:18px}}main{{max-width:1050px;margin:30px auto;padding:0 20px}}.hero,.card,.box{{background:white;border:1px solid #e2e8f0;border-radius:18px;padding:22px;box-shadow:0 8px 25px #1111}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:16px;margin-top:20px}}.price{{font-size:22px;font-weight:800}}button,a.btn{{border:0;border-radius:10px;padding:11px 15px;background:#4f46e5;color:white;cursor:pointer;text-decoration:none;display:inline-block}}button.secondary,a.secondary{{background:#e2e8f0;color:#172033}}input{{padding:12px;border:1px solid #cbd5e1;border-radius:10px;width:100%;margin:6px 0 12px}}.muted{{color:#64748b}}.badge{{display:inline-block;padding:4px 8px;border-radius:999px;background:#eef2ff;color:#4338ca;font-size:12px}}.error{{background:#fee2e2;color:#991b1b;padding:14px;border-radius:12px}}.success{{background:#dcfce7;color:#166534;padding:14px;border-radius:12px}}.checkout-wrap{{margin-top:20px}}{overlay}</style>'''

def layout(v, body, title='ShopEasy'):
    products_json = __import__('json').dumps({p['id']:p for p in PRODUCTS})
    return HTMLResponse(f'''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title>{base_css(v)}</head><body><header><b>🛍 ShopEasy <span class="badge">V{v}</span></b><nav><a href="/target/v{v}">Home</a><a href="/target/v{v}/products">Products</a><a href="/target/v{v}/cart">Cart</a></nav></header><main>{body}</main><script>
const PRODUCTS={products_json};
function add(id){{let c=JSON.parse(localStorage.getItem('cart')||'[]');let p=c.find(x=>x.id===id);if(p)p.qty++;else c.push({{id,qty:1}});localStorage.setItem('cart',JSON.stringify(c));let m=document.getElementById('msg');if(m)m.textContent='Added to cart';}}
function renderCart(){{let c=JSON.parse(localStorage.getItem('cart')||'[]');let total=0;let box=document.getElementById('cartitems');if(!box)return;box.innerHTML='';c.forEach(x=>{{let p=PRODUCTS[x.id];if(!p)return;total+=p.price*x.qty;box.innerHTML+=`<div class="card"><b>${{p.name}}</b><p>${{x.qty}} × ${{p.price}}</p></div>`}});let t=document.getElementById('total');if(t)t.textContent='$'+total;if(c.length===0)box.innerHTML='<div class="muted">Your cart is empty.</div>';}}
if(document.getElementById('cartitems')) renderCart();</script></body></html>''' )

@router.get('/target/v{version}')
async def home(version:int):
    v=2 if version==2 else 1
    body='''<section class="hero"><h1>ShopEasy</h1><p>Black-box UI audit demo store.</p><form action="/target/v{v}/products" method="get"><input name="q" placeholder="Search products" aria-label="Search products"><button>Search</button></form></section><h2>Categories</h2><div class="grid"><a class="btn" href="/target/v{v}/products?q=running+shoes">Running Shoes</a><a class="btn secondary" href="/target/v{v}/products?q=electronics">Electronics</a><a class="btn secondary" href="/target/v{v}/products?q=jackets">Jackets</a><a class="btn secondary" href="/target/v{v}/products?q=sneakers">Sneakers</a><a class="btn secondary" href="/target/v{v}/products?q=hoodies">Hoodies</a></div><h2>Featured</h2><div class="grid">{cards}</div>'''.format(v=v,cards=''.join([f'<div class="card"><h3>{p["name"]}</h3><p class="price">${p["price"]}</p><p class="muted">{p["desc"]}</p><a class="btn" href="/target/v{v}/product/{p["id"]}">View Product</a></div>' for p in PRODUCTS[:3]]))
    return layout(v,body)

@router.get('/target/v{version}/products')
async def products(version:int,q:str=''):
    v=2 if version==2 else 1
    ql=q.lower().strip()
    # Black-box demo search: treat a multi-word query as a set of product
    # constraints instead of requiring the whole phrase to appear literally
    # in one field. This makes natural queries such as "blue running shoes"
    # match the real catalog items while keeping impossible combinations
    # (for example "red running shoes") empty.
    stop={'find','under','below','less','than','the','a','an','and','with','for'}
    tokens=[t for t in ql.replace('-',' ').split() if t not in stop]
    def matches(p):
        hay=' '.join([p['name'].lower(),p['category'].lower(),p['color'].lower(),p['desc'].lower()])
        if not tokens:
            return True
        return all(t in hay for t in tokens)
    items=[p for p in PRODUCTS if matches(p)]
    cards=''.join([f'<div class="card"><span class="badge">{p["color"]}</span><h3>{p["name"]}</h3><p class="price">${p["price"]}</p><p>Stock: {p["stock"]}</p><a class="btn" href="/target/v{v}/product/{p["id"]}">View Product</a></div>' for p in items])
    if not items: cards='<div class="error"><b>No products found</b><p>No product matches the requested criteria. Try another search.</p><a class="btn secondary" href="/target/v%d/products">Reset search</a></div>'%v
    body=f'<section class="hero"><h1>Products</h1><p class="muted">Search results for: {q or "all products"}</p><a class="btn secondary" href="/target/v{v}">Back Home</a></section><div class="grid">{cards}</div>'
    return layout(v,body)

@router.get('/target/v{version}/product/{pid}')
async def product(version:int,pid:str):
    v=2 if version==2 else 1
    p=next((x for x in PRODUCTS if x['id']==pid),None)
    if not p:return layout(v,'<div class="error">Product not found.</div>')
    body=f'''<div class="box"><span class="badge">{p['color']}</span><h1>{p['name']}</h1><p>{p['desc']}</p><p class="price">${p['price']}</p><p>Stock available: {p['stock']}</p><button onclick="add('{p['id']}')">Add to Cart</button> <a class="btn secondary" href="/target/v{v}/products">Continue Shopping</a><p id="msg" class="success"></p></div>'''
    return layout(v,body)

@router.get('/target/v{version}/cart')
async def cart(version:int):
    v=2 if version==2 else 1
    # V2 changes the demo UI: checkout remains present but is visually occluded by an overlay.
    checkout=f'''<div class="checkout-wrap"><a id="guest-checkout" class="btn" href="/target/v{v}/checkout">Guest Checkout</a>{'<div class="occluder" aria-hidden="true"></div>' if v==2 else ''}</div>'''
    body=f'''<div class="hero"><h1>Your Cart</h1><div id="cartitems"></div><h3>Total: <span id="total">$0</span></h3>{checkout}<p class="muted">Guest checkout is a mock flow for testing.</p></div>'''
    return layout(v,body)

@router.get('/target/v{version}/checkout')
async def checkout(version:int):
    v=2 if version==2 else 1
    body=f'''<div class="box"><h1>Guest Checkout</h1><label>Full name<input aria-label="Full name" id="name"></label><label>Email<input aria-label="Email" id="email"></label><label>Delivery address<input aria-label="Delivery address" id="address"></label><a id="continue-payment" class="btn" href="/target/v{v}/checkout/payment">Continue to payment</a></div>'''
    return layout(v,body)

@router.get('/target/v{version}/checkout/payment')
async def payment(version:int):
    v=2 if version==2 else 1
    body=f'''<div class="box"><h1>Payment</h1><label>Card number<input aria-label="Card number" value=""></label><label>CVV<input aria-label="CVV" value=""></label><a class="btn" href="/target/v{v}/checkout/success">Place order</a></div>'''
    return layout(v,body)

@router.get('/target/v{version}/checkout/success')
async def success(version:int):
    v=2 if version==2 else 1
    return layout(v,'<div class="success"><h1>Order Confirmed</h1><p>Your mock order has been placed successfully.</p></div>','Confirmation')
