# NetMirror Stream API

A robust Python-based API to extract streaming URLs from Netflix Mirror services, supporting Netflix, Prime Video, Disney+, and Hotstar.

## Features

- 🎬 **Multiple Providers**: Netflix, Prime Video, Disney+, Hotstar
- 🔍 **Search Content**: Search across all providers
- 📺 **Get Details**: Fetch detailed information including episodes, cast, ratings
- 🎥 **Stream URLs**: Extract M3U8 streaming URLs with quality options
- 📝 **Subtitles**: Automatic subtitle extraction
- ⚡ **Cookie Caching**: Smart bypass cookie management (15-hour cache)
- 🚀 **Fast & Async**: Built with FastAPI and httpx for optimal performance
- 🌐 **CORS Enabled**: Ready for cross-origin requests

## API Endpoints

### 1. Root
```
GET /
```
Returns API information and available endpoints.

### 2. Health Check
```
GET /health
```
Check API health status.

### 3. Search Content
```
GET /api/{provider}/search?query={query}
```

**Parameters:**
- `provider`: netflix | primevideo | hotstar | disneyplus
- `query`: Search term

**Example:**
```bash
curl "https://your-api.vercel.app/api/netflix/search?query=stranger+things"
```

**Response:**
```json
{
  "provider": "netflix",
  "query": "stranger things",
  "results": [
    {
      "id": "12345",
      "title": "Stranger Things",
      "provider": "netflix",
      "poster_url": "https://imgcdn.kim/poster/v/12345.jpg"
    }
  ],
  "count": 1
}
```

### 4. Get Content Details
```
GET /api/{provider}/details?id={id}
```

**Parameters:**
- `provider`: netflix | primevideo | hotstar | disneyplus
- `id`: Content ID from search results

**Example:**
```bash
curl "https://your-api.vercel.app/api/netflix/details?id=12345"
```

**Response:**
```json
{
  "id": "12345",
  "title": "Stranger Things",
  "description": "A group of young friends witness supernatural forces...",
  "year": "2016",
  "type": "series",
  "poster_url": "https://imgcdn.kim/poster/v/12345.jpg",
  "background_url": "https://imgcdn.kim/poster/h/12345.jpg",
  "genres": ["Drama", "Fantasy", "Horror"],
  "cast": ["Millie Bobby Brown", "Finn Wolfhard"],
  "rating": "8.7",
  "runtime_minutes": 50,
  "content_rating": "TV-14",
  "provider": "netflix",
  "episodes": [
    {
      "id": "ep001",
      "title": "Chapter One: The Vanishing of Will Byers",
      "episode": 1,
      "season": 1,
      "runtime": "47",
      "poster_url": "https://imgcdn.kim/epimg/150/ep001.jpg"
    }
  ],
  "total_episodes": 42
}
```

### 5. Get Stream URLs
```
GET /api/{provider}/stream?id={id}&title={title}
```

**Parameters:**
- `provider`: netflix | primevideo | hotstar | disneyplus
- `id`: Content or Episode ID
- `title`: Content title (optional but recommended)

**Example:**
```bash
curl "https://your-api.vercel.app/api/netflix/stream?id=ep001&title=Stranger+Things"
```

**Response:**
```json
{
  "id": "ep001",
  "title": "Stranger Things",
  "provider": "netflix",
  "streams": [
    {
      "url": "https://net51.cc/path/to/stream.m3u8?q=1080p",
      "quality": "1080p",
      "type": "m3u8",
      "headers": {
        "Referer": "https://net51.cc/home",
        "Cookie": "hd=on"
      }
    },
    {
      "url": "https://net51.cc/path/to/stream.m3u8?q=720p",
      "quality": "720p",
      "type": "m3u8",
      "headers": {
        "Referer": "https://net51.cc/home",
        "Cookie": "hd=on"
      }
    }
  ],
  "subtitles": [
    {
      "language": "English",
      "url": "https://example.com/subtitles/en.vtt"
    }
  ],
  "timestamp": "2026-02-05T10:30:00"
}
```

### 6. Get Episodes
```
GET /api/{provider}/episodes?series_id={series_id}&season_id={season_id}&page={page}
```

**Parameters:**
- `provider`: netflix | primevideo | hotstar | disneyplus
- `series_id`: Series ID
- `season_id`: Season ID
- `page`: Page number (default: 1)

## Deployment to Vercel

