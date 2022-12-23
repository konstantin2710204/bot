from urllib.parse import urlparse
from typing import Optional
import re

import bs4
from loguru import logger

from . import model


def parse_replaces_base(page: str) -> str:
    # r = session.get(url=MAIN_SITE_URL, params=MAIN_SITE_PARAMS)
    # r.raise_for_status()

    souped = bs4.BeautifulSoup(page, 'html.parser')
    a = souped.find('a', text="Замены в расписании", attrs={'class': 'sublevel'})
    link = a['href']

    parsed = urlparse(link)
    netloc = parsed.netloc
    scheme = parsed.scheme

    return scheme + '://' + netloc


def parse_replaces(page: bytes) -> model.Replaces:
    # r = session.get(endpoint)
    # r.raise_for_status()

    souped = bs4.BeautifulSoup(page, 'html.parser', from_encoding='utf-8')
    the_table = souped.find('table')

    header: Optional[str] = None
    groups: dict[int, model.GroupReplaces] = dict()

    expecting_group_header = False
    current_group: Optional[int] = None
    structure_incorrect = False

    for tr in the_table:
        td: bs4.element.Tag = tr.contents[0]
        td_class: str = td['class'][0]

        if td_class == 'header':
            logger.debug(f'header: {td}')
            if header is not None:
                logger.warning('Met second header', page)

            header = str(td.string)

        elif td_class == 'footer':
            logger.debug(f'Footer: {td.string}')

        elif td_class == 'section':  # Group number row
            logger.debug(f'section: {td}')
            if td.string is None:
                structure_incorrect = True
                logger.warning(f'Empty section: {td}')
                continue

            try:
                stringed_group = str(td.string)
                stringed_group = re.sub('\(.*\)', '', stringed_group)  # group number can be like `121(1)`
                # The lib does not handle such cases and strip it to `121`, for now at least (soon TM)
                current_group = int(stringed_group)

            except ValueError:
                structure_incorrect = True
                logger.opt(exception=True).warning(f"Can't parse section td: {td!r}")
                continue

            else:
                groups[current_group] = model.GroupReplaces(current_group, list())
                expecting_group_header = True  # After section goes group header

        elif td_class == 'content':
            if not expecting_group_header:
                logger.debug(f'Group row: {tr}')
                try:
                    replace = model.replace_from_tr(tr)

                except (ValueError, TypeError):
                    structure_incorrect = True
                    logger.opt(exception=True).warning(f"Couldn't parse tr: {tr!r}")
                    continue

                else:
                    if current_group is None:
                        logger.warning('Current group is None', page)

                    groups[current_group].group_replaces.append(replace)

            else:
                expecting_group_header = False
                if td.string != '№ пары':
                    logger.warning('expecting group header and do not got one', page)

    if structure_incorrect:
        logger.info(f'Incorrect structure detected')

    return model.Replaces(header=header, groups=groups)