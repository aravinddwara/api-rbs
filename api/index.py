from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import httpx
import asyncio
from typing import Optional, List, Dict, Any
import time
import json
from datetime import datetime, timedelta

app = FastAPI(
    title="NetMirror Stream API",
    description="API to extract streaming URLs from Netflix Mirror services",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
BASE_URL = "https://net20.cc"
NEW_URL = "https://net51.cc"
COOKIE_CACHE = {}
COOKIE_EXPIRY = 15 * 60 * 60  # 15 hours in seconds

# Provider configurations
PROVIDERS = {
    "netflix": {
        "name": "Netflix",
        "ott": "nf",
        "poster_base": "https://imgcdn.kim/poster/v",
        "poster_bg": "https://imgcdn.kim/poster/h",
        "episode_poster": "https://imgcdn.kim/epimg/150",
        "search_endpoint": "/search.php",
        "post_endpoint": "/post.php",
        "episodes_endpoint": "/episodes.php",
        "playlist_endpoint": "/tv/playlist.php",
        "home_endpoint": "/home",
        "user_token": "233123f803cf02184bf6c67e149cdd50"
    },
    "primevideo": {
        "name": "PrimeVideo",
        "ott": "pv",
        "poster_base": "https://wsrv.nl/?url=https://imgcdn.kim/pv/v",
        "poster_bg": "https://wsrv.nl/?url=https://imgcdn.kim/pv/h",
        "episode_poster": "https://imgcdn.kim/pvepimg/150",
        "search_endpoint": "/pv/search.php",
        "post_endpoint": "/pv/post.php",
        "episodes_endpoint": "/pv/episodes.php",
        "playlist_endpoint": "/pv/playlist.php",
        "home_endpoint": "/tv/pv/homepage.php"
    },
    "hotstar": {
        "name": "Hotstar",
        "ott": "hs",
        "poster_base": "https://imgcdn.kim/hs/v",
        "poster_bg": "https://imgcdn.kim/hs/h",
        "episode_poster": "https://imgcdn.kim/hsepimg/150",
        "search_endpoint": "/mobile/hs/search.php",
        "post_endpoint": "/mobile/hs/post.php",
        "episodes_endpoint": "/mobile/hs/episodes.php",
        "playlist_endpoint": "/mobile/hs/playlist.php",
        "home_endpoint": "/mobile/home"
    },
    "disneyplus": {
        "name": "Disney Plus",
        "ott": "dp",
        "poster_base": "https://imgcdn.kim/hs/v",
        "poster_bg": "https://imgcdn.kim/hs/h",
        "episode_poster": "https://imgcdn.kim/hsepimg/150",
        "search_endpoint": "/mobile/hs/search.php",
        "post_endpoint": "/mobile/hs/post.php",
        "episodes_endpoint": "/mobile/hs/episodes.php",
        "playlist_endpoint": "/mobile/hs/playlist.php",
        "home_endpoint": "/mobile/home"
    }
}


async def get_bypass_cookie() -> str:
    """Get bypass cookie with caching mechanism"""
    current_time = time.time()
    
    # Check cache
    if "cookie" in COOKIE_CACHE and "timestamp" in COOKIE_CACHE:
        if current_time - COOKIE_CACHE["timestamp"] < COOKIE_EXPIRY:
            return COOKIE_CACHE["cookie"]
    
    # Get new cookie
    async with httpx.AsyncClient(timeout=30.0) as client:
        max_retries = 5
        for attempt in range(max_retries):
            try:
                response = await client.post(f"{BASE_URL}/tv/p.php")
                response_json = response.json()
                
                if response_json.get("r") == "n":
                    cookie = response.cookies.get("t_hash_t", "")
                    if cookie:
                        COOKIE_CACHE["cookie"] = cookie
                        COOKIE_CACHE["timestamp"] = current_time
                        return cookie
                
                await asyncio.sleep(1)
            except Exception as e:
                if attempt == max_retries - 1:
                    raise HTTPException(status_code=500, detail=f"Failed to obtain bypass cookie: {str(e)}")
                await asyncio.sleep(2)
    
    raise HTTPException(status_code=500, detail="Failed to obtain bypass cookie")


def get_unix_time() -> int:
    """Get current Unix timestamp in milliseconds"""
    return int(time.time() * 1000)


def convert_runtime_to_minutes(runtime: str) -> Optional[int]:
    """Convert runtime string (e.g., '2h 30m') to minutes"""
    if not runtime:
        return None
    
    total_minutes = 0
    parts = runtime.split()
    
    for part in parts:
        if part.endswith('h'):
            hours = int(part[:-1])
            total_minutes += hours * 60
        elif part.endswith('m'):
            minutes = int(part[:-1])
            total_minutes += minutes
    
    return total_minutes if total_minutes > 0 else None


@app.get("/")
async def root():
    """API root endpoint"""
    return {
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


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


@app.get("/api/{provider}/search")
async def search(
    provider: str,
    query: str = Query(..., description="Search query string")
):
    """Search for content across providers"""
    if provider not in PROVIDERS:
        raise HTTPException(status_code=400, detail=f"Invalid provider. Choose from: {list(PROVIDERS.keys())}")
    
    config = PROVIDERS[provider]
    cookie = await get_bypass_cookie()
    
    cookies = {
        "t_hash_t": cookie,
        "hd": "on",
        "ott": config["ott"]
    }
    
    if provider == "netflix":
        cookies["user_token"] = config["user_token"]
    
    headers = {
        "X-Requested-With": "XMLHttpRequest",
        "Referer": f"{BASE_URL}/home"
    }
    
    url = f"{BASE_URL}{config['search_endpoint']}?s={query}&t={get_unix_time()}"
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(url, headers=headers, cookies=cookies)
            response.raise_for_status()
            data = response.json()
            
            results = []
            for item in data.get("searchResult", []):
                result = {
                    "id": item["id"],
                    "title": item["t"],
                    "provider": provider,
                    "poster_url": f"{config['poster_base']}/{item['id']}.jpg"
                }
                if provider == "primevideo":
                    result["poster_url"] += "&w=500"
                results.append(result)
            
            return {
                "provider": provider,
                "query": query,
                "results": results,
                "count": len(results)
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@app.get("/api/{provider}/details")
async def get_details(
    provider: str,
    id: str = Query(..., description="Content ID")
):
    """Get detailed information about content"""
    if provider not in PROVIDERS:
        raise HTTPException(status_code=400, detail=f"Invalid provider. Choose from: {list(PROVIDERS.keys())}")
    
    config = PROVIDERS[provider]
    cookie = await get_bypass_cookie()
    
    cookies = {
        "t_hash_t": cookie,
        "hd": "on",
        "ott": config["ott"]
    }
    
    if provider == "netflix":
        cookies["user_token"] = config["user_token"]
    
    headers = {
        "X-Requested-With": "XMLHttpRequest",
        "Referer": f"{BASE_URL}/home"
    }
    
    url = f"{BASE_URL}{config['post_endpoint']}?id={id}&t={get_unix_time()}"
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(url, headers=headers, cookies=cookies)
            response.raise_for_status()
            data = response.json()
            
            # Parse episodes
            episodes = []
            if data.get("episodes") and data["episodes"][0] is not None:
                for ep in data["episodes"]:
                    if ep:
                        episodes.append({
                            "id": ep["id"],
                            "title": ep["t"],
                            "episode": int(ep["ep"].replace("E", "")) if ep.get("ep") else None,
                            "season": int(ep["s"].replace("S", "")) if ep.get("s") else None,
                            "runtime": ep.get("time", "").replace("m", ""),
                            "poster_url": f"{config['episode_poster']}/{ep['id']}.jpg"
                        })
            
            # Parse cast
            cast = []
            if data.get("cast"):
                cast = [name.strip() for name in data["cast"].split(",")]
            
            # Parse genres
            genres = []
            if data.get("genre"):
                genres = [g.strip() for g in data["genre"].split(",") if g.strip()]
            
            # Parse rating
            rating = None
            if data.get("match"):
                rating = data["match"].replace("IMDb ", "")
            
            content_type = "movie" if not episodes else "series"
            
            result = {
                "id": id,
                "title": data["title"],
                "description": data.get("desc"),
                "year": data.get("year"),
                "type": content_type,
                "poster_url": f"{config['poster_base']}/{id}.jpg",
                "background_url": f"{config['poster_bg']}/{id}.jpg",
                "genres": genres,
                "cast": cast,
                "rating": rating,
                "runtime_minutes": convert_runtime_to_minutes(data.get("runtime", "")),
                "content_rating": data.get("ua"),
                "provider": provider,
                "episodes": episodes,
                "total_episodes": len(episodes)
            }
            
            if provider == "primevideo":
                result["poster_url"] += "&w=500"
                result["background_url"] += "&w=500"
            
            return result
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to get details: {str(e)}")


@app.get("/api/{provider}/stream")
async def get_stream_urls(
    provider: str,
    id: str = Query(..., description="Content/Episode ID"),
    title: str = Query("", description="Content title")
):
    """Get streaming URLs for content"""
    if provider not in PROVIDERS:
        raise HTTPException(status_code=400, detail=f"Invalid provider. Choose from: {list(PROVIDERS.keys())}")
    
    config = PROVIDERS[provider]
    cookie = await get_bypass_cookie()
    
    cookies = {
        "t_hash_t": cookie,
        "hd": "on",
        "ott": config["ott"]
    }
    
    if provider == "netflix":
        cookies["user_token"] = config["user_token"]
    
    headers = {
        "X-Requested-With": "XMLHttpRequest",
        "Referer": f"{BASE_URL}/home"
    }
    
    url = f"{NEW_URL}{config['playlist_endpoint']}?id={id}&t={title}&tm={get_unix_time()}"
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(url, headers=headers, cookies=cookies)
            response.raise_for_status()
            playlist = response.json()
            
            streams = []
            subtitles = []
            
            for item in playlist:
                # Process video sources
                for source in item.get("sources", []):
                    file_url = source["file"]
                    
                    # Adjust URL for Netflix and PrimeVideo
                    if provider in ["netflix", "primevideo"]:
                        file_url = file_url.replace("/tv/", "/")
                    
                    stream_url = f"{NEW_URL}/{file_url}" if not file_url.startswith("http") else file_url
                    
                    # Extract quality from URL
                    quality = "HD"
                    if "q=" in file_url:
                        quality = file_url.split("q=")[1].split("&")[0]
                    
                    streams.append({
                        "url": stream_url,
                        "quality": source.get("label", quality),
                        "type": source.get("type", "m3u8"),
                        "headers": {
                            "Referer": f"{NEW_URL}/home",
                            "Cookie": "hd=on"
                        }
                    })
                
                # Process subtitles
                for track in item.get("tracks", []):
                    if track.get("kind") == "captions":
                        subtitle_url = track.get("file", "")
                        if subtitle_url and not subtitle_url.startswith("http"):
                            subtitle_url = f"https:{subtitle_url}" if subtitle_url.startswith("//") else subtitle_url
                        
                        subtitles.append({
                            "language": track.get("label", "Unknown"),
                            "url": subtitle_url
                        })
            
            return {
                "id": id,
                "title": title,
                "provider": provider,
                "streams": streams,
                "subtitles": subtitles,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to get stream URLs: {str(e)}")


@app.get("/api/{provider}/episodes")
async def get_episodes(
    provider: str,
    series_id: str = Query(..., description="Series ID"),
    season_id: str = Query(..., description="Season ID"),
    page: int = Query(1, description="Page number")
):
    """Get episodes for a specific season"""
    if provider not in PROVIDERS:
        raise HTTPException(status_code=400, detail=f"Invalid provider. Choose from: {list(PROVIDERS.keys())}")
    
    config = PROVIDERS[provider]
    cookie = await get_bypass_cookie()
    
    cookies = {
        "t_hash_t": cookie,
        "hd": "on",
        "ott": config["ott"]
    }
    
    headers = {
        "X-Requested-With": "XMLHttpRequest",
        "Referer": f"{BASE_URL}/home"
    }
    
    episodes = []
    current_page = page
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        while True:
            url = f"{BASE_URL}{config['episodes_endpoint']}?s={season_id}&series={series_id}&t={get_unix_time()}&page={current_page}"
            
            try:
                response = await client.get(url, headers=headers, cookies=cookies)
                response.raise_for_status()
                data = response.json()
                
                if data.get("episodes"):
                    for ep in data["episodes"]:
                        episodes.append({
                            "id": ep["id"],
                            "title": ep["t"],
                            "episode": int(ep["ep"].replace("E", "")) if ep.get("ep") else None,
                            "season": int(ep["s"].replace("S", "")) if ep.get("s") else None,
                            "runtime": ep.get("time", "").replace("m", ""),
                            "poster_url": f"{config['episode_poster']}/{ep['id']}.jpg"
                        })
                
                if data.get("nextPageShow") == 0:
                    break
                
                current_page += 1
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Failed to get episodes: {str(e)}")
    
    return {
        "series_id": series_id,
        "season_id": season_id,
        "provider": provider,
        "episodes": episodes,
        "total": len(episodes)
    }


# Vercel serverless handler
handler = app
