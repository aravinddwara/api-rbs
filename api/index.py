from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import json
import httpx
import asyncio
import time
from datetime import datetime
import hashlib

# Configuration
BASE_DOMAIN = "net20.cc"
STREAM_DOMAIN = "net51.cc"
BASE_URL = f"https://{BASE_DOMAIN}"
STREAM_URL = f"https://{STREAM_DOMAIN}"

# Global cookie cache
COOKIE_CACHE = {
    "cookie": None,
    "timestamp": 0,
    "expiry": 15 * 60 * 60  # 15 hours
}

# Provider configurations
PROVIDERS = {
    "netflix": {
        "id": "nf",
        "name": "Netflix",
        "search_path": "/search.php",
        "details_path": "/post.php",
        "stream_path": "/tv/playlist.php",
        "episodes_path": "/episodes.php",
        "poster_base": "https://imgcdn.kim/poster/v",
        "episode_poster": "https://imgcdn.kim/epimg/150",
        "user_token": "233123f803cf02184bf6c67e149cdd50",
        "requires_token": True
    },
    "primevideo": {
        "id": "pv",
        "name": "Prime Video",
        "search_path": "/pv/search.php",
        "details_path": "/pv/post.php",
        "stream_path": "/pv/playlist.php",
        "episodes_path": "/pv/episodes.php",
        "poster_base": "https://imgcdn.kim/pv/v",
        "episode_poster": "https://imgcdn.kim/pvepimg/150",
        "requires_token": False
    },
    "hotstar": {
        "id": "hs",
        "name": "Hotstar",
        "search_path": "/mobile/hs/search.php",
        "details_path": "/mobile/hs/post.php",
        "stream_path": "/mobile/hs/playlist.php",
        "episodes_path": "/mobile/hs/episodes.php",
        "poster_base": "https://imgcdn.kim/hs/v",
        "episode_poster": "https://imgcdn.kim/hsepimg/150",
        "requires_token": False
    },
    "disneyplus": {
        "id": "dp",
        "name": "Disney+",
        "search_path": "/mobile/hs/search.php",
        "details_path": "/mobile/hs/post.php",
        "stream_path": "/mobile/hs/playlist.php",
        "episodes_path": "/mobile/hs/episodes.php",
        "poster_base": "https://imgcdn.kim/hs/v",
        "episode_poster": "https://imgcdn.kim/hsepimg/150",
        "requires_token": False
    }
}


def get_timestamp():
    """Get current Unix timestamp in milliseconds"""
    return int(time.time() * 1000)


def get_headers(provider_id=None):
    """Get standard headers for requests"""
    return {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Language": "en-US,en;q=0.9",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": f"{BASE_URL}/home",
        "Origin": BASE_URL,
    }


def get_cookies(provider_id, bypass_cookie=None):
    """Get cookies for a specific provider"""
    cookies = {
        "hd": "on",
        "ott": provider_id
    }
    
    if bypass_cookie:
        cookies["t_hash_t"] = bypass_cookie
    
    # Add user token for Netflix
    if provider_id == "nf":
        cookies["user_token"] = PROVIDERS["netflix"]["user_token"]
    
    return cookies


async def get_bypass_cookie(force_refresh=False):
    """
    Obtain bypass cookie from the service
    Uses multiple strategies and caching
    """
    current_time = time.time()
    
    # Return cached cookie if valid
    if not force_refresh and COOKIE_CACHE["cookie"]:
        if current_time - COOKIE_CACHE["timestamp"] < COOKIE_CACHE["expiry"]:
            return COOKIE_CACHE["cookie"]
    
    # URLs to try for cookie
    endpoints = [
        f"{BASE_URL}/tv/p.php",
        f"{STREAM_URL}/tv/p.php",
        f"{BASE_URL}/p.php",
        f"{STREAM_URL}/p.php"
    ]
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": f"{BASE_URL}/home",
        "Origin": BASE_URL
    }
    
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        for endpoint in endpoints:
            for method in ["POST", "GET"]:
                try:
                    if method == "POST":
                        response = await client.post(endpoint, headers=headers)
                    else:
                        response = await client.get(endpoint, headers=headers)
                    
                    # Check for cookie
                    cookie = response.cookies.get("t_hash_t")
                    if cookie:
                        COOKIE_CACHE["cookie"] = cookie
                        COOKIE_CACHE["timestamp"] = current_time
                        return cookie
                    
                    # Check response for verification
                    try:
                        data = response.json()
                        if data.get("r") == "n":
                            cookie = response.cookies.get("t_hash_t")
                            if cookie:
                                COOKIE_CACHE["cookie"] = cookie
                                COOKIE_CACHE["timestamp"] = current_time
                                return cookie
                    except:
                        pass
                    
                    await asyncio.sleep(0.5)
                    
                except Exception as e:
                    continue
    
    # Return cached even if expired as fallback
    if COOKIE_CACHE["cookie"]:
        return COOKIE_CACHE["cookie"]
    
    # Generate a fallback cookie
    fallback = f"fallback_{hashlib.md5(str(current_time).encode()).hexdigest()[:16]}"
    COOKIE_CACHE["cookie"] = fallback
    COOKIE_CACHE["timestamp"] = current_time
    return fallback


