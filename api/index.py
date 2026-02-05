from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import json
import httpx
import asyncio
import time
from datetime import datetime

# Configuration - matching CloudStream exactly
BASE_URL = "https://net20.cc"  # mainUrl in CloudStream
NEW_URL = "https://net51.cc"   # newUrl in CloudStream

# Cookie cache - 15 hour expiry like CloudStream
COOKIE_CACHE = {"value": None, "timestamp": 0}
COOKIE_EXPIRY = 15 * 60 * 60  # 54000 seconds

# Provider configs - matching CloudStream exactly
PROVIDERS = {
    "netflix": {
        "id": "nf",
        "name": "Netflix",
        "user_token": "233123f803cf02184bf6c67e149cdd50",
        "search_path": "/search.php",
        "details_path": "/post.php",
        "episodes_path": "/episodes.php",
        "stream_path": "/tv/playlist.php",
        "poster_base": "https://imgcdn.kim/poster/v",
        "poster_bg": "https://imgcdn.kim/poster/h",
        "episode_poster": "https://imgcdn.kim/epimg/150",
        "referer_home": f"{BASE_URL}/home",
        "referer_stream": f"{NEW_URL}/",
        "use_tv_home": True
    },
    "primevideo": {
        "id": "pv",
        "name": "Prime Video",
        "search_path": "/pv/search.php",
        "details_path": "/pv/post.php",
        "episodes_path": "/pv/episodes.php",
        "stream_path": "/pv/playlist.php",
        "poster_base": "https://imgcdn.kim/pv/v",
        "poster_bg": "https://imgcdn.kim/pv/h",
        "episode_poster": "https://imgcdn.kim/pvepimg/150",
        "referer_home": f"{BASE_URL}/home",
        "referer_stream": f"{NEW_URL}/",
        "use_tv_home": False
    },
    "hotstar": {
        "id": "hs",
        "name": "Hotstar",
        "search_path": "/mobile/hs/search.php",
        "details_path": "/mobile/hs/post.php",
        "episodes_path": "/mobile/hs/episodes.php",
        "stream_path": "/mobile/hs/playlist.php",
        "poster_base": "https://imgcdn.kim/hs/v",
        "poster_bg": "https://imgcdn.kim/hs/h",
        "episode_poster": "https://imgcdn.kim/hsepimg/150",
        "referer_home": f"{BASE_URL}/home",
        "referer_stream": f"{NEW_URL}/home",
        "use_mobile": True
    },
    "disneyplus": {
        "id": "dp",
        "name": "Disney+",
        "search_path": "/mobile/hs/search.php",
        "details_path": "/mobile/hs/post.php",
        "episodes_path": "/mobile/hs/episodes.php",
        "stream_path": "/mobile/hs/playlist.php",
        "poster_base": "https://imgcdn.kim/hs/v",
        "poster_bg": "https://imgcdn.kim/hs/h",
        "episode_poster": "https://imgcdn.kim/hsepimg/150",
        "referer_home": f"{BASE_URL}/home",
        "referer_stream": f"{NEW_URL}/home",
        "use_mobile": True
    }
}


def unix_time():
    """Get Unix timestamp in milliseconds - matching APIHolder.unixTime"""
    return int(time.time() * 1000)


async def bypass(base_url):
    """
    CloudStream's bypass() function - EXACT implementation
    
    suspend fun bypass(mainUrl: String): String {
        var verifyCheck: String
        var verifyResponse: NiceResponse
        do {
            verifyResponse = app.post("$mainUrl/tv/p.php")
            verifyCheck = verifyResponse.text
        } while (!verifyCheck.contains("\"r\":\"n\""))
        return verifyResponse.cookies["t_hash_t"].orEmpty()
    }
    """
    current_time = time.time()
    
    # Check cache - valid if less than 15 hours old
    if COOKIE_CACHE["value"] and (current_time - COOKIE_CACHE["timestamp"] < COOKIE_EXPIRY):
        return COOKIE_CACHE["value"]
    
    # Get fresh cookie
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        verify_check = ""
        max_attempts = 20
        attempt = 0
        
        while '{"r":"n"}' not in verify_check and attempt < max_attempts:
            try:
                verify_response = await client.post(f"{base_url}/tv/p.php")
                verify_check = verify_response.text
                
                if '{"r":"n"}' in verify_check or '"r":"n"' in verify_check:
                    cookie = verify_response.cookies.get("t_hash_t", "")
                    if cookie:
                        COOKIE_CACHE["value"] = cookie
                        COOKIE_CACHE["timestamp"] = current_time
                        return cookie
                
                attempt += 1
                await asyncio.sleep(0.3)
            except:
                attempt += 1
                await asyncio.sleep(0.3)
    
    # If we have cached cookie, return it even if expired
    if COOKIE_CACHE["value"]:
        return COOKIE_CACHE["value"]
    
    raise Exception("Failed to obtain bypass cookie")


