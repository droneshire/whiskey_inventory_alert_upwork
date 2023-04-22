import gspread
import typing as T

from utils import logger

SHARE_MESSAGE = """
I'd like to share a document with you!
"""


class GoogleSheets:
    def __init__(self, title: str, credential_file: str, share_emails: T.Dict[str, str]):
        self.title = title
        self.gspread_client = gspread.service_account(filename=credential_file)
        self.share_emails = share_emails if share_emails is not None else {}
        self.sheet = None

        try:
            self.sheet = self.gspread_client.open(title)
        except:
            self.sheet = self.create(title, self.share_emails)

    def create(self, title: str, worksheet: str, share_emails: T.Dict[str, str]) -> None:
        self.sheet = self.gspread_client.create(title)
        self.sheet.add_worksheet(worksheet, rows=100, cols=40)
        for email, role in share_emails.items():
            self.sheet.share(
                email,
                perm_type="user",
                role=role,
                notify=True,
                email_message=SHARE_MESSAGE,
            )

    def read_row(self, row: int, worksheet_inx: int = 0) -> T.List[T.Any]:
        worksheet = self.sheet.get_worksheet(worksheet_inx)
        return worksheet.row_values(row)

    def read_column(self, column: int, worksheet_inx: int = 0) -> T.List[T.Any]:
        worksheet = self.sheet.get_worksheet(worksheet_inx)
        return worksheet.col_values(column)

    def read_range(self, ranges: str, worksheet_inx: int = 0) -> T.List[T.List[T.Any]]:
        worksheet = self.sheet.get_worksheet(worksheet_inx)
        return worksheet.batch_get(ranges)

    def write(self, cell_range: str, value: T.Any, worksheet_inx: int = 0) -> None:
        worksheet = self.sheet.get_worksheet(worksheet_inx)
        if ":" in cell_range:
            assert isinstance(value, list), "value not a range"
            data = [{"range": cell_range, "values": value}]
            worksheet.batch_update(data)
        else:
            worksheet.update(cell_range, value)

    def format(
        self,
        cell_range: str,
        cell_format: T.Dict[T.Any, T.Any],
        worksheet_inx: int = 0,
    ) -> None:
        worksheet = self.sheet.get_worksheet(worksheet_inx)
        worksheet.format(cell_range, cell_format)
