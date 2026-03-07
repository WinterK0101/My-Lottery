"""
Singapore Pools Results Scraper
Handles fetching latest and past lottery results for 4D and TOTO games.

Targets: Singapore Pools official website
Robustness: Browser-like headers, error handling, retry logic
"""

import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple
import logging
import time
import re
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


class SingaporePoolsScraper:
    """
    Web scraper for Singapore Pools lottery results.
    Handles both 4D and TOTO game types with robust error handling.
    """

    # Singapore Pools URLs
    BASE_URL = "https://www.singaporepools.com.sg"
    RESULTS_4D_URL = f"{BASE_URL}/en/product/pages/4d_results.aspx"
    RESULTS_TOTO_URL = f"{BASE_URL}/en/product/pages/toto_results.aspx"
    RESULTS_PAST_URL = f"{BASE_URL}/en/product/pages"

    # Pre-generated result files (authoritative source used by the results pages)
    DATA_ARCHIVE_BASE = f"{BASE_URL}/DataFileArchive/Lottery/Output"
    TOTO_DRAW_LIST_URL = f"{DATA_ARCHIVE_BASE}/toto_result_draw_list_en.html"
    TOTO_TOP_DRAWS_URL = f"{DATA_ARCHIVE_BASE}/toto_result_top_draws_en.html"
    FOURD_DRAW_LIST_URL = f"{DATA_ARCHIVE_BASE}/fourd_result_draw_list_en.html"
    FOURD_TOP_DRAWS_URL = f"{DATA_ARCHIVE_BASE}/fourd_result_top_draws_en.html"

    # Single draw pages resolved via encrypted query string from draw list files
    TOTO_SINGLE_RESULT_URL = f"{BASE_URL}/en/product/sr/Pages/toto_results.aspx"
    FOURD_SINGLE_RESULT_URL = f"{BASE_URL}/en/product/Pages/4d_results.aspx"

    # Browser-like headers to avoid being blocked
    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-SG,en;q=0.9",
        "Accept-Encoding": "gzip, deflate",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }

    def __init__(self, timeout: int = 10, max_retries: int = 3):
        """
        Initialize the scraper with session and retry logic.
        
        Args:
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
        """
        self.timeout = timeout
        self.max_retries = max_retries
        self.session = self._create_session()

    def _create_session(self) -> requests.Session:
        """Create a requests session with retry strategy."""
        session = requests.Session()
        retry_strategy = Retry(
            total=self.max_retries,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session

    @staticmethod
    def _normalize_whitespace(text: str) -> str:
        """Collapse duplicate whitespace and normalize nbsp characters."""
        if not text:
            return ""
        return " ".join(text.replace("\xa0", " ").split())

    @staticmethod
    def _draw_date_to_label(draw_date: datetime) -> str:
        """Convert YYYY-MM-DD date to Singapore Pools draw label format."""
        return draw_date.strftime("%a, %d %b %Y")

    def _parse_draw_label_to_iso(self, draw_label: str) -> Optional[str]:
        """Parse draw label like 'Thu, 05 Mar 2026' into YYYY-MM-DD."""
        normalized = self._normalize_whitespace(draw_label)
        try:
            return datetime.strptime(normalized, "%a, %d %b %Y").date().isoformat()
        except ValueError:
            return None

    def _fetch_draw_info_from_draw_list(
        self,
        game_type: str,
        target_draw_date: Optional[datetime] = None,
    ) -> Optional[Dict[str, str]]:
        """
        Resolve draw metadata from draw-list archive files.

        Returns draw info containing draw_date, draw_number and query_string.
        If target_draw_date is None, returns the latest draw (first option).
        """
        list_url = (
            self.TOTO_DRAW_LIST_URL if game_type == "TOTO" else self.FOURD_DRAW_LIST_URL
        )

        response = self.session.get(list_url, headers=self.HEADERS, timeout=self.timeout)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, "html.parser")
        options = soup.select("option")
        if not options:
            return None

        target_iso = target_draw_date.date().isoformat() if target_draw_date else None

        for idx, option in enumerate(options):
            label = self._normalize_whitespace(option.get_text(strip=True))
            label_iso = self._parse_draw_label_to_iso(label)
            query_string = option.get("querystring") or option.get("queryString")
            draw_number = option.get("value")

            if not query_string:
                continue

            if target_iso is None and idx == 0:
                return {
                    "draw_date": label_iso or "",
                    "draw_date_label": label,
                    "draw_number": draw_number or "",
                    "query_string": query_string,
                }

            if target_iso is not None and label_iso == target_iso:
                return {
                    "draw_date": label_iso,
                    "draw_date_label": label,
                    "draw_number": draw_number or "",
                    "query_string": query_string,
                }

        return None

    def _parse_draw_number(self, draw_number_text: Optional[str]) -> Optional[str]:
        """Extract numeric draw number from text like 'Draw No. 4162'."""
        if not draw_number_text:
            return None
        match = re.search(r"(\d+)", draw_number_text)
        return match.group(1) if match else None

    def _fetch_toto_result_by_query_string(
        self,
        query_string: str,
        expected_draw_date: Optional[datetime] = None,
    ) -> Dict[str, any]:
        """Fetch a specific TOTO draw via encrypted query string."""
        url = f"{self.TOTO_SINGLE_RESULT_URL}?{query_string}"
        response = self.session.get(url, headers=self.HEADERS, timeout=self.timeout)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, "html.parser")
        draw_date_elem = soup.select_one(".toto-result .drawDate") or soup.select_one(".drawDate")
        draw_number_elem = soup.select_one(".toto-result .drawNumber") or soup.select_one(".drawNumber")

        winning_numbers = []
        for idx in range(1, 7):
            elem = soup.select_one(f".toto-result .win{idx}") or soup.select_one(f".win{idx}")
            num = self._extract_number(elem)
            if num is not None:
                winning_numbers.append(num)

        additional_elem = soup.select_one(".toto-result .additional") or soup.select_one(".additional")
        additional_number = self._extract_number(additional_elem)

        if len(winning_numbers) != 6 or additional_number is None:
            html_text = response.text
            winning_numbers = [
                int(num)
                for num in re.findall(r"class=['\"]win[1-6]['\"]>\s*(\d+)\s*<", html_text)
            ][:6]
            add_match = re.search(r"class=['\"]additional['\"]>\s*(\d+)\s*<", html_text)
            additional_number = int(add_match.group(1)) if add_match else None

        if len(winning_numbers) != 6 or additional_number is None:
            raise ValueError("Could not parse TOTO results from page")

        parsed_draw_date = (
            self._parse_draw_label_to_iso(draw_date_elem.get_text(strip=True))
            if draw_date_elem
            else None
        )
        fallback_draw_date = expected_draw_date.date().isoformat() if expected_draw_date else None

        return {
            "status": "success",
            "game_type": "TOTO",
            "draw_date": parsed_draw_date or fallback_draw_date,
            "draw_number": self._parse_draw_number(
                draw_number_elem.get_text(strip=True) if draw_number_elem else None
            ),
            "results": {
                "winning_numbers": sorted(winning_numbers),
                "additional_number": additional_number,
            },
        }

    def _fetch_4d_result_by_query_string(
        self,
        query_string: str,
        expected_draw_date: Optional[datetime] = None,
    ) -> Dict[str, any]:
        """Fetch a specific 4D draw via encrypted query string."""
        url = f"{self.FOURD_SINGLE_RESULT_URL}?{query_string}"
        response = self.session.get(url, headers=self.HEADERS, timeout=self.timeout)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, "html.parser")
        draw_date_elem = soup.select_one(".four-d-results .drawDate") or soup.select_one(".drawDate")
        draw_number_elem = soup.select_one(".four-d-results .drawNumber") or soup.select_one(".drawNumber")

        first_prize = self._extract_4d_number(
            soup.select_one(".four-d-results .tdFirstPrize") or soup.select_one(".tdFirstPrize")
        )
        second_prize = self._extract_4d_number(
            soup.select_one(".four-d-results .tdSecondPrize") or soup.select_one(".tdSecondPrize")
        )
        third_prize = self._extract_4d_number(
            soup.select_one(".four-d-results .tdThirdPrize") or soup.select_one(".tdThirdPrize")
        )

        starter_numbers = [
            self._extract_4d_number(td)
            for td in soup.select(".tbodyStarterPrizes td")
            if self._extract_4d_number(td)
        ]
        consolation_numbers = [
            self._extract_4d_number(td)
            for td in soup.select(".tbodyConsolationPrizes td")
            if self._extract_4d_number(td)
        ]

        if not all([first_prize, second_prize, third_prize]):
            html_text = response.text
            first_match = re.search(r"class=['\"]tdFirstPrize['\"]>\s*(\d{4})\s*<", html_text)
            second_match = re.search(r"class=['\"]tdSecondPrize['\"]>\s*(\d{4})\s*<", html_text)
            third_match = re.search(r"class=['\"]tdThirdPrize['\"]>\s*(\d{4})\s*<", html_text)
            first_prize = first_prize or (first_match.group(1) if first_match else None)
            second_prize = second_prize or (second_match.group(1) if second_match else None)
            third_prize = third_prize or (third_match.group(1) if third_match else None)

        if not all([first_prize, second_prize, third_prize]):
            raise ValueError("Could not parse 4D top-3 prize results from page")

        parsed_draw_date = (
            self._parse_draw_label_to_iso(draw_date_elem.get_text(strip=True))
            if draw_date_elem
            else None
        )
        fallback_draw_date = expected_draw_date.date().isoformat() if expected_draw_date else None

        return {
            "status": "success",
            "game_type": "4D",
            "draw_date": parsed_draw_date or fallback_draw_date,
            "draw_number": self._parse_draw_number(
                draw_number_elem.get_text(strip=True) if draw_number_elem else None
            ),
            "results": {
                "first_prize": first_prize,
                "second_prize": second_prize,
                "third_prize": third_prize,
                "starter": starter_numbers,
                "consolation": consolation_numbers,
            },
        }

    def get_latest_results(
        self, game_type: str
    ) -> Dict[str, any]:
        """
        Fetch latest lottery results for a specific game type.
        
        Args:
            game_type: Either "4D" or "TOTO"
        
        Returns:
            Dict containing:
            - game_type: The game type
            - draw_date: Date of the draw
            - draw_number: Draw number (for 4D)
            - results: Extracted results based on game type
            - status: Success or error status
            - message: Additional information
        
        Raises:
            ValueError: If game_type is invalid
        """
        if game_type not in ["4D", "TOTO"]:
            raise ValueError("game_type must be '4D' or 'TOTO'")

        try:
            if game_type == "4D":
                return self._scrape_4d_latest()
            else:
                return self._scrape_toto_latest()

        except Exception as e:
            logger.error(f"Error fetching {game_type} results: {str(e)}")
            return {
                "status": "error",
                "message": f"Result not yet released or scraper error: {str(e)}",
                "game_type": game_type,
            }

    def get_past_results(
        self, game_type: str, draw_date: str
    ) -> Dict[str, any]:
        """
        Fetch past lottery results for a specific game and date.
        
        Args:
            game_type: Either "4D" or "TOTO"
            draw_date: Date in format 'YYYY-MM-DD'
        
        Returns:
            Dict containing past results or error message
        """
        if game_type not in ["4D", "TOTO"]:
            raise ValueError("game_type must be '4D' or 'TOTO'")

        try:
            # Parse the date
            draw_datetime = datetime.strptime(draw_date, "%Y-%m-%d")

            if game_type == "4D":
                return self._scrape_4d_past(draw_datetime)
            else:
                return self._scrape_toto_past(draw_datetime)

        except Exception as e:
            logger.error(f"Error fetching past {game_type} results: {str(e)}")
            return {
                "status": "error",
                "message": f"Could not retrieve past results: {str(e)}",
                "game_type": game_type,
                "draw_date": draw_date,
            }

    def _scrape_4d_latest(self) -> Dict[str, any]:
        """
        Scrape latest 4D results from Singapore Pools website.
        
        Returns:
            Dict with 4D results: 1st, 2nd, 3rd, Starter, Consolation
        """
        try:
            draw_info = self._fetch_draw_info_from_draw_list("4D")
            if not draw_info:
                return {
                    "status": "error",
                    "message": "Result not yet released",
                    "game_type": "4D",
                }

            return self._fetch_4d_result_by_query_string(draw_info["query_string"])

        except requests.RequestException as e:
            logger.error(f"Request error while scraping 4D: {str(e)}")
            return {
                "status": "error",
                "message": "Failed to fetch results from Singapore Pools",
                "game_type": "4D",
            }
        except Exception as e:
            logger.error(f"Error while scraping latest 4D: {str(e)}")
            return {
                "status": "error",
                "message": f"Result not yet released or parse failed: {str(e)}",
                "game_type": "4D",
            }

    def _scrape_toto_latest(self) -> Dict[str, any]:
        """
        Scrape latest TOTO results from Singapore Pools website.
        
        Returns:
            Dict with TOTO results: 6 winning numbers + additional number
        """
        try:
            draw_info = self._fetch_draw_info_from_draw_list("TOTO")
            if not draw_info:
                return {
                    "status": "error",
                    "message": "Result not yet released",
                    "game_type": "TOTO",
                }

            return self._fetch_toto_result_by_query_string(draw_info["query_string"])

        except requests.RequestException as e:
            logger.error(f"Request error while scraping TOTO: {str(e)}")
            return {
                "status": "error",
                "message": "Failed to fetch results from Singapore Pools",
                "game_type": "TOTO",
            }
        except Exception as e:
            logger.error(f"Error while scraping latest TOTO: {str(e)}")
            return {
                "status": "error",
                "message": f"Result not yet released or parse failed: {str(e)}",
                "game_type": "TOTO",
            }

    def _scrape_4d_past(self, draw_date: datetime) -> Dict[str, any]:
        """
        Scrape past 4D results for a specific date.
        
        Args:
            draw_date: datetime object of the draw date
        
        Returns:
            Dict with past 4D results
        """
        try:
            draw_info = self._fetch_draw_info_from_draw_list("4D", draw_date)
            if not draw_info:
                return {
                    "status": "error",
                    "message": f"No results found for {draw_date.strftime('%Y-%m-%d')}",
                    "game_type": "4D",
                    "draw_date": draw_date.date().isoformat(),
                }

            return self._fetch_4d_result_by_query_string(
                draw_info["query_string"],
                expected_draw_date=draw_date,
            )

        except Exception as e:
            logger.error(f"Error scraping past 4D results: {str(e)}")
            return {
                "status": "error",
                "message": str(e),
                "game_type": "4D",
                "draw_date": draw_date.date().isoformat(),
            }

    def _scrape_toto_past(self, draw_date: datetime) -> Dict[str, any]:
        """
        Scrape past TOTO results for a specific date.
        
        Args:
            draw_date: datetime object of the draw date
        
        Returns:
            Dict with past TOTO results
        """
        try:
            draw_info = self._fetch_draw_info_from_draw_list("TOTO", draw_date)
            if not draw_info:
                return {
                    "status": "error",
                    "message": f"No results found for {draw_date.strftime('%Y-%m-%d')}",
                    "game_type": "TOTO",
                    "draw_date": draw_date.date().isoformat(),
                }

            return self._fetch_toto_result_by_query_string(
                draw_info["query_string"],
                expected_draw_date=draw_date,
            )

        except Exception as e:
            logger.error(f"Error scraping past TOTO results: {str(e)}")
            return {
                "status": "error",
                "message": str(e),
                "game_type": "TOTO",
                "draw_date": draw_date.date().isoformat(),
            }

    def _parse_4d_html(self, soup: BeautifulSoup) -> Optional[Dict[str, any]]:
        """
        Parse 4D results from BeautifulSoup object.
        
        Expected structure from Singapore Pools (adjust selectors as needed):
        - Class/ID for draw date
        - Class/ID for first prize
        - Class/ID for second prize
        - Class/ID for third prize
        - Class/ID for starter
        - Class/ID for consolation
        
        Returns:
            Dict with extracted 4D data or None if not found
        """
        try:
            # These selectors are illustrative - adjust based on actual HTML structure
            draw_date_elem = soup.select_one("[data-date]")
            first_prize_elem = soup.select_one(".first-prize, [data-prize='1']")
            second_prize_elem = soup.select_one(".second-prize, [data-prize='2']")
            third_prize_elem = soup.select_one(".third-prize, [data-prize='3']")
            starter_elem = soup.select_one(".starter, [data-prize='starter']")
            consolation_elem = soup.select_one(".consolation, [data-prize='consolation']")

            # If no results found, return None
            if not all([first_prize_elem, second_prize_elem, third_prize_elem]):
                return None

            # Extract numbers (assuming 4-digit format)
            return {
                "draw_date": (
                    draw_date_elem.get_text(strip=True) if draw_date_elem else None
                ),
                "draw_number": None,  # If available in HTML
                "first_prize": self._extract_4d_number(first_prize_elem),
                "second_prize": self._extract_4d_number(second_prize_elem),
                "third_prize": self._extract_4d_number(third_prize_elem),
                "starter": self._extract_4d_number(starter_elem) if starter_elem else None,
                "consolation": (
                    self._extract_4d_number(consolation_elem)
                    if consolation_elem
                    else None
                ),
            }

        except Exception as e:
            logger.error(f"Error parsing 4D HTML: {str(e)}")
            return None

    def _parse_toto_html(self, soup: BeautifulSoup) -> Optional[Dict[str, any]]:
        """
        Parse TOTO results from BeautifulSoup object.
        
        Expected structure from Singapore Pools:
        - 6 winning numbers
        - 1 additional number
        
        Returns:
            Dict with extracted TOTO data or None if not found
        """
        try:
            # These selectors are illustrative - adjust based on actual HTML structure
            draw_date_elem = soup.select_one("[data-date]")

            # Find winning numbers (typically in numbered list or badges)
            winning_nums_elem = soup.select(".winning-num, .number-badge, [data-number]")

            if len(winning_nums_elem) < 7:
                return None  # Need at least 6 + 1 additional

            # Extract winning numbers (first 6)
            winning_numbers = []
            for elem in winning_nums_elem[:6]:
                num = self._extract_number(elem)
                if num is not None:
                    winning_numbers.append(num)

            # Extract additional number (7th)
            additional_number = self._extract_number(winning_nums_elem[6])

            if len(winning_numbers) != 6 or additional_number is None:
                return None

            return {
                "draw_date": (
                    draw_date_elem.get_text(strip=True) if draw_date_elem else None
                ),
                "draw_number": None,
                "winning_numbers": sorted(winning_numbers),
                "additional_number": additional_number,
            }

        except Exception as e:
            logger.error(f"Error parsing TOTO HTML: {str(e)}")
            return None

    @staticmethod
    def _extract_number(element) -> Optional[int]:
        """Extract a single number from HTML element."""
        if element is None:
            return None

        text = element.get_text(strip=True)
        try:
            return int(text)
        except ValueError:
            return None

    @staticmethod
    def _extract_4d_number(element) -> Optional[str]:
        """Extract 4D number from HTML element (returns as string)."""
        if element is None:
            return None

        text = element.get_text(strip=True)
        # Extract only digits
        digits = "".join(filter(str.isdigit, text))
        if len(digits) == 4:
            return digits
        return None


def create_scraper(timeout: int = 10, max_retries: int = 3) -> SingaporePoolsScraper:
    """Factory function to create a scraper instance."""
    return SingaporePoolsScraper(timeout=timeout, max_retries=max_retries)
