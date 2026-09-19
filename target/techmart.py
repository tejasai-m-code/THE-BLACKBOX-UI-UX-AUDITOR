import json
from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()

PRODUCTS = [
    {'id':'wired-earphones','name':'Wired Earphones','color':'black','category':'audio','price':29,'stock':15,'desc':'Wired in-ear earphones with microphone.'},
    {'id':'wireless-headphones','name':'Wireless Headphones','color':'black','category':'audio','price':69,'stock':10,'desc':'Wireless over-ear headphones.'},
    {'id':'gaming-mouse','name':'RGB Gaming Mouse','color':'black','category':'accessories','price':39,'stock':12,'desc':'Lightweight wired gaming mouse.'},
    {'id':'mechanical-keyboard','name':'Mechanical Keyboard','color':'white','category':'accessories','price':79,'stock':8,'desc':'Compact mechanical keyboard.'},
    {'id':'usb-c-cable','name':'USB-C Fast Charging Cable','color':'white','category':'accessories','price':19,'stock':20,'desc':'Durable USB-C charging cable.'},
    {'id':'red-earbuds','name':'Red Wireless Earbuds','color':'red','category':'audio','price':59,'stock':6,'desc':'Compact wireless earbuds.'},
    {'id':'yellow-jacket','name':'Yellow Jacket','color':'yellow','category':'wearables','price':74,'stock':5,'desc':'Lightweight yellow utility jacket.'},
    {'id':'black-jacket','name':'Black Jacket','color':'black','category':'wearables','price':64,'stock':0,'desc':'Black utility jacket, currently out of stock.'},
    {'id':'blue-backpack','name':'Blue Tech Backpack','color':'blue','category':'accessories','price':49,'stock':7,'desc':'Compact laptop backpack.'},
    {'id':'silver-usb-hub','name':'Silver USB Hub','color':'silver','category':'accessories','price':35,'stock':9,'desc':'Four-port USB hub.'},
    {'id':'green-desk-lamp','name':'Green Desk Lamp','color':'green','category':'accessories','price':45,'stock':4,'desc':'Adjustable LED desk lamp.'},
    {'id':'white-headset','name':'White Gaming Headset','color':'white','category':'audio','price':72,'stock':6,'desc':'Closed-back gaming headset.'},
]


def css(v):
    # See target/app.py for why this is anchored top-left rather than right/bottom.
    overlay = '' if v == 1 else '.checkout-wrap{position:relative;display:inline-block}.occluder{position:absolute;left:0;top:0;width:180px;height:48px;background:rgba(10,16,30,.84);z-index:20;border-radius:12px;pointer-events:auto}'
    return f'''<style>
*{{box-sizing:border-box}}body{{margin:0;font-family:Inter,Arial,sans-serif;background:#f4f7fb;color:#172033}}header{{background:#0f172a;color:#fff;padding:18px 7%;display:flex;justify-content:space-between;align-items:center}}header a{{color:#cbd5e1;text-decoration:none;margin-left:18px}}main{{max-width:1050px;margin:30px auto;padding:0 20px}}.hero,.card,.box{{background:#fff;border:1px solid #dbe3ef;border-radius:18px;padding:22px;box-shadow:0 8px 25px #1111}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:16px;margin-top:20px}}.price{{font-size:22px;font-weight:800}}button,a.btn{{border:0;border-radius:10px;padding:11px 15px;background:#2563eb;color:white;cursor:pointer;text-decoration:none;display:inline-block}}a.secondary{{background:#e2e8f0;color:#172033}}input{{padding:12px;border:1px solid #cbd5e1;border-radius:10px;width:100%;margin:6px 0 12px}}.muted{{color:#64748b}}.badge{{display:inline-block;padding:4px 8px;border-radius:999px;background:#eff6ff;color:#1d4ed8;font-size:12px}}.error{{background:#fee2e2;color:#991b1b;padding:14px;border-radius:12px}}.success{{background:#dcfce7;color:#166534;padding:14px;border-radius:12px}}.checkout-wrap{{margin-top:20px}}{overlay}</style>'''


def layout(v, body):
    products_json=json.dumps({p['id']:p for p in PRODUCTS})
    return HTMLResponse(f'''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>TechMart</title>{css(v)}</head><body><header><b>💻 TechMart <span class="badge">V{v}</span></b><nav><a href="/target/tech/v{v}">Home</a><a href="/target/tech/v{v}/products">Products</a><a href="/target/tech/v{v}/cart">Cart</a></nav></header><main>{body}</main><script>
const PRODUCTS={products_json};const CART_KEY='techmart_cart';
function add(id){{let c=JSON.parse(localStorage.getItem(CART_KEY)||'[]');let p=c.find(x=>x.id===id);if(p)p.qty++;else c.push({{id,qty:1}});localStorage.setItem(CART_KEY,JSON.stringify(c));let m=document.getElementById('msg');if(m)m.textContent='Added to cart';}}
function renderCart(){{let c=JSON.parse(localStorage.getItem(CART_KEY)||'[]');let total=0;let box=document.getElementById('cartitems');if(!box)return;box.innerHTML='';c.forEach(x=>{{let p=PRODUCTS[x.id];if(!p)return;total+=p.price*x.qty;box.innerHTML+=`<div class="card"><b>${{p.name}}</b><p>${{x.qty}} × ${{p.price}}</p></div>`}});let t=document.getElementById('total');if(t)t.textContent='$'+total;if(c.length===0)box.innerHTML='<div class="muted">Your cart is empty.</div>';}}
if(document.getElementById('cartitems'))renderCart();</script></body></html>''')