async def search_content(provider, query):
    """
    CloudStream search implementation
    
    override suspend fun search(query: String): List<SearchResponse> {
        cookie_value = if(cookie_value.isEmpty()) bypass(mainUrl) else cookie_value
        val cookies = mapOf(
            "t_hash_t" to cookie_value,
            "hd" to "on",
            "ott" to "nf"
        )
        val url = "$mainUrl/search.php?s=$query&t=${APIHolder.unixTime}"
        val data = app.get(url, referer = "$mainUrl/home", cookies = cookies).parsed<SearchData>()
        ...
    }
    """
    if provider not in PROVIDERS:
        return {"error": "Invalid provider"}, 400
    
    config = PROVIDERS[provider]
    cookie_value = await bypass(BASE_URL)
    
    # Build cookies - matching CloudStream
    cookies = {
        "t_hash_t": cookie_value,
        "hd": "on",
        "ott": config["id"]
    }
    
    # Add user_token for Netflix
    if provider == "netflix":
        cookies["user_token"] = config["user_token"]
    
    # Build URL
    url = f"{BASE_URL}{config['search_path']}?s={query}&t={unix_time()}"
    
    # Headers matching CloudStream
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": config["referer_home"]
    }
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=headers, cookies=cookies)
            data = response.json()
        
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
        return {"error": str(e)}, 500


async def get_details(provider, content_id):
    """
    CloudStream load() implementation
    
    override suspend fun load(url: String): LoadResponse? {
        cookie_value = if(cookie_value.isEmpty()) bypass(mainUrl) else cookie_value
        val id = parseJson<Id>(url).id
        val cookies = mapOf(...)
        val data = app.get(
            "$mainUrl/post.php?id=$id&t=${APIHolder.unixTime}",
            headers,
            referer = "$mainUrl/home",
            cookies = cookies
        ).parsed<PostData>()
        ...
    }
    """
    if provider not in PROVIDERS:
        return {"error": "Invalid provider"}, 400
    
    config = PROVIDERS[provider]
    cookie_value = await bypass(BASE_URL)
    
    cookies = {
        "t_hash_t": cookie_value,
        "hd": "on",
        "ott": config["id"]
    }
    
    if provider == "netflix":
        cookies["user_token"] = config["user_token"]
    
    url = f"{BASE_URL}{config['details_path']}?id={content_id}&t={unix_time()}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": config["referer_home"]
    }
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=headers, cookies=cookies)
            data = response.json()
        
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
        
        return {
            "id": content_id,
            "title": data.get("title", "Unknown"),
            "description": data.get("desc"),
            "year": data.get("year"),
            "type": "movie" if not episodes else "series",
            "poster_url": f"{config['poster_base']}/{content_id}.jpg",
            "background_url": f"{config['poster_bg']}/{content_id}.jpg",
            "genres": [g.strip() for g in data.get("genre", "").split(",") if g.strip()],
            "cast": [c.strip() for c in data.get("cast", "").split(",") if c.strip()],
            "rating": data.get("match", "").replace("IMDb ", ""),
            "provider": provider,
            "episodes": episodes,
            "total_episodes": len(episodes)
        }, 200
    except Exception as e:
        return {"error": str(e)}, 500


