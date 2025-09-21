"""
Enhanced Screenshot service with Twitter Embed API support
Handles both direct tweet URLs and Twitter embed HTML
"""

import asyncio
import base64
import io
import re
import time
from datetime import datetime
from typing import List, Dict, Any, Optional, Union
from urllib.parse import urlparse, parse_qs

from playwright.async_api import async_playwright, Page, Browser
from PIL import Image, ImageDraw
import aiofiles

from .models import ScreenshotOptions, ScreenshotResult
from .config import settings
from .utils import extract_tweet_id, generate_filename, clean_tweet_content

class ScreenshotService:
    """Enhanced service with Twitter Embed API and direct tweet support"""

    def __init__(self):
        self.playwright = None
        self.browser = None
        self.context = None
        self.page_pool = []
        self.max_concurrent_pages = 3

    async def initialize(self):
        """Initialize Playwright and browser"""
        try:
            self.playwright = await async_playwright().start()

            self.browser = await self.playwright.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-gpu',
                    '--disable-web-security',
                    '--disable-features=VizDisplayCompositor',
                    '--disable-background-timer-throttling',
                    '--disable-renderer-backgrounding',
                    '--disable-backgrounding-occluded-windows',
                    '--autoplay-policy=no-user-gesture-required',
                    '--disable-blink-features=AutomationControlled',
                    '--disable-extensions',
                    '--disable-plugins',
                    '--no-first-run',
                    '--no-default-browser-check',
                    '--disable-site-isolation-trials',
                    '--disable-permissions-api',
                ]
            )

            self.context = await self.browser.new_context(
                viewport={'width': 1400, 'height': 2000},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                java_script_enabled=True,
                accept_downloads=False,
                has_touch=False,
                is_mobile=False,
                locale='en-US',
                timezone_id='UTC',
                bypass_csp=True
            )

            print("Screenshot service initialized with EMBED API support")
            return True

        except Exception as e:
            print(f"Failed to initialize screenshot service: {e}")
            return False

    async def cleanup(self):
        """Clean up browser resources"""
        try:
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()
            print("Screenshot service cleaned up successfully")
        except Exception as e:
            print(f"Error during cleanup: {e}")

    async def health_check(self) -> bool:
        """Check if service is healthy"""
        try:
            if not self.browser:
                return False

            page = await self.context.new_page()
            await page.goto('data:text/html,<html><body>Health Check</body></html>')
            await page.close()
            return True

        except Exception:
            return False

    async def capture_tweets(self, urls: List[str], options: ScreenshotOptions) -> List[ScreenshotResult]:
        """Capture screenshots for multiple tweet URLs or embed HTML"""
        results = []
        semaphore = asyncio.Semaphore(self.max_concurrent_pages)

        async def capture_single_tweet(url_or_html: str) -> ScreenshotResult:
            async with semaphore:
                return await self._capture_tweet_screenshot(url_or_html, options)

        start_time = time.time()
        tasks = [capture_single_tweet(url) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        processing_time = time.time() - start_time

        final_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                print(f"Screenshot failed for {urls[i]}: {str(result)}")
                final_results.append(ScreenshotResult(
                    url=urls[i],
                    success=False,
                    error=str(result)
                ))
            else:
                final_results.append(result)

        print(f"Batch completed: {len(urls)} URLs, {len([r for r in final_results if r.success])} successful, {processing_time:.2f}s")
        return final_results

    async def _capture_tweet_screenshot(self, url_or_html: str, options: ScreenshotOptions) -> ScreenshotResult:
        """Capture screenshot from tweet URL or embed HTML"""
        page = None
        try:
            page = await self.context.new_page()
            page.set_default_timeout(20000)

            # Determine if input is HTML embed code or URL
            if self._is_embed_html(url_or_html):
                print("Processing Twitter embed HTML...")
                return await self._capture_from_embed_html(page, url_or_html, options)
            else:
                print(f"Processing tweet URL: {url_or_html}")
                # Try embed API first, then fall back to direct scraping
                embed_result = await self._try_embed_api_approach(page, url_or_html, options)
                if embed_result.success:
                    return embed_result
                else:
                    print("Embed API failed, trying direct approach...")
                    return await self._capture_direct_tweet(page, url_or_html, options)

        except Exception as e:
            error_msg = str(e)
            print(f"❌ Screenshot failed: {error_msg}")
            return ScreenshotResult(
                url=url_or_html,
                success=False,
                error=error_msg
            )

        finally:
            if page:
                await page.close()

    def _is_embed_html(self, content: str) -> bool:
        """Check if content is Twitter embed HTML"""
        embed_indicators = [
            'class="twitter-tweet"',
            'blockquote class="twitter-tweet"',
            'platform.twitter.com/widgets.js',
            'twitter.com/embed',
            'data-tweet-id'
        ]
        return any(indicator in content for indicator in embed_indicators)

    async def _try_embed_api_approach(self, page: Page, tweet_url: str, options: ScreenshotOptions) -> ScreenshotResult:
        """Try using Twitter's official embed API"""
        try:
            tweet_id = extract_tweet_id(tweet_url)
            if not tweet_id:
                raise Exception("Could not extract tweet ID from URL")

            print(f"Trying embed API for tweet ID: {tweet_id}")

            # Method 1: Use Twitter's oEmbed API
            oembed_url = f"https://publish.twitter.com/oembed?url=https://twitter.com/i/status/{tweet_id}"

            try:
                # Get embed HTML from Twitter's API
                embed_response = await page.evaluate(f"""
                async () => {{
                    try {{
                        const response = await fetch('{oembed_url}');
                        const data = await response.json();
                        return data.html;
                    }} catch (e) {{
                        return null;
                    }}
                }}
                """)

                if embed_response:
                    print("✅ Got embed HTML from Twitter API")
                    return await self._capture_from_embed_html(page, embed_response, options)

            except Exception as e:
                print(f"oEmbed API failed: {e}")

            # Method 2: Create embed manually using Twitter's widget
            print("Trying manual embed creation...")
            embed_html = self._create_embed_html(tweet_id, tweet_url)
            return await self._capture_from_embed_html(page, embed_html, options)

        except Exception as e:
            print(f"Embed API approach failed: {e}")
            return ScreenshotResult(
                url=tweet_url,
                success=False,
                error=str(e)
            )

    def _create_embed_html(self, tweet_id: str, tweet_url: str) -> str:
        """Create Twitter embed HTML manually"""
        # Extract username from URL if possible
        username_match = re.search(r'twitter\.com/([^/]+)/', tweet_url) or re.search(r'x\.com/([^/]+)/', tweet_url)
        username = username_match.group(1) if username_match else 'user'

        embed_html = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Tweet Embed</title>
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
                    margin: 20px;
                    background: white;
                }}
                .twitter-tweet {{
                    max-width: {options.width}px !important;
                    margin: 0 auto !important;
                }}
            </style>
        </head>
        <body>
            <blockquote class="twitter-tweet" data-tweet-id="{tweet_id}">
                <p>Loading tweet...</p>
                <a href="{tweet_url}">@{username}</a>
            </blockquote>

            <script async src="https://platform.twitter.com/widgets.js" charset="utf-8"></script>

            <script>
                // Wait for Twitter widget to load
                window.twttr = window.twttr || {{}};
                window.twttr.ready = window.twttr.ready || function(f) {{
                    if (window.twttr.widgets) {{
                        f();
                    }} else {{
                        setTimeout(() => f(), 100);
                    }}
                }};
            </script>
        </body>
        </html>
        """
        return embed_html

    async def _capture_from_embed_html(self, page: Page, embed_html: str, options: ScreenshotOptions) -> ScreenshotResult:
        """Capture screenshot from Twitter embed HTML"""
        try:
            print("Loading embed HTML...")

            # Load the embed HTML
            await page.set_content(embed_html)

            # Wait for Twitter widget to load
            print("Waiting for Twitter widget to load...")
            await page.wait_for_load_state('networkidle')

            # Wait for the tweet to fully render
            tweet_loaded = False
            max_attempts = 20

            for attempt in range(max_attempts):
                try:
                    # Check if the tweet iframe has loaded
                    iframe = await page.wait_for_selector('iframe[src*="platform.twitter.com"]', timeout=1000)
                    if iframe:
                        print("✅ Twitter widget iframe loaded")
                        tweet_loaded = True
                        break
                except:
                    pass

                # Also check for direct tweet content
                try:
                    tweet_content = await page.wait_for_selector('.twitter-tweet p', timeout=1000)
                    if tweet_content:
                        text_content = await tweet_content.text_content()
                        if text_content and not text_content.startswith('Loading'):
                            print("✅ Tweet content loaded")
                            tweet_loaded = True
                            break
                except:
                    pass

                print(f"Waiting for tweet to load... ({attempt + 1}/{max_attempts})")
                await asyncio.sleep(0.5)

            if not tweet_loaded:
                print("⚠️ Tweet may not have loaded completely, proceeding anyway...")

            # Additional wait for rendering
            await asyncio.sleep(3)

            # Apply embed-specific customizations
            await self._apply_embed_customizations(page, options)

            # Find the best element to screenshot
            screenshot_target = None
            selectors_to_try = [
                'iframe[src*="platform.twitter.com"]',
                '.twitter-tweet',
                'blockquote',
                'body'
            ]

            for selector in selectors_to_try:
                try:
                    element = await page.wait_for_selector(selector, timeout=2000)
                    if element:
                        screenshot_target = element
                        print(f"Found screenshot target: {selector}")
                        break
                except:
                    continue

            if not screenshot_target:
                raise Exception("Could not find any element to screenshot")

            # Take screenshot
            print("Taking embed screenshot...")
            screenshot_options = {
                'type': options.format,
                'quality': 90 if options.format == 'jpg' else None,
                'omit_background': options.background == 'transparent',
                'animations': 'disabled'
            }

            # For iframes, we need to take a full page screenshot and crop
            if 'iframe' in str(screenshot_target):
                screenshot_bytes = await page.screenshot(
                    type=options.format,
                    quality=90 if options.format == 'jpg' else None,
                    full_page=True
                )
            else:
                screenshot_bytes = await screenshot_target.screenshot(**screenshot_options)

            if not screenshot_bytes:
                raise Exception("Screenshot capture returned empty data")

            # Process image
            processed_image = await self._process_image_full(
                screenshot_bytes, 
                options.width, 
                options.border_radius,
                options.background
            )

            # Generate filename
            tweet_id = self._extract_tweet_id_from_html(embed_html)
            filename = generate_filename(tweet_id or 'embed', options.format, options.include_metadata)

            # Encode to base64
            buffered = io.BytesIO()
            processed_image.save(buffered, 
                               format=options.format.upper() if options.format != 'jpg' else 'JPEG',
                               quality=90 if options.format == 'jpg' else None,
                               optimize=True)
            img_base64 = base64.b64encode(buffered.getvalue()).decode()

            print(f"✅ EMBED screenshot successful: {filename} ({processed_image.width}x{processed_image.height}px)")

            return ScreenshotResult(
                url=embed_html[:100] + "..." if len(embed_html) > 100 else embed_html,
                image_base64=img_base64,
                filename=filename,
                success=True,
                file_size=len(buffered.getvalue()),
                dimensions={"width": processed_image.width, "height": processed_image.height}
            )

        except Exception as e:
            print(f"Embed capture failed: {e}")
            raise e

    def _extract_tweet_id_from_html(self, html: str) -> Optional[str]:
        """Extract tweet ID from embed HTML"""
        # Try various patterns to find tweet ID
        patterns = [
            r'data-tweet-id="([^"]+)"',
            r'/status/(\d+)',
            r'twitter\.com/[^/]+/status/(\d+)',
            r'x\.com/[^/]+/status/(\d+)'
        ]

        for pattern in patterns:
            match = re.search(pattern, html)
            if match:
                return match.group(1)

        return None

    async def _apply_embed_customizations(self, page: Page, options: ScreenshotOptions):
        """Apply customizations specific to embed screenshots"""

        css_customizations = f"""
        <style>
        /* Apply theme */
        {'html, body { filter: invert(1) hue-rotate(180deg); }' if options.theme == 'dark' else ''}
        {('iframe, img { filter: invert(1) hue-rotate(180deg) !important; }' if options.theme == 'dark' else '')}

        /* Embed styling */
        body {{
            margin: 0 !important;
            padding: 20px !important;
            background: {options.background if options.background != 'transparent' else 'white'} !important;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif !important;
        }}

        .twitter-tweet, blockquote {{
            max-width: {options.width}px !important;
            width: {options.width}px !important;
            border-radius: {options.border_radius}px !important;
            margin: 0 auto !important;
            background: {options.background if options.background != 'transparent' else 'white'} !important;
        }}

        iframe {{
            max-width: {options.width}px !important;
            border-radius: {options.border_radius}px !important;
        }}

        /* Hide any unwanted elements */
        .twitter-follow-button,
        .twitter-hashtag-button,
        .twitter-mention-button {{
            display: none !important;
        }}
        </style>
        """

        await page.add_style_tag(content=css_customizations)

    async def _capture_direct_tweet(self, page: Page, url: str, options: ScreenshotOptions) -> ScreenshotResult:
        """Fallback: Capture tweet using direct scraping (existing method)"""
        try:
            print("Using direct tweet capture method...")

            normalized_url = self._normalize_tweet_url(url)

            response = await page.goto(normalized_url, wait_until='domcontentloaded', timeout=20000)

            if response and response.status >= 400:
                raise Exception(f"HTTP {response.status}: Failed to load tweet")

            await asyncio.sleep(2)

            # Check for restrictions and bypass if needed
            age_restricted = await self._check_age_restriction(page)
            login_required = await self._check_login_required(page)

            if age_restricted:
                await self._bypass_age_restriction(page)
            elif login_required:
                await self._bypass_login_requirement(page, normalized_url)

            # Find tweet element
            tweet_selectors = [
                'article[data-testid="tweet"]',
                'article[role="article"]',
                '[data-testid="tweet"]'
            ]

            tweet_element = None
            for selector in tweet_selectors:
                try:
                    await page.wait_for_selector(selector, timeout=8000)
                    tweet_element = page.locator(selector).first
                    print(f"✅ Found tweet element: {selector}")
                    break
                except Exception:
                    continue

            if not tweet_element:
                raise Exception("Could not find tweet element")

            await self._apply_direct_customizations(page, options)

            # Handle videos
            video_count = await self._quick_video_check(page)
            if video_count > 0:
                await self._process_videos_minimal(page)

            await asyncio.sleep(2)

            screenshot_bytes = await tweet_element.screenshot(
                type=options.format,
                quality=90 if options.format == 'jpg' else None,
                omit_background=options.background == 'transparent',
                animations='disabled'
            )

            processed_image = await self._process_image_full(
                screenshot_bytes, 
                options.width, 
                options.border_radius,
                options.background
            )

            tweet_id = extract_tweet_id(url)
            filename = generate_filename(tweet_id, options.format, options.include_metadata)

            buffered = io.BytesIO()
            processed_image.save(buffered, 
                               format=options.format.upper() if options.format != 'jpg' else 'JPEG',
                               quality=90 if options.format == 'jpg' else None,
                               optimize=True)
            img_base64 = base64.b64encode(buffered.getvalue()).decode()

            print(f"✅ DIRECT screenshot successful: {filename}")

            return ScreenshotResult(
                url=url,
                image_base64=img_base64,
                filename=filename,
                success=True,
                file_size=len(buffered.getvalue()),
                dimensions={"width": processed_image.width, "height": processed_image.height}
            )

        except Exception as e:
            raise Exception(f"Direct capture failed: {e}")

    # [Include all the existing bypass methods here...]
    def _normalize_tweet_url(self, url: str) -> str:
        if 'twitter.com' in url:
            return url.replace('twitter.com', 'x.com')
        return url

    async def _check_age_restriction(self, page: Page) -> bool:
        age_indicators = [
            'button:has-text("Yes, view profile")',
            'text="This account may include potentially sensitive content"',
            '[data-testid="confirmationSheetConfirm"]'
        ]

        for indicator in age_indicators:
            try:
                element = await page.wait_for_selector(indicator, timeout=2000)
                if element:
                    return True
            except:
                continue
        return False

    async def _check_login_required(self, page: Page) -> bool:
        login_indicators = [
            'a[href="/login"]',
            'text="Log in"',
            'button:has-text("Log in")'
        ]

        for indicator in login_indicators:
            try:
                element = await page.wait_for_selector(indicator, timeout=2000)
                if element:
                    return True
            except:
                continue
        return False

    async def _bypass_age_restriction(self, page: Page):
        bypass_buttons = [
            'button:has-text("Yes, view profile")',
            'button:has-text("View")',
            '[data-testid="confirmationSheetConfirm"]'
        ]

        for button_selector in bypass_buttons:
            try:
                button = await page.wait_for_selector(button_selector, timeout=3000)
                if button:
                    await button.click()
                    await asyncio.sleep(2)
                    return
            except:
                continue

    async def _bypass_login_requirement(self, page: Page, url: str):
        tweet_id = extract_tweet_id(url)
        alt_url = f"https://x.com/i/web/status/{tweet_id}"

        try:
            await page.goto(alt_url, wait_until='domcontentloaded', timeout=10000)
            await asyncio.sleep(2)
        except:
            pass

    async def _quick_video_check(self, page: Page) -> int:
        try:
            return await page.evaluate("""
            () => {
                const videos = document.querySelectorAll('video, [data-testid="videoComponent"]');
                return videos.length;
            }
            """)
        except:
            return 0

    async def _process_videos_minimal(self, page: Page):
        try:
            await page.add_style_tag(content="""
                <style>
                video, [data-testid="videoComponent"] { 
                    position: relative !important; 
                    border-radius: 12px !important; 
                }
                video::after, [data-testid="videoComponent"]::after { 
                    content: "▶️" !important; 
                    position: absolute !important; 
                    top: 50% !important; 
                    left: 50% !important; 
                    transform: translate(-50%, -50%) !important; 
                    font-size: 24px !important; 
                    opacity: 0.8 !important; 
                    z-index: 1000 !important; 
                }
                </style>
            """)
        except:
            pass

    async def _apply_direct_customizations(self, page: Page, options: ScreenshotOptions):
        css = f"""
        div[data-testid="reply"], div[data-testid="retweet"], div[data-testid="like"], 
        div[data-testid="share"], div[data-testid="bookmark"], nav[role="navigation"],
        div[data-testid="sidebarColumn"], header[role="banner"] {{ display: none !important; }}

        {'html { filter: invert(1) hue-rotate(180deg); }' if options.theme == 'dark' else ''}
        {('img, video { filter: invert(1) hue-rotate(180deg) !important; }' if options.theme == 'dark' else '')}

        article[data-testid="tweet"], article[role="article"] {{
            max-width: {options.width}px !important;
            width: {options.width}px !important;
            border-radius: {options.border_radius}px !important;
            padding: 16px !important;
            background: {options.background if options.background != 'transparent' else 'white'} !important;
            height: auto !important;
            max-height: none !important;
            overflow: visible !important;
        }}

        body {{ overflow: hidden !important; }}
        """

        await page.add_style_tag(content=css)

    async def _process_image_full(self, image_bytes: bytes, width: int, border_radius: int, background: str) -> Image.Image:
        try:
            image = Image.open(io.BytesIO(image_bytes))

            if image.width != width:
                aspect_ratio = image.height / image.width
                new_height = int(width * aspect_ratio)
                image = image.resize((width, new_height), Image.Resampling.LANCZOS)

            if background != 'transparent' and image.mode == 'RGBA':
                bg_image = Image.new('RGB', image.size, background)
                bg_image.paste(image, mask=image.split()[-1] if image.mode == 'RGBA' else None)
                image = bg_image

            if border_radius > 0 and border_radius < min(image.width, image.height) // 2:
                image = self._apply_border_radius(image, border_radius)

            return image
        except:
            return Image.open(io.BytesIO(image_bytes))

    def _apply_border_radius(self, image: Image.Image, radius: int) -> Image.Image:
        try:
            mask = Image.new('L', image.size, 0)
            draw = ImageDraw.Draw(mask)
            draw.rounded_rectangle([(0, 0), image.size], radius=radius, fill=255)

            if image.mode != 'RGBA':
                image = image.convert('RGBA')

            output = Image.new('RGBA', image.size, (0, 0, 0, 0))
            output.paste(image, (0, 0))
            output.putalpha(mask)
            return output
        except:
            return image
