"""StreamWorker class for managing individual stream watching"""
import json
import threading
import time
import random
import re
from selenium.webdriver.common.by import By

from utils.helpers import domain_from_url, debug_print, _kick_username_from_url
from .browser import make_chrome_driver, CookieManager


class StreamWorker(threading.Thread):
    """Manages individual stream watching in a separate thread"""
    
    def __init__(
        self,
        url,
        minutes_target,
        on_update=None,
        on_finish=None,
        stop_event=None,
        driver_path=None,
        extension_path=None,
        hide_player=False,
        mute=True,
        mini_player=False,
        force_160p=False,
        offline_fresh_checks_to_switch=2,
        required_category_id=None,
        cumulative_time_callback=None,
    ):
        super().__init__(daemon=True)
        self.url = url
        self.minutes_target = minutes_target
        self.on_update = on_update
        self.on_finish = on_finish
        self.stop_event = stop_event or threading.Event()
        self.elapsed_seconds = 0
        self.driver = None
        self.driver_path = driver_path
        self.extension_path = extension_path
        self.hide_player = hide_player
        self.mute = mute
        self.mini_player = mini_player
        self.force_160p = force_160p
        self.completed = False
        self.ended_because_offline = False
        self.ended_because_wrong_category = False
        self.required_category_id = required_category_id
        self.cumulative_time_callback = cumulative_time_callback
        self._offline_fresh_checks = 0
        self.offline_fresh_checks_to_switch = max(0, int(offline_fresh_checks_to_switch or 0))
        # Anti rate-limit: cache "is live" checks
        self._last_live_check = 0.0
        self._last_live_value = True
        self._live_check_interval = 10  # seconds (reduced for faster detection)
        self._last_live_source = "unknown"  # api | dom | unknown
        # Category check interval (check every 30 seconds)
        self._last_category_check = 0.0
        self._category_check_interval = 30  # seconds

    def run(self):
        """Main worker loop"""
        domain = domain_from_url(self.url)
        try:
            # If loading a .crx, Chrome cannot be headless
            use_headless = bool(self.hide_player)
            # If mini_player enabled, force visible to show the small window
            if self.mini_player:
                use_headless = False
            # If hide_player enabled, force headless to hide the entire window (unless mini_player has priority)
            if self.extension_path and self.extension_path.endswith(".crx"):
                use_headless = False

            self.driver = make_chrome_driver(
                headless=use_headless,
                driver_path=self.driver_path,
                extension_path=self.extension_path,
            )

            if not use_headless:
                try:
                    if self.mini_player:
                        self.driver.set_window_size(360, 360)
                        self.driver.set_window_position(20, 20)
                    else:
                        # Always bring the main Chrome window back on-screen so it can be moved
                        self.driver.set_window_position(60, 60)
                except Exception:
                    pass

            base = f"https://{domain}" if domain else "about:blank"
            if domain:
                self.driver.get(base)
                CookieManager.load_cookies(self.driver, domain)
                
                # Set stream quality in session storage BEFORE navigating to stream URL
                if self.force_160p:
                    try:
                        self.driver.execute_script("sessionStorage.setItem('stream_quality', '160');")
                    except Exception as e:
                        print(f"Error setting stream_quality: {e}")
            
            self.driver.get(self.url)
            
            # Wait for page to load (give it time for stream to initialize)
            time.sleep(5)

            try:
                self.ensure_player_state()
            except Exception:
                pass

            last_report = 0
            while not self.stop_event.is_set():
                prev_live_check = self._last_live_check
                live = self.is_stream_live()
                fresh_check = self._last_live_check != prev_live_check
                try:
                    self.ensure_player_state()
                except Exception:
                    pass

                if fresh_check:
                    if live:
                        self._offline_fresh_checks = 0
                    else:
                        self._offline_fresh_checks += 1

                if (
                    not live
                    and self.offline_fresh_checks_to_switch
                    and self._offline_fresh_checks >= self.offline_fresh_checks_to_switch
                ):
                    self.ended_because_offline = True
                    break
                
                # Check category if required (every 30 seconds)
                if self.required_category_id and live:
                    now = time.time()
                    if now - self._last_category_check >= self._category_check_interval:
                        self._last_category_check = now
                        current_category_id = self.get_streamer_category_id()
                        if current_category_id is not None and current_category_id != self.required_category_id:
                            debug_print(f"DEBUG: Streamer changed category from {self.required_category_id} to {current_category_id}, switching...")
                            self.ended_because_wrong_category = True
                            break
                
                if live:
                    self.elapsed_seconds += 1
                if time.time() - last_report >= 1:
                    last_report = time.time()
                    if self.on_update:
                        self.on_update(self.elapsed_seconds, live)
                
                # Check completion: for global drops, use cumulative time; otherwise use individual time
                if self.minutes_target:
                    if self.cumulative_time_callback:
                        # Global drop - check cumulative time
                        current_cumulative = self.cumulative_time_callback()
                        if current_cumulative >= self.minutes_target * 60:
                            self.completed = True
                            break
                    else:
                        # Regular drop - use individual time
                        if self.elapsed_seconds >= self.minutes_target * 60:
                            self.completed = True
                            break
                time.sleep(1)
        except Exception as e:
            print("StreamWorker error:", e)
        finally:
            try:
                if self.driver:
                    self.driver.quit()
            except Exception:
                pass
            try:
                if self.on_finish:
                    self.on_finish(self.elapsed_seconds, self.completed)
            except Exception:
                pass

    def stop(self):
        """Stop the worker"""
        self.stop_event.set()
    
    def get_streamer_category_id(self):
        """Get the current category ID of the streamer's livestream"""
        if not self.driver:
            return None
        
        try:
            username = _kick_username_from_url(self.url)
            if not username:
                return None
            
            api_url = f"https://kick.com/api/v2/channels/{username}"
            script = """
            const cb = arguments[arguments.length - 1];
            fetch(arguments[0], { credentials: 'include', cache: 'no-store', headers: { 'Accept': 'application/json' } })
              .then(r => r.text())
              .then(t => cb(t))
              .catch(e => cb(JSON.stringify({ error: String(e) })));
            """
            try:
                self.driver.set_script_timeout(10)
            except Exception:
                pass
            text = self.driver.execute_async_script(script, api_url)
            data = json.loads(text) if text else None
            if isinstance(data, dict) and not data.get("error"):
                livestream = data.get("livestream")
                if livestream and livestream.get("is_live"):
                    categories = livestream.get("categories", [])
                    if categories and len(categories) > 0:
                        # Return the first category's ID
                        return categories[0].get("id")
        except Exception as e:
            debug_print(f"DEBUG: Error getting streamer category: {e}")
        return None

    def is_stream_live(self):
        """Check if the stream is currently live"""
        now = time.time()
        # Cache API checks to reduce rate-limit risk
        if now - self._last_live_check < self._live_check_interval:
            return self._last_live_value
        try:
            # Kick is frequently protected (403 from Python). Prefer checking from inside the browser.
            username = _kick_username_from_url(self.url)
            if username:
                try:
                    api_url = f"https://kick.com/api/v2/channels/{username}"
                    script = """
                    const cb = arguments[arguments.length - 1];
                    fetch(arguments[0], { credentials: 'include', cache: 'no-store', headers: { 'Accept': 'application/json' } })
                      .then(r => r.text())
                      .then(t => cb(t))
                      .catch(e => cb(JSON.stringify({ error: String(e) })));
                    """
                    try:
                        self.driver.set_script_timeout(10)
                    except Exception:
                        pass
                    text = self.driver.execute_async_script(script, api_url)
                    data = json.loads(text) if text else None
                    if isinstance(data, dict) and not data.get("error"):
                        livestream = data.get("livestream")
                        is_live = bool(livestream and livestream.get("is_live"))
                        self._last_live_value = is_live
                        self._last_live_source = "browser_api"
                        return is_live
                except Exception:
                    pass

                # Fallback: extract app state from the page (when available) and look for is_live.
                try:
                    state_text = self.driver.execute_script(
                        """
                        try {
                          const next = document.getElementById('__NEXT_DATA__');
                          if (next && next.textContent) return next.textContent;
                          if (window.__NUXT__) return JSON.stringify(window.__NUXT__);
                        } catch (e) {}
                        return null;
                        """
                    )
                    if isinstance(state_text, str) and state_text:
                        m = re.search(r"\"is_live\"\\s*:\\s*(true|false)", state_text, re.IGNORECASE)
                        if m:
                            is_live = m.group(1).lower() == "true"
                            self._last_live_value = is_live
                            self._last_live_source = "page_state"
                            return is_live
                except Exception:
                    pass

            # Last-resort DOM heuristic: only try to detect offline (avoid false positives on generic 'LIVE' text).
            try:
                body = self.driver.find_element(By.TAG_NAME, "body").text.upper()
                offline_markers = (
                    "OFFLINE",
                    "IS OFFLINE",
                    "CHANNEL IS OFFLINE",
                    "NOT LIVE",
                    "HORS LIGNE",
                    "N'EST PAS EN DIRECT",
                )
                if any(m in body for m in offline_markers):
                    self._last_live_value = False
                    self._last_live_source = "dom_offline"
                    return False
            except Exception:
                pass

            self._last_live_source = "unknown"
            return self._last_live_value
        except Exception:
            self._last_live_value = False
            self._last_live_source = "unknown"
            return False
        finally:
            # Add slight jitter to desync multiple workers
            jitter = random.uniform(-3, 3)
            base_interval = 8 if self._last_live_value else 5  # More frequent when offline
            self._live_check_interval = max(4, base_interval + jitter)
            self._last_live_check = now

    def ensure_player_state(self):
        """Ensure video player is in the correct state (muted, hidden, etc.)"""
        try:
            hide = "true" if self.hide_player else "false"
            muted = "true" if self.mute else "false"
            volume = "0" if self.mute else "1"
            mini = "true" if (not self.hide_player and self.mini_player) else "false"
            js = f"""
            (function(){{
              var v = document.querySelector('video');
              if (v) {{
                try {{ v.muted = {muted}; v.volume = {volume}; }} catch(e) {{}}
                if ({hide}) {{
                  v.style.opacity='0';
                  v.style.width='1px';
                  v.style.height='1px';
                  v.style.position='fixed';
                  v.style.bottom='0';
                  v.style.right='0';
                  v.style.pointerEvents='none';
                }} else if ({mini}) {{
                  v.style.opacity='1';
                  v.style.width='100px';
                  v.style.height='100px';
                  v.style.position='fixed';
                  v.style.bottom='6px';
                  v.style.right='6px';
                  v.style.pointerEvents='none';
                  v.style.zIndex='999999';
                }} else {{
                  v.style.opacity='';
                  v.style.width='';
                  v.style.height='';
                  v.style.position='';
                  v.style.bottom='';
                  v.style.right='';
                  v.style.pointerEvents='';
                }}
              }}
            }})();
            """
            self.driver.execute_script(js)
        except Exception:
            pass

