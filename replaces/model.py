from dataclasses import dataclass, field
from enum import Enum

import bs4


class SubLessonsNumbers(Enum):
    none = None
    first = 1
    second = 2
    third = 3
    fourth = 4
    fifth = 5
    sixth = 6
    seventh = 7
    eighth = 8
    ninth = 9
    tenth = 10


# class LessonsNumbers(Enum):
#     """TODO: Implement deduplication"""
#     first_lesson = {SubLessonsNumbers.first, SubLessonsNumbers.second}
#     second_lesson = {SubLessonsNumbers.third, SubLessonsNumbers.fourth}
#     third_lesson = {SubLessonsNumbers.fifth, SubLessonsNumbers.sixth}
#     fifth_lesson = {SubLessonsNumbers.seventh, SubLessonsNumbers.eighth}
#     sixth_lesson = {SubLessonsNumbers.ninth, SubLessonsNumbers.tenth}


@dataclass
class Replace:
    lesson_number: SubLessonsNumbers

    replacement_subject: str

    replacing_teacher: str
    replacing_subject: str
    replacing_classroom: str


def replace_from_tr(td: bs4.Tag) -> Replace:
    args = (getattr(i, 'string') for i in td.contents)
    args = list(map(lambda x: str(x) if isinstance(x, bs4.NavigableString) else x, args))

    if args[0] is None:
        args[0] = SubLessonsNumbers(args[0])  # lesson num

    else:
        args[0] = SubLessonsNumbers(int(args[0]))  # lesson num

    if len(args) == 4:  # Workaround: Default is 5, probably classroom is missing
        args.append(None)  # Then classroom is None

    return Replace(*args[:5])  # Slice :5 is workaround for incorrect structure (i.e. Замены Пятница 18.11.22 четная)


@dataclass
class GroupReplaces:
    group_number: int
    group_replaces: list[Replace]


@dataclass
class Replaces:
    header: str
    groups: dict[int, GroupReplaces] = field(default_factory=dict)  # group numbers as keys