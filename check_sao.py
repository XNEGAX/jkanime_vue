import cloudscraper

scraper = cloudscraper.create_scraper()
url = "https://xo247l.cloudatacdn.com/u5kj7ugsdlplsdgge6u3ciqbkdpzinzuignofwvnhedwvkwkr6tvhlmmxo5a/jja8abvcua~"
print(f"Probando descarga desde cloudatacdn...")
resp = scraper.get(url, stream=True, timeout=30)
print(f"Status: {resp.status_code}")
print(f"Content-Type: {resp.headers.get('content-type')}")
print(f"Content-Length: {resp.headers.get('content-length')}")

ct = resp.headers.get('content-type', '')
if 'video' in ct or 'octet' in ct:
    print("OK: Video detectado!")
    chunk = next(resp.iter_content(4096))
    print(f"Primer chunk: {len(chunk)} bytes")
    print(f"Header bytes: {chunk[:20].hex()}")
elif 'text/html' in ct:
    print("HTML devuelto")
    print(resp.text[:500])
else:
    print(f"Content-Type inesperado: {ct}")
    chunk = next(resp.iter_content(4096))
    print(f"First bytes: {chunk[:50]}")