async def get_stream(provider, content_id, title=""):
    """
    CloudStream loadLinks() implementation - EXACT MATCH
    
    override suspend fun loadLinks(...): Boolean {
        val (title, id) = parseJson<LoadData>(data)
        val cookies = mapOf(
            "t_hash_t" to cookie_value,
            "ott" to "nf",
            "hd" to "on"
        )
        val playlist = app.get(
            "$newUrl/tv/playlist.php?id=$id&t=$title&tm=${APIHolder.unixTime}",
            headers,
            referer = "$mainUrl/home",
            cookies = cookies
        ).parsed<PlayList>()

        playlist.forEach { item ->
            item.sources.forEach {
                callback.invoke(
                    newExtractorLink(
                        name,
                        it.label,
                        "$newUrl${it.file.replace("/tv/", "/")}",
                        type = ExtractorLinkType.M3U8
                    ) {
                        this.referer = "$newUrl/"
                        this.quality = getQualityFromName(it.file.substringAfter("q=", ""))
                    }
                )
            }
        }
    }
    """
    if provider not in PROVIDERS:
        return {"error": "Invalid provider"}, 400
    
    config = PROVIDERS[provider]
    cookie_value = await bypass(BASE_URL)
    
    # Build cookies - EXACTLY like CloudStream
    cookies = {
        "t_hash_t": cookie_value,
        "ott": config["id"],
        "hd": "on"
    }
    
    # Add user_token for Netflix
    if provider == "netflix":
        cookies["user_token"] = config["user_token"]
    
    # Build URL - matching CloudStream paths exactly
    if provider == "netflix":
        # "$newUrl/tv/playlist.php?id=$id&t=$title&tm=${APIHolder.unixTime}"
        url = f"{NEW_URL}/tv/playlist.php?id={content_id}&t={title}&tm={unix_time()}"
    elif provider == "primevideo":
        # "$newUrl/pv/playlist.php?id=$id&t=$title&tm=${APIHolder.unixTime}"
        url = f"{NEW_URL}/pv/playlist.php?id={content_id}&t={title}&tm={unix_time()}"
    elif provider in ["hotstar", "disneyplus"]:
        # "$newUrl/mobile/hs/playlist.php?id=$id&t=$title&tm=${APIHolder.unixTime}"
        url = f"{NEW_URL}/mobile/hs/playlist.php?id={content_id}&t={title}&tm={unix_time()}"
    else:
        url = f"{NEW_URL}{config['stream_path']}?id={content_id}&t={title}&tm={unix_time()}"
    
    # Headers
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": config["referer_home"]
    }
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=headers, cookies=cookies)
            playlist_data = response.json()
        
        # Handle array or single object
        if isinstance(playlist_data, list):
            playlist = playlist_data
        else:
            playlist = [playlist_data]
        
        streams = []
        subtitles = []
        
        # Extract streams - EXACTLY like CloudStream
        for item in playlist:
            for source in item.get("sources", []):
                file = source.get("file", "")
                
                # CloudStream logic: """$newUrl${it.file.replace("/tv/", "/")}"""
                # This means:
                # 1. Replace /tv/ with /
                # 2. Prepend NEW_URL
                
                if provider == "netflix" or provider == "primevideo":
                    # Remove /tv/ prefix
                    file = file.replace("/tv/", "/")
                
                # Build stream URL
                if file.startswith("http"):
                    stream_url = file
                else:
                    # Prepend NEW_URL
                    stream_url = f"{NEW_URL}{file}" if file.startswith("/") else f"{NEW_URL}/{file}"
                
                # Extract quality - getQualityFromName(it.file.substringAfter("q=", ""))
                quality = source.get("label", "HD")
                if "q=" in file:
                    # substringAfter("q=", "") - get everything after q=, or empty if not found
                    try:
                        q_value = file.split("q=")[1].split("&")[0]
                        if q_value:
                            quality = q_value
                    except:
                        pass
                
                streams.append({
                    "url": stream_url,
                    "quality": quality,
                    "type": source.get("type", "application/vnd.apple.mpegurl"),
                    "headers": {
                        "Referer": config["referer_stream"],
                        "Cookie": "hd=on",
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                    }
                })
            
            # Extract subtitles
            for track in item.get("tracks", []):
                if track.get("kind") == "captions":
                    sub_file = track.get("file", "")
                    if sub_file:
                        # httpsify()
                        if sub_file.startswith("//"):
                            sub_url = f"https:{sub_file}"
                        elif not sub_file.startswith("http"):
                            sub_url = f"{NEW_URL}/{sub_file.lstrip('/')}"
                        else:
                            sub_url = sub_file
                        
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
            "total_streams": len(streams)
        }, 200
    except Exception as e:
        return {"error": str(e)}, 500


class handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass
    
    def send_json(self, data, status=200):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))
    
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', '*')
        self.end_headers()
    
    def do_GET(self):
        try:
            parsed = urlparse(self.path)
            path = parsed.path
            params = parse_qs(parsed.query)
            
            # Root
            if path in ['/', '']:
                self.send_json({
                    "name": "CloudStream API",
                    "version": "3.0.0",
                    "status": "online",
                    "note": "Rebuilt from scratch matching CloudStream exactly",
                    "providers": list(PROVIDERS.keys())
                })
                return
            
            # Health
            if path == '/health':
                self.send_json({
                    "status": "healthy",
                    "cookie_cached": COOKIE_CACHE["value"] is not None,
                    "cookie_age": int(time.time() - COOKIE_CACHE["timestamp"]) if COOKIE_CACHE["value"] else None
                })
                return
            
            # API endpoints
            if path.startswith('/api/'):
                parts = [p for p in path.split('/') if p]
                
                if len(parts) >= 3:
                    provider = parts[1]
                    action = parts[2]
                    
                    if action == 'search':
                        query = params.get('query', [''])[0]
                        if not query:
                            self.send_json({"error": "Query required"}, 400)
                            return
                        result, status = asyncio.run(search_content(provider, query))
                        self.send_json(result, status)
                        return
                    
                    elif action == 'details':
                        content_id = params.get('id', [''])[0]
                        if not content_id:
                            self.send_json({"error": "ID required"}, 400)
                            return
                        result, status = asyncio.run(get_details(provider, content_id))
                        self.send_json(result, status)
                        return
                    
                    elif action == 'stream':
                        content_id = params.get('id', [''])[0]
                        title = params.get('title', [''])[0]
                        if not content_id:
                            self.send_json({"error": "ID required"}, 400)
                            return
                        result, status = asyncio.run(get_stream(provider, content_id, title))
                        self.send_json(result, status)
                        return
            
            self.send_json({"error": "Not found"}, 404)
        except Exception as e:
            self.send_json({"error": str(e)}, 500)
