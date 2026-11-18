# KINEXO Search API

Aggregates openly licensed media from Internet Archive and PeerTube. Source license metadata is not independent rights verification.

## Local startup
```sh
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000
```

## Container deployment
From this directory:
```sh
docker build -t kinexo-search .
docker run --rm -p 8000:8000 -e PORT=8000 kinexo-search
curl --fail http://localhost:8000/health
```

Deploy the server directory as a Docker web service with outbound HTTPS access. Set PORT to the hosting platform's assigned port and configure /health as its health endpoint. Use the public HTTPS URL for Android integration.

## Android integration
In the repository Settings > Secrets and variables > Actions > Variables, create KINEXO_SEARCH_API with the deployed HTTPS base URL (without /search). Run Build KINEXO APK manually. The workflow embeds the URL in BuildConfig; no user configuration is required. When the API is unavailable, Android falls back to direct Internet Archive search.

## Verification
Check GET /health and GET /search?q=Big%20Buck%20Bunny on the deployed host. Install the newly published APK and test search, playback, and fallback. The public deployment is not yet provisioned.
