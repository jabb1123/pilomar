#!/usr/bin/python3
"""Class to download and manage TLE data from CelesTrak.org."""

import json
import os
from datetime import datetime, timedelta

import requests  # To handle json response for seeing conditions from online services.
from requests.exceptions import HTTPError  # Error handling.

from pilomar.core.base import AttributeMaster
from pilomar.core.time_utils import hr_seconds
from pilomar.ui.text_color import TextColor


class Celestrak(AttributeMaster):
    """Download celestrak TLE data.
    Data is cached on disc and only updated once the disc cache is > 30 days old."""

    def __init__(self, url, logger=None, projectroot=None):
        super().__init__()
        self.set_logger(logger)  # Define which logging stream to use.
        # Where to find the latest TLE data
        # "https://celestrak.org/NORAD/elements/gp.php?GROUP=stations&FORMAT=tle"
        self.url = url
        self.tle_dict = {}  # TLE data converted into a dictionary for easy searching.
        if projectroot is None:
            # The disc cache filename used to store the data locally.
            self.celestrak_cache_filename = "/home/pi/pilomar/data/celestrakcache.json"
        else:  # ProjectRoot = '/home/pi/pilomar'
            self.celestrak_cache_filename = (
                projectroot + "/data/celestrakcache.json"
            )  # The disc cache filename used to store the data locally.
        self.satellite_list = []  # List of satellite names, use for selecting objects.
        self.refresh()  # Refresh the data, load from CelesTrak if needed else use the disc cache.

    def tle_age_warning(self, name):  # *Q* Is this still used?
        """Extract the epoch datetime from the 1st line of a TLE entry.
        Warn if it's > 30days old. It will need updating."""
        line1, _line2 = self.get_tle_lines(name)
        if line1 is None:
            if self.log is not None:
                self.log(
                    f"celestrak.TleAgeWarning: {name} is not recognised.",
                    level="error",
                    terminal=True,
                )
            return
        epochyear = int(line1[18:20]) + 2000
        epochday = float(line1[20:32])
        epochdate = datetime(year=epochyear, month=1, day=1)
        epochdate += timedelta(days=int(epochday) - 1)
        daysold = (datetime.now() - epochdate).days  # *Q* Offset not supported.
        if self.log is not None:
            self.log(
                f"celestrak.TleAgeWarning: {name} TLE data was updated {epochdate}",
                terminal=False,
            )
        if daysold > 30:
            print(
                TextColor.yellow(
                    f"WARNING: {name} TLE data is {daysold} days old. It may now be inaccurate. "
                    "Consider refreshing it."
                )
            )
            print(TextColor.yellow("Check the source of data from the celestrak.org website."))
        else:
            print(TextColor.green(f"{name} TLE data is {daysold} days old."))

    def refresh(self):
        """Load data from cache if recent enough, else from celestrak.org website."""
        if self.log is not None:
            self.log("celestrak.Refresh: Begin", terminal=False)
            self.log("celestrak.Refresh: Try disc cache", terminal=False)
        self.tle_dict = {}  # No data until refreshed.
        self.load_cache(self.celestrak_cache_filename)  # Try to load from disc if recent enough.
        if self.tle_dict == {}:  # Empty, get a fresh copy.
            if self.log is not None:
                self.log("celestrak.Refresh: Download fresh from internet.", terminal=False)
            if self.download_data():
                if self.log is not None:
                    self.log("celestrak.Refresh: Successful.", terminal=False)
            else:
                if self.log is not None:
                    self.log(
                        "celestrak.Refresh: Failed to download from internet, using cache anyway.",
                        terminal=False,
                    )
                else:
                    print(
                        "celestrak.Refresh: Failed to download from internet. Using cache anyway."
                    )
                self.load_cache(
                    self.celestrak_cache_filename, force=True
                )  # Load the cache regardless of age.
        else:
            if self.log is not None:
                self.log(
                    "celestrak.Refresh: Used cached data instead of downloading from internet.",
                    terminal=False,
                )
        self.satellite_list = []  # Make new list of satellite names.
        for key, _ in self.tle_dict.items():
            self.satellite_list.append(key)
        if len(self.satellite_list) < 1:  # The list is empty, something went wrong.
            if self.log is not None:
                self.log(
                    "celestrak.Refresh: Failed to identify any satellies.",
                    level="error",
                )
            else:
                print("celestrak.Refresh: Failed to identify any satellies.")
        if self.log is not None:
            self.log(f"celestrak.Refresh: Satellites: {self.satellite_list}", terminal=False)
            self.log("celestrak.Refresh: done", terminal=False)

    def download_data(self):
        """Download fresh data from CelesTrak directly."""
        if self.log is not None:
            self.log("celestrak.DownloadData: begin", terminal=False)
        wsok = True
        try:  # Trap and report errors, but don't allow the entire program to abort.
            response = requests.get(
                self.url, timeout=10
            )  # Try to retrieve the response from the remote server.
            response.raise_for_status()  # Check for errors in the request.
            tle_text = response.text  # Convert the response into a text object.
            self.extract_data(tle_text)  # Convert text into dictionary.
        except HTTPError as e:  # There was an HTTP error.
            if self.log is not None:
                self.log(
                    f"celestrak.DownloadData: HTTPError: {str(e)}",
                    level="warning",
                    terminal=False,
                )
            wsok = False
        except Exception as e:  # pylint: disable=broad-except
            if self.log is not None:
                self.log(
                    f"celestrak.DownloadData: Error: {str(e)}",
                    level="warning",
                    terminal=True,
                )
            wsok = False
        self.log("celestrak.DownloadData: end", wsok, terminal=False)
        return wsok

    def file_age(self, filename):  # 2 references.
        """How many seconds old is a file?"""
        if os.path.exists(filename):
            mtime = os.path.getmtime(filename)
            td = datetime.now() - datetime.fromtimestamp(mtime)  # *Q* Offset not supported.
            result = int(td.total_seconds())
        else:
            result = None
        return result

    def load_cache(self, filename, force=False):
        """Load a single cache if available and recent enough.
        force=False: A blank dictionary is returned if the cache is too old.
        force=True: Dictionary is returned from cache regardless of age."""
        if os.path.exists(filename):
            fa = self.file_age(filename)
            if fa is not None:
                self.log(
                    f"celestrak.LoadCache: {filename} is {hr_seconds(fa)} old",
                    terminal=False,
                )
            else:
                self.log(
                    f"celestrak.LoadCache: {filename} age is unknown",
                    terminal=False,
                )
            if fa is not None and (
                force or fa < (5 * 24 * 60 * 60)
            ):  # Only use the cache if less than 5 days old.
                with open(filename, encoding="utf-8") as f:
                    self.log(
                        f"celestrak.LoadCache: Loading Cache: {filename}, force={force}",
                        terminal=False,
                    )
                    self.tle_dict = json.load(f)
        else:
            if self.log is not None:
                self.log(
                    f"celestrak.LoadCache: Cache file {filename} does not exist.",
                    terminal=False,
                )

    def extract_data(self, tle_text: str):
        """Given the tle_text list of satellites, extract each satellite entry into a dictionary.
        Save the dictionary as a json file so it can be reused without more web calls.
        """
        if self.log is not None:
            self.log("celestrak.ExtractData: Begin", terminal=False)
        itemdict = {}
        itemname = ""
        for line in tle_text.split("\n"):  # Split the text by newline characters.
            line = line.strip()  # Remove all other line terminators.
            if line.startswith("1 "):  # 1st data line of tle data.
                itemdict["1"] = line  # Set TLE line 1 element.
            elif line.startswith("2 "):  # last data line of tle data.
                itemdict["2"] = line  # Set TLE line 2 element.
                self.tle_dict[itemname] = (
                    itemdict  # This completes the TLE entry, add it to the dictionary.
                )
                itemdict = {}  # clear for building next entry.
            else:  # 1st line of tle data.
                itemname = line  # Set the name of the satellite.
        with open(
            self.celestrak_cache_filename, "w", encoding="utf-8"
        ) as f:  # Dump as json to disc.
            json.dump(
                self.tle_dict, f, indent=4, default=str
            )  # Save the updated dictionary back to disc.

    def get_tle_lines(self, name):
        """Return the two TLE lines for any given satellite name.
        Returns None values if the name does not exist."""
        line1 = None
        line2 = None
        if name in self.tle_dict:
            line1 = self.tle_dict[name]["1"]
            line2 = self.tle_dict[name]["2"]
        else:
            if self.log is not None:
                self.log(
                    "celestrak.GetTleLines: '" + str(name) + "' not found.",
                    terminal=False,
                )
        return line1, line2
