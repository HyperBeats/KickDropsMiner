"""Kick API functions for fetching campaigns, progress, and streamer data"""
import json
import os
import time
from urllib.parse import urlparse
import urllib.request
from datetime import datetime

from utils.helpers import cookie_file_for_domain, debug_print, _kick_username_from_url
from .browser import make_chrome_driver, CookieManager


def _kick_api_headers(extra_headers=None):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json",
        "Origin": "https://kick.com",
        "Referer": "https://kick.com/",
    }
    if extra_headers:
        headers.update(extra_headers)
    return headers


def _cookie_header_for_domain(domain):
    path = cookie_file_for_domain(domain)
    if not os.path.exists(path):
        return "", None

    try:
        with open(path, "r", encoding="utf-8") as f:
            cookies = json.load(f)
    except Exception:
        return "", None

    parts = []
    session_token = None
    for cookie in cookies:
        name = cookie.get("name")
        value = cookie.get("value")
        if not name or value is None:
            continue
        parts.append(f"{name}={value}")
        if name == "session_token":
            session_token = value
    return "; ".join(parts), session_token


def _fetch_kick_json(api_url, authenticated=False):
    headers = _kick_api_headers()
    if authenticated:
        cookie_header, session_token = _cookie_header_for_domain("kick.com")
        if cookie_header:
            headers["Cookie"] = cookie_header
        if session_token:
            headers["Authorization"] = f"Bearer {session_token}"

    req = urllib.request.Request(api_url, headers=headers)
    with urllib.request.urlopen(req, timeout=12) as resp:
        return json.load(resp)


def _campaigns_from_response(response):
    campaigns = []
    data = response.get("data", []) if isinstance(response, dict) else []

    if isinstance(data, list):
        for campaign in data:
            if not isinstance(campaign, dict):
                continue
            category = campaign.get("category", {})
            if not isinstance(category, dict):
                category = {}
            campaign_info = {
                "id": campaign.get("id"),
                "name": campaign.get("name", "Unknown Campaign"),
                "game": category.get("name", "Unknown Game"),
                "game_slug": category.get("slug", ""),
                "game_image": category.get("image_url", ""),
                "status": campaign.get("status", "unknown"),
                "starts_at": campaign.get("starts_at"),
                "ends_at": campaign.get("ends_at"),
                "rewards": campaign.get("rewards", []),
                "channels": [],
            }

            channels = campaign.get("channels", [])
            if isinstance(channels, list):
                for channel in channels:
                    if isinstance(channel, dict):
                        slug = channel.get("slug")
                        user = channel.get("user", {})
                        if not isinstance(user, dict):
                            user = {}
                        username = user.get("username") or slug
                        if slug:
                            campaign_info["channels"].append(
                                {
                                    "slug": slug,
                                    "username": username,
                                    "url": f"https://kick.com/{slug}",
                                    "profile_picture": user.get("profile_picture", ""),
                                }
                            )

            if campaign_info["channels"] or campaign.get("status") == "active":
                campaigns.append(campaign_info)

    return campaigns


def kick_is_live_by_api(url: str) -> bool:
    """Returns True if the Kick channel is live (via API).
     In case of network error, returns True to avoid blocking the queue.
    """
    status = kick_live_status_by_api(url)
    return True if status is None else status