async def make_request(url, provider_id, bypass_cookie):
    """Make a request to the streaming service"""
    headers = get_headers(provider_id)
    cookies = get_cookies(provider_id, bypass_cookie)
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url, headers=headers, cookies=cookies)
        
        if not response.text or not response.text.strip():
            raise ValueError("Empty response from server")
        
        try:
            return response.json()
        except json.JSONDecodeError:
            raise ValueError(f"Invalid JSON response: {response.text[:200]}")


async def search_content(provider, query):
    """Search for content on a specific provider"""
    if provider not in PROVIDERS:
        return {"error": f"Invalid provider: {provider}"}, 400
    
    config = PROVIDERS[provider]
    bypass_cookie = await get_bypass_cookie()
    
    url = f"{BASE_URL}{config['search_path']}?s={query}&t={get_timestamp()}"
    
    try:
        data = await make_request(url, config["id"], bypass_cookie)
        
        results = []
        for item in data.get("searchResult", []):
            results.append({
                "id": item["id"],
                "title": item["t"],
                "provider": provider,
                "poster_url": f"{config['poster_base']}/{item['id']}.jpg"
            })
        
        return {
            "provider": provider,
            "query": query,
            "results": results,
            "count": len(results)
        }, 200
        
    except Exception as e:
        return {"error": str(e), "provider": provider}, 500


async def get_details(provider, content_id):
    """Get detailed information about content"""
    if provider not in PROVIDERS:
        return {"error": f"Invalid provider: {provider}"}, 400
    
    config = PROVIDERS[provider]
    bypass_cookie = await get_bypass_cookie()
    
    url = f"{BASE_URL}{config['details_path']}?id={content_id}&t={get_timestamp()}"
    
    try:
        data = await make_request(url, config["id"], bypass_cookie)
        
        # Parse episodes
        episodes = []
        if data.get("episodes") and data["episodes"][0]:
            for ep in data["episodes"]:
                if ep:
                    episodes.append({
                        "id": ep["id"],
                        "title": ep.get("t", ""),
                        "episode": int(ep.get("ep", "E0").replace("E", "")) if ep.get("ep") else None,
                        "season": int(ep.get("s", "S0").replace("S", "")) if ep.get("s") else None,
                        "poster_url": f"{config['episode_poster']}/{ep['id']}.jpg"
                    })
        
        # Parse cast and genres
        cast = [n.strip() for n in data.get("cast", "").split(",")] if data.get("cast") else []
        genres = [g.strip() for g in data.get("genre", "").split(",") if g.strip()]
        
        return {
            "id": content_id,
            "title": data.get("title", "Unknown"),
            "description": data.get("desc"),
            "year": data.get("year"),
            "type": "movie" if not episodes else "series",
            "poster_url": f"{config['poster_base']}/{content_id}.jpg",
            "genres": genres,
            "cast": cast,
            "rating": data.get("match", "").replace("IMDb ", ""),
            "provider": provider,
            "episodes": episodes,
            "total_episodes": len(episodes)
        }, 200
        
    except Exception as e:
        return {"error": str(e), "provider": provider}, 500


async def get_stream(provider, content_id, title=""):
    """Extract streaming URLs for content"""
    if provider not in PROVIDERS:
        return {"error": f"Invalid provider: {provider}"}, 400
    
    config = PROVIDERS[provider]
    bypass_cookie = await get_bypass_cookie()
    
    # Build URL
    url = f"{STREAM_URL}{config['stream_path']}?id={content_id}&t={title}&tm={get_timestamp()}"
    
    try:
        data = await make_request(url, config["id"], bypass_cookie)
        
        streams = []
        subtitles = []
        
        # Handle array response
        if isinstance(data, list):
            playlist = data
        else:
            playlist = [data]
        
        for item in playlist:
            # Extract streams
            for source in item.get("sources", []):
                file_url = source.get("file", "")
                
                # Clean up URL
                if provider in ["netflix", "primevideo"]:
                    file_url = file_url.replace("/tv/", "/")
                
                # Build full URL
                if not file_url.startswith("http"):
                    stream_url = f"{STREAM_URL}/{file_url.lstrip('/')}"
                else:
                    stream_url = file_url
                
                # Extract quality
                quality = "HD"
                if "q=" in file_url:
                    quality = file_url.split("q=")[1].split("&")[0]
                
                streams.append({
                    "url": stream_url,
                    "quality": source.get("label", quality),
                    "type": source.get("type", "m3u8"),
                    "headers": {
                        "Referer": f"{STREAM_URL}/home",
                        "Cookie": "hd=on",
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                    }
                })
            
            # Extract subtitles
            for track in item.get("tracks", []):
                if track.get("kind") == "captions":
                    sub_url = track.get("file", "")
                    if sub_url:
                        if sub_url.startswith("//"):
                            sub_url = f"https:{sub_url}"
                        elif not sub_url.startswith("http"):
                            sub_url = f"{STREAM_URL}/{sub_url.lstrip('/')}"
                        
                        subtitles.append({
                            "language": track.get("label", "Unknown"),
                            "url": sub_url
                        })
        
        return {
            "id": content_id,
            "title": title,
            "provider": provider,
            "streams": streams,
            "subtitles": subtitles,
            "timestamp": datetime.now().isoformat(),
            "total_streams": len(streams)
        }, 200
        
    except Exception as e:
        return {"error": str(e), "provider": provider}, 500


