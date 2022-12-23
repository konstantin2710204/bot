from functools import partial

import requests

from . import parsers

SPBKIT_SITE_URL = "http://www.spbkit.edu.ru/index.php"
SPBKIT_SITE_PARAMS = {"option": "com_content", "task": "view", "id": "28", "Itemid": "65"}

REPLACES_ENDPOINT = '/replacements/api/fetch-rep'


def get_session() -> requests.Session:
    session = requests.Session()
    session.request = partial(session.request, timeout=10)
    # session.headers.update({'User-Agent': 'Custom user agent'})  # TODO: uncomment!
    return session


def fetch(session: requests.Session, endpoint: str, return_content=True, *args, **kwargs) -> bytes | str:
    r = session.get(url=endpoint, *args, **kwargs)
    r.raise_for_status()
    return r.content if return_content else r.text


def fetch_spbkit_page() -> str:
    return fetch(the_session, SPBKIT_SITE_URL, return_content=False, params=SPBKIT_SITE_PARAMS)


def fetch_replaces_page() -> bytes:
    replaces_url = fetch_replaces_url()
    return fetch(the_session, replaces_url)


def fetch_replaces_url() -> str:
    spbkit_page = fetch_spbkit_page()
    replaces_base = parsers.parse_replaces_base(spbkit_page)

    replaces_url = replaces_base + REPLACES_ENDPOINT
    return replaces_url


the_session = get_session()