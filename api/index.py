from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import json
import httpx
import asyncio
import time
from datetime import datetime

# Configuration
BASE_URL = "https://net20.cc"
NEW_URL = "https://net51.cc"
COOKIE_CACHE = {}
COOKIE_EXPIRY = 15 * 60 * 60

PROVIDERS = {
    "netflix": {
        "ott": "nf",
        "poster_base": "https://imgcdn.kim/poster/v",
        "episode_poster": "https://imgcdn.kim/epimg/150",
        "search_endpoint": "/search.php",
        "post_endpoint": "/post.php",
        "playlist_endpoint": "/tv/playlist.php",
        "user_token": "233123f803cf02184bf6c67e149cdd50"
    },
    "primevideo": {
        "ott": "pv",
        "poster_base": "https://wsrv.nl/?url=https://imgcdn.kim/pv/v",
        "episode_poster": "https://imgcdn.kim/pvepimg/150",
        "search_endpoint": "/pv/search.php",
        "post_endpoint": "/pv/post.php",
        "playlist_endpoint": "/pv/playlist.php"
    },
    "hotstar": {
        "ott": "hs",
        "poster_base": "https://imgcdn.kim/hs/v",
        "episode_poster": "https://imgcdn.kim/hsepimg/150",
        "search_endpoint": "/mobile/hs/search.php",
        "post_endpoint": "/mobile/hs/post.php",
        "playlist_endpoint": "/mobile/hs/playlist.php"
    },
    "disneyplus": {
        "ott": "dp",
        "poster_base": "https://imgcdn.kim/hs/v",
        "episode_poster": "https://imgcdn.kim/hsepimg/150",
        "search_endpoint": "/mobile/hs/search.php",
        "post_endpoint": "/mobile/hs/post.php",
        "playlist_endpoint": "/mobile/hs/playlist.php"
    }
}


async def get_bypass_cookie():
    """Get bypass cookie with caching"""
    current_time = time.time()
    
    if "cookie" in COOKIE_CACHE and "timestamp" in COOKIE_CACHE:
        if current_time - COOKIE_CACHE["timestamp"] < COOKIE_EXPIRY:
            return COOKIE_CACHE["cookie"]
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        for attempt in range(5):
            try:
                response = await client.post(f"{BASE_URL}/tv/p.php")
                data = response.json()
                
                if data.get("r") == "n":
                    cookie = response.cookies.get("t_hash_t", "")
                    if cookie:
                        COOKIE_CACHE["cookie"] = cookie
                        COOKIE_CACHE["timestamp"] = current_time
                        return cookie
                
                await asyncio.sleep(1)
            except Exception:
                if attempt == 4:
                    raise Exception("Failed to get bypass cookie")
                await asyncio.sleep(2)
    
    raise Exception("Failed to obtain bypass cookie")


def get_unix_time():
    return int(time.time() * 1000)


async def handle_search(provider, query):
    """Handle search request"""
    if provider not in PROVIDERS:
        return {"error": f"Invalid provider: {provider}"}, 400
    
    config = PROVIDERS[provider]
    cookie = await get_bypass_cookie()
    
    cookies = {"t_hash_t": cookie, "hd": "on", "ott": config["ott"]}
    if provider == "netflix":
        cookies["user_token"] = config["user_token"]
    
    headers = {"X-Requested-With": "XMLHttpRequest", "Referer": f"{BASE_URL}/home"}
    url = f"{BASE_URL}{config['search_endpoint']}?s={query}&t={get_unix_time()}"
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url, headers=headers, cookies=cookies)
        data = response.json()
        
        results = []
        for item in data.get("searchResult", []):
            poster = f"{config['poster_base']}/{item['id']}.jpg"
            if provider == "primevideo":
                poster += "&w=500"
            
            results.append({
                "id": item["id"],
                "title": item["t"],
                "provider": provider,
                "poster_url": poster
            })
        
        return {"provider": provider, "query": query, "results": results, "count": len(results)}, 200


async def handle_details(provider, content_id):
    """Handle details request"""
    if provider not in PROVIDERS:
        return {"error": f"Invalid provider: {provider}"}, 400
    
    config = PROVIDERS[provider]
    cookie = await get_bypass_cookie()
    
    cookies = {"t_hash_t": cookie, "hd": "on", "ott": config["ott"]}
    if provider == "netflix":
        cookies["user_token"] = config["user_token"]
    
    headers = {"X-Requested-With": "XMLHttpRequest", "Referer": f"{BASE_URL}/home"}
    url = f"{BASE_URL}{config['post_endpoint']}?id={content_id}&t={get_unix_time()}"
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url, headers=headers, cookies=cookies)
        data = response.json()
        
        episodes = []
        if data.get("episodes") and data["episodes"][0]:
            for ep in data["episodes"]:
                if ep:
                    episodes.append({
                        "id": ep["id"],
                        "title": ep["t"],
                        "episode": int(ep["ep"].replace("E", "")) if ep.get("ep") else None,
                        "season": int(ep["s"].replace("S", "")) if ep.get("s") else None,
                        "poster_url": f"{config['episode_poster']}/{ep['id']}.jpg"
                    })
        
        cast = [n.strip() for n in data.get("cast", "").split(",")] if data.get("cast") else []
        genres = [g.strip() for g in data.get("genre", "").split(",") if g.strip()]
        
        poster = f"{config['poster_base']}/{content_id}.jpg"
        if provider == "primevideo":
            poster += "&w=500"
        
        result = {
            "id": content_id,
            "title": data["title"],
            "description": data.get("desc"),
            "year": data.get("year"),
            "type": "movie" if not episodes else "series",
            "poster_url": poster,
            "genres": genres,
            "cast": cast,
            "rating": data.get("match", "").replace("IMDb ", ""),
            "provider": provider,
            "episodes": episodes,
            "total_episodes": len(episodes)
        }
        
        return result, 200