async def search_all_providers(query):
    """Search across all providers concurrently"""
    tasks = [search_content(provider, query) for provider in PROVIDERS.keys()]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    all_results = []
    errors = []
    
    for i, result in enumerate(results):
        provider = list(PROVIDERS.keys())[i]
        
        if isinstance(result, Exception):
            errors.append({"provider": provider, "error": str(result)})
        elif isinstance(result, tuple):
            data, status = result
            if status == 200:
                all_results.extend(data.get("results", []))
            else:
                errors.append({"provider": provider, "error": data.get("error", "Unknown")})
    
    return {
        "query": query,
        "results": all_results,
        "total": len(all_results),
        "providers_searched": len(PROVIDERS),
        "errors": errors if errors else None
    }, 200


class handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        """Suppress default logging"""
        pass
    
    def send_json_response(self, data, status=200):
        """Send JSON response with proper headers"""
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', '*')
        self.send_header('Access-Control-Max-Age', '86400')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))
    
    def do_OPTIONS(self):
        """Handle CORS preflight"""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', '*')
        self.send_header('Access-Control-Max-Age', '86400')
        self.end_headers()
    
    def do_GET(self):
        """Handle GET requests"""
        try:
            parsed = urlparse(self.path)
            path = parsed.path
            params = parse_qs(parsed.query)
            
            # Root endpoint
            if path in ['/', '']:
                response = {
                    "name": "Streaming Content API",
                    "version": "2.0.0",
                    "status": "online",
                    "providers": {k: v["name"] for k, v in PROVIDERS.items()},
                    "endpoints": {
                        "search_all": "/api/search?query={query}",
                        "search": "/api/{provider}/search?query={query}",
                        "details": "/api/{provider}/details?id={id}",
                        "stream": "/api/{provider}/stream?id={id}&title={title}",
                        "health": "/health"
                    }
                }
                self.send_json_response(response)
                return
            
            # Health check
            if path == '/health':
                response = {
                    "status": "healthy",
                    "timestamp": datetime.now().isoformat(),
                    "cookie_cached": COOKIE_CACHE["cookie"] is not None,
                    "cookie_age": int(time.time() - COOKIE_CACHE["timestamp"]) if COOKIE_CACHE["cookie"] else None
                }
                self.send_json_response(response)
                return
            
            # API endpoints
            if path.startswith('/api/'):
                parts = [p for p in path.split('/') if p]
                
                # Unified search
                if len(parts) == 2 and parts[1] == 'search':
                    query = params.get('query', [''])[0]
                    if not query:
                        self.send_json_response({"error": "Query parameter required"}, 400)
                        return
                    
                    result, status = asyncio.run(search_all_providers(query))
                    self.send_json_response(result, status)
                    return
                
                # Provider-specific endpoints
                if len(parts) >= 3:
                    provider = parts[1]
                    action = parts[2]
                    
                    if action == 'search':
                        query = params.get('query', [''])[0]
                        if not query:
                            self.send_json_response({"error": "Query parameter required"}, 400)
                            return
                        
                        result, status = asyncio.run(search_content(provider, query))
                        self.send_json_response(result, status)
                        return
                    
                    elif action == 'details':
                        content_id = params.get('id', [''])[0]
                        if not content_id:
                            self.send_json_response({"error": "ID parameter required"}, 400)
                            return
                        
                        result, status = asyncio.run(get_details(provider, content_id))
                        self.send_json_response(result, status)
                        return
                    
                    elif action == 'stream':
                        content_id = params.get('id', [''])[0]
                        title = params.get('title', [''])[0]
                        
                        if not content_id:
                            self.send_json_response({"error": "ID parameter required"}, 400)
                            return
                        
                        result, status = asyncio.run(get_stream(provider, content_id, title))
                        self.send_json_response(result, status)
                        return
            
            # 404
            self.send_json_response({"error": "Endpoint not found"}, 404)
            
        except Exception as e:
            self.send_json_response({
                "error": str(e),
                "type": type(e).__name__
            }, 500)
    
    def do_POST(self):
        """Handle POST requests"""
        self.do_GET()
