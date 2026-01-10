# Version: 1.1.0
"""Constants and utility functions for the LSR integration.

This module defines constants such as domain, API URL, namespace, and default scan interval,
along with a transliteration function for converting Russian text to Latin for unique IDs.
"""

DOMAIN = "lsr"
API_URL = "https://mp.lsr.ru/api/rpc"
# noinspection HttpUrlsUsage
NAMESPACE = "http://www.lsr.ru/estate/headlessCMS"
DEFAULT_SCAN_INTERVAL = 43200  # 12 часов в секундах

def transliterate(text: str) -> str:
    """Transliterate Russian text to Latin for unique_id.

    Args:
        text (str): The Russian text to transliterate.

    Returns:
        str: The transliterated text in Latin characters, with spaces and underscores removed.
    """
    translit_map = {
        'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'yo', 'ж': 'zh',
        'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm', 'н': 'n', 'о': 'o',
        'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u', 'ф': 'f', 'х': 'kh', 'ц': 'ts',
        'ч': 'ch', 'ш': 'sh', 'щ': 'sch', 'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu',
        'я': 'ya', ' ': '', '_': ''
    }
    text = text.lower()
    result = ''
    for char in text:
        result += translit_map.get(char, char)
    return result