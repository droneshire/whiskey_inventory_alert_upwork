import typing as T


def check_dict_keys_recursive(
    dict1: T.Dict[T.Any, T.Any], dict2: T.Dict[T.Any, T.Any]
) -> T.List[T.Any]:
    missing_keys = []
    for key in dict1.keys():
        if key not in dict2.keys():
            missing_keys.append(key)
        elif type(dict1[key]) == dict:
            missing_keys += check_dict_keys_recursive(dict1[key], dict2[key])
    return missing_keys


def patch_missing_keys_recursive(
    dict1: T.Dict[T.Any, T.Any], dict2: T.Dict[T.Any, T.Any]
) -> T.Dict[T.Any, T.Any]:
    for key in dict1.keys():
        if key not in dict2.keys():
            dict2[key] = dict1[key]
        elif type(dict1[key]) == dict:
            patch_missing_keys_recursive(dict1[key], dict2[key])
    return dict2


def safe_get(dictionary: T.Dict[T.Any, T.Any], keys: T.List[T.Any], default: T.Any = {}) -> T.Any:
    for key in keys:
        dictionary = dictionary.get(key, {})
    return dictionary if dictionary else default
