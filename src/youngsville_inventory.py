import os
import typing as T

import dotenv
import pandas as pd
import requests
from bs4 import BeautifulSoup

HEADERS = {
    "login": {
        "authority": "shopncabc.com",
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "accept-language": "en-US,en;q=0.9",
        "cache-control": "max-age=0",
        "content-type": "application/x-www-form-urlencoded",
        # 'cookie': 'ASP.NET_SessionId=20qosvn5tctp0k2tdnigghr0',
        "dnt": "1",
        "origin": "https://shopncabc.com",
        "referer": "https://shopncabc.com/Login.aspx?logout=1",
        "sec-ch-ua": '"Google Chrome";v="113", "Chromium";v="113", "Not-A.Brand";v="24"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Linux"',
        "sec-fetch-dest": "document",
        "sec-fetch-mode": "navigate",
        "sec-fetch-site": "same-origin",
        "sec-fetch-user": "?1",
        "upgrade-insecure-requests": "1",
        "user-agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36",
    },
    "inventory": {
        "authority": "shopncabc.com",
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "accept-language": "en-US,en;q=0.9",
        # 'cookie': 'ASP.NET_SessionId=20qosvn5tctp0k2tdnigghr0',
        "dnt": "1",
        "referer": "https://shopncabc.com/ItemList.aspx",
        "sec-ch-ua": '"Google Chrome";v="113", "Chromium";v="113", "Not-A.Brand";v="24"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Linux"',
        "sec-fetch-dest": "document",
        "sec-fetch-mode": "navigate",
        "sec-fetch-site": "same-origin",
        "sec-fetch-user": "?1",
        "upgrade-insecure-requests": "1",
        "user-agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36",
    },
}

PARAMS = {
    "logout": "1",
}

DATA = "__VIEWSTATE=M9MU9LFbiMDREFyfwqHPKqjkwwIauCAecfhRShaDIG%2BgIPc0TQ4H16D6%2BYYAAD0NdxMOiI%2F4Kleka%2Fy0WxqmvipUvz%2BELWsxD9F%2FuBb4cTcHDxcBemwtFA9lxrW0pDu5DU7VLU5HbdQMG4a5r72qgdr1rWZS6%2BIEoIf%2Bij%2BbMV3wenTeB9FmXA8QFW7UNUng7wUgjC%2BwxKB%2B%2BhZVxjYv3kqINpZsDo2%2Bt%2BYukOg62mBBxLeNg9o00eTAyqRW0y7ho%2Bjs2UxIu8Ve5pH3UasTEOO98lmarJS%2FsNAejTPqaMmojKqcO3r9hislUjRJ%2F4k73mmMTKhKLzqlR2GChddsSBRg4Hw1hvVOO%2FpUiNzejpGMWted%2BH2RNl3DxdAuBcVzeopjvHaFfdF6MlB8VE9pbQqLBzi%2BN6xfRdkxjZCHjsY%3D&__VIEWSTATEGENERATOR=C2EE9ABB&__EVENTTARGET=&__EVENTARGUMENT=&__EVENTVALIDATION=1e5W%2B8R2bBn0DUA3kvw4a2oLsEz%2B%2BP%2FFCa0QH9BQjIfdQj%2Fqg1zQdgXazQZ5Zza1VjTUQYyUbvDJLCdIvui3dJp1bc%2FIgCk78%2Fxf0s8uFsuRFrY0tbiLTwcVJPmYDMqgZzrn%2FZZMGMUlr%2BwGd8jPjikZL%2B42%2BufFSJJYR8p4cZ8%3D&ctl00%24ContentPlaceHolder1%24txtUserName={}&ctl00%24ContentPlaceHolder1%24txtPassword={}&ctl00%24ContentPlaceHolder1%24btnLogin=Login"


class YoungsvilleAbcInventory:
    NAME = "Brand Name"
    NC_CODE = "NC Code"
    TOTAL_AVAILABLE = "Total Available"

    def __init__(self, username: str, password: str) -> None:
        self.inventory: T.Dict[str, T.Dict[str, T.Any]] = {}
        self.session = requests.Session()
        self.data = DATA.format(username, password)

    def login(self) -> None:
        self.session.post(
            "https://shopncabc.com/Login.aspx",
            params=PARAMS,
            headers=HEADERS["login"],
            data=self.data,
        )

    def get_inventory(self) -> T.Dict[str, T.Dict[str, int]]:
        response = self.session.get(
            "https://shopncabc.com/ItemList.aspx", headers=HEADERS["inventory"]
        )
        html_content = response.text
        soup = BeautifulSoup(html_content, "html.parser")
        rows = soup.find_all("tr")

        inventory = {}
        for row in rows[1:]:  # Skip the first row (header row)
            class_cd, class_nm = row.find_all("div", class_=["c-cd", "c-nm"])

            nc_code = class_cd.text.strip()
            info = class_nm.text.strip()
            name = info.split("[")[0].strip()
            available = int(info.split("[")[1].split(" ")[0])
            inventory[nc_code] = {"name": name, "available": available}
        return inventory

    def inventory_to_dataframe(self) -> pd.core.frame.DataFrame:
        df = pd.DataFrame.from_dict(self.get_inventory(), orient="index")
        df = df.reset_index()
        df = df.rename(
            columns={"index": self.NC_CODE, "name": self.NAME, "available": self.TOTAL_AVAILABLE}
        )
        df = df.sort_values(by=[self.NC_CODE])
        return df