def kick_live_status_by_api(url: str):
    """Returns True/False when known, otherwise None (network error / not Kick / invalid URL)."""
    try:
        p = urlparse(url)
        if "kick.com" not in p.netloc:
            return None
        username = p.path.strip("/").split("/")[0]
        if not username:
            return None
        api_url = f"https://kick.com/api/v2/channels/{username}"
        req = urllib.request.Request(api_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.load(resp)
        livestream = data.get("livestream")
        return bool(livestream and livestream.get("is_live"))
    except Exception:
        return None


def is_campaign_expired(campaign):
    """Check if a campaign has expired based on ends_at timestamp"""
    try:
        ends_at = campaign.get("ends_at")
        if not ends_at:
            return False  # No end date means not expired
        
        now = datetime.now()
        
        if isinstance(ends_at, str):
            # Try ISO format first
            try:
                # Handle various ISO formats
                ends_at_clean = ends_at.replace("Z", "").replace("+00:00", "")
                # Try with microseconds
                try:
                    end_date = datetime.fromisoformat(ends_at_clean)
                except:
                    # Try without microseconds
                    if "." in ends_at_clean:
                        ends_at_clean = ends_at_clean.split(".")[0]
                    end_date = datetime.fromisoformat(ends_at_clean)
                
                # Compare (end_date is naive, now is naive, so direct comparison)
                return now >= end_date
            except:
                # Try parsing as Unix timestamp (string)
                try:
                    end_date = datetime.fromtimestamp(float(ends_at))
                    return now >= end_date
                except:
                    return False
        else:
            # Assume it's a numeric timestamp
            try:
                end_date = datetime.fromtimestamp(float(ends_at))
                return now >= end_date
            except:
                return False
    except Exception as e:
        print(f"Error checking expiration: {e}")
        return False  # On error, assume not expired


def fetch_live_streamers_by_category(category_id, limit=24, driver=None):
    """Fetches live streamers currently streaming a specific game category.
    Uses category_id from the campaign data.
    Returns list of channel URLs.
    """
    if not category_id:
        return []
    
    should_close_driver = False
    if driver is None:
        try:
            driver = make_chrome_driver(headless=True, visible_width=400, visible_height=300)
            driver.get("https://kick.com")
            time.sleep(1)
            
            # Load cookies
            cookie_path = cookie_file_for_domain("kick.com")
            if os.path.exists(cookie_path):
                with open(cookie_path, "r", encoding="utf-8") as f:
                    cookies = json.load(f)
                for cookie in cookies:
                    try:
                        if "expiry" in cookie and cookie["expiry"] is None:
                            del cookie["expiry"]
                        driver.add_cookie(cookie)
                    except:
                        pass
                driver.refresh()
                time.sleep(1)
            should_close_driver = True
        except Exception as e:
            print(f"Error creating driver for game search: {e}")
            return []
    
    try:
        # Use the correct API endpoint with category_id
        api_url = f"https://web.kick.com/api/v1/livestreams?limit={limit}&sort=viewer_count_desc&category_id={category_id}"
        debug_print(f"DEBUG: Fetching from API: {api_url}")
        
        fetch_script = f"""
        return fetch('{api_url}', {{
            method: 'GET',
            headers: {{
                'Accept': 'application/json',
            }},
            credentials: 'include'
        }})
        .then(response => {{
            console.log('Response status:', response.status);
            return response.text();
        }})
        .then(data => data)
        .catch(error => JSON.stringify({{error: error.toString()}}));
        """
        
        debug_print("DEBUG: Executing fetch script in browser...")
        page_text = driver.execute_script(fetch_script)
        debug_print(f"DEBUG: Received response (first 500 chars): {page_text[:500]}")
        
        if not page_text or "error" in page_text.lower():
            debug_print(f"DEBUG: Error in response: {page_text[:500]}")
            return []
        
        debug_print("DEBUG: Parsing JSON response...")
        data = json.loads(page_text)
        debug_print(f"DEBUG: Parsed data keys: {list(data.keys())}")
        
        streamers = []
        # Handle response format - nested structure: {"data": {"livestreams": [...]}}
        data_obj = data.get("data", {})
        if isinstance(data_obj, dict):
            # Nested structure: data.livestreams
            streams = data_obj.get("livestreams", [])
            debug_print(f"DEBUG: Found {len(streams)} streams in nested structure")
        elif isinstance(data_obj, list):
            # Flat structure: data is directly a list
            streams = data_obj
            debug_print(f"DEBUG: Found {len(streams)} streams in flat structure")
        else:
            streams = []
            debug_print(f"DEBUG: Unexpected data structure: {type(data_obj)}")
        
        debug_print(f"DEBUG: Processing {min(len(streams), limit)} streams (limit={limit})")
        
        for idx, stream in enumerate(streams[:limit]):
            try:
                debug_print(f"DEBUG: Processing stream {idx + 1}/{min(len(streams), limit)}")
                # Extract channel slug/username
                channel = stream.get("channel", {})
                if not channel:
                    debug_print(f"DEBUG: Stream {idx + 1} has no channel data")
                    continue
                
                debug_print(f"DEBUG: Channel data keys: {list(channel.keys())}")
                slug = channel.get("slug")
                if not slug:
                    # Try alternative structure
                    user = channel.get("user", {})
                    slug = user.get("username") or user.get("slug")
                    debug_print(f"DEBUG: Got slug from user object: {slug}")
                
                if slug:
                    viewer_count = stream.get("viewer_count", 0)
                    title = stream.get("session_title", "")
                    debug_print(f"DEBUG: Adding streamer: {slug} ({viewer_count} viewers) - {title[:50]}")
                    streamers.append({
                        "url": f"https://kick.com/{slug}",
                        "username": slug,
                        "title": title,
                        "viewer_count": viewer_count
                    })
                else:
                    debug_print(f"DEBUG: Could not extract slug from stream {idx + 1}")
            except Exception as e:
                debug_print(f"DEBUG: Error parsing stream {idx + 1}: {e}")
                import traceback
                traceback.print_exc()
                continue
        
        debug_print(f"DEBUG: Successfully parsed {len(streamers)} streamers")
        return streamers
    except Exception as e:
        print(f"Error fetching streamers for category_id {category_id}: {e}")
        import traceback
        traceback.print_exc()
        return []
    finally:
        if should_close_driver and driver:
            try:
                driver.quit()
            except:
                pass


def _load_cookies_to_driver(driver):
    """Helper to load cookies into driver"""
    cookie_path = cookie_file_for_domain("kick.com")
    if os.path.exists(cookie_path):
        with open(cookie_path, "r", encoding="utf-8") as f:
            cookies = json.load(f)
        for cookie in cookies:
            try:
                if "expiry" in cookie and cookie["expiry"] is None:
                    del cookie["expiry"]
                driver.add_cookie(cookie)
            except:
                pass
        driver.refresh()
        time.sleep(1)


def fetch_drop_campaigns():
    """Fetches active drop campaigns from the Kick API.
     Uses undetected_chromedriver to bypass Cloudflare and handle compression.
    """
    driver = None
    try:
        api_url = "https://web.kick.com/api/v1/drops/campaigns"

        print(f"Fetching drops...")
        try:
            response = _fetch_kick_json(api_url)
            campaigns = _campaigns_from_response(response)
            print(f"Successfully fetched {len(campaigns)} campaigns via direct API")
            return {"campaigns": campaigns, "driver": None}
        except Exception as e:
            print(f"Direct drops API failed, falling back to headless Chrome: {e}")

        # ONLY for fetching campaigns: run Chrome headless.
        driver = make_chrome_driver(
            headless=True, visible_width=400, visible_height=300
        )
        
        # Visit kick.com and load cookies
        print("Establishing Session on kick.com...")
        driver.get("https://kick.com")
        time.sleep(1)
        _load_cookies_to_driver(driver)

        # Use JavaScript to make the fetch request from the page context
        print(f"Fetching Drops from API...")

        fetch_script = f"""
        return fetch('{api_url}', {{
            method: 'GET',
            headers: {{
                'Accept': 'application/json',
            }},
            credentials: 'include'
        }})
        .then(response => response.text())
        .then(data => data)
        .catch(error => JSON.stringify({{error: error.toString()}}));
        """

        # Execute the script and get the result
        page_text = driver.execute_script(fetch_script)

        # Check if blocked
        if "blocked by security policy" in page_text.lower():
            print(f"Request blocked! Response: {page_text}")
            if driver:
                try:
                    driver.quit()
                except:
                    pass
            return {"campaigns": [], "driver": None}

        # Parse le JSON
        response = json.loads(page_text)
        print(f"Successfully fetched campaign data!")
        print(f"We have found {len(response.get('data', []))} campaigns")

        # Return data AND driver (to load images)
        campaigns = _campaigns_from_response(response)

        # Retourne les campagnes ET le driver
        return {"campaigns": campaigns, "driver": driver}
    except Exception as e:
        print(f"Error fetching drop campaigns: {e}")
        import traceback
        traceback.print_exc()
        # On error, close driver and return empty
        if driver:
            try:
                driver.quit()
            except:
                pass
        return {"campaigns": [], "driver": None}


def fetch_drops_progress(driver=None):
    """Fetches current drop progress from the Kick API.
    Uses undetected_chromedriver and requires authentication via session_token cookie.
    If driver is provided, reuses it instead of creating a new one.
    """
    use_existing_driver = driver is not None
    if not use_existing_driver:
        driver = None
    
    try:
        api_url = "https://web.kick.com/api/v1/drops/progress"
        
        if not use_existing_driver:
            print("Fetching drops progress...")
            try:
                response = _fetch_kick_json(api_url, authenticated=True)
                progress_data = response.get("data", []) if isinstance(response, dict) else []
                print(f"Successfully fetched {len(progress_data)} campaigns with progress via direct API")
                return {"progress": progress_data, "driver": None}
            except Exception:
                debug_print("DEBUG: Direct progress API failed, falling back to headless Chrome")
            
            # Use the same approach as fetch_drop_campaigns
            driver = make_chrome_driver(
                headless=True, visible_width=400, visible_height=300
            )
            
            # Visit kick.com and load cookies
            print("Establishing session on kick.com...")
            driver.get("https://kick.com")
            time.sleep(1)
            _load_cookies_to_driver(driver)
        else:
            print("Fetching progress from API (reusing existing session)...")
        
        # Get session_token cookie for Authorization header
        session_token = None
        try:
            all_cookies = driver.get_cookies()
            for cookie in all_cookies:
                if cookie.get("name") == "session_token":
                    session_token = cookie.get("value")
                    break
        except:
            pass
        
        if not session_token:
            print("Warning: No session_token cookie found. Progress may require authentication.")
        
        # Use JavaScript to make the fetch request with Authorization header
        print("Fetching progress from API...")
        
        # Build the fetch script with optional Authorization header
        auth_header = f"'Authorization': 'Bearer {session_token}'," if session_token else ""
        
        fetch_script = f"""
        return fetch('{api_url}', {{
            method: 'GET',
            headers: {{
                'Accept': 'application/json',
                {auth_header}
            }},
            credentials: 'include'
        }})
        .then(response => response.text())
        .then(data => data)
        .catch(error => JSON.stringify({{error: error.toString()}}));
        """
        
        # Execute the script and get the result
        page_text = driver.execute_script(fetch_script)
        
        # Check if blocked
        if "blocked by security policy" in page_text.lower():
            print(f"Request blocked! Response: {page_text}")
            if driver and not use_existing_driver:
                try:
                    driver.quit()
                except:
                    pass
            return {"progress": [], "driver": None}
        
        # Parse the JSON
        response = json.loads(page_text)
        print(f"Successfully fetched progress data!")
        print(f"Found {len(response.get('data', []))} campaigns with progress")
        
        # Return progress data
        progress_data = response.get("data", [])
        
        # Return driver only if we created it (not if it was passed in)
        return {"progress": progress_data, "driver": driver if not use_existing_driver else None}
        
    except Exception as e:
        print(f"Error fetching drops progress: {e}")
        import traceback
        traceback.print_exc()
        if driver and not use_existing_driver:
            try:
                driver.quit()
            except:
                pass
        return {"progress": [], "driver": None}


def fetch_drops_campaigns_and_progress():
    """Fetches both campaigns and progress data using a single Chrome driver instance"""
    driver = None
    try:
        campaigns_api_url = "https://web.kick.com/api/v1/drops/campaigns"
        progress_api_url = "https://web.kick.com/api/v1/drops/progress"
        
        print("Fetching drops campaigns and progress...")
        try:
            campaigns_response = _fetch_kick_json(campaigns_api_url)
            campaigns = _campaigns_from_response(campaigns_response)
            print(f"Successfully fetched {len(campaigns)} campaigns via direct API")

            progress_data = []
            try:
                progress_response = _fetch_kick_json(progress_api_url, authenticated=True)
                progress_data = progress_response.get("data", []) if isinstance(progress_response, dict) else []
                print(f"Successfully fetched {len(progress_data)} campaigns with progress via direct API")
            except Exception:
                debug_print("DEBUG: Direct progress API failed, continuing without progress")

            return {"campaigns": campaigns, "progress": progress_data, "driver": None}
        except Exception as e:
            print(f"Direct campaigns API failed, falling back to headless Chrome: {e}")
        
        # Create one driver for both requests
        driver = make_chrome_driver(
            headless=True, visible_width=400, visible_height=300
        )
        
        # Visit kick.com and load cookies
        print("Establishing session on kick.com...")
        driver.get("https://kick.com")
        time.sleep(1)
        _load_cookies_to_driver(driver)
        
        # Get session_token cookie for Authorization header
        session_token = None
        try:
            all_cookies = driver.get_cookies()
            for cookie in all_cookies:
                if cookie.get("name") == "session_token":
                    session_token = cookie.get("value")
                    break
        except:
            pass
        
        # Fetch campaigns
        print("Fetching campaigns from API...")
        campaigns_script = f"""
        return fetch('{campaigns_api_url}', {{
            method: 'GET',
            headers: {{
                'Accept': 'application/json',
            }},
            credentials: 'include'
        }})
        .then(response => response.text())
        .then(data => data)
        .catch(error => JSON.stringify({{error: error.toString()}}));
        """
        
        campaigns_text = driver.execute_script(campaigns_script)
        
        # Fetch progress
        print("Fetching progress from API...")
        auth_header = f"'Authorization': 'Bearer {session_token}'," if session_token else ""
        progress_script = f"""
        return fetch('{progress_api_url}', {{
            method: 'GET',
            headers: {{
                'Accept': 'application/json',
                {auth_header}
            }},
            credentials: 'include'
        }})
        .then(response => response.text())
        .then(data => data)
        .catch(error => JSON.stringify({{error: error.toString()}}));
        """
        
        progress_text = driver.execute_script(progress_script)
        
        # Check if blocked
        if "blocked by security policy" in campaigns_text.lower():
            print(f"Campaigns request blocked! Response: {campaigns_text}")
            return {"campaigns": [], "progress": [], "driver": None}
        
        if "blocked by security policy" in progress_text.lower():
            print(f"Progress request blocked! Response: {progress_text}")
            # Still return campaigns even if progress is blocked
            progress_text = '{"data": []}'
        
        # Parse campaigns JSON
        campaigns_response = json.loads(campaigns_text)
        campaigns = _campaigns_from_response(campaigns_response)
        
        print(f"Successfully fetched {len(campaigns)} campaigns")
        
        # Parse progress JSON
        progress_response = json.loads(progress_text)
        progress_data = progress_response.get("data", [])
        print(f"Successfully fetched {len(progress_data)} campaigns with progress")
        
        return {"campaigns": campaigns, "progress": progress_data, "driver": driver}
        
    except Exception as e:
        print(f"Error fetching drops data: {e}")
        import traceback
        traceback.print_exc()
        if driver:
            try:
                driver.quit()
            except:
                pass
        return {"campaigns": [], "progress": [], "driver": None}
