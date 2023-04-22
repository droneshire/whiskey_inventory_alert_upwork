"""
Utility script that helps write transactions to a spreadsheet
"""
import csv
import json
import os
import typing as T

from utils import logger


class CsvLogger:
    def __init__(self, csv_file: str, header: T.List[str], dry_run=False, verbose=False) -> None:
        self.csv_file = csv_file
        self.header = header
        self.col_map = {col.lower(): i for i, col in enumerate(header)}
        self.dry_run = dry_run
        self._write_header_if_needed()
        self.verbose = verbose

    def write(self, data: T.Dict[str, T.Any]) -> None:
        if self.dry_run:
            return

        if self.verbose:
            logger.print_bold(
                f"Writing stats to {self.csv_file}:\nStats:\n{json.dumps(data, indent=4)}"
            )
        with open(self.csv_file, "a") as appendfile:
            csv_writer = csv.writer(appendfile)

            row = [""] * len(self.header)
            for k, v in data.items():
                inx = self.col_map.get(k.lower(), None)
                if inx is None:
                    continue
                row[inx] = v
            csv_writer.writerow(row)

    def read(self) -> T.List[T.List[T.Any]]:
        if not os.path.isfile(self.csv_file):
            return []

        with open(self.csv_file) as infile:
            reader = list(csv.reader(infile))
        return reader[1:]

    def get_col_map(self) -> T.Dict[str, int]:
        return self.col_map

    def _write_header_if_needed(self) -> None:
        if self.dry_run:
            return

        reader = []
        if os.path.isfile(self.csv_file):
            with open(self.csv_file) as infile:
                reader = list(csv.reader(infile))

        if len(reader) == 0 or len(self.header) != len([i for i in reader[0] if i in self.header]):
            reader.insert(0, self.header)

        with open(self.csv_file, "w") as outfile:
            writer = csv.writer(outfile)
            for row in reader:
                writer.writerow(row)
