from . import model


def printer(replaces) -> str:
    if isinstance(replaces, model.Replaces):
        return _replaces_printer(replaces)

    elif isinstance(replaces, model.GroupReplaces):
        return _group_replaces_printer(replaces)

    elif isinstance(replaces, model.Replace):
        return _replace_printer(replaces)

    else:
        raise TypeError('replaces must be instance of  model.Replaces or model.GroupReplaces or model.Replace')


def _replace_printer(replace: model.Replace) -> str:
    return f'{replace.lesson_number.value}\t{replace.replacement_subject} -> ({replace.replacing_teacher} - {replace.replacing_subject} - {replace.replacing_classroom})'


def _group_replaces_printer(group_replaces: model.GroupReplaces) -> str:
    res = f'{group_replaces.group_number}\n'
    for replace in group_replaces.group_replaces:
        res += f'{_replace_printer(replace)}\n'

    return res


def _replaces_printer(replaces: model.Replaces) -> str:
    res = replaces.header + '\n'
    for group in replaces.groups.values():
        res += _group_replaces_printer(group)

    return res