@router.get('/target/tech/v{version}')
async def home(version:int):
    v=2 if version==2 else 1
    cards=''.join([f'<div class="card"><h3>{p["name"]}</h3><p class="price">${p["price"]}</p><p class="muted">{p["desc"]}</p><a class="btn" href="/target/tech/v{v}/product/{p["id"]}">View Product</a></div>' for p in PRODUCTS[:4]])
    body=f'''<section class="hero"><h1>TechMart</h1><p>Black-box technology shopping demo for autonomous UI auditing.</p><form action="/target/tech/v{v}/products" method="get"><input name="q" placeholder="Search products" aria-label="Search products"><button>Search</button></form></section><h2>Categories</h2><div class="grid"><a class="btn" href="/target/tech/v{v}/products?q=audio">Audio</a><a class="btn secondary" href="/target/tech/v{v}/products?q=accessories">Accessories</a><a class="btn secondary" href="/target/tech/v{v}/products?q=wearables">Wearables</a></div><h2>Featured</h2><div class="grid">{cards}</div>'''
    return layout(v,body)

@router.get('/target/tech/v{version}/products')
async def products(version:int,q:str=''):
    v=2 if version==2 else 1; ql=q.lower().strip(); stop={'find','under','below','less','than','the','a','an','and','with','for'}
    tokens=[t for t in ql.replace('-',' ').split() if t not in stop]
    def matches(p):
        hay=' '.join([p['name'].lower(),p['category'].lower(),p['color'].lower(),p['desc'].lower()]);return not tokens or all(t in hay for t in tokens)
    items=[p for p in PRODUCTS if matches(p)]
    cards=''.join([f'<div class="card"><span class="badge">{p["category"]}</span><h3>{p["name"]}</h3><p class="price">${p["price"]}</p><p>Stock: {p["stock"]}</p><a class="btn" href="/target/tech/v{v}/product/{p["id"]}">View Product</a></div>' for p in items])
    if not items: cards=f'<div class="error"><b>No products found</b><p>No product matches the requested criteria.</p><a class="btn secondary" href="/target/tech/v{v}/products">Reset search</a></div>'
    body=f'<section class="hero"><h1>Products</h1><p class="muted">Search results for: {q or "all products"}</p><a class="btn secondary" href="/target/tech/v{v}">Back Home</a></section><div class="grid">{cards}</div>'
    return layout(v,body)

@router.get('/target/tech/v{version}/product/{pid}')
async def product(version:int,pid:str):
    v=2 if version==2 else 1;p=next((x for x in PRODUCTS if x['id']==pid),None)
    if not p:return layout(v,'<div class="error">Product not found.</div>')
    body=f'''<div class="box"><span class="badge">{p['category']}</span><h1>{p['name']}</h1><p>{p['desc']}</p><p class="price">${p['price']}</p><p>Stock available: {p['stock']}</p><button onclick="add('{p['id']}')">Add to Cart</button> <a class="btn secondary" href="/target/tech/v{v}/products">Continue Shopping</a><p id="msg" class="success"></p></div>'''
    return layout(v,body)

@router.get('/target/tech/v{version}/cart')
async def cart(version:int):
    v=2 if version==2 else 1
    checkout=f'''<div class="checkout-wrap"><a id="guest-checkout" class="btn" href="/target/tech/v{v}/checkout">Guest Checkout</a>{'<div class="occluder" aria-hidden="true"></div>' if v==2 else ''}</div>'''
    body=f'''<div class="hero"><h1>Your Cart</h1><div id="cartitems"></div><h3>Total: <span id="total">$0</span></h3>{checkout}<p class="muted">Guest checkout is a mock flow for testing.</p></div>'''
    return layout(v,body)

@router.get('/target/tech/v{version}/checkout')
async def checkout(version:int):
    v=2 if version==2 else 1
    body=f'''<div class="box"><h1>Guest Checkout</h1><label>Full name<input aria-label="Full name" id="name"></label><label>Email<input aria-label="Email" id="email"></label><label>Delivery address<input aria-label="Delivery address" id="address"></label><a id="continue-payment" class="btn" href="/target/tech/v{v}/checkout/payment">Continue to payment</a></div>'''
    return layout(v,body)

@router.get('/target/tech/v{version}/checkout/payment')
async def payment(version:int):
    v=2 if version==2 else 1
    body=f'''<div class="box"><h1>Payment</h1><label>Card number<input aria-label="Card number" value=""></label><label>CVV<input aria-label="CVV" value=""></label><a class="btn" href="/target/tech/v{v}/checkout/success">Place order</a></div>'''
    return layout(v,body)

@router.get('/target/tech/v{version}/checkout/success')
async def success(version:int):
    v=2 if version==2 else 1
    return layout(v,'<div class="success"><h1>Order Confirmed</h1><p>Your TechMart mock order has been placed successfully.</p></div>')