### Prerequisites
- [Vercel Account](https://vercel.com/signup)
- [Vercel CLI](https://vercel.com/cli) (optional)

### Method 1: Deploy via Vercel Dashboard

1. **Fork/Clone this repository**
   ```bash
   git clone <your-repo-url>
   cd netmirror-api
   ```

2. **Push to GitHub**
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git remote add origin <your-github-repo-url>
   git push -u origin main
   ```

3. **Import to Vercel**
   - Go to [Vercel Dashboard](https://vercel.com/dashboard)
   - Click "Add New Project"
   - Import your GitHub repository
   - Vercel will auto-detect the configuration
   - Click "Deploy"

### Method 2: Deploy via Vercel CLI

1. **Install Vercel CLI**
   ```bash
   npm i -g vercel
   ```

2. **Login to Vercel**
   ```bash
   vercel login
   ```

3. **Deploy**
   ```bash
   vercel --prod
   ```

### Environment Variables (Optional)

You can add custom environment variables in Vercel dashboard:
- `BASE_URL`: Override default base URL
- `NEW_URL`: Override default streaming URL
- `COOKIE_EXPIRY`: Cookie cache duration in seconds

## Local Development

1. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Run the server**
   ```bash
   uvicorn api.index:app --reload --host 0.0.0.0 --port 8000
   ```

3. **Access API documentation**
   - Swagger UI: http://localhost:8000/docs
   - ReDoc: http://localhost:8000/redoc

## Usage Examples

### Python Example
```python
import requests

# Search for content
response = requests.get(
    "https://your-api.vercel.app/api/netflix/search",
    params={"query": "breaking bad"}
)
results = response.json()

# Get stream URLs
content_id = results["results"][0]["id"]
stream_response = requests.get(
    "https://your-api.vercel.app/api/netflix/stream",
    params={"id": content_id, "title": "Breaking Bad"}
)
streams = stream_response.json()

# Use the M3U8 URL with appropriate headers
stream_url = streams["streams"][0]["url"]
headers = streams["streams"][0]["headers"]
```

### JavaScript/Fetch Example
```javascript
// Search for content
const searchResponse = await fetch(
  'https://your-api.vercel.app/api/netflix/search?query=stranger+things'
);
const searchData = await searchResponse.json();

// Get stream URLs
const contentId = searchData.results[0].id;
const streamResponse = await fetch(
  `https://your-api.vercel.app/api/netflix/stream?id=${contentId}&title=Stranger+Things`
);
const streamData = await streamResponse.json();

// Use the stream URL
const streamUrl = streamData.streams[0].url;
const headers = streamData.streams[0].headers;
```

### cURL Example
```bash
# Search
curl "https://your-api.vercel.app/api/hotstar/search?query=loki"

# Get details
curl "https://your-api.vercel.app/api/hotstar/details?id=12345"

# Get streams
curl "https://your-api.vercel.app/api/hotstar/stream?id=ep001&title=Loki"
```

## Video Player Integration

### Using video.js
```html
<!DOCTYPE html>
<html>
<head>
  <link href="https://vjs.zencdn.net/7.20.3/video-js.css" rel="stylesheet" />
</head>
<body>
  <video id="my-video" class="video-js" controls preload="auto" width="640" height="264">
    <source src="STREAM_URL_HERE" type="application/x-mpegURL">
  </video>

  <script src="https://vjs.zencdn.net/7.20.3/video.min.js"></script>
  <script>
    const player = videojs('my-video', {
      html5: {
        vhs: {
          withCredentials: false
        }
      }
    });
    
    // Add custom headers
    player.ready(function() {
      this.src({
        src: 'STREAM_URL_HERE',
        type: 'application/x-mpegURL',
        withCredentials: false
      });
    });
  </script>
</body>
</html>
```

### Using HLS.js
```javascript
import Hls from 'hls.js';

const video = document.getElementById('video');
const streamUrl = 'STREAM_URL_HERE';

if (Hls.isSupported()) {
  const hls = new Hls({
    xhrSetup: function(xhr, url) {
      xhr.setRequestHeader('Referer', 'https://net51.cc/home');
    }
  });
  
  hls.loadSource(streamUrl);
  hls.attachMedia(video);
} else if (video.canPlayType('application/vnd.apple.mpegurl')) {
  video.src = streamUrl;
}
```

## Features & Capabilities

### Cookie Management
- Automatic bypass cookie generation
- 15-hour cache to minimize requests
- Automatic retry mechanism
- Thread-safe cookie storage

### Error Handling
- Comprehensive error responses
- Timeout handling (30 seconds)
- Retry logic for bypass cookies
- Detailed error messages

### Performance
- Asynchronous requests with httpx
- Concurrent episode fetching
- Efficient cookie caching
- Optimized response parsing

## Supported Providers

| Provider | Code | Features |
|----------|------|----------|
| Netflix | `netflix` | Movies, Series, Anime |
| Prime Video | `primevideo` | Movies, Series, Originals |
| Hotstar | `hotstar` | Movies, Series, Sports, Live TV |
| Disney+ | `disneyplus` | Movies, Series, Originals |

## Rate Limiting

The API implements smart cookie caching to minimize requests to the source. However, consider implementing rate limiting on your client side:
- Max 10 requests per minute recommended
- Use response caching where possible
- Reuse stream URLs within their validity period

## Troubleshooting

### "Failed to obtain bypass cookie"
- The source service may be temporarily unavailable
- Network connectivity issues
- Try again after a few minutes

### "Invalid provider"
- Ensure provider name is lowercase
- Valid options: netflix, primevideo, hotstar, disneyplus

### Stream URL not playing
- Ensure you're using the correct headers (Referer and Cookie)
- Check if the content is still available
- Try a different quality stream

## Security Notes

⚠️ **Important**: This API is for educational purposes. Ensure you comply with:
- Terms of service of streaming platforms
- Copyright laws in your jurisdiction
- API usage policies

## Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

MIT License - feel free to use this project for learning and development.

## Support

For issues and questions:
- Open an issue on GitHub
- Check existing documentation
- Review API response errors

## Changelog

### v1.0.0 (2026-02-05)
- Initial release
- Support for 4 providers
- Cookie caching mechanism
- Complete API documentation
- Vercel deployment ready

---

**Note**: This project is not affiliated with Netflix, Prime Video, Hotstar, Disney+, or any streaming service. It's an educational project demonstrating API development and web scraping techniques.
