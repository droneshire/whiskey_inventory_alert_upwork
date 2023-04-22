def camel_to_snake(s):
    # https://stackoverflow.com/a/1176023/10940584
    return "".join(["_" + c.lower() if c.isupper() else c for c in s]).lstrip("_")


def snake_to_camel(s):
    # https://stackoverflow.com/a/19053800/10940584
    return "".join([t.title() for t in s.split("_")])


def dict_keys_camel_to_snake_deep(d):
    # recursively convert dict keys from camelCase to snake_case
    if isinstance(d, dict):
        d = {camel_to_snake(k): dict_keys_camel_to_snake_deep(v) for k, v in d.items()}
    return d


def dict_keys_snake_to_camel_deep(d):
    # recursively convert dict keys from snake_case to camelCase
    if isinstance(d, dict):
        d = {snake_to_camel(k): dict_keys_snake_to_camel_deep(v) for k, v in d.items()}
    return d
