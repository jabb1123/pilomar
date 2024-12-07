#!/usr/bin/python

# Class to handle satellite TLE data from Celestrack online source.

# This software is published under the GNU General Public License v3.0.
# Also respect any pre-existing terms of any components that this incorporates.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
# OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
# LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
# WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

# 11.Dec.2023 / projectroot is now received from calling program and respected.

import os
from datetime import datetime, timedelta
from utils.text.human_readable import human_readable_seconds
from utils.text.textcolor import TextColor
import json
import requests  # To handle json response for seeing conditions from online services.
from requests.exceptions import HTTPError  # Error handling.


class Celestrack:
    """Download Celestrack TLE data.
    Data is cached on disc and only updated once the disc cache is > 30 days old."""

    def __init__(self, url, logger=None, projectroot=None):
        self.set_logger(logger)  # Define which logging stream to use.
        self.url = url  # "https://Celestrack.org/NORAD/elements/gp.php?GROUP=stations&FORMAT=tle" # Where to find the latest TLE data
        self.tle_dict = {}  # TLE data converted into a dictionary for easy searching.
        if projectroot is None:
            self.celestrack_cache_file_name = "/home/pi/pilomar/data/Celestrackcache.json"  # The disc cache filename used to store the data locally.
        else:  # ProjectRoot = '/home/pi/pilomar'
            self.celestrack_cache_file_name = (
                projectroot + "/data/Celestrackcache.json"
            )  # The disc cache filename used to store the data locally.
        self.satellite_list = []  # List of satellite names, use for selecting objects.
        self.refresh()  # Refresh the data, load from Celestrack if needed else use the disc cache.

    def set_logger(self, logger):
        """Set up link to logging class and shortcuts to common methods."""
        self.logger = logger  # Logger instance.
        self.log = logger.Log  # Log method.
        self.report_exception = (
            logger.ReportException
        )  # Report exception details to logfile.
        self.raise_exception = logger.RaiseException  # Report and raise exception.
        self.log("Celestrack.SetLogger: Linked to this log file.", terminal=False)

    def tle_age_warning(self, name):  # *Q* Is this still used?
        """Extract the epoch datetime from the 1st line of a TLE entry.
        Warn if it's > 30days old. It will need updating."""
        line1, line2 = self.get_tle_lines(name)
        if line1 is None:
            if self.log is not None:
                self.log(
                    "Celestrack.TleAgeWarning:",
                    name,
                    "is not recognised.",
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
            self.log(name, "TLE data was updated", epochdate, terminal=False)
        if daysold > 30:
            print(
                "WARNING: "
                + name
                + " TLE data is "
                + str(daysold)
                + " days old. It may now be inaccurate. Consider refreshing it."
            )
            print("Check the source of data from the Celestrack.org website.")
        else:
            print(name + " TLE data is " + str(daysold) + " days old.")

    def refresh(self):
        """Load data from cache if recent enough, else from Celestrack.org website."""
        if self.log is not None:
            self.log("Celestrack.Refresh: Begin", terminal=False)
            self.log("Celestrack.Refresh: Try disc cache", terminal=False)
        self.tle_dict = {}  # No data until refreshed.
        self.load_cache(
            self.celestrack_cache_file_name
        )  # Try to load from disc if recent enough.
        if self.tle_dict == {}:  # Empty, get a fresh copy.
            if self.log is not None:
                self.log(
                    "Celestrack.Refresh: Download fresh from internet.", terminal=False
                )
            if self.download_data():
                if self.log is not None:
                    self.log("Celestrack.Refresh: Successful.", terminal=False)
            else:
                if self.log is not None:
                    self.log(
                        "Celestrack.Refresh: Failed to download from internet, using cache anyway.",
                        terminal=False,
                    )
                else:
                    print(
                        "Celestrack.Refresh: Failed to download from internet. Using cache anyway."
                    )
                self.load_cache(
                    self.celestrack_cache_file_name, force=True
                )  # Load the cache regardless of age.
        else:
            if self.log is not None:
                self.log(
                    "Celestrack.Refresh: Used cached data instead of downloading from internet.",
                    terminal=False,
                )
        self.satellite_list = []  # Make new list of satellite names.
        for key, _ in self.tle_dict.items():
            self.satellite_list.append(key)
        if len(self.satellite_list) < 1:  # The list is empty, something went wrong.
            if self.log is not None:
                self.log(
                    "Celestrack.Refresh: Failed to identify any satellies.",
                    level="error",
                )
            else:
                print("Celestrack.Refresh: Failed to identify any satellies.")
        if self.log is not None:
            self.log(
                "Celestrack.Refresh: Satellites:", self.satellite_list, terminal=False
            )
            self.log("Celestrack.Refresh: done", terminal=False)

    def download_data(self):
        """Download fresh data from Celestrack directly."""
        if self.log is not None:
            self.log("Celestrack.DownloadData: begin", terminal=False)
        WSOK = True
        try:  # Trap and report errors, but don't allow the entire program to abort.
            response = requests.get(
                self.url
            )  # Try to retrieve the response from the remote server.
            response.raise_for_status()  # Check for errors in the request.
            TLEText = response.text  # Convert the response into a text object.
            self.extract_data(TLEText)  # Convert text into dictionary.
        except HTTPError as e:  # There was an HTTP error.
            if self.log is not None:
                self.log(
                    "Celestrack.DownloadData: HTTPError: " + str(e),
                    level="warning",
                    terminal=False,
                )
            WSOK = False
        except Exception as e:  # There was some other sort of error.
            if self.log is not None:
                self.log(
                    "Celestrack.DownloadData: Error: " + str(e),
                    level="warning",
                    terminal=True,
                )
            WSOK = False
        self.log("Celestrack.DownloadData: end", WSOK, terminal=False)
        return WSOK

    def file_age(self, filename):  # 2 references.
        """How many seconds old is a file?"""
        if os.path.exists(filename):
            mtime = os.path.getmtime(filename)
            td = datetime.now() - datetime.fromtimestamp(
                mtime
            )  # *Q* Offset not supported.
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
            self.log(
                "Celestrack.LoadCache:",
                filename,
                "is",
                human_readable_seconds(fa),
                "old",
                terminal=False,
            )
            if force or fa < (
                5 * 24 * 60 * 60
            ):  # Only use the cache if less than 5 days old.
                with open(filename, "r", encoding="utf-8") as f:
                    self.log(
                        "Celestrack.LoadCache: Loading Cache:",
                        filename,
                        "force",
                        force,
                        terminal=False,
                    )
                    self.tle_dict = json.load(f)
        else:
            if self.log is not None:
                self.log(
                    "Celestrack.LoadCache:",
                    filename,
                    "cache does not exist.",
                    terminal=False,
                )

    def extract_data(self, TLEText):
        """Given the TLEText list of satellites, extract each satellite entry into a dictionary.
        Save the dictionary as a json file so it can be reused without more web calls.
        """
        if self.log is not None:
            self.log("Celestrack.ExtractData: Begin", terminal=False)
        itemdict = {}
        itemname = ""
        for line in TLEText.split("\n"):  # Split the text by newline characters.
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
            self.celestrack_cache_file_name, "w", encoding="utf-8"
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
                    "Celestrack.GetTleLines: '" + str(name) + "' not found.",
                    terminal=False,
                )
        return line1, line2