async def handle_stream(provider, content_id, title):
    """Handle stream request"""
    if provider not in PROVIDERS:
        return {"error": f"Invalid provider: {provider}"}, 400
    
    config = PROVIDERS[provider]
    cookie = await get_bypass_cookie()
    
    cookies = {"t_hash_t": cookie, "hd": "on", "ott": config["ott"]}
    if provider == "netflix":
        cookies["user_token"] = config["user_token"]
    
    headers = {"X-Requested-With": "XMLHttpRequest", "Referer": f"{BASE_URL}/home"}
    url = f"{NEW_URL}{config['playlist_endpoint']}?id={content_id}&t={title}&tm={get_unix_time()}"
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url, headers=headers, cookies=cookies)
        playlist = response.json()
        
        streams = []
        subtitles = []
        
        for item in playlist:
            for source in item.get("sources", []):
                file_url = source["file"]
                if provider in ["netflix", "primevideo"]:
                    file_url = file_url.replace("/tv/", "/")
                
                stream_url = f"{NEW_URL}/{file_url}" if not file_url.startswith("http") else file_url
                quality = file_url.split("q=")[1].split("&")[0] if "q=" in file_url else "HD"
                
                streams.append({
                    "url": stream_url,
                    "quality": source.get("label", quality),
                    "type": source.get("type", "m3u8"),
                    "headers": {"Referer": f"{NEW_URL}/home", "Cookie": "hd=on"}
                })
            
            for track in item.get("tracks", []):
                if track.get("kind") == "captions":
                    sub_url = track.get("file", "")
                    if sub_url and not sub_url.startswith("http"):
                        sub_url = f"https:{sub_url}" if sub_url.startswith("//") else sub_url
                    
                    subtitles.append({
                        "language": track.get("label", "Unknown"),
                        "url": sub_url
                    })
        
        result = {
            "id": content_id,
            "title": title,
            "provider": provider,
            "streams": streams,
            "subtitles": subtitles,
            "timestamp": datetime.now().isoformat()
        }
        
        return result, 200


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        """Handle GET requests"""
        try:
            # Parse URL
            parsed = urlparse(self.path)
            path = parsed.path
            params = parse_qs(parsed.query)
            
            # CORS headers
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
            self.send_header('Access-Control-Allow-Headers', '*')
            self.end_headers()
            
            # Route handling
            if path == '/' or path == '':
                response = {
                    "name": "NetMirror Stream API",
                    "version": "1.0.0",
                    "providers": list(PROVIDERS.keys()),
                    "endpoints": {
                        "search": "/api/{provider}/search?query={query}",
                        "details": "/api/{provider}/details?id={id}",
                        "stream": "/api/{provider}/stream?id={id}&title={title}",
                        "health": "/health"
                    }
                }
                self.wfile.write(json.dumps(response).encode())
                
            elif path == '/health':
                response = {"status": "healthy", "timestamp": datetime.now().isoformat()}
                self.wfile.write(json.dumps(response).encode())
                
            elif path.startswith('/api/'):
                parts = path.split('/')
                
                if len(parts) >= 4:
                    provider = parts[2]
                    action = parts[3]
                    
                    if action == 'search':
                        query = params.get('query', [''])[0]
                        if not query:
                            self.wfile.write(json.dumps({"error": "Query parameter required"}).encode())
                            return
                        
                        result, status = asyncio.run(handle_search(provider, query))
                        self.wfile.write(json.dumps(result).encode())
                        
                    elif action == 'details':
                        content_id = params.get('id', [''])[0]
                        if not content_id:
                            self.wfile.write(json.dumps({"error": "ID parameter required"}).encode())
                            return
                        
                        result, status = asyncio.run(handle_details(provider, content_id))
                        self.wfile.write(json.dumps(result).encode())
                        
                    elif action == 'stream':
                        content_id = params.get('id', [''])[0]
                        title = params.get('title', [''])[0]
                        if not content_id:
                            self.wfile.write(json.dumps({"error": "ID parameter required"}).encode())
                            return
                        
                        result, status = asyncio.run(handle_stream(provider, content_id, title))
                        self.wfile.write(json.dumps(result).encode())
                        
                    else:
                        self.wfile.write(json.dumps({"error": "Invalid action"}).encode())
                else:
                    self.wfile.write(json.dumps({"error": "Invalid path"}).encode())
            else:
                self.wfile.write(json.dumps({"error": "Not found"}).encode())
                
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())
    
    def do_OPTIONS(self):
        """Handle OPTIONS for CORS"""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', '*')
        self.end_headers()
