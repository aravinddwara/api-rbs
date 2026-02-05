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

# IMPORTANT: Check if net52.cc is the actual streaming domain
# The user mentioned net52.cc in their example
# Let's keep both for fallback
ALT_STREAM_DOMAIN = "net52.cc"
ALT_STREAM_URL = f"https://{ALT_STREAM_DOMAIN}"

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
    """Get standard headers for requests - matching CloudStream"""
    return {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Language": "en-US,en;q=0.9",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": f"{BASE_URL}/home",
        "Origin": BASE_URL,
    }


def get_cookies(provider_id, bypass_cookie=None):
    """Get cookies for a specific provider - matching CloudStream"""
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
    Obtain bypass cookie - exactly matching CloudStream's bypass() function
    """
    current_time = time.time()
    
    # Return cached cookie if valid (≤15 hours old)
    if not force_refresh and COOKIE_CACHE["cookie"]:
        if current_time - COOKIE_CACHE["timestamp"] < COOKIE_CACHE["expiry"]:
            return COOKIE_CACHE["cookie"]
    
    # CloudStream's bypass logic: POST to /tv/p.php until we get {"r":"n"}
    max_attempts = 10
    attempt = 0
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": f"{BASE_URL}/home",
        "Origin": BASE_URL,
        "X-Requested-With": "XMLHttpRequest"
    }
    
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        while attempt < max_attempts:
            try:
                # POST request to bypass endpoint
                response = await client.post(
                    f"{BASE_URL}/tv/p.php",
                    headers=headers,
                    cookies={"hd": "on"}
                )
                
                # Check if we got the right response
                try:
                    data = response.json()
                    if data.get("r") == "n":
                        # Success! Extract the cookie
                        cookie = response.cookies.get("t_hash_t")
                        if cookie:
                            COOKIE_CACHE["cookie"] = cookie
                            COOKIE_CACHE["timestamp"] = current_time
                            return cookie
                except:
                    pass
                
                # Also check cookies even if JSON parsing fails
                cookie = response.cookies.get("t_hash_t")
                if cookie:
                    COOKIE_CACHE["cookie"] = cookie
                    COOKIE_CACHE["timestamp"] = current_time
                    return cookie
                
                attempt += 1
                await asyncio.sleep(0.5)
                
            except Exception as e:
                attempt += 1
                await asyncio.sleep(0.5)
                continue
    
    # If we couldn't get a cookie, return cached one if available
    if COOKIE_CACHE["cookie"]:
        return COOKIE_CACHE["cookie"]
    
    raise ValueError("Failed to obtain bypass cookie after multiple attempts")


async def make_request(url, provider_id, bypass_cookie):
    """Make a request to the streaming service - matching CloudStream logic"""
    headers = get_headers(provider_id)
    cookies = get_cookies(provider_id, bypass_cookie)
    
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        response = await client.get(url, headers=headers, cookies=cookies)
        
        # Check for empty response
        if not response.text or not response.text.strip():
            raise ValueError("Empty response from server")
        
        # Parse JSON
        try:
            return response.json()
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON response: {response.text[:200]}")


async def search_content(provider, query):
    """Search for content on a specific provider"""
    if provider not in PROVIDERS:
        return {"error": f"Invalid provider: {provider}"}, 400
    
    config = PROVIDERS[provider]
    
    # Get fresh bypass cookie
    bypass_cookie = await get_bypass_cookie()
    
    # Build search URL with timestamp
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
    """Get detailed information about content - matching CloudStream logic"""
    if provider not in PROVIDERS:
        return {"error": f"Invalid provider: {provider}"}, 400
    
    config = PROVIDERS[provider]
    
    # Get fresh bypass cookie
    bypass_cookie = await get_bypass_cookie()
    
    # Build details URL
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
                        "poster_url": f"{config['episode_poster']}/{ep['id']}.jpg",
                        "runtime": ep.get("time", "").replace("m", "")
                    })
        
        # Parse cast and genres
        cast = [n.strip() for n in data.get("cast", "").split(",")] if data.get("cast") else []
        genres = [g.strip() for g in data.get("genre", "").split(",") if g.strip()]
        
        # Convert runtime
        runtime_str = data.get("runtime", "")
        runtime_minutes = 0
        if runtime_str:
            parts = runtime_str.split()
            for part in parts:
                if part.endswith("h"):
                    runtime_minutes += int(part.replace("h", "")) * 60
                elif part.endswith("m"):
                    runtime_minutes += int(part.replace("m", ""))
        
        return {
            "id": content_id,
            "title": data.get("title", "Unknown"),
            "description": data.get("desc"),
            "year": data.get("year"),
            "type": "movie" if not episodes else "series",
            "poster_url": f"{config['poster_base']}/{content_id}.jpg",
            "background_url": f"{config['poster_base'].replace('/v', '/h')}/{content_id}.jpg",
            "genres": genres,
            "cast": cast,
            "rating": data.get("match", "").replace("IMDb ", ""),
            "runtime_minutes": runtime_minutes if runtime_minutes > 0 else None,
            "content_rating": data.get("ua"),
            "provider": provider,
            "episodes": episodes,
            "total_episodes": len(episodes)
        }, 200
        
    except Exception as e:
        return {"error": str(e), "provider": provider}, 500


async def get_stream(provider, content_id, title=""):
    """Extract streaming URLs - exactly matching CloudStream's loadLinks logic"""
    if provider not in PROVIDERS:
        return {"error": f"Invalid provider: {provider}"}, 400
    
    config = PROVIDERS[provider]
    
    # Get fresh bypass cookie
    bypass_cookie = await get_bypass_cookie()
    
    # Build stream URL - matching CloudStream exactly
    # IMPORTANT: For stream requests, we need to use proper cookies
    cookies = get_cookies(config["id"], bypass_cookie)
    
    # CloudStream uses different paths per provider
    if provider == "netflix":
        # Netflix: /tv/playlist.php on STREAM_URL domain
        url = f"{STREAM_URL}/tv/playlist.php?id={content_id}&t={title}&tm={get_timestamp()}"
    elif provider == "primevideo":
        # Prime Video: /pv/playlist.php
        url = f"{STREAM_URL}/pv/playlist.php?id={content_id}&t={title}&tm={get_timestamp()}"
    elif provider in ["hotstar", "disneyplus"]:
        # Hotstar/Disney+: /mobile/hs/playlist.php
        url = f"{STREAM_URL}/mobile/hs/playlist.php?id={content_id}&t={title}&tm={get_timestamp()}"
    else:
        url = f"{STREAM_URL}{config['stream_path']}?id={content_id}&t={title}&tm={get_timestamp()}"
    
    try:
        # Make request with proper cookies
        headers = get_headers(config["id"])
        
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            response = await client.get(url, headers=headers, cookies=cookies)
            
            if not response.text or not response.text.strip():
                raise ValueError("Empty response from server")
            
            try:
                data = response.json()
            except json.JSONDecodeError:
                raise ValueError(f"Invalid JSON response: {response.text[:200]}")
        
        # DEBUG: Store raw response
        raw_response = data
        
        streams = []
        subtitles = []
        
        # Handle array or single object response
        if isinstance(data, list):
            playlist = data
        else:
            playlist = [data]
        
        for item in playlist:
            # Extract streams - matching CloudStream logic exactly
            for source in item.get("sources", []):
                # Get the EXACT file URL from API - don't modify it!
                file_url = source.get("file", "")
                
                # CloudStream's logic: 
                # For Netflix/Prime: """$newUrl${it.file.replace("/tv/", "/")}"""
                # This means we should use the EXACT file path from API
                
                if provider == "netflix" or provider == "primevideo":
                    # Only replace /tv/ prefix, keep everything else including query params
                    file_url = file_url.replace("/tv/", "/")
                    if not file_url.startswith("http"):
                        # Prepend STREAM_URL - file_url should have the full path + params
                        stream_url = f"{STREAM_URL}{file_url}" if file_url.startswith("/") else f"{STREAM_URL}/{file_url}"
                    else:
                        stream_url = file_url
                    referer = f"{STREAM_URL}/"
                elif provider in ["hotstar", "disneyplus"]:
                    # Hotstar/Disney+: Keep exact file URL
                    if not file_url.startswith("http"):
                        stream_url = f"{STREAM_URL}/{file_url.lstrip('/')}"
                    else:
                        stream_url = file_url
                    referer = f"{STREAM_URL}/home"
                else:
                    # Fallback
                    if not file_url.startswith("http"):
                        stream_url = f"{STREAM_URL}/{file_url.lstrip('/')}"
                    else:
                        stream_url = file_url
                    referer = f"{STREAM_URL}/home"
                
                # Extract quality - CloudStream gets it via getQualityFromName(it.file.substringAfter("q=", ""))
                quality = source.get("label", "HD")
                # Try to extract from URL parameter q=
                if "q=" in file_url:
                    try:
                        # substringAfter("q=", "") means: get everything after q=, or empty string if not found
                        # But we only want the quality value, not the rest
                        quality_param = file_url.split("q=")[1].split("&")[0] if "q=" in file_url else ""
                        if quality_param:
                            quality = quality_param
                    except:
                        pass
                
                # Determine type from source or file extension
                stream_type = source.get("type", "application/vnd.apple.mpegurl")
                
                streams.append({
                    "url": stream_url,
                    "quality": quality,
                    "type": stream_type,
                    "headers": {
                        "Referer": referer,
                        "Cookie": "hd=on",
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                    }
                })
            
            # Extract subtitles - matching CloudStream logic
            for track in item.get("tracks", []):
                if track.get("kind") == "captions":
                    sub_url = track.get("file", "")
                    if sub_url:
                        # Fix URL format - httpsify(track.file.toString())
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
            "total_streams": len(streams),
            "_raw_api_response": raw_response  # DEBUG: Include raw response
        }, 200
        
    except Exception as e:
        return {"error": str(e), "provider": provider, "details": str(type(e).__name__)}, 500


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
                    "version": "2.0.2",
                    "status": "online",
                    "providers": {k: v["name"] for k, v in PROVIDERS.items()},
                    "endpoints": {
                        "search_all": "/api/search?query={query}",
                        "search": "/api/{provider}/search?query={query}",
                        "details": "/api/{provider}/details?id={id}",
                        "stream": "/api/{provider}/stream?id={id}&title={title}&debug=1 (optional)",
                        "health": "/health"
                    },
                    "note": "Stream requests now include proper cookies and user_token. Add &debug=1 to stream endpoint to see raw API response."
                }
                self.send_json_response(response)
                return
            
            # Health check
            if path == '/health':
                response = {
                    "status": "healthy",
                    "timestamp": datetime.now().isoformat(),
                    "cookie_cached": COOKIE_CACHE["cookie"] is not None,
                    "cookie_age_seconds": int(time.time() - COOKIE_CACHE["timestamp"]) if COOKIE_CACHE["cookie"] else None
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
                        debug = params.get('debug', ['0'])[0] == '1'
                        
                        if not content_id:
                            self.send_json_response({"error": "ID parameter required"}, 400)
                            return
                        
                        result, status = asyncio.run(get_stream(provider, content_id, title))
                        
                        # Remove raw response if not in debug mode
                        if not debug and isinstance(result, dict) and '_raw_api_response' in result:
                            del result['_raw_api_response']
                        
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
