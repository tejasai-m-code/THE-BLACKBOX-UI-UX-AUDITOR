from fastapi.testclient import TestClient
from app.main import app, classify_catalog, site_config, normalize_checkpoint

client = TestClient(app)

def test_shop_routes():
    assert client.get('/target/v1').status_code == 200
    assert client.get('/target/v2').status_code == 200

def test_tech_routes():
    assert client.get('/target/tech/v1').status_code == 200
    assert client.get('/target/tech/v2').status_code == 200

def test_exact_outcomes():
    pool=site_config('shopeasy')['products']
    assert classify_catalog('Find yellow jacket under $100 and add to cart.',pool)[0]=='AVAILABLE'
    assert classify_catalog('Find black jacket under $100 and add to cart.',pool)[0]=='OUT_OF_STOCK'
    assert classify_catalog('Find purple jacket under $100 and add to cart.',pool)[0]=='UNAVAILABLE'

def test_v1_v2_checkpoint_normalization():
    a=normalize_checkpoint('http://127.0.0.1:8000/target/v1/products?q=blue')
    b=normalize_checkpoint('http://127.0.0.1:8000/target/v2/products?q=blue')
    assert a==b